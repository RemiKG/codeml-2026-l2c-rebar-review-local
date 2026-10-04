"""Explicitly synthetic plans. No sponsor drawing or derived example is used."""
from pathlib import Path
import json
from reportlab.pdfgen.canvas import Canvas

CASES=[
    ("S-100","FOUNDATION","F"),
    ("S-300","BEAM","P"),
    ("S-400","SHEAR WALL","M"),
    ("S-500","COLUMN","C"),
    ("S-600","SLAB","D"),
]

def generate_project(folder):
    folder=Path(folder)
    for role in ("plans","shop"):
        dest=folder/role; dest.mkdir(parents=True,exist_ok=True)
        canvas=Canvas(str(dest/("plan_synthetic.pdf" if role=="plans" else "shop_synthetic.pdf")),pagesize=(612,792))
        for index,(sheet,family,prefix) in enumerate(CASES):
            canvas.setFont("Helvetica-Bold",15)
            canvas.drawString(45,750,"SYNTHETIC EXAMPLE - "+family+" - SHEET "+sheet)
            canvas.setFont("Helvetica",12)
            canvas.drawString(45,718,"LEVEL 2")
            quantity=8 if role=="plans" else 6
            rows=[f"{prefix}-1 | LEVEL 2 | MARK {prefix}1-1 | 8-25M | L=3600 mm",
                  f"{prefix}-2 | LEVEL 2 | MARK {prefix}2-1 | {quantity}-20M | L=2400 mm"]
            if index==0:
                rows.append(f"{prefix}-99 | LEVEL 2 | 4-15M | L=1200 mm" if role=="plans" else f"{prefix}-88 | LEVEL 2 | 4-15M | L=1200 mm")
            for row_number,text in enumerate(rows):
                canvas.drawString(45,665-row_number*66,text)
            canvas.showPage()
        canvas.save()
    meta={"synthetic":True,"source":"Hand-authored public-notation fixtures; no sponsor data.",
          "expected":{"families":5,"plan_elements":11,"shop_elements":11,"compliant":5,"non_compliant":5,"missing":1,"added":1},
          "scope":"Complete only for this intentionally generated fixture."}
    (folder/"SYNTHETIC.json").write_text(json.dumps(meta,indent=2),encoding="utf-8")
    return meta

if __name__=="__main__":
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",required=True)
    args=parser.parse_args()
    print(json.dumps(generate_project(args.output)))
