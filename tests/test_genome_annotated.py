import pathlib,sys,tempfile,subprocess,json,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scientific'))
from worker import Service
class AnnotatedImportTests(unittest.TestCase):
 def test_actual_biopython_genbank_and_embl_roundtrip_preserves_original(self):
  runtime=pathlib.Path(__file__).resolve().parents[2]/'current/FOLD STUDIO Metal Dev.app/Contents/Resources/runtime-boltz/bin/python3.12'
  if not runtime.is_file():self.skipTest('Existing Biopython runtime unavailable')
  with tempfile.TemporaryDirectory() as tmp:
   root=pathlib.Path(tmp)
   script="""from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord
from Bio.SeqFeature import SeqFeature,SimpleLocation,CompoundLocation
import pathlib,sys
r=SeqRecord(Seq('ATGACCCCAATAA'),id='ARTIFICIAL.1',name='ARTIFICIAL',description='Synthetic splice QA only')
r.annotations={'molecule_type':'DNA','topology':'circular','organism':'Synthetic numerical fixture'}
r.features=[SeqFeature(CompoundLocation([SimpleLocation(0,4,strand=1),SimpleLocation(8,13,strand=1)]),type='CDS',qualifiers={'gene':['fixture'],'codon_start':['1'],'transl_table':['11']})]
for fmt,ext in [('genbank','gb'),('embl','embl')]:SeqIO.write(r,pathlib.Path(sys.argv[1])/('reference.'+ext),fmt)
"""
   subprocess.run([str(runtime),'-I','-B','-c',script,str(root)],check=True,capture_output=True)
   s=Service(root/'research');s.setting_set({'key':'enginePython','value':str(runtime)});project=s.project_create({'name':'Isolated annotated format QA'})['id']
   for fmt,ext in [('genbank','gb'),('embl','embl')]:
    original=root/('reference.'+ext);row=s.dispatch('genome_import_annotated',{'projectId':project,'path':str(original),'format':fmt,'metadata':{'organism':'Synthetic fixture','assembly':'Artificial','source':'Biopython fixture, not a biological genome'}})
    self.assertEqual(len(row['sources']),3);self.assertEqual(row['circularReplicons'],['ARTIFICIAL.1'])
    source=next(item for item in row['sources'] if item['kind']==fmt);self.assertEqual((s.root/'genome-assets'/source['asset']).read_bytes(),original.read_bytes())
    features=s.dispatch('genome_features',{'projectId':project,'id':row['id'],'query':'fixture'})['features'];self.assertEqual(len(features),2)
    product=s.dispatch('genome_product',{'projectId':project,'id':row['id'],'featureIndex':features[0]['index'],'kind':'cds','translationTable':11,'completeCDS':True});self.assertEqual(product['dna'],'ATGAAATAA');self.assertEqual(product['translation']['protein'],'MK')
   s.db.close()
