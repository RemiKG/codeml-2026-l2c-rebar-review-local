"""Explicit positioned schedule axes, without fuzzy element or level guesses."""
import re
from collections import defaultdict
from .model import Observation,center,union_box,normalized,stable_id
from .parsing import ELEMENT,level_from,parse_reinforcement,family_from,sheet_from,colocated

def clusters(items,coordinate,tolerance=8.0):
    groups=[]
    for item in sorted(items,key=lambda a:center(a['line'].bbox)[coordinate]):
        value=center(item['line'].bbox)[coordinate]
        if groups and abs(value-groups[-1][0])<=tolerance: groups[-1][1].append(item)
        else: groups.append([value,[item]])
    return [members for _,members in groups if len({m['value'] for m in members})>=2]

def nearest(value,items,coordinate,max_distance):
    ranked=sorted((abs(center(i['line'].bbox)[coordinate]-value),n,i) for n,i in enumerate(items))
    if not ranked or ranked[0][0]>max_distance: return None
    if len(ranked)>1 and ranked[1][0]-ranked[0][0]<4: return None
    return ranked[0][2]

def schedule_observations(lines,*,source,fichier,page,width,height):
    sheet,sheet_status=sheet_from(lines,width,height)
    if not sheet: return [],[],{'schedule_cells':0,'schedule_ambiguous_lines':0}
    elements=[]; levels=[]
    for line in lines:
        text=normalized(line.text).strip()
        # Punctuation and an explicit physical-element label do not change the
        # literal identifier. Prose or several identifiers still cannot be an axis.
        element_text=text.strip('()[]{}:;')
        element_text=re.sub(r'^(?:COLONNE|COLUMN|COL\.?|POUTRE|BEAM|ELEMENT|TYPE)\s*[:=-]?\s+','',element_text)
        element=ELEMENT.fullmatch(element_text)
        if element:
            elements.append({'line':line,'value':element.group(1).replace(' ','-')})
        level=level_from(text)
        if level and len(text)<=48:
            levels.append({'line':line,'value':level})
    # Bare level values are allowed only under an actual NIVEAU/LEVEL column label.
    level_labels=[l for l in lines if re.fullmatch(r'(?:NIVEAU[X]?|NIV\.?|LEVELS?|FLOORS?|ETAGES?)',normalized(l.text).strip().rstrip(':'))]
    for line in lines:
        text=normalized(line.text).strip()
        if not re.fullmatch(r'(?:SS[- ]?\d+|RDC|FDN|TOIT|ROOF|\d{1,2})',text): continue
        x,y=center(line.bbox)
        if any(abs(x-center(label.bbox)[0])<=25 and 0<y-center(label.bbox)[1]<=height*.7 for label in level_labels):
            value=str(int(text)) if text.isdigit() else re.sub(r'[- ]','',text)
            levels.append({'line':line,'value':value})
    arrangements=[]
    for row_kind,row_items,column_items in [('element',elements,levels),('level',levels,elements)]:
        for rows in clusters(row_items,0):
            for columns in clusters(column_items,1):
                row_x=sum(center(r['line'].bbox)[0] for r in rows)/len(rows)
                column_y=sum(center(c['line'].bbox)[1] for c in columns)/len(columns)
                min_row_y=min(center(r['line'].bbox)[1] for r in rows)
                min_column_x=min(center(c['line'].bbox)[0] for c in columns)
                if 0<min_row_y-column_y<=160 and row_x<min_column_x:
                    arrangements.append((row_kind,rows,columns))
    cells={}; ambiguous=0; used=[]
    for line in lines:
        bars,issues=parse_reinforcement(line.text)
        if not bars or issues: continue
        x,y=center(line.bbox); options={}
        for row_kind,rows,columns in arrangements:
            row=nearest(y,rows,1,max(5,(line.bbox[3]-line.bbox[1])*.55))
            if row is None: continue
            col=nearest(x,columns,0,width*.25)
            if col is None or x<=center(row['line'].bbox)[0] or y<=center(col['line'].bbox)[1]: continue
            # Require the annotation to fall in its column's Voronoi band, bounded
            # at the outside edges by half the next actual header separation.
            xs=sorted(center(c['line'].bbox)[0] for c in columns)
            if x<xs[0]-(xs[1]-xs[0])/2 or x>xs[-1]+(xs[-1]-xs[-2])/2: continue
            element=row['value'] if row_kind=='element' else col['value']
            level=col['value'] if row_kind=='element' else row['value']
            options[(element,level)]=(row,col)
        if len(options)>1: ambiguous+=1; continue
        if len(options)!=1: continue
        (element,level),(row,col)=next(iter(options.items()))
        family=family_from('',None,element)
        if family is None: continue
        # Separate physical cells even when an element label occurs in two tables.
        key=(element,level,tuple(row['line'].bbox),tuple(col['line'].bbox))
        cell=cells.setdefault(key,{'element':element,'level':level,'family':family,'row':row,'col':col,'lines':[],'bars':[],
                                   'repetition':False,'duplicates':0})
        identical=[previous for previous in cell['lines'] if normalized(previous.text)==normalized(line.text)]
        if any(colocated(previous.bbox,line.bbox) for previous in identical):
            cell['duplicates']+=1; continue
        if identical: cell['repetition']=True
        cell['lines'].append(line); cell['bars'].extend(bars); used.append(line.bbox)
    output=[]
    for cell in cells.values():
        box=union_box(l.bbox for l in cell['lines']); x,y=center(box)
        rid=stable_id('schedule',source,fichier,page,cell['element'],cell['level'],box)
        record={'id':rid,'source':source,'fichier':fichier,'feuillet':sheet,'page':page,'x':round(x,3),'y':round(y,3),
                'type_element':cell['family'],'element':cell['element'],'armature':cell['bars']}
        flags=['positioned_schedule_association']
        if cell['repetition']: flags.append('positioned_repetition_unresolved')
        context={'level':cell['level'],'part':None,'bbox':list(box),'sheet_status':sheet_status,
                 'method':sorted({l.method for l in cell['lines']}),'annotation_boxes':[list(l.bbox) for l in cell['lines']],
                 'context_boxes':[list(cell['row']['line'].bbox),list(cell['col']['line'].bbox)],
                 'evidence_text':'\n'.join([cell['row']['line'].text,cell['col']['line'].text]+[l.text for l in cell['lines']]),
                 'duplicate_annotations_suppressed':cell['duplicates'],'scope':'identified_schedule_cell','flags':flags,
                 'measurement_policy':'Explicit metric/imperial converted to mm; original annotation retained.'}
        output.append(Observation(record,context))
    return output,used,{'schedule_cells':len(output),'schedule_ambiguous_lines':ambiguous}
