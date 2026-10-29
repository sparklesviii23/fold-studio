import pathlib,sys,tempfile,subprocess,json,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scientific'))
from worker import Service
class ORFTests(unittest.TestCase):
 def test_real_biopython_codes_and_reverse_coordinates(self):
  runtime=pathlib.Path(__file__).resolve().parents[2]/'current/FOLD STUDIO Metal Dev.app/Contents/Resources/runtime-boltz/bin/python3.12'
  if not runtime.is_file():self.skipTest('Existing Biopython runtime unavailable')
  script=pathlib.Path(__file__).resolve().parents[1]/'scientific/genome_orfs.py'
  def scan(dna,table=11):return json.loads(subprocess.run([str(runtime),'-I','-B',str(script)],input=json.dumps({'dna':dna,'table':table,'minimum':1}),text=True,capture_output=True,check=True).stdout)
  forward=scan('ATGAAATAA');self.assertIn({'strand':'+','windowFrameOffsetZeroBased':0,'windowStart':1,'windowEnd':9,'startCodon':'ATG','terminalStopCodon':'TAA','residuesExcludingTerminalStop':2},forward['orfs'])
  reverse=scan('TTATTTCAT');self.assertTrue(any(r['strand']=='-' and r['windowStart']==1 and r['windowEnd']==9 for r in reverse['orfs']))
  self.assertTrue(any(r['startCodon']=='GTG' for r in scan('GTGAAATAA',11)['orfs']));self.assertFalse(any(r['startCodon']=='GTG' for r in scan('GTGAAATAA',1)['orfs']));self.assertEqual(scan('ATGAAA')['total'],0)
  self.assertEqual(len([r for r in scan('ATGATGTAA')['orfs'] if r['strand']=='+']),2)
 def test_circular_genomic_mapping_and_reference_provenance(self):
  runtime=pathlib.Path(__file__).resolve().parents[2]/'current/FOLD STUDIO Metal Dev.app/Contents/Resources/runtime-boltz/bin/python3.12'
  if not runtime.is_file():self.skipTest('Existing Biopython runtime unavailable')
  with tempfile.TemporaryDirectory() as tmp:
   root=pathlib.Path(tmp);s=Service(root/'library');s.setting_set({'key':'enginePython','value':str(runtime)});pid=s.project_create({'name':'Isolated ORF coordinate fixture'})['id'];fa=root/'ref.fa';fa.write_text('>chr\nAATAACATGA\n');ref=s.dispatch('genome_import',{'projectId':pid,'fastaPath':str(fa),'circularReplicons':['chr'],'metadata':{'organism':'Artificial','assembly':'Numerical fixture','source':'Synthetic QA'}})
   result=s.dispatch('genome_orfs',{'projectId':pid,'id':ref['id'],'replicon':'chr','start':7,'end':15,'translationTable':11,'minimumResidues':1});match=next(r for r in result['orfs'] if r['strand']=='+');self.assertEqual((match['genomicStart'],match['genomicEnd']),(7,15));self.assertEqual(result['referenceId'],ref['id']);self.assertEqual(result['total'],1);s.db.close()
