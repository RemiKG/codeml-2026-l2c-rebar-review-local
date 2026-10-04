"""One local input-to-output path used by the CLI and notebook."""
from pathlib import Path
from collections import Counter
from datetime import datetime,timezone
import contextlib,hashlib,json,math,time,traceback
import pymupdf as fitz
import jsonschema
from .pdfio import document_role,native_lines,LocalOCR,OCRMemoryDeferred
from .parsing import parse_page,BAR_HINT
from .schedules import schedule_observations
from .matching import reconcile,decision_counts
from .reporting import render_reports
from .model import stable_id

def write_json(path,value):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.name+".tmp")
    temp.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    temp.replace(path)

def run_project(input_dir,output_dir,*,ocr_mode="off",ocr_max_pages=8,max_pixels=2_000_000,
                max_pages=None,assert_complete_scope=False,synthetic=False,length_tolerance_mm=0.0,role_map=None):
    input_dir=Path(input_dir).resolve(); output_dir=Path(output_dir).resolve()
    repo=Path(__file__).resolve().parents[1]
    if not input_dir.is_dir(): raise ValueError("input directory unavailable")
    if output_dir.is_relative_to(repo): raise ValueError("outputs must be outside the public repository")
    if output_dir.is_relative_to(input_dir) or input_dir.is_relative_to(output_dir):
        raise ValueError("input and output directories must be disjoint")
    if output_dir.exists() and any(output_dir.iterdir()): raise ValueError("output directory must be empty for an auditable run")
    if ocr_mode not in ("off","auto"): raise ValueError("invalid OCR mode")
    if ocr_max_pages<0 or max_pixels<10_000 or max_pixels>8_000_000: raise ValueError("invalid bounded OCR budget")
    if max_pages is not None and max_pages<1: raise ValueError("max_pages must be positive")
    if length_tolerance_mm<0 or not math.isfinite(length_tolerance_mm): raise ValueError("invalid length tolerance")
    role_map=role_map or {}
    if not isinstance(role_map,dict) or any(not isinstance(k,str) or v not in ("plan","atelier") for k,v in role_map.items()):
        raise ValueError("role map must assign relative PDF paths to plan or atelier")
    output_dir.mkdir(parents=True,exist_ok=True)
    log=output_dir/"runtime.log"
    with log.open("w",encoding="utf-8") as stream,contextlib.redirect_stdout(stream),contextlib.redirect_stderr(stream):
        try:
            return _run(input_dir,output_dir,ocr_mode,ocr_max_pages,max_pixels,max_pages,assert_complete_scope,synthetic,length_tolerance_mm,role_map)
        except Exception:
            traceback.print_exc()
            write_json(output_dir/"run_status.json",{"status":"failed","details":"See private runtime.log"})
            raise RuntimeError("local run failed; private runtime log contains details") from None

def _run(input_dir,output_dir,ocr_mode,ocr_max_pages,max_pixels,max_pages,assert_complete_scope,synthetic,length_tolerance_mm,role_map):
    started=time.perf_counter()
    observations,coverage,rejections,input_manifest=[],[],[],[]
    ocr=LocalOCR(max_pixels)
    ocr_pages=0; pages_attempted=0; omitted_by_limit=0
    files=sorted(p for p in input_dir.rglob("*") if p.is_file() and p.suffix.lower()==".pdf" and not p.name.lower().startswith("consignes"))
    relative_files={p.relative_to(input_dir).as_posix() for p in files}
    if set(role_map)-relative_files: raise ValueError("role map contains paths absent from the input")
    schema=json.loads((Path(__file__).resolve().parents[1]/"schema"/"extractions.schema.json").read_text(encoding="utf-8"))
    for path in files:
        relative=path.relative_to(input_dir).as_posix(); role=role_map.get(relative) or document_role(relative)
        with path.open("rb") as fh: checksum=hashlib.file_digest(fh,"sha256").hexdigest()
        input_manifest.append({"file":relative,"bytes":path.stat().st_size,"sha256":checksum})
        try:
            with fitz.open(path) as document:
                if document.needs_pass: raise ValueError("password required")
                for number,page in enumerate(document,1):
                    if max_pages is not None and pages_attempted>=max_pages:
                        omitted_by_limit+=1; continue
                    pages_attempted+=1
                    base={"file":relative,"file_id":stable_id(relative),"page":number,"source":role}
                    if role is None:
                        coverage.append({**base,"status":"unclassified_document","records":0,"rejected_annotations":0,"sheet":None})
                        continue
                    try:
                        lines=native_lines(page)
                        method="native"
                        weak_native=sum(len(line.text.strip()) for line in lines)<35
                        page_ocr_info=None
                        ocr_deferred=False
                        if weak_native and ocr_mode=="auto" and ocr_pages<ocr_max_pages:
                            try:
                                lines,page_ocr_info=ocr.recognize(page); method="ocr"; ocr_pages+=1
                            except OCRMemoryDeferred:
                                ocr_deferred=True
                        scheduled,used_boxes,schedule_info=schedule_observations(lines,source=role,fichier=relative,page=number,
                            width=page.rect.width,height=page.rect.height)
                        remaining=[line for line in lines if line.bbox not in used_boxes]
                        parsed,rejected,info=parse_page(remaining,source=role,fichier=relative,page=number,
                            width=page.rect.width,height=page.rect.height,path_hint=relative)
                        parsed=scheduled+parsed
                        info.update(schedule_info,line_count=len(lines),records=len(parsed),
                            reinforcement_hint_lines=sum(bool(BAR_HINT.search(line.text)) for line in lines))
                        for r in rejected: r["file"]=relative
                        observations.extend(parsed); rejections.extend(rejected)
                        state="extracted" if parsed else ("unsupported_or_empty" if info["reinforcement_hint_lines"] or not lines else "no_supported_reinforcement")
                        if weak_native and method=="native": state="ocr_not_run"
                        if ocr_deferred: state="ocr_deferred_low_memory"
                        coverage.append({**base,**info,"status":state,"method":method,"ocr":page_ocr_info})
                    except Exception as error:
                        coverage.append({**base,"status":"page_error","error_type":type(error).__name__,"records":0,"sheet":None})
                        traceback.print_exc()
        except Exception as error:
            coverage.append({"file":relative,"file_id":stable_id(relative),"source":role,"page":None,"sheet":None,
                             "status":"file_error","error_type":type(error).__name__,"records":0})
            traceback.print_exc()
    records=[o.record for o in observations]
    jsonschema.Draft202012Validator(schema).validate(records)
    ids=[r["id"] for r in records]
    if len(ids)!=len(set(ids)): raise ValueError("duplicate extraction IDs")
    bounds={(c["file"],c["page"]):(c.get("page_width_pt"),c.get("page_height_pt")) for c in coverage}
    for r in records:
        w,h=bounds[(r["fichier"],r["page"])]
        if not (0<=r["x"]<=w and 0<=r["y"]<=h): raise ValueError("coordinate outside displayed page")
    incomplete=omitted_by_limit or any(c["status"] in ("unclassified_document","ocr_not_run","ocr_deferred_low_memory","page_error","file_error","unsupported_or_empty") or c.get("rejected_annotations",0)>0 for c in coverage)
    scope_verified=bool(assert_complete_scope and not incomplete and files)
    matches,decisions=reconcile(observations,shop_scope_complete=scope_verified,plan_scope_complete=scope_verified,
                                length_tolerance_mm=length_tolerance_mm)
    candidates=[{k:v for k,v in r.items()} for r in rejections if r.get("candidate")]
    summary={"synthetic":synthetic,"pdf_files":len(files),"pages_attempted":pages_attempted,"pages_omitted_by_limit":omitted_by_limit,
             "extractions":len(records),"matches":len(matches),"decisions":decision_counts(decisions),
             "records_by_family":dict(Counter(r["type_element"] for r in records)),
             "page_status_counts":dict(Counter(c["status"] for c in coverage)),
             "rejected_annotations":len(rejections),"unresolved_extraction_candidates":len(candidates),"ocr_pages":ocr_pages,
             "complete_scope_user_asserted":assert_complete_scope,"complete_scope_accepted":scope_verified,
             "no_records_is_not_conformity":True,"precision_recall_measured":False,
             "elapsed_seconds":round(time.perf_counter()-started,3)}
    for name,value in [("extractions.json",records),("provenance.json",{o.record["id"]:o.context for o in observations}),
                       ("matches.json",matches),("discrepancies.json",decisions),("coverage.json",coverage),
                       ("rejections.json",rejections),("candidates.json",candidates),("input_manifest.json",input_manifest)]:
        write_json(output_dir/name,value)
    summary.update(render_reports(output_dir,observations,decisions,coverage,summary,synthetic=synthetic))
    summary["elapsed_seconds"]=round(time.perf_counter()-started,3)
    write_json(output_dir/"aggregate.json",summary)
    write_json(output_dir/"run_status.json",{"status":"completed_with_review_cases" if incomplete or summary["decisions"]["review_required"] else "completed",
               "finished_at":datetime.now(timezone.utc).isoformat(),"synthetic":synthetic,"quality_evaluation_complete":False})
    return summary
