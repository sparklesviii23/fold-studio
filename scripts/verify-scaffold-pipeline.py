"""Inspect saved technical paired-scaffold outputs; never rerun a model or import.
Checks actual two-domain chain roles, sequence correspondence, and framework
retention through ProteinMPNN using the exact written redesign-site stamp.
"""
import argparse,hashlib,json,pathlib,re,sys
sys.dont_write_bytecode=True
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scientific'))
import intelligence as mi
from bindcraft_provenance import chain_roles
p=argparse.ArgumentParser();p.add_argument('--directory',required=True);p.add_argument('--report',required=True);a=p.parse_args();folder=pathlib.Path(a.directory).resolve();result=json.loads((folder/'result.json').read_text())
if result['state']!='technical_pipeline_completed' or result['modality']!='scFv' or result.get('researchAcceptance') is not False or result.get('importedRecords')!=0:raise ValueError('Expected a completed quarantined paired-scaffold technical pipeline.')
config=result['settings'];target=pathlib.Path(config['targets'][0]['target_path']);target_st=mi.parse_structure(target.read_text(),'pdb');target_sequence=''.join(c['sequence'] for c in target_st['chains'])
scaffold=pathlib.Path(config['binder_scaffold']);prep=result['preparedInputs'][0]
if hashlib.sha256(target.read_bytes()).hexdigest()!=result['sourceSha256']:raise ValueError('Prepared target changed.')
# Scaffold pin is stored in the preparation-only library, not invented from output.
provenance=json.loads(scaffold.with_name('provenance.json').read_text())
if hashlib.sha256(scaffold.read_bytes()).hexdigest()!=provenance['scaffold']['sha256']:raise ValueError('Original scaffold snapshot changed.')
trajectory=next(rows[0] for name,rows in result['tables'].items() if name.endswith('1_Trajectories/!_Trajectories.csv'))
original_sequences=trajectory['Binder_Sequence'].split('/')
outputs=[]
for name,expected_sha in result['technicalStructures'].items():
 file=folder/name;raw=file.read_bytes()
 if hashlib.sha256(raw).hexdigest()!=expected_sha:raise ValueError('Technical output checksum changed.')
 st=mi.parse_structure(raw.decode(),'mmcif');roles=chain_roles(raw,st);binders=[c for c in st['chains'] if roles[c['id']]['role']=='candidate'];targets=[c for c in st['chains'] if roles[c['id']]['role']=='target']
 if len(binders)!=2 or len(targets)!=1 or targets[0]['sequence']!=target_sequence:raise ValueError('Paired domains or target sequence changed.')
 tokens=list(mi.cif_tokens(raw.decode()));stamp=tokens[tokens.index('_bindcraft.redesigned_residues')+1];editable={c['id']:set() for c in binders}
 for part in stamp.split(','):
  match=re.fullmatch(r'([A-Za-z])(\d+)(?:-(\d+))?',part)
  if not match or match[1] not in editable:raise ValueError('Invalid explicit redesign-site stamp.')
  editable[match[1]].update(range(int(match[2]),int(match[3] or match[2])+1))
 checks=[]
 for chain,sequence in zip(binders,original_sequences,strict=True):
  residues=[r for r in st['residues'] if r['chain']==chain['id']]
  if len(residues)!=len(sequence):raise ValueError('Domain length changed during redesign.')
  fixed=[i for i,r in enumerate(residues) if r['num'] not in editable[chain['id']]]
  if any(chain['sequence'][i]!=sequence[i] for i in fixed):raise ValueError('ProteinMPNN changed a fixed framework position.')
  checks.append({'chain':chain['id'],'residues':len(sequence),'fixedFrameworkResidues':len(fixed),'fixedSequenceUnchanged':True})
 if sum(c['fixedFrameworkResidues'] for c in checks)!=199:raise ValueError('Unexpected original framework coverage.')
 outputs.append({'file':str(file),'sha256':expected_sha,'chainRoles':roles,'domains':checks,'targetSequenceUnchanged':True})
report={'state':'passed','scope':'Saved quarantined scFv CPU pipeline. Two explicit variable-domain chains and original target retained; all 199 fixed positions unchanged through real ProteinMPNN redesign. No model rerun or research-record import.','originalScaffoldSha256':provenance['scaffold']['sha256'],'outputs':outputs,'limitations':['Permissive diagnostic filters; no original-filter antibody acceptance or binding claim.','Upstream raw ranking retains -inf where interface evidence is absent; no finite score is synthesized.','The unused binder-length metadata field is not a domain-length measurement. Actual chain lengths are reported above.','A VH–VL linker is not designed.']}
pathlib.Path(a.report).write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
