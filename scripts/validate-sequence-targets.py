"""Original FASTA/disordered-target preparation only; no trained model computation."""
import argparse,hashlib,json,os,pathlib,sys
sys.dont_write_bytecode=True
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scientific'));sys.path.insert(0,str(ROOT/'vendor/bindcraft2'))
from worker import Service
from campaign_profile import resource_estimate,ensemble_models
from bindcraft_cpu import execution_config
from bindcraft.settings import load_settings,build_design_settings
from bindcraft.protein_preparation import prepare_targets
from bindcraft.protein import ResidueFlags
p=argparse.ArgumentParser();p.add_argument('--directory',required=True);p.add_argument('--report',required=True);a=p.parse_args();root=pathlib.Path(a.directory).resolve()
if root.exists():raise SystemExit('Choose a new isolated sequence-input QA root.')
s=Service(root);python=os.path.abspath(sys.executable);s.setting_set({'key':'bindcraftPython','value':python});project=s.project_create({'name':'Authentic FASTA preparation QA'});source=ROOT/'vendor/bindcraft2/settings/target/structures/hPDL1.pdb';sha=hashlib.sha256(source.read_bytes()).hexdigest()
import intelligence as mi
sequence=mi.parse_structure(source.read_text(),'pdb')['chains'][0]['sequence'];record=s.sequence_save({'projectId':project['id'],'name':'Official hPDL1 sequence only · technical input QA, no disorder claim','sequence':sequence,'origin':{'referenceCoordinateSha256':sha,'scope':'Sequence extracted for testing original FASTA input, source coordinates deliberately not provided to campaign'}});cases=[]
try:
 for mode,length in [('binder',60),('peptide',15)]:
  payload={'projectId':project['id'],'structureId':record['id'],'name':'Original FASTA '+mode+' preparation','modality':mode,'targetChains':['A'],'binderLengths':[length],'hotspots':[],'coldspots':[],'candidates':1,'attempts':1,'seed':42};job=s.dispatch('bindcraft_prepare',payload);prep=job['data']['preparation'];folder=root/'jobs'/job['id'];config,heldout=execution_config(prep['config'],folder);settings=load_settings(config);design=build_design_settings(settings);estimate=resource_estimate(python,config,ROOT/'vendor/bindcraft2');assert estimate['paddedResidues']<=192;assert len(design.prepared_states)==1
  assert settings['weights_target_plddt']==1.0 and settings['weights_target_helicity']==-0.3 and settings['weights_interface_pae']==0.3
  assert settings['losses']['interface_contacts']['params']['cutoff']==10.0;assert settings['filters']['Target_pLDDT']['threshold']==0.6
  crops=[]
  for seed in (42,2718):
   for validation in (False,True):
    target=prepare_targets(design,seed,validation_crop=validation)['target'];numbers=target.residue_index.tolist()
    # Use the upstream amino-acid alphabet, not a guessed numeric ordering.
    from bindcraft.protein import AMINO_ACIDS
    written=''.join(AMINO_ACIDS[int(i)] for i in target.sequence.argmax(-1).tolist())
    assert written==sequence[numbers[0]-1:numbers[-1]];assert not bool(target.atom_mask.any());assert all(int(flag)&int(ResidueFlags.SEQUENCE) for flag in target.flags.tolist());crops.append({'seed':seed,'validationFlanks':validation,'start':numbers[0],'end':numbers[-1],'sequence':written,'observedAtomMaskCount':int(target.atom_mask.sum())})
  assert prep['residueMap']==[];assert (folder/'input.fasta').read_bytes()==('>A\n'+sequence+'\n').encode();assert not (folder/'input.pdb').exists();cases.append({'modality':mode,'jobId':job['id'],'state':'prepared_not_executed','resourceEstimate':estimate,'actualUpstreamCrops':crops,'originalDisorderedTargetSettingsRetained':True,'originalEnsembleSelection':ensemble_models(python,{**prep['config'],'targets':config['targets']},ROOT/'vendor/bindcraft2'),'diagnosticHeldoutModel':heldout})
  try:s.dispatch('bindcraft_prepare',{**payload,'properties':['forced_targeting']})
  except ValueError as error:assert 'forced targeting' in str(error)
  else:raise AssertionError('Source-incompatible forced targeting must fail before saving a prepared campaign.')
 assert hashlib.sha256(source.read_bytes()).hexdigest()==sha
 report={'state':'passed','scope':'Immutable native FASTA inputs execute original disordered-target feature/input preflight, deterministic source-indexed crops, five-residue validation flanks and unresolved atom masks without inventing input geometry. Binder and peptide preparation only; no AF2 forward/gradient, full trajectory or biological disorder/binding claim.','root':str(root),'officialCoordinateSourceUnchanged':True,'officialCoordinateSourceSha256':sha,'sequenceSha256':record['data']['sha256'],'cases':cases};pathlib.Path(a.report).write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'state':'passed','cases':len(cases)}))
finally:s.db.close()
