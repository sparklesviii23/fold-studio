import ast,base64,gzip,hashlib,io,json,sys,tempfile,unittest,zlib
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scientific'))
import borzoi_panel as P
import numpy as np

class ReferenceTests(unittest.TestCase):
 def test_outside_chromosome_is_retained_without_fetch_or_padding(self):
  panel={'sha256':'panel','loci':[{'symbol':'valid','chromosome':'chr1','inputStart':0},{'symbol':'outside','chromosome':'chr1','inputStart':200000}]}
  def fetch(url,**kw):return io.BytesIO(json.dumps({'chromosomes':{'chr1':600000}} if 'list/chromosomes' in url else {'dna':'A'*524288}).encode())
  with tempfile.TemporaryDirectory() as folder,patch.object(P.urllib.request,'urlopen',side_effect=fetch) as request:
   result=P.prepare_sequences(panel,folder)
   self.assertEqual(request.call_count,2);self.assertEqual(result['loci'][1]['status'],'unsupported_input_window')
   self.assertEqual(result['loci'][0]['sequenceSha256'],hashlib.sha256(b'A'*524288).hexdigest())
   self.assertEqual(result['sha256'],P._hash({k:v for k,v in result.items() if k!='sha256'}))
 def test_unsupported_locus_is_a_counted_failure_not_a_panel_abort(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);run='a'*32;out=root/'gpu_tasks'/run/'outputs';out.mkdir(parents=True);reference=root/'reference';reference.mkdir()
   panel={'loci':[{'symbol':'G','cohort':'heldout','expressionStratum':'low','lengthStratum':'short'}],'tracks':[{'index':1}],'seed':29,'testLoci':1,'illustrativeLoci':0};panel['sha256']=P._hash(panel)
   receipt={'panelSha256':panel['sha256'],'reproductionPassed':True,'loci':[{'status':'unsupported_input_window','reason':'bounds'}],'checkpoints':[],'seconds':0,'replicateSeconds':{},'sourceRevision':'fixture','baskervilleRevision':'fixture'}
   (out/'panel.json').write_text(json.dumps(panel));(out/'panel-inference.json').write_text(json.dumps(receipt))
   np.savez(out/'predictions-f0.npz');np.savez(out/'predictions-f1.npz');np.savez(reference/'observed.npz',locus_0_track_1=np.ones(6144))
   task={'id':run,'recipe':'bio_borzoi_panel','state':'done','outputs':[{'path':p.name,'sha256':P.file_hash(p)} for p in out.iterdir()]};(out.parent/'task.json').write_text(json.dumps(task))
   with patch.object(P,'prepare_reference',return_value={}):report=P.evaluate(root,run,reference)
   self.assertEqual(report['summary']['1']['f0']['attempted'],1);self.assertEqual(report['summary']['1']['f0']['scored'],0);self.assertEqual(report['perLocus'][0]['reason'],'bounds')
 def decoder(self):
  tree=ast.parse((Path(P.__file__).with_name('borzoi_panel_runner.py')).read_text());fn=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='decode_panel_input');scope={'base64':base64,'zlib':zlib}
  exec(compile(ast.Module(body=[fn],type_ignores=[]),'decoder','exec'),scope);return scope['decode_panel_input']
 def test_two_manifests_roundtrip_and_oversize_is_refused(self):
  decoder=self.decoder();encode=lambda b:base64.b64encode(gzip.compress(b)).decode()
  inputs={'files':{'panel.json.gz.b64':encode(b'panel'),'preflight.json.gz.b64':encode(b'preflight')}}
  self.assertEqual(decoder(inputs),'panel');self.assertEqual(decoder(inputs,'preflight.json.gz.b64'),'preflight')
  inputs['files']['preflight.json.gz.b64']=encode(b'x'*200001)
  with self.assertRaises(ValueError):decoder(inputs,'preflight.json.gz.b64')
 def test_truncated_or_concatenated_transport_is_refused(self):
  for raw in [b'bad',gzip.compress(b'{}')[:-3],gzip.compress(b'{}')+gzip.compress(b'{}')]:
   with self.assertRaises((ValueError,zlib.error)):self.decoder()({'files':{'panel.json.gz.b64':base64.b64encode(raw).decode()}})

if __name__=='__main__':unittest.main()
