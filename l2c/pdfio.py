"""Local PDF reading and optional bounded CPU OCR. Never contacts a service."""
import math
from pathlib import Path
import pymupdf as fitz
from .model import TextLine, normalized
fitz.TOOLS.mupdf_display_errors(False)
fitz.TOOLS.mupdf_display_warnings(False)

class OCRMemoryDeferred(RuntimeError):
    """Retry locally when another process has released sufficient memory."""

def document_role(relative_path):
    value=normalized(str(relative_path).replace("\\","/"))
    import re
    if re.search(r"(?:^|/)(?:DA|SHOP|ATELIER|DESSINS ATELIER)(?:/|$)",value): return "atelier"
    if re.search(r"(?:^|/)(?:PLAN|PLANS|STRUCTURE)(?:/|$)|_PLAN_|PLAN_STR",value): return "plan"
    if "SHOP" in Path(value).stem: return "atelier"
    return None

def join_fragments(lines):
    """Join close horizontal PDF fragments on one baseline, not distant cells."""
    pending=sorted(lines,key=lambda line:((line.bbox[1]+line.bbox[3])/2,line.bbox[0]))
    rows=[]
    for line in pending:
        cy=(line.bbox[1]+line.bbox[3])/2
        row=next((r for r in reversed(rows[-5:]) if abs(r[0]-cy)<=2.0),None)
        if row is None: rows.append([cy,[line]])
        else: row[1].append(line)
    output=[]
    for _,row in rows:
        row.sort(key=lambda line:line.bbox[0]); current=None
        for line in row:
            if current is not None:
                gap=line.bbox[0]-current.bbox[2]
                h=min(line.bbox[3]-line.bbox[1],current.bbox[3]-current.bbox[1])
                if 0<=gap<=min(12.0,max(3.0,h)):
                    box=(current.bbox[0],min(current.bbox[1],line.bbox[1]),line.bbox[2],max(current.bbox[3],line.bbox[3]))
                    current=TextLine(current.text+' '+line.text,box,min(current.block,line.block),'native_fragments')
                    continue
                output.append(current)
            current=line
        if current is not None: output.append(current)
    return output

def native_lines(page):
    lines=[]
    rotated=[]
    for block_no,block in enumerate(page.get_text("dict",flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]):
        for line in block.get("lines",[]):
            spans=line.get("spans",[])
            text=" ".join(s["text"] for s in spans).strip()
            if not text: continue
            box=fitz.Rect(line["bbox"])*page.rotation_matrix
            target=lines if abs(line.get('dir',(1,0))[1])<0.01 and not page.rotation else rotated
            target.append(TextLine(text,tuple(box),block_no,"native"))
    return join_fragments(lines)+rotated

class LocalOCR:
    def __init__(self,max_pixels=2_000_000):
        self.max_pixels=max_pixels
        self._engine=None
    def recognize(self,page):
        import psutil
        # Preserve the user's workspace headroom, including initial model load.
        minimum = (1.5 + (0.25 if self._engine is None else 0)) * 1024**3
        if psutil.virtual_memory().available < minimum:
            raise OCRMemoryDeferred("OCR deferred for available-memory reserve")
        import cv2,numpy as np
        cv2.setNumThreads(2)
        if self._engine is None:
            from rapidocr_onnxruntime import RapidOCR
            self._engine=RapidOCR(intra_op_num_threads=2,inter_op_num_threads=1,print_verbose=False,use_cls=False,
                det_use_cuda=False,rec_use_cuda=False,cls_use_cuda=False,
                det_use_dml=False,rec_use_dml=False,cls_use_dml=False)
        if psutil.virtual_memory().available < 1.5 * 1024**3:
            raise OCRMemoryDeferred("OCR deferred for available-memory reserve")
        desired=2.0
        scale=min(desired,math.sqrt(self.max_pixels/(page.rect.width*page.rect.height)))
        pix=page.get_pixmap(matrix=fitz.Matrix(scale,scale),alpha=False,colorspace=fitz.csRGB)
        array=np.frombuffer(pix.samples,dtype=np.uint8).reshape(pix.height,pix.width,3)
        output,_=self._engine(array)
        lines=[]
        for number,(points,text,score) in enumerate(output or []):
            xs=[p[0]/scale for p in points]; ys=[p[1]/scale for p in points]
            lines.append(TextLine(text,(min(xs),min(ys),max(xs),max(ys)),number,"ocr"))
        return lines,{"scale_pixels_per_point":scale,"pixels":pix.width*pix.height,"regions":len(lines)}
