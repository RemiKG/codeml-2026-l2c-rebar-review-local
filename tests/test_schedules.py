"""Only authored fictional table layouts, never sponsor snippets."""
import unittest
from l2c.model import TextLine
from l2c.schedules import schedule_observations
from l2c.matching import reconcile

def line(text,x,y,w=70): return TextLine(text,(x,y,x+w,y+10))
def parse(lines,source='plan'):
    return schedule_observations(lines,source=source,fichier='synthetic.pdf',page=1,width=612,height=792)[0]

class ScheduleTests(unittest.TestCase):
    def test_element_columns_and_explicit_level_rows(self):
        lines=[line('SHEET S-500',30,20),line('C-1',180,100),line('C-2',380,100),
               line('LEVEL 1',30,180),line('LEVEL 2',30,240),
               line('8-25M',180,180),line('6-20M',380,180),line('10-25M',180,240),line('8-20M',380,240)]
        records=parse(lines)
        self.assertEqual(4,len(records))
        self.assertEqual({('C-1','1'),('C-1','2'),('C-2','1'),('C-2','2')},
                         {(r.record['element'],r.context['level']) for r in records})
    def test_level_columns_and_element_rows(self):
        lines=[line('SHEET S-500',30,20),line('LEVEL 1',180,100),line('LEVEL 2',380,100),
               line('C-1',30,180),line('C-2',30,240),line('8-25M',180,180),line('6-25M',380,240)]
        self.assertEqual(2,len(parse(lines)))
    def test_bare_levels_require_actual_column_header(self):
        lines=[line('SHEET S-500',30,20),line('C-1',180,100),line('C-2',380,100),
               line('1',30,180),line('2',30,240),line('8-25M',180,180)]
        self.assertEqual([],parse(lines))
        self.assertEqual(1,len(parse(lines+[line('NIVEAU',30,100)])))
    def test_single_axis_or_distant_note_does_not_create_table(self):
        lines=[line('SHEET S-500',30,20),line('C-1',180,100),line('LEVEL 1',30,180),line('8-25M',180,180)]
        self.assertFalse(parse(lines))
    def test_supported_synthetic_table_comparison(self):
        lines=[line('SHEET S-500',30,20),line('C-1',180,100),line('C-2',380,100),
               line('LEVEL 1',30,180),line('LEVEL 2',30,240),line('8-25M',180,180)]
        plan=parse(lines); shop=parse(lines,'atelier'); shop[0].record['armature'][0]['quantite']=6
        matches,decisions=reconcile(plan+shop)
        self.assertEqual(1,len(matches)); self.assertEqual('non_compliant',decisions[0]['status'])
        self.assertEqual(-2,decisions[0]['differences'][0]['delta'])
    def test_record_coordinate_is_bar_cell_not_middle_of_headers(self):
        lines=[line('SHEET S-500',30,20),line('C-1',180,100),line('C-2',380,100),
               line('LEVEL 1',30,180),line('LEVEL 2',30,240),line('8-25M',180,180)]
        r=parse(lines)[0].record
        self.assertEqual((215,185),(r['x'],r['y']))
    def test_wrapped_literal_ids_and_french_plural_level_header(self):
        lines=[line('SHEET S-500',30,20),line('(C-1)',180,100),line('COL. C-2',380,100),
               line('NIVEAUX',30,100),line('SS-1',30,180),line('RDC',30,240),line('8-25M',180,180)]
        records=parse(lines)
        self.assertEqual(1,len(records)); self.assertEqual('C-1',records[0].record['element'])
        self.assertEqual('SS1',records[0].context['level'])
    def test_prose_mention_is_not_a_schedule_axis(self):
        lines=[line('SHEET S-500',30,20),line('SEE C-1 DETAIL',180,100),line('C-2',380,100),
               line('LEVEL 1',30,180),line('LEVEL 2',30,240),line('8-25M',180,180)]
        self.assertFalse(parse(lines))

if __name__=='__main__': unittest.main()
