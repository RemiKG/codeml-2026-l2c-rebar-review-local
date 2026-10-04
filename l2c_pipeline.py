"""CLI intentionally emits aggregate counts only; detailed output remains local."""
import argparse,json,sys
from pathlib import Path
from l2c.pipeline import run_project

def main():
    parser=argparse.ArgumentParser(description="Local plan/shop reinforcement reconciliation. Confidential input stays on this machine.")
    parser.add_argument("--input",required=True)
    parser.add_argument("--output",required=True)
    parser.add_argument("--ocr",choices=["off","auto"],default="off")
    parser.add_argument("--ocr-max-pages",type=int,default=8)
    parser.add_argument("--ocr-max-pixels",type=int,default=2_000_000)
    parser.add_argument("--max-pages",type=int)
    parser.add_argument("--roles",help="Local JSON mapping relative PDF paths to plan or atelier for unfamiliar filenames.")
    parser.add_argument("--length-tolerance-mm",type=float,default=0.0)
    parser.add_argument("--assert-complete-scope",action="store_true",help="Use only after local scope review; does not certify semantic extraction accuracy.")
    parser.add_argument("--synthetic",action="store_true",help="Label intentionally generated examples. This flag does not anonymize real inputs.")
    args=parser.parse_args()
    try:
        role_map=json.loads(Path(args.roles).read_text(encoding="utf-8")) if args.roles else None
        summary=run_project(args.input,args.output,ocr_mode=args.ocr,ocr_max_pages=args.ocr_max_pages,max_pixels=args.ocr_max_pixels,
            max_pages=args.max_pages,assert_complete_scope=args.assert_complete_scope,synthetic=args.synthetic,
            length_tolerance_mm=args.length_tolerance_mm,role_map=role_map)
    except Exception as error:
        print(json.dumps({"status":"failed","error_type":type(error).__name__,"details":"Inspect the local output log if created. No source content is printed."}))
        return 2
    print(json.dumps(summary,ensure_ascii=True))
    return 0

if __name__=="__main__":
    sys.exit(main())
