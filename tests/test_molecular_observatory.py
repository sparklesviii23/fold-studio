"""Coordinate-preserving polymer identity, authentic structures and ownership."""
import hashlib,json,pathlib,sys,tempfile,unittest
from unittest.mock import patch
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scientific'))
from molecular_observatory import inspect_bytes,cif_categories,public_json
from polymer_identity import chemical_identity
from worker import Service,ACTIONS

class PolymerContracts(unittest.TestCase):
 def test_cif_quoted_tags_are_values_not_headers(self):
  text="data_test\nloop_\n_x.id\n_x.value\n1 '_database_2.pdbx_DOI'\n2 'loop_'\n3 \"_value\"\n#\n_y.name 'data_test'\n"
  self.assertEqual(cif_categories(text,{'_x','_y'}),{'_x':[{'id':'1','value':'_database_2.pdbx_DOI'},{'id':'2','value':'loop_'},{'id':'3','value':'_value'}],'_y':[{'name':'data_test'}]})
 def test_experimental_dna_retains_both_strands_and_water(self):
  raw=(ROOT/'fixtures/nucleic-acids/1BNA.cif').read_bytes();d=inspect_bytes(raw,'mmcif');chains=[c for c in d['chains'] if c['observedSequence']]
  self.assertEqual(d['sourceAtomCount'],566);self.assertEqual([c['polymerType'] for c in chains],['DNA','DNA']);self.assertEqual([c['observedSequence'] for c in chains],['CGCGAATTCGCG']*2)
  self.assertEqual([len(c['residues']) for c in chains],[12,12]);self.assertIn('X-RAY DIFFRACTION',d['experimentalMethods']);self.assertEqual(hashlib.sha256(raw).hexdigest(),d['sourceSha256'])
  self.assertGreater(sum(c['sourceAtomCount'] for c in d['chains'] if not c['observedSequence']),0)
 def test_hybrid_complex_distinguishes_author_and_label_chains_from_protein(self):
  d=inspect_bytes((ROOT/'fixtures/nucleic-acids/1ZBI.cif').read_bytes(),'mmcif');self.assertEqual(d['sourceAtomCount'],2943)
  chains=[c for c in d['chains'] if c['observedSequence']];self.assertEqual([(c['authorChain'],c['labelChain'],c['polymerType'],len(c['observedSequence'])) for c in chains],[('C','A','RNA',12),('D','B','DNA',12),('A','C','Protein',135),('B','D','Protein',136)])
  self.assertEqual(chains[0]['observedSequence'],'GACACCUGAUUC');self.assertEqual(chains[1]['observedSequence'],'GAATCAGGTGTC')
 def test_authentic_trna_keeps_modified_identity_and_explicit_parent_map(self):
  d=inspect_bytes((ROOT/'fixtures/nucleic-acids/1EHZ.cif').read_bytes(),'mmcif');chain=next(c for c in d['chains'] if c['observedSequence']);self.assertEqual(d['sourceAtomCount'],1821)
  self.assertEqual(chain['polymerType'],'RNA');self.assertEqual(len(chain['observedSequence']),76);self.assertTrue(chain['mappingComplete'])
  modified=[r for r in chain['residues'] if r['modified']];self.assertEqual(len(modified),14);self.assertEqual(next(r for r in modified if r['component']=='PSU')['parentComponent'],'U');self.assertEqual(next(r for r in modified if r['component']=='YYG')['canonicalSymbol'],'G')
 def test_standard_unknown_hybrid_and_explicit_chemistry_precedence(self):
  self.assertEqual(chemical_identity('DA')['polymerType'],'DNA');self.assertEqual(chemical_identity('ALA')['polymerType'],'Protein')
  self.assertEqual(chemical_identity('PSU','RNA linking','U')['canonicalSymbol'],'U')
  unresolved=chemical_identity('XYZ',atom_names=["C1'","C3'","C4'"]);self.assertEqual(unresolved['polymerType'],'Nucleic acid (unresolved)');self.assertFalse(unresolved['identityResolved'])
  self.assertEqual(chemical_identity('A',entity_type='polydeoxyribonucleotide/polyribonucleotide hybrid')['polymerType'],'DNA/RNA hybrid')
  self.assertEqual(chemical_identity('C',entity_type='polypeptide(L)')['polymerType'],'Protein')
 def test_pdb_numbering_insertion_altloc_zero_occupancy_and_multiple_models(self):
  # Exact fixed-column fields; alternate conformers and zero occupancy are not dropped.
  def atom(serial,name,residue,number,ins,alt,x,occupancy):
   return f"ATOM  {serial:5d} {name:>4s}{alt:1s}{residue:>3s} A{number:4d}{ins:1s}   {x:8.3f}{2.:8.3f}{3.:8.3f}{occupancy:6.2f}{20.:6.2f}          {'C':>2s}"
  raw=('MODEL        1\n'+atom(1,"C1'",'DA',-2,'B','A',1.,.6)+'\n'+atom(2,"C1'",'DA',-2,'B','B',2.,0.)+'\nENDMDL\nMODEL        2\n'+atom(3,"C1'",'DA',-2,'B','',3.,1.)+'\nENDMDL\n').encode()
  d=inspect_bytes(raw,'pdb');self.assertEqual(d['models'],['1','2']);self.assertEqual(d['sourceAtomCount'],3);r=d['chains'][0]['residues'][0];self.assertEqual((r['authorNumber'],r['insertionCode'],r['alternateLocations']),(-2,'B',['A','B']));self.assertEqual(r['sourceAtomCount'],2)
 def test_reference_hashes_match_recorded_official_sources(self):
  for source in json.loads((ROOT/'fixtures/nucleic-acids/SOURCES.json').read_text()):self.assertEqual(hashlib.sha256((ROOT/'fixtures/nucleic-acids'/(source['pdbId']+'.cif')).read_bytes()).hexdigest(),source['sha256'])
 def test_rcsb_no_hits_http204_is_empty_result(self):
  with patch('molecular_observatory.urllib.request.urlopen') as request:
   response=request.return_value.__enter__.return_value;response.status=204;response.read.return_value=b'';self.assertEqual(public_json('https://search.rcsb.org/test'),{})
 def test_import_inspection_cache_ownership_and_source_integrity(self):
  with tempfile.TemporaryDirectory() as directory:
   s=Service(directory)
   try:
    p=s.project_create({'name':'DNA'});other=s.project_create({'name':'Other'});item=s.import_structure({'projectId':p['id'],'path':str(ROOT/'fixtures/nucleic-acids/1BNA.cif')});params={'projectId':p['id'],'structureId':item['id']};result=s.dispatch('molecular_inspect',params);self.assertEqual(result['sourceSha256'],item['data']['sha256']);self.assertEqual(result['origin'],'experimental method reported in source file');self.assertEqual(s.dispatch('molecular_inspect',params),result)
    self.assertEqual((s.root/'assets'/item['data']['asset']).read_bytes(),(ROOT/'fixtures/nucleic-acids/1BNA.cif').read_bytes())
    with self.assertRaisesRegex(ValueError,'this research project'):s.dispatch('molecular_inspect',{**params,'projectId':other['id']})
    (s.root/'assets'/item['data']['asset']).write_bytes(b'changed')
    with self.assertRaisesRegex(ValueError,'Source coordinates changed'):s.dispatch('molecular_inspect',params)
   finally:s.db.close()
 def test_public_discovery_rejects_non_ids_and_never_accepts_arbitrary_urls(self):
  with tempfile.TemporaryDirectory() as directory:
   s=Service(directory)
   try:
    p=s.project_create({'name':'Research'})
    for value in ('https://example.com/private','../../secret','1BN','1BNA\nBAD'):
     with self.assertRaises(ValueError):s.dispatch('molecular_rcsb',{'projectId':p['id'],'pdbId':value})
    self.assertTrue({'molecular_inspect','molecular_rcsb','molecular_rcsb_search'}<=ACTIONS)
   finally:s.db.close()
