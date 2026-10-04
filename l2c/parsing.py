"""Conservative, inspectable grammar. Unsupported notation remains visible."""
import re
from fractions import Fraction
from collections import Counter
from .model import TextLine, Observation, normalized, identifier, stable_id, center, union_box, SHEET_FAMILY

SHEET = re.compile(r"\bS[-_ ]?(\d{2,4}(?:[.-]\d{1,2})?[A-Z]?)\b", re.I)
LABELLED_SHEET = re.compile(r"(?:SHEET|FEUILLET)\s*[:=]?\s*S[-_ ]?(\d{2,4}(?:[.-]\d{1,2})?[A-Z]?)\b", re.I)
SHEET_FIELD = re.compile(r"^(?:FEUILLET|SHEET|DESSIN|DRAWING)(?:\s*(?:N[O°.]|NUMBER|NUMERO))*\s*[:=.-]?\s*$", re.I)
SHEET_VALUE = re.compile(r"^(?=[A-Z0-9_. /-]*\d)[A-Z0-9][A-Z0-9_. /-]{0,25}$", re.I)
ELEMENT = re.compile(r"(?<![A-Z0-9])((?:SF|C|P|B|M|W|D|F|R)[- ]?\d{1,4}[A-Z]?)(?![A-Z0-9]|-\d)", re.I)
LEVEL = re.compile(r"\b(?:LEVEL|NIVEAU|NIV\.?|ETAGE|FLOOR)\s*[:=-]?\s*(SS\d+|RDC|FDN|TOIT|ROOF|\d+(?:\s*[@/]\s*\d+)?)\b")
PART = re.compile(r"\bPART(?:IE)?\s*(\d+)\s*(?:/|OF|SUR)\s*(\d+)\b")
DIAMETER = r"(?:10|15|20|25|30|35|45|55)\s*M"
BAR = re.compile(r"(?<![\w.])(?:(\d{1,4})\s*(?:[-X*]\s*|\s+))?("+DIAMETER+r")\b", re.I)
SPACING_MARKER = r"(?:@|ESP(?:ACEMENT)?\s*[:=])"
LENGTH_MARKER = r"\b(?:L|LONG(?:UEUR)?|LENGTH)\s*[:=]"
NUMBER = r"(?:\d+\s+\d+/\d+|\d+/\d+|\d+(?:[.,]\d+)?)"
SPACING = re.compile(SPACING_MARKER + r"\s*(" + NUMBER + r")", re.I)
LENGTH = re.compile(LENGTH_MARKER + r"\s*(" + NUMBER + r")", re.I)
MARK = re.compile(r"\b(?:MARK|REPERE|REP)\s*[:=]?\s*([A-Z][A-Z0-9_-]*)\b")
BAR_HINT = re.compile(r"\b\d{1,3}\s*M\b|ARMATURE|REBAR|\bBARRES?\b", re.I)

def numeric(value):
    pieces=value.replace(",", ".").split()
    return sum((Fraction(piece) for piece in pieces), Fraction(0))

def measurement(tail, pattern, marker, name):
    """Exact metric/imperial conversion; never ignore an explicit suffix."""
    match = pattern.search(tail)
    if not match:
        return (None, ["unsupported_" + name + "_notation"]) if re.search(marker, tail, re.I) else (None, [])
    try: amount = numeric(match.group(1))
    except (ValueError, ZeroDivisionError): return None, ["unsupported_" + name + "_notation"]
    suffix = tail[match.end():].lstrip()
    unit = re.match(r"(?:(MM|CM|M|FT|FEET|FOOT|INCHES|INCH|IN)\b|(['\"\u2032\u2033]))", suffix, re.I)
    # A following labelled attribute is not a unit. Unknown suffixes require review.
    next_field = re.match(r"(?:" + LENGTH_MARKER + "|" + SPACING_MARKER + r"|MARK\s*[:=]|REP(?:ERE)?\s*[:=])", suffix, re.I)
    if suffix and not unit and not next_field and suffix[0] not in ";|,)":
        return None, ["unsupported_" + name + "_unit_or_notation"]
    unit_name=(unit.group(1) or unit.group(2)).upper() if unit else "MM"
    factors={"MM":Fraction(1),"CM":Fraction(10),"M":Fraction(1000),
             "FT":Fraction("304.8"),"FEET":Fraction("304.8"),"FOOT":Fraction("304.8"),"'":Fraction("304.8"),"\u2032":Fraction("304.8"),
             "IN":Fraction("25.4"),"INCH":Fraction("25.4"),"INCHES":Fraction("25.4"),'"':Fraction("25.4"),"\u2033":Fraction("25.4")}
    value=amount*factors[unit_name]
    if unit:
        remainder=suffix[unit.end():].lstrip()
        if factors[unit_name]==Fraction("304.8"):
            inches=re.match(r"-?\s*("+NUMBER+r")\s*(?:INCHES\b|INCH\b|IN\b|[\"\u2033])",remainder,re.I)
            if inches:
                try: value+=numeric(inches.group(1))*Fraction("25.4")
                except (ValueError,ZeroDivisionError): return None,["unsupported_"+name+"_notation"]
                remainder=remainder[inches.end():].lstrip()
        next_after_unit=re.match(r"(?:"+LENGTH_MARKER+"|"+SPACING_MARKER+r"|MARK\s*[:=]|REP(?:ERE)?\s*[:=])",remainder,re.I)
        if remainder and not next_after_unit and remainder[0] not in ";|,)":
            return None,["unsupported_"+name+"_unit_or_notation"]
    return (int(value) if value.denominator==1 else float(value)),[]

def colocated(first, second, tolerance=1.0):
    return max(abs(a-b) for a,b in zip(first, second)) <= tolerance

def level_from(text):
    match = LEVEL.search(normalized(text))
    if not match: return None
    value=re.sub(r"\s+","",match.group(1)).replace("@","/")
    if re.fullmatch(r"\d+(?:/\d+)?",value): return "/".join(str(int(p)) for p in value.split("/"))
    return value

def part_from(text):
    match = PART.search(normalized(text))
    return [int(match.group(1)), int(match.group(2))] if match else None

def family_from(text, sheet=None, element=None):
    text = normalized(text)
    for family, pattern in [
        ("fondation", r"FONDATION|FOUNDATION|SEMELLE|FOOTING|RADIER"),
        ("poutre", r"POUTRE|\bBEAM\b"),
        ("mur_refend", r"REFEND|CISAILLEMENT|SHEAR|\bWALL\b|\bMUR\b"),
        ("colonne", r"COLONNE|COLUMN"),
        ("dalle", r"DALLE|\bSLAB\b"),
    ]:
        if re.search(pattern, text): return family
    match = SHEET.search(sheet or "")
    if match and match.group(1)[0] in SHEET_FAMILY: return SHEET_FAMILY[match.group(1)[0]]
    prefix = re.sub(r"[^A-Z]", "", normalized(element or ""))
    return {"F":"fondation","SF":"fondation","R":"fondation","P":"poutre","B":"poutre",
            "M":"mur_refend","W":"mur_refend","C":"colonne","D":"dalle"}.get(prefix)

def sheet_from(lines, width, height):
    candidates = []
    for line in lines:
        # OCR may remove the space in 'SHEET S-100'; no digits are guessed.
        labelled = list(LABELLED_SHEET.finditer(normalized(line.text)))
        values = {match.group(1).upper() for match in SHEET.finditer(line.text)}
        values.update(match.group(1).upper() for match in labelled)
        for token in sorted(values):
            value = "S-" + token
            x, y = center(line.bbox)
            footer=y>height*.75 and x>width*.55
            score=4 if footer else 1
            reference=bool(re.search(r"\b(?:VOIR|SEE|REF|REFERENCE)\b",normalized(line.text)))
            if labelled and not reference: score=6 if footer else 5
            candidates.append((value, score))
    # A literal title-block label and its unique geometric value are evidence;
    # a filename or page ordinal is never invented as a sheet number.
    for label in lines:
        lx,ly=center(label.bbox)
        if not (lx>width*.55 and ly>height*.7 and SHEET_FIELD.fullmatch(normalized(label.text))): continue
        neighbors=[]
        for value_line in lines:
            value=normalized(value_line.text).strip()
            if value_line is label or not SHEET_VALUE.fullmatch(value): continue
            vx,vy=center(value_line.bbox)
            dx,dy=vx-lx,vy-ly
            right=abs(dy)<=max(3,(label.bbox[3]-label.bbox[1])/2) and 0<value_line.bbox[0]-label.bbox[2]<=120
            below=0<dy<=55 and abs(dx)<=100
            if right or below:
                neighbors.append((abs(dx)*.35+abs(dy),value))
        neighbors.sort()
        if neighbors and (len(neighbors)==1 or neighbors[1][0]-neighbors[0][0]>=8):
            value=neighbors[0][1]
            token=SHEET.fullmatch(value)
            candidates.append(("S-"+token.group(1).upper() if token else value,7))
    if not candidates: return None, "unidentified"
    highest=max(score for _,score in candidates)
    strongest={value for value,score in candidates if score==highest}
    if len(strongest)!=1: return None,"ambiguous"
    return next(iter(strongest)),"located" if highest>=4 else "inferred"

def parse_reinforcement(text):
    text = normalized(text).replace("\u00d7", "X").replace("\u2044", "/")
    issues = []
    if re.search(r"(?<!\w)-\d+\s*[-X ]\s*" + DIAMETER, text):
        return [], ["negative_quantity_not_supported"]
    matches = list(BAR.finditer(text))
    records = []
    mark = MARK.search(text)
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        tail = text[match.end():end]
        quantity = int(match.group(1)) if match.group(1) else None
        spacing, spacing_issues = measurement(tail, SPACING, SPACING_MARKER, "spacing")
        length, length_issues = measurement(tail, LENGTH, LENGTH_MARKER, "length")
        issues.extend(spacing_issues + length_issues)
        records.append({"repere": mark.group(1) if mark else None, "diametre":re.sub(r"\s+","",match.group(2).upper()),
                        "quantite":quantity, "espacement_mm":spacing, "longueur_mm":length})
    # Keep the original annotation in private rejections instead of comparing
    # a partly parsed bar whose unknown unit could turn into false conformity.
    if issues: return [], sorted(set(issues))
    if BAR_HINT.search(text) and not records: issues.append("reinforcement_notation_unparsed")
    return records, issues

def parse_page(lines, *, source, fichier, page, width, height, sheet=None, path_hint=""):
    located, sheet_status = sheet_from(lines, width, height)
    sheet = sheet or located
    default_levels = {level_from(line.text) for line in lines if level_from(line.text)}
    default_level = next(iter(default_levels)) if len(default_levels) == 1 else level_from(path_hint)
    headings = []
    for index, line in enumerate(lines):
        ids = [m.group(1).upper().replace(" ", "-") for m in ELEMENT.finditer(normalized(line.text))]
        ids = list(dict.fromkeys(ids))
        if len(ids) == 1:
            same = next((h for h in headings if normalized(h["line"].text)==normalized(line.text)
                         and colocated(h["line"].bbox, line.bbox)), None)
            headings.append({"index":index,"group_index":same["group_index"] if same else index,"element":ids[0],"line":line,
                             "level":level_from(line.text) or default_level,"part":part_from(line.text) or part_from(path_hint)})
    groups, rejected = {}, []
    for index, line in enumerate(lines):
        bars, issues = parse_reinforcement(line.text)
        if issues:
            rejected.append({"page":page,"bbox":list(line.bbox),"reason":issues,"text":line.text})
        if not bars: continue
        inline = [h for h in headings if h["index"] == index]
        candidates = inline
        if not inline:
            lx, ly = center(line.bbox)
            ranked = []
            for head in headings:
                hx, hy = center(head["line"].bbox)
                dx, dy = abs(lx-hx), ly-hy
                if -5 <= dy <= 90 and dx <= 160:
                    distance = dx * 0.45 + abs(dy)
                    ranked.append((distance, head))
            ranked.sort(key=lambda item:item[0])
            if ranked and (len(ranked) == 1 or ranked[1][0]-ranked[0][0] >= 12):
                candidates = [ranked[0][1]]
        if len(candidates) != 1:
            rejected.append({"page":page,"bbox":list(line.bbox),"reason":["element_association_ambiguous"],"text":line.text,
                             "candidate":{"source":source,"element":None,"feuillet":sheet,"armature":bars,"confirmed":False}})
            continue
        head = candidates[0]
        family = family_from(path_hint, sheet, head["element"])
        if family is None or sheet is None:
            rejected.append({"page":page,"bbox":list(line.bbox),"reason":["family_or_sheet_unidentified"],"text":line.text,
                             "candidate":{"source":source,"element":head["element"],"feuillet":sheet,"type_element":family,
                                          "level":head["level"],"armature":bars,"confirmed":False}})
            continue
        key = head["group_index"]
        group = groups.setdefault(key, {"head":head,"family":family,"bars":[],"lines":[],"duplicates":0,"positioned_repeat":False})
        signature = (normalized(line.text), tuple((b["repere"],b["diametre"],b["quantite"],b["espacement_mm"],b["longueur_mm"]) for b in bars))
        same_content = [item for item in group["lines"] if item[0] == signature]
        if any(colocated(item[1].bbox, line.bbox) for item in same_content):
            group["duplicates"] += 1
            continue
        if same_content: group["positioned_repeat"] = True
        group["bars"].extend(bars)
        group["lines"].append((signature,line))
    observations = []
    for group in groups.values():
        head = group["head"]
        support = [line for _,line in group["lines"]]
        bbox = union_box([head["line"].bbox]+[line.bbox for line in support])
        x,y = center(bbox)
        rid = stable_id(source,fichier,page,head["element"],head["level"],head["part"],[round(v,3) for v in bbox])
        record = {"id":rid,"source":source,"fichier":fichier,"feuillet":sheet,"page":page,"x":round(x,3),"y":round(y,3),
                  "type_element":group["family"],"element":head["element"],"armature":group["bars"]}
        flags = ["nearby_heading_association"] if any(line is not head["line"] for line in support) else []
        if group["positioned_repeat"]: flags.append("positioned_repetition_unresolved")
        observations.append(Observation(record,{"level":head["level"],"part":head["part"],"bbox":list(bbox),
            "sheet_status":sheet_status,"method":sorted({line.method for line in support}),
            "annotation_boxes":[list(line.bbox) for line in support],
            "measurement_policy":"Explicit metric/imperial converted to mm; unitless mm; original annotation retained in evidence_text.",
            "duplicate_annotations_suppressed":group["duplicates"],"evidence_text":"\n".join(line.text for line in support),
            "scope":"local_annotation","flags":flags}))
    coverage = {"line_count":len(lines),"reinforcement_hint_lines":sum(bool(BAR_HINT.search(line.text)) for line in lines),
                "records":len(observations),"rejected_annotations":len(rejected),"sheet":sheet,"sheet_status":sheet_status,
                "page_width_pt":width,"page_height_pt":height}
    return observations,rejected,coverage
