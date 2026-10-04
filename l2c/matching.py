"""Context-aware matching; uncertainty never silently becomes conformity."""
from collections import defaultdict
from .model import Observation, identifier, stable_id

def group_key(observation):
    record, context = observation.record, observation.context
    return (record["type_element"],identifier(record["element"]),context.get("level"))

def complete_parts(group):
    parts = [o.context.get("part") for o in group]
    if not parts or any(not p or len(p)!=2 or p[0]<1 or p[1]<1 for p in parts): return False
    total = parts[0][1]
    return all(p[1]==total for p in parts) and len(parts)==total and {p[0] for p in parts}==set(range(1,total+1))

def comparison(plan,shop,length_tolerance_mm=0.0):
    expected = [bar for obs in plan for bar in obs.record["armature"]]
    observed = [bar for obs in shop for bar in obs.record["armature"]]
    differences, unknown, tested = [], [], []
    def quantities(rows):
        if any(r["quantite"] is None for r in rows): return None
        return sum(r["quantite"] for r in rows)
    eq,aq=quantities(expected),quantities(observed)
    if eq is None or aq is None: unknown.append("quantite")
    else:
        tested.append("quantite")
        if eq != aq: differences.append({"attribute":"quantite","expected":eq,"observed":aq,"delta":aq-eq})
    def distribution(rows,attribute,weighted):
        if any(r[attribute] is None for r in rows): return None
        aggregate=defaultdict(int)
        for r in rows:
            key=(r["diametre"] or "unknown",r[attribute])
            if weighted:
                aggregate[key] += r["quantite"]
            else:
                aggregate[key] = 1
        return sorted([[key[0],key[1],amount] for key,amount in aggregate.items()],key=str)
    for attribute in ("diametre","espacement_mm","longueur_mm"):
        epresent=any(r[attribute] is not None for r in expected)
        apresent=any(r[attribute] is not None for r in observed)
        if not epresent and not apresent: continue
        weighted=eq is not None and aq is not None and eq==aq
        ev,av=distribution(expected,attribute,weighted),distribution(observed,attribute,weighted)
        if ev is None or av is None:
            unknown.append(attribute); continue
        tested.append(attribute)
        equal=ev==av
        if attribute=="longueur_mm" and length_tolerance_mm and len(ev)==len(av):
            equal=all(e[0]==a[0] and e[2]==a[2] and abs(e[1]-a[1])<=length_tolerance_mm for e,a in zip(ev,av))
        # A quantity-only difference already explains different distribution weights.
        if not equal and (attribute!="diametre" or {r["diametre"] for r in expected}!={r["diametre"] for r in observed}
                          or eq==aq):
            differences.append({"attribute":attribute,"expected":ev,"observed":av,"tolerance_mm":length_tolerance_mm if attribute=="longueur_mm" else 0})
    status="non_compliant" if differences else ("needs_review" if unknown or not tested else "compliant")
    return status,differences,sorted(set(unknown)),tested

def reconcile(observations,*,shop_scope_complete=False,plan_scope_complete=False,length_tolerance_mm=0.0):
    by_source={"plan":defaultdict(list),"atelier":defaultdict(list)}
    for obs in observations: by_source[obs.record["source"]][group_key(obs)].append(obs)
    plans,shops=by_source["plan"],by_source["atelier"]
    decisions, matches=[],[]
    for key in sorted(set(plans)|set(shops),key=str):
        plan,shop=plans.get(key,[]),shops.get(key,[])
        ids=[o.record["id"] for o in plan+shop]
        did=stable_id("decision",key,sorted(ids))
        base={"id":did,"plan_ids":[o.record["id"] for o in plan],"shop_ids":[o.record["id"] for o in shop],
              "context":{"type_element":key[0],"element_key":key[1],"level":key[2]},
              "differences":[],"unresolved_attributes":[],"tested_attributes":[],"confirmed":False}
        if not plan or not shop:
            desired="added_in_shop" if not plan else "missing_from_shop"
            opposite_complete=plan_scope_complete if not plan else shop_scope_complete
            # Same identity on a different/unknown level requires review, not absence.
            opposite=plans if not plan else shops
            conflicting=any(other[:2]==key[:2] and other!=key for other in opposite)
            base.update(status=desired,confirmed=bool(opposite_complete and not conflicting),
                review_required=not opposite_complete or conflicting,
                reason="context_conflict_or_unknown_level" if conflicting else ("unmatched_in_asserted_complete_scope" if opposite_complete else "unmatched_candidate_scope_not_verified"))
        elif key[2] is None:
            base.update(status="needs_review",review_required=True,reason="level_context_unidentified")
        elif any("positioned_repetition_unresolved" in o.context.get("flags",[]) for o in plan+shop):
            base.update(status="needs_review",review_required=True,reason="positioned_repetition_unresolved")
        elif ((len(plan)>1 or any(o.context.get("part") for o in plan)) and not complete_parts(plan)) or ((len(shop)>1 or any(o.context.get("part") for o in shop)) and not complete_parts(shop)):
            base.update(status="needs_review",review_required=True,reason="duplicate_or_incomplete_parts")
        else:
            status,diffs,unknown,tested=comparison(plan,shop,length_tolerance_mm)
            base.update(status=status,differences=diffs,unresolved_attributes=unknown,tested_attributes=tested,
                        confirmed=status in ("compliant","non_compliant"),review_required=bool(unknown) or status=="needs_review",
                        reason="observed_attributes_compared" if not unknown else "partial_attribute_coverage")
            matches.append({"id":did,"plan_ids":base["plan_ids"],"shop_ids":base["shop_ids"],
                            "strategy":"exact_element_family_and_level","explicit_parts_aggregated":len(plan)>1 or len(shop)>1})
        decisions.append(base)
    return matches,decisions

def decision_counts(decisions):
    counts={k:0 for k in ("compliant","non_compliant","missing_from_shop","added_in_shop","needs_review")}
    for d in decisions: counts[d["status"]]+=1
    counts["confirmed_decisions"]=sum(d["confirmed"] for d in decisions)
    counts["review_required"]=sum(d["review_required"] for d in decisions)
    counts["total"]=len(decisions)
    return counts
