"""Explained local reports; generated contents may be confidential."""
from pathlib import Path
from collections import Counter
from hashlib import sha256
from xml.sax.saxutils import escape
import json,re
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,PageBreak
from .matching import decision_counts

LABELS={"compliant":"Compliant on compared attributes", "non_compliant":"Non-compliant",
        "missing_from_shop":"Missing from shop drawings", "added_in_shop":"Added in shop drawings",
        "needs_review":"Unresolved association", "confirmed_decisions":"Confirmed decisions",
        "review_required":"Cases requiring review", "total":"Total decisions",
        "quantite":"Quantity", "diametre":"Diameter", "espacement_mm":"Spacing (mm)", "longueur_mm":"Length (mm)"}
REASONS={"observed_attributes_compared":"The identified element and level match; the listed attributes were compared.",
         "partial_attribute_coverage":"One or more attributes are missing or unreadable; the comparison is partial.",
         "duplicate_or_incomplete_parts":"Repeated candidates or incomplete part definitions prevent a unique association.",
         "level_context_unidentified":"The level could not be established; a match is not confirmed.",
         "positioned_repetition_unresolved":"Repeated annotations at different positions are preserved; their quantities cannot be added without establishing their physical scope.",
         "context_conflict_or_unknown_level":"A possible counterpart exists in a different or unknown level context.",
         "unmatched_in_asserted_complete_scope":"No counterpart was found in a scope explicitly asserted complete by the local reviewer.",
         "unmatched_candidate_scope_not_verified":"No counterpart was found, but complete source coverage has not been verified."}

def readable_value(attribute,value):
    if not isinstance(value,list): return str(value)
    pieces=[]
    for diameter,amount,weight in value:
        if attribute=="diametre": pieces.append(f"{diameter} (weight {weight})")
        else: pieces.append(f"{diameter}: {amount} mm (weight {weight})")
    return "; ".join(pieces)

def filename(label):
    slug=re.sub(r"[^A-Za-z0-9_-]","_",label)[:65] or "review"
    return slug+"_"+sha256(label.encode("utf-8")).hexdigest()[:8]+".pdf"

def render_reports(output,observations,decisions,coverage,summary,*,synthetic=False):
    root=Path(output)/"reports"; root.mkdir(parents=True,exist_ok=True)
    styles=getSampleStyleSheet()
    def para(text,style="BodyText"): return Paragraph(escape(str(text)).replace("\n","<br/>"),styles[style])
    by_id={o.record["id"]:o.record for o in observations}
    plan_pages=[c for c in coverage if c.get("source")=="plan"]
    labels={c.get("sheet") or "UNIDENTIFIED_"+str(c.get("file_id"))+"_p"+str(c.get("page")) for c in plan_pages}
    decisions_by_sheet={label:[] for label in labels}
    for decision in decisions:
        sheets={by_id[r]["feuillet"] for r in decision["plan_ids"] if r in by_id}
        if not sheets: sheets={"UNASSOCIATED_SHOP_ADDITIONS"}
        for sheet in sheets: decisions_by_sheet.setdefault(sheet,[]).append(decision)
    if not decisions_by_sheet: decisions_by_sheet["NO_CONFIRMED_PLAN_SHEETS"]=[]
    index=[]
    for label,rows in sorted(decisions_by_sheet.items()):
        counts=decision_counts(rows)
        title=("SYNTHETIC EXAMPLE - " if synthetic else "PRIVATE L2C REVIEW - ")+label
        flow=[para(title,"Title"),para("Decision support only. The engineer makes the final determination."),
              Spacer(1,10),para("Confirmed findings and cases requiring review are counted separately.")]
        table=[["Decision","Count"]]+[[LABELS.get(k,k),str(v)] for k,v in counts.items()]
        grid=Table(table,colWidths=[3.9*inch,1.2*inch])
        grid.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#18334a")),
            ("TEXTCOLOR",(0,0),(-1,0),colors.white),("GRID",(0,0),(-1,-1),0.4,colors.lightgrey),
            ("VALIGN",(0,0),(-1,-1),"TOP")]))
        flow += [grid,Spacer(1,12)]
        if not rows:
            flow.append(para("No comparison could be established for this scope. This does not mean there are no discrepancies.","Heading2"))
        for row in rows:
            status=LABELS.get(row["status"],row["status"])+(" - REVIEW REQUIRED" if row["review_required"] else "")
            flow += [para(status,"Heading2"),para(REASONS.get(row["reason"],row["reason"]))]
            for side,key in [("Plan","plan_ids"),("Shop","shop_ids")]:
                for rid in row[key]:
                    record=by_id[rid]
                    location=f"{side}: {record['fichier']} | {record['feuillet']} | page {record['page']} | centre ({record['x']}, {record['y']}) pt"
                    flow += [para(location),para("Element: "+record["element"])]
            for difference in row["differences"]:
                attribute=difference["attribute"]
                flow.append(para(LABELS.get(attribute,attribute)+": expected "+readable_value(attribute,difference["expected"])+"; observed "+readable_value(attribute,difference["observed"])))
            if row["unresolved_attributes"]:
                flow.append(para("Unresolved attributes: "+", ".join(LABELS.get(a,a) for a in row["unresolved_attributes"])))
            flow.append(para("Compared attributes: "+(", ".join(LABELS.get(a,a) for a in row["tested_attributes"]) or "none")))
            flow.append(Spacer(1,6))
        target=root/filename(label)
        SimpleDocTemplate(str(target),pagesize=(612,792),rightMargin=40,leftMargin=40,topMargin=38,bottomMargin=38).build(flow)
        index.append({"sheet":label,"file":target.name,"decision_counts":counts,"bytes":target.stat().st_size})
    flow=[para("SYNTHETIC PROJECT SUMMARY" if synthetic else "PRIVATE PROJECT SUMMARY","Title"),
          para("Counts describe the program's observations, not measured precision or recall."),
          para(json.dumps(summary,ensure_ascii=False)),Spacer(1,14),para("Coverage by input page","Heading1")]
    for c in coverage:
        flow.append(para(f"{c.get('source') or 'unclassified'} | {c.get('file')} | page {c.get('page')} | sheet {c.get('sheet') or 'unidentified'} | {c.get('status')} | records {c.get('records',0)} | rejected {c.get('rejected_annotations',0)}"))
    SimpleDocTemplate(str(root/"summary.pdf"),pagesize=(612,792),rightMargin=40,leftMargin=40,topMargin=38,bottomMargin=38).build(flow)
    (root/"index.json").write_text(json.dumps({"synthetic":synthetic,"reports":index,"summary":"summary.pdf"},ensure_ascii=False,indent=2),encoding="utf-8")
    return {"sheet_reports":len(index),"pdf_reports":len(index)+1}
