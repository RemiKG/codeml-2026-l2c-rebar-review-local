"""One synthetic raster page validates the real OCR integration in isolation."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,json,sys,socket,time,hashlib
REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO))
from l2c.synthetic import generate_project
from l2c.pipeline import run_project
import pymupdf as fitz
import psutil

parser=argparse.ArgumentParser()
parser.add_argument("--work",required=True)
args=parser.parse_args()
work=Path(args.work).resolve(); work.mkdir(parents=True,exist_ok=False)
generate_project(work/"source-synthetic")
input_root=work/"raster-input"
for role in ("plans","shop"):
    dest=input_root/role; dest.mkdir(parents=True)
    original=next((work/"source-synthetic"/role).glob("*.pdf"))
    with fitz.open(original) as doc:
        target=fitz.open()
        if role=="plans":
            pix=doc[0].get_pixmap(matrix=fitz.Matrix(2,2),alpha=False)
            page=target.new_page(width=doc[0].rect.width,height=doc[0].rect.height)
            page.insert_image(page.rect,pixmap=pix)
            assert not page.get_text().strip()
        else:
            target.insert_pdf(doc,from_page=0,to_page=0)
        target.save(dest/"synthetic.pdf"); target.close()
attempts=[]
original_connect=socket.socket.connect
def deny(*args,**kwargs):
    attempts.append(True)
    raise RuntimeError("Network disabled for synthetic OCR integration check")
socket.socket.connect=deny
start=time.perf_counter()
try:
    result=run_project(input_root,work/"output",ocr_mode="auto",ocr_max_pages=1,synthetic=True,assert_complete_scope=True)
finally:
    socket.socket.connect=original_connect
memory=psutil.Process().memory_info()
passed=result["ocr_pages"]==1 and result["extractions"]==6 and not attempts
record={"checked_at":datetime.now(timezone.utc).isoformat(),"synthetic_only":True,"real_source_files_opened":0,
        "passed":passed,"aggregate":result,"python_network_attempts":len(attempts),"elapsed_seconds":round(time.perf_counter()-start,3),
        "peak_working_set_mib":round(getattr(memory,"peak_wset",memory.rss)/1024**2,1),"python":sys.executable}
(work/"OCR_CHECK.json").write_text(json.dumps(record,indent=2)+"\n",encoding="utf-8")
print(json.dumps(record))
sys.exit(0 if passed else 1)
