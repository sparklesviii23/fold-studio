"""Check existing quarantined calculations without rerunning trained models."""
import argparse,csv,hashlib,json,pathlib,sys
sys.dont_write_bytecode=True
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scientific'))
import intelligence as mi
from campaign_inputs import ranked_target,verify
from bindcraft_provenance import chain_roles

p=argparse.ArgumentParser();p.add_argument('--directory',required=True);p.add_argument('--report',required=True);a=p.parse_args()
folder=pathlib.Path(a.directory).resolve();result=json.loads((folder/'result.json').read_text())
if result['state']!='technical_pipeline_completed' or result['researchAcceptance'] or result['importedRecords']!=0:raise ValueError('Expected completed quarantined technical calculation.')
job_folder=pathlib.Path(result['settings']['targets'][0]['target_path']).parent
if not job_folder.is_relative_to(folder):raise ValueError('Input snapshots are outside the saved diagnostic case.')
prep=json.loads((job_folder/'provenance.json').read_text());inputs=verify(job_folder,prep)
ranked=folder/'QUARANTINED_OUTPUT/3_Ranked';rows=list(csv.DictReader((ranked/'!_Ranked.csv').open()))
checks=[];binders={};states={}
for file in sorted(ranked.glob('*.cif')):
 matched=[row for row in rows if file.stem==row['design'] or file.stem.startswith(row['design']+'_')]
 if len(matched)!=1:raise ValueError('Ambiguous ranked candidate identity.')
 row=matched[0];state=ranked_target(prep,file.name,row['design']);raw=file.read_bytes()
 if hashlib.sha256(raw).hexdigest()!=result['technicalStructures'][str(file.relative_to(folder))]:raise ValueError('Saved technical output checksum changed.')
 structure=mi.parse_structure(raw.decode(),'mmcif');roles=chain_roles(raw,structure)
 target_chains=[c for c in structure['chains'] if roles[c['id']]['role']=='target']
 candidate_chains=[c for c in structure['chains'] if roles[c['id']]['role']=='candidate']
 target=next(t for t in prep['config']['targets'] if t['name']==state['name'])
 # These explicit reference cases have one selected receptor chain per state.
 selected=target['chains'].split(',')
 if len(selected)!=1 or len(target_chains)!=1 or len(candidate_chains)!=1:raise ValueError('Reference validator requires one target and one designed chain per state.')
 source=mi.parse_structure((job_folder/state['file']).read_text(),state['source']['format'])
 expected=next(c['sequence'] for c in source['chains'] if c['id']==selected[0])
 if target_chains[0]['sequence']!=expected:raise ValueError('Written target sequence differs from its exact prepared state.')
 binders.setdefault(row['design'],set()).add(candidate_chains[0]['sequence']);states.setdefault(row['design'],set()).add(state['name'])
 checks.append({'file':file.name,'state':state['name'],'objective':state['objective'],'weight':state['weight'],'preparedSourceSha256':state['source']['sha256'],'outputSha256':hashlib.sha256(raw).hexdigest(),'targetSequence':expected,'binderSequence':candidate_chains[0]['sequence']})
for design in binders:
 if len(binders[design])!=1 or states[design]!={s['name'] for s in inputs}:raise ValueError('Candidate sequence is not shared across the complete target-state set.')
report={'state':'passed','scope':'Exact saved target-state/sequence correspondence and shared designed sequence across real quarantined upstream outputs. Permissive diagnostic filters; not biological specificity, design quality or default-filter acceptance.','case':str(folder),'modality':result.get('modality','peptide'),'backend':result['backend'],'researchAcceptance':False,'generatedRecordsImported':0,'seconds':result['seconds'],'checks':checks,'runtime':result['runtime'],'settings':result['settings']}
pathlib.Path(a.report).write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'state':'passed','states':len(checks),'modality':report['modality'],'seconds':report['seconds']},indent=2))
