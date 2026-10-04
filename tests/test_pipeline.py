"""Behavioral tests against entirely synthetic inputs."""
import copy,json,os,subprocess,sys,tempfile,unittest
from unittest.mock import patch
from pathlib import Path
import pymupdf as fitz
from reportlab.pdfgen.canvas import Canvas
from l2c.model import Observation,TextLine
from l2c.parsing import parse_reinforcement,parse_page,sheet_from,level_from
from l2c.matching import reconcile,decision_counts
from l2c.pdfio import native_lines,join_fragments,LocalOCR,OCRMemoryDeferred
from l2c.pipeline import run_project
from l2c.synthetic import generate_project

REPO=Path(__file__).resolve().parents[1]
TEST_ROOT=Path(os.environ.get("L2C_TEST_TMP",str(REPO.parent/"verification"/"test-runs"))).resolve()
TEST_ROOT.mkdir(parents=True,exist_ok=True)

def obs(source,id,quantity=8,*,element="C-12",level="2",part=None,diameter="25M",length=3600,spacing=None):
    record={"id":id,"source":source,"fichier":"synthetic.pdf","feuillet":"S-500","page":1,"x":100.0,"y":150.0,
            "type_element":"colonne","element":element,"armature":[{"repere":None,"diametre":diameter,"quantite":quantity,
            "espacement_mm":spacing,"longueur_mm":length}]}
    return Observation(record,{"level":level,"part":part})

class NotationTests(unittest.TestCase):
    def test_counts_and_metric_conversion(self):
        bars,issues=parse_reinforcement("C-12 MARK C12-1 8-25M @20 cm L=3.6 m")
        self.assertEqual([],issues)
        self.assertEqual([{"repere":"C12-1","diametre":"25M","quantite":8,"espacement_mm":200,"longueur_mm":3600}],bars)
    def test_whitespace_quantity(self):
        bars,_=parse_reinforcement("8 25M")
        self.assertEqual(8,bars[0]["quantite"])
    def test_explicit_unsupported_units_never_default_to_mm(self):
        for text in ["8-15M L=10yd", "8-15M L=-10", "8-15M L=1/0 in", "8-15M L=10 unknown", "8-15M L=10 mm ft"]:
            with self.subTest(text=text):
                bars,issues=parse_reinforcement(text)
                self.assertEqual([],bars); self.assertTrue(issues)
    def test_explicit_imperial_conversion_is_not_default_mm(self):
        for text,attribute,expected in [("8-15M L=10'","longueur_mm",3048),("8-15M L=10 in","longueur_mm",254),
              ('8-15M @8"',"espacement_mm",203.2),("8-15M L=10ft","longueur_mm",3048),
              ('8-15M L=10\'-6"',"longueur_mm",3200.4),('8-15M @8 1/2"',"espacement_mm",215.9),
              ('8-15M L=1/2 in',"longueur_mm",12.7)]:
            with self.subTest(text=text):
                bars,issues=parse_reinforcement(text)
                self.assertFalse(issues); self.assertEqual(expected,bars[0][attribute])
    def test_equivalent_metric_imperial_measurements_compare_equal(self):
        p=obs("plan","p",length=3048)
        a=obs("atelier","a")
        a.record["armature"]=parse_reinforcement("8-25M L=10'")[0]
        self.assertEqual("compliant",reconcile([p,a])[1][0]["status"])
    def test_spaced_canadian_bar_size(self):
        bars,issues=parse_reinforcement("8-15 M")
        self.assertFalse(issues); self.assertEqual("15M",bars[0]["diametre"])
    def test_adjacent_native_fragments_join_without_crossing_distant_cells(self):
        lines=[TextLine("8-",(40,100,52,110)),TextLine("15 M",(55,100,78,110)),TextLine("C-99",(200,100,230,110))]
        joined=join_fragments(lines)
        self.assertEqual(2,len(joined)); self.assertEqual("8- 15 M",joined[0].text)
        self.assertEqual(8,parse_reinforcement(joined[0].text)[0][0]["quantite"])
    def test_native_fragments_do_not_merge_different_rows_or_overlaps(self):
        lines=[TextLine("8-15M",(40,100,80,110)),TextLine("8-15M",(40,100,80,110)),TextLine("L=500",(40,115,80,125))]
        self.assertEqual(3,len(join_fragments(lines)))
    def test_metric_and_unitless_defaults_are_deliberate(self):
        bars,issues=parse_reinforcement("8-15M @200 L=0.5M")
        self.assertFalse(issues); self.assertEqual(200,bars[0]["espacement_mm"])
        self.assertEqual(500,bars[0]["longueur_mm"])
        bars,issues=parse_reinforcement("8-15M L=1000")
        self.assertFalse(issues); self.assertEqual(1000,bars[0]["longueur_mm"])
    def test_unsupported_unit_keeps_private_rejection(self):
        lines=[TextLine("SHEET S-500",(40,20,220,40)),TextLine("C-12 LEVEL 2 8-15M L=10 yd",(40,100,300,120))]
        records,rejected,_=parse_page(lines,source="plan",fichier="synthetic.pdf",page=1,width=612,height=792)
        self.assertFalse(records); self.assertEqual(1,len(rejected))
    def test_missing_quantity_is_null(self):
        bars,_=parse_reinforcement("15M @ 200 mm")
        self.assertIsNone(bars[0]["quantite"])
        self.assertEqual(200,bars[0]["espacement_mm"])
    def test_explicit_negative_is_rejected(self):
        bars,issues=parse_reinforcement("-8-25M")
        self.assertEqual([],bars); self.assertIn("negative_quantity_not_supported",issues)
    def test_unrecognized_diameter_is_visible(self):
        bars,issues=parse_reinforcement("8-99M")
        self.assertFalse(bars); self.assertTrue(issues)
    def test_nearby_label_and_rebar_line(self):
        lines=[TextLine("SHEET S-500",(40,20,220,40)),TextLine("C-12 LEVEL 2",(40,100,180,120)),
               TextLine("8-25M L=3600 mm",(40,130,210,150))]
        records,rejected,_=parse_page(lines,source="plan",fichier="synthetic.pdf",page=1,width=612,height=792)
        self.assertEqual(1,len(records)); self.assertFalse(rejected)
        self.assertEqual("C-12",records[0].record["element"])
    def test_ocr_joined_sheet_label_preserves_digits(self):
        lines=[TextLine("SYNTHETICEXAMPLE-COLUMN-SHEETS-500",(40,20,400,40),method="ocr"),
               TextLine("C-12|LEVEL2|8-25M",(40,100,240,120),method="ocr")]
        records,rejected,_=parse_page(lines,source="plan",fichier="synthetic.pdf",page=1,width=612,height=792)
        self.assertEqual(1,len(records)); self.assertFalse(rejected)
        self.assertEqual("S-500",records[0].record["feuillet"])
    def test_sheet_footer_outranks_repeated_body_references(self):
        lines=[TextLine("SEE S-100",(30,50+i*20,120,65+i*20)) for i in range(12)]
        lines.append(TextLine("S-502",(530,740,590,770)))
        self.assertEqual(("S-502","located"),sheet_from(lines,612,792))
    def test_nonfamily_structural_sheet_stays_literal(self):
        lines=[TextLine("SHEET S-002.1",(40,20,240,40))]
        self.assertEqual(("S-002.1","located"),sheet_from(lines,612,792))
    def test_explicit_title_block_field_locates_nonstructural_sheet(self):
        lines=[TextLine("DRAWING NO.",(490,700,590,712)),TextLine("SHOP-42",(510,725,580,738))]
        self.assertEqual(("SHOP-42","located"),sheet_from(lines,612,792))
    def test_ambiguous_title_block_values_are_not_guessed(self):
        lines=[TextLine("FEUILLET",(480,700,570,712)),TextLine("A-42",(465,725,505,738)),TextLine("A-43",(545,725,585,738))]
        self.assertEqual((None,"unidentified"),sheet_from(lines,612,792))
    def test_unknown_sheet_retains_candidate_without_fabricating_schema_record(self):
        lines=[TextLine("C-12 LEVEL 2 8-25M",(40,100,250,120))]
        records,rejected,_=parse_page(lines,source="plan",fichier="synthetic.pdf",page=1,width=612,height=792)
        self.assertFalse(records); self.assertIsNone(rejected[0]["candidate"]["feuillet"])
        self.assertEqual(8,rejected[0]["candidate"]["armature"][0]["quantite"])
    def test_explicit_level_abbreviation_and_leading_zero(self):
        self.assertEqual("2",level_from("NIV. 02"))
        self.assertEqual("2",level_from("FLOOR 2"))
    def test_level_range_never_collapses_into_different_floor_number(self):
        self.assertEqual("2/3",level_from("NIVEAU 2 @ 3"))
        self.assertNotEqual(level_from("NIVEAU 2 @ 3"),level_from("NIVEAU 23"))
    def test_equally_near_labels_are_reviewed(self):
        lines=[TextLine("SHEET S-500",(40,20,220,40)),TextLine("C-1",(40,100,80,120)),
               TextLine("C-2",(160,100,200,120)),TextLine("8-25M",(100,130,140,150))]
        records,rejected,_=parse_page(lines,source="plan",fichier="synthetic.pdf",page=1,width=612,height=792)
        self.assertFalse(records); self.assertTrue(rejected)
    def test_positioned_repeats_are_preserved_and_not_summed(self):
        lines=[TextLine("SHEET S-500",(40,20,220,40)),TextLine("C-12 LEVEL 2",(40,100,180,120)),
               TextLine("8-25M",(40,130,100,150)),TextLine("8-25M",(40,151,100,171))]
        records,_,_=parse_page(lines,source="plan",fichier="synthetic.pdf",page=1,width=612,height=792)
        self.assertEqual(2,len(records[0].record["armature"]))
        self.assertEqual(2,len(records[0].context["annotation_boxes"]))
        self.assertEqual(0,records[0].context["duplicate_annotations_suppressed"])
        result=reconcile(records+[obs("atelier","a",16)])[1][0]
        self.assertEqual("needs_review",result["status"]); self.assertFalse(result["confirmed"])
        self.assertEqual("positioned_repetition_unresolved",result["reason"])
    def test_colocated_duplicates_are_suppressed(self):
        lines=[TextLine("SHEET S-500",(40,20,220,40)),TextLine("C-12 LEVEL 2",(40,100,180,120)),
               TextLine("8-25M",(40,130,100,150)),TextLine("8-25M",(40.2,130.2,100.2,150.2))]
        records,_,_=parse_page(lines,source="plan",fichier="synthetic.pdf",page=1,width=612,height=792)
        self.assertEqual(1,len(records[0].record["armature"]))
        self.assertEqual(1,records[0].context["duplicate_annotations_suppressed"])
    def test_colocated_inline_duplicates_have_one_stable_record(self):
        line=TextLine("C-12 LEVEL 2 8-25M",(40,100,250,120))
        lines=[TextLine("SHEET S-500",(40,20,220,40)),line,copy.deepcopy(line)]
        records,_,_=parse_page(lines,source="plan",fichier="synthetic.pdf",page=1,width=612,height=792)
        self.assertEqual(1,len(records)); self.assertEqual(1,records[0].context["duplicate_annotations_suppressed"])

class AssociationTests(unittest.TestCase):
    def status(self,items,**kwargs):
        return reconcile(items,**kwargs)[1]
    def test_equal_known_quantity_is_compliant(self):
        result=self.status([obs("plan","p"),obs("atelier","a")])
        self.assertEqual("compliant",result[0]["status"])
    def test_quantity_difference_is_explained_once(self):
        result=self.status([obs("plan","p"),obs("atelier","a",6)])[0]
        self.assertEqual("non_compliant",result["status"])
        self.assertEqual(["quantite"],[d["attribute"] for d in result["differences"]])
        self.assertEqual(-2,result["differences"][0]["delta"])
    def test_missing_quantity_does_not_create_false_attribute_error(self):
        result=self.status([obs("plan","p"),obs("atelier","a",None)])[0]
        self.assertEqual("needs_review",result["status"])
        self.assertFalse(result["differences"])
    def test_missing_expected_length_needs_review(self):
        result=self.status([obs("plan","p"),obs("atelier","a",length=None)])[0]
        self.assertEqual("needs_review",result["status"])
    def test_spacing_mismatch_detected(self):
        result=self.status([obs("plan","p",spacing=200),obs("atelier","a",spacing=250)])[0]
        self.assertEqual("non_compliant",result["status"])
        self.assertIn("espacement_mm",[d["attribute"] for d in result["differences"]])
    def test_levels_never_cross_match(self):
        result=self.status([obs("plan","p",level="2"),obs("atelier","a",level="3")],
            shop_scope_complete=True,plan_scope_complete=True)
        self.assertEqual(2,len(result))
        self.assertTrue(all(r["review_required"] and not r["confirmed"] for r in result))
    def test_unknown_level_is_not_equal_to_known_level(self):
        result=self.status([obs("plan","p",level=None),obs("atelier","a",level="2")])
        self.assertEqual(2,len(result)); self.assertTrue(all(r["review_required"] for r in result))
    def test_two_unknown_levels_do_not_certify_a_match(self):
        result=self.status([obs("plan","p",level=None),obs("atelier","a",level=None)])[0]
        self.assertEqual("needs_review",result["status"])
        self.assertFalse(result["confirmed"])
    def test_explicit_complete_parts_aggregate(self):
        result=self.status([obs("plan","p"),obs("atelier","a1",3,part=[1,2]),obs("atelier","a2",5,part=[2,2])])[0]
        self.assertEqual("compliant",result["status"])
    def test_unmarked_duplicates_need_review(self):
        result=self.status([obs("plan","p"),obs("atelier","a1",4),obs("atelier","a2",4)])[0]
        self.assertEqual("needs_review",result["status"])
    def test_missing_part_not_silently_summed(self):
        result=self.status([obs("plan","p"),obs("atelier","a1",4,part=[1,3]),obs("atelier","a2",4,part=[2,3])])[0]
        self.assertEqual("needs_review",result["status"])
    def test_single_incomplete_part_is_not_a_confirmed_shortage(self):
        result=self.status([obs("plan","p"),obs("atelier","a1",4,part=[1,2])])[0]
        self.assertEqual("needs_review",result["status"])
        self.assertFalse(result["confirmed"])
    def test_unmatched_without_scope_is_candidate(self):
        result=self.status([obs("plan","p")])[0]
        self.assertEqual("missing_from_shop",result["status"])
        self.assertFalse(result["confirmed"])
    def test_complete_synthetic_scope_supports_missing_and_added(self):
        result=self.status([obs("plan","p",element="C-1"),obs("atelier","a",element="C-2")],
            shop_scope_complete=True,plan_scope_complete=True)
        self.assertEqual({"missing_from_shop","added_in_shop"},{r["status"] for r in result})
        self.assertTrue(all(r["confirmed"] for r in result))
    def test_length_tolerance_is_explicit(self):
        items=[obs("plan","p"),obs("atelier","a",length=3601)]
        self.assertEqual("non_compliant",self.status(items)[0]["status"])
        self.assertEqual("compliant",self.status(items,length_tolerance_mm=1)[0]["status"])
    def test_empty_input_has_no_conformities(self):
        self.assertEqual([],self.status([]))

class EndToEndTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=TEST_ROOT)
        self.root=Path(self.temp.name)
    def tearDown(self):
        self.temp.cleanup()
    def test_five_families_and_reports(self):
        generate_project(self.root/"input")
        result=run_project(self.root/"input",self.root/"output",assert_complete_scope=True,synthetic=True)
        self.assertEqual(22,result["extractions"]); self.assertEqual(5,len(result["records_by_family"]))
        self.assertEqual(5,result["decisions"]["compliant"]); self.assertEqual(5,result["decisions"]["non_compliant"])
        self.assertEqual(1,result["decisions"]["missing_from_shop"]); self.assertEqual(1,result["decisions"]["added_in_shop"])
        self.assertEqual(0,result["decisions"]["review_required"])
        out=self.root/"output"
        for pdf in (out/"reports").glob("*.pdf"):
            with fitz.open(pdf) as document:
                self.assertGreater(document.page_count,0)
                self.assertIn("SYNTHETIC",document[0].get_text())
        index=json.loads((out/"reports/index.json").read_text(encoding="utf-8"))
        self.assertEqual(6,len(index["reports"]))
    def test_crop_rotation_coordinates_stay_reversible(self):
        p=self.root/"rotations.pdf"
        c=Canvas(str(p),pagesize=(612,792)); c.drawString(100,642,"C-12 8-25M"); c.save()
        for angle in (0,90,180,270):
            with fitz.open(p) as doc:
                page=doc[0]; page.set_cropbox(fitz.Rect(20,30,592,762)); page.set_rotation(angle)
                line=native_lines(page)[0]
                self.assertTrue(page.rect.contains(fitz.Rect(line.bbox)))
                raw=fitz.Rect(line.bbox)*page.derotation_matrix
                displayed=raw*page.rotation_matrix
                self.assertLess(max(abs(a-b) for a,b in zip(displayed,line.bbox)),0.001)
    def test_unknown_role_and_broken_pdf_are_visible(self):
        source=self.root/"input"; source.mkdir()
        c=Canvas(str(source/"unfamiliar.pdf")); c.drawString(40,500,"Unknown local file"); c.save()
        (source/"broken.pdf").write_bytes(b"not a PDF")
        result=run_project(source,self.root/"output",synthetic=True)
        self.assertEqual(0,result["decisions"]["compliant"])
        self.assertEqual(1,result["page_status_counts"]["unclassified_document"])
        self.assertEqual(1,result["page_status_counts"]["file_error"])
    def test_unfamiliar_filename_has_explicit_role_override(self):
        generate_project(self.root/"generated")
        source=self.root/"input"; source.mkdir()
        (source/"unfamiliar.pdf").write_bytes((self.root/"generated/plans/plan_synthetic.pdf").read_bytes())
        result=run_project(source,self.root/"output",role_map={"unfamiliar.pdf":"plan"},synthetic=True)
        self.assertEqual(11,result["extractions"])
        self.assertNotIn("unclassified_document",result["page_status_counts"])
    def test_page_budget_is_explicit(self):
        generate_project(self.root/"input")
        result=run_project(self.root/"input",self.root/"output",max_pages=1,assert_complete_scope=True,synthetic=True)
        self.assertEqual(9,result["pages_omitted_by_limit"])
        self.assertFalse(result["complete_scope_accepted"])
    def test_output_inside_repo_is_refused(self):
        source=self.root/"input"; source.mkdir()
        with self.assertRaises(ValueError): run_project(source,REPO/"outputs"/"forbidden")
    def test_cli_emits_only_aggregate(self):
        generate_project(self.root/"input")
        p=subprocess.run([sys.executable,str(REPO/"l2c_pipeline.py"),"--input",str(self.root/"input"),
            "--output",str(self.root/"output"),"--synthetic"],capture_output=True,text=True,timeout=60)
        self.assertEqual(0,p.returncode)
        result=json.loads(p.stdout)
        self.assertEqual(22,result["extractions"])
        self.assertNotIn("fichier",p.stdout); self.assertNotIn("plan_synthetic.pdf",p.stdout)
        self.assertNotIn("8-25M",p.stdout)
    def test_existing_run_is_not_overwritten(self):
        generate_project(self.root/"input")
        output=self.root/"output"; output.mkdir(); (output/"existing.txt").write_text("keep",encoding="utf-8")
        with self.assertRaises(ValueError): run_project(self.root/"input",output)
    def test_low_memory_defers_ocr_without_initializing_model(self):
        engine=LocalOCR()
        with patch("psutil.virtual_memory") as memory:
            memory.return_value.available=1024**3
            with self.assertRaises(OCRMemoryDeferred): engine.recognize(None)
        self.assertIsNone(engine._engine)
    def test_deferred_ocr_keeps_partial_scope_visible(self):
        source=self.root/"input"/"plans"; source.mkdir(parents=True)
        c=Canvas(str(source/"blank.pdf")); c.showPage(); c.save()
        with patch.object(LocalOCR,"recognize",side_effect=OCRMemoryDeferred("synthetic memory test")):
            result=run_project(source.parent,self.root/"output",ocr_mode="auto",assert_complete_scope=True,synthetic=True)
        self.assertEqual(1,result["page_status_counts"]["ocr_deferred_low_memory"])
        self.assertFalse(result["complete_scope_accepted"])
    def test_explicit_schedule_layout_runs_through_shared_pipeline(self):
        for role,quantity in [('plans',8),('shop',6)]:
            folder=self.root/'input'/role; folder.mkdir(parents=True)
            c=Canvas(str(folder/'schedule.pdf'),pagesize=(612,792))
            for text,x,y in [('SHEET S-500',30,30),('C-1',200,100),('C-2',400,100),
                              ('LEVEL 1',30,180),('LEVEL 2',30,240),
                              (f'{quantity}-25M',200,180),(f'{quantity}-25M',400,180),
                              (f'{quantity}-25M',200,240),(f'{quantity}-25M',400,240)]:
                c.drawString(x,792-y,text)
            c.save()
        result=run_project(self.root/'input',self.root/'output',synthetic=True)
        self.assertEqual(8,result['extractions']); self.assertEqual(4,result['matches'])
        self.assertEqual(4,result['decisions']['non_compliant'])

if __name__=="__main__":
    unittest.main(verbosity=2)
