"""Real full-gradient coordinates test transport; not an accepted Fab fixture."""
import copy
import csv
import io
import json
import pathlib
import unittest
import sys
import zipfile
from unittest.mock import patch

ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scientific'))
import fold_engine as fe
from bindcraft_provenance import prediction_context
from test_project_metal import ProjectMetalTests as Fixtures


class FullFabTransport(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.raw=(ROOT/'reports/amme-fab-memory-scheduler-gradient_target.cif').read_bytes()
  cls.structure=fe.mi.parse_structure(cls.raw.decode(),'mmcif')
  target_raw=(fe.UPSTREAM/'settings/target/structures/hPDL1.pdb').read_text()
  target=fe.mi.parse_structure(target_raw,'pdb')
  residues=[{'chain':r['chain'],'aminoAcid':r['one']} for r in target['residues'] if r['chain']=='A' and r['polymer']]
  cls.prep={'modality':'Fab','config':{'targets':[{'name':'target','target_path':'input.pdb'}]},'source':{'sha256':fe.checksum(target_raw.encode())},'residueMap':residues}
  cls.row={'design':'gradient_diagnostic_not_accepted','Binder_Sequence':'/'.join(c['sequence'] for c in cls.structure['chains'] if c['id'] in ('B','C'))}

 def context(self,structure=None,raw=None,row=None):
  return prediction_context(self.prep,self.row['design']+'.cif',row or self.row,raw or self.raw,structure or self.structure,'mmcif')

 def test_genuine_full_structure_preserves_two_antibody_chains_and_full_target(self):
  result=self.context();stamp=result['metadata']['fabChainTransport']
  self.assertEqual(stamp['binderChains'],[{'id':'B','residues':231},{'id':'C','residues':213}])
  self.assertEqual(stamp['targetChains'],[{'id':'A','residues':115}])
  self.assertEqual(stamp['state'],'reported_sequences_matched')
  self.assertNotIn('accepted',stamp)

 def test_missing_light_chain_cannot_silently_import(self):
  structure=copy.deepcopy(self.structure);structure['chains']=[c for c in structure['chains'] if c['id']!='C']
  raw=self.raw.replace(b'_bindcraft.binder_chains          B,C',b'_bindcraft.binder_chains          B')
  with self.assertRaisesRegex(ValueError,'both antibody chains'):self.context(structure=structure,raw=raw)

 def test_truncated_constant_body_is_detected_against_original_reported_sequence(self):
  structure=copy.deepcopy(self.structure);next(c for c in structure['chains'] if c['id']=='B')['sequence']=self.row['Binder_Sequence'].split('/')[0][:110]
  with self.assertRaisesRegex(ValueError,'original reported antibody sequences'):self.context(structure=structure)

 def test_truncated_target_is_detected_against_original_observed_input(self):
  structure=copy.deepcopy(self.structure);next(c for c in structure['chains'] if c['id']=='A')['sequence']=next(c for c in structure['chains'] if c['id']=='A')['sequence'][:-1]
  with self.assertRaisesRegex(ValueError,'complete prepared target'):self.context(structure=structure)

 def test_missing_or_merged_reported_chain_sequence_is_refused(self):
  for value in ('',self.row['Binder_Sequence'].replace('/',''),self.row['Binder_Sequence']+'/A'):
   with self.subTest(value=value[:30]),self.assertRaisesRegex(ValueError,'both antibody chains'):
    self.context(row={**self.row,'Binder_Sequence':value})

 def test_unassigned_extra_chain_is_not_given_native_fab_transport_status(self):
  structure=copy.deepcopy(self.structure);structure['chains'].append({'id':'Z','sequence':'ACD'})
  with self.assertRaisesRegex(ValueError,'complete binder and target chain roles'):self.context(structure=structure)

 def test_chain_presentation_order_does_not_change_assembly_identity(self):
  structure=copy.deepcopy(self.structure);structure['chains'].reverse()
  self.assertEqual(self.context(structure=structure)['metadata']['fabChainTransport']['state'],'reported_sequences_matched')


class FabImportTransportContracts(unittest.TestCase):
 """Synthetic completion receipt around genuine diagnostic coordinates only.

 These isolated-store tests do not demonstrate accepted Fab generation.
 """
 setUp=Fixtures.setUp
 tearDown=Fixtures.tearDown

 def output(self,truncated=False):
  source=fe.UPSTREAM/'settings/target/structures/hPDL1.pdb'
  record=self.s.import_structure({'projectId':self.project['id'],'path':str(source)})
  config={k:v for k,v in self.config.items() if k!='binderLengths'}
  config.update(structureId=record['id'],hotspots=[],modality='Fab',name='Transport contract only')
  job=self.s.dispatch('bindcraft_prepare',config)
  output=self.s.root/'jobs'/job['id']/'output';ranked=output/'3_Ranked';ranked.mkdir(parents=True)
  raw=(ROOT/'reports/amme-fab-memory-scheduler-gradient_target.cif').read_bytes()
  (ranked/'gradient_diagnostic_not_accepted.cif').write_bytes(raw)
  structure=fe.mi.parse_structure(raw.decode(),'mmcif')
  sequences=[c['sequence'] for c in structure['chains'] if c['id'] in ('B','C')]
  if truncated:sequences[0]=sequences[0][:110]
  table=io.StringIO();writer=csv.DictWriter(table,fieldnames=['design','Binder_Sequence']);writer.writeheader();writer.writerow({'design':'gradient_diagnostic_not_accepted','Binder_Sequence':'/'.join(sequences)})
  (ranked/'!_Ranked.csv').write_text(table.getvalue());(output/'campaign_metadata.json').write_text(json.dumps({'settings':{},'scope':'Synthetic transport receipt; not an accepted design.'}))
  return {'projectId':self.project['id'],'id':job['id'],'directory':str(output)},raw

 def receipt(self):
  return patch('bindcraft_provenance.native_receipt',return_value={'state':'native_receipts_verified','execution':'cpu','scope':'Synthetic completion receipt for transport contract; real gradient diagnostic is not an accepted Fab.'})

 def test_native_import_and_project_export_preserve_full_genuine_coordinates(self):
  payload,raw=self.output()
  with self.receipt():result=self.s.dispatch('bindcraft_import',payload)
  record=next(r for r in self.s.library({})['records'] if r['id']==result['records'][0]);info=record['data']
  self.assertEqual((self.s.root/'assets'/info['asset']).read_bytes(),raw)
  self.assertEqual(info['metadata']['fabChainTransport']['binderChains'],[{'id':'B','residues':231},{'id':'C','residues':213}])
  self.assertEqual(set(info['metadata']['chainRoles']),{'A','B','C'})
  export=self.base/'transport.zip';self.s.dispatch('export_project',{'id':self.project['id'],'path':str(export)})
  with zipfile.ZipFile(export) as archive:
   self.assertEqual(archive.read('assets/'+info['asset']),raw)

 def test_inconsistent_assembly_refuses_before_any_record_or_asset_write(self):
  payload,raw=self.output(truncated=True)
  before=self.s.library({})['records'];assets={p.name:p.read_bytes() for p in (self.s.root/'assets').iterdir() if p.is_file()}
  with self.receipt(),self.assertRaisesRegex(ValueError,'original reported antibody sequences'):
   self.s.dispatch('bindcraft_import',payload)
  self.assertEqual(self.s.library({})['records'],before)
  self.assertEqual({p.name:p.read_bytes() for p in (self.s.root/'assets').iterdir() if p.is_file()},assets)


del Fixtures
