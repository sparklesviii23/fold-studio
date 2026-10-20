"""Verify native run receipts and transfer explicit upstream chain roles.
This verifies correspondence/reproducibility receipts, not experimental binding.
External campaigns never acquire a native provenance claim from their filenames.
"""
import json,pathlib
import fold_engine as fe

def native_receipt(service,job,root,metadata):
 folder=service.root/'jobs'/job['id'];data=job['data']
 if root.resolve()!=(folder/'output').resolve() or data.get('execution') not in ('cpu','metal'):return None
 settings_path=folder/'execution-settings.json';runtime_path=folder/'runtime-provenance.json'
 if not settings_path.is_file() or not runtime_path.is_file():raise ValueError('Native campaign receipts are missing; provenance cannot be verified.')
 raw=settings_path.read_bytes();settings=json.loads(raw);runtime=json.loads(runtime_path.read_text())
 if fe.checksum(fe.canonical(settings).encode())!=data.get('executionSettingsSha256') or fe.checksum(raw)!=runtime.get('executionSettingsSha256'):raise ValueError('Native execution settings receipt differs from the queued calculation.')
 if runtime.get('state')!='finished' or runtime.get('exitCode')!=0:raise ValueError('Native campaign has no successful finished execution receipt.')
 if runtime.get('execution')!=data['execution'] or runtime.get('precision')!=data.get('precision'):raise ValueError('Native backend/precision receipt differs from the queued calculation.')
 if pathlib.Path(metadata.get('settings_path','')).resolve()!=settings_path.resolve():raise ValueError('Campaign metadata points to a different execution input.')
 source=fe.verify_source()
 if runtime.get('upstreamSource',{}).get('revision')!=fe.PIN or runtime['upstreamSource'].get('manifestSha256')!=source['manifestSha256']:raise ValueError('Native source receipt differs from the pinned scientific implementation.')
 preparation=data['preparation']
 from campaign_inputs import verify
 inputs=verify(folder,preparation,'Native target snapshot changed.','Native scaffold snapshot changed.')
 checkpoints=metadata.get('checkpoints',{})
 for model,expected in data.get('checkpointSha256',{}).items():
  values=[sha for name,sha in checkpoints.items() if pathlib.Path(name).name=='params_'+model+'.npz']
  if values!=[expected]:raise ValueError('Native campaign checkpoint receipt mismatch: '+model)
 if not data.get('checkpointSha256'):raise ValueError('No native model checkpoint pins were recorded.')
 return {'state':'native_receipts_verified','execution':data['execution'],'precision':data['precision'],'upstreamSource':source,'reportedCampaignRevision':metadata.get('revision'),'executionSettingsSha256':fe.checksum(raw),'runtimeReceiptSha256':fe.checksum(runtime_path.read_bytes()),'checkpointSha256':data['checkpointSha256'],'preparedSource':preparation['source'],'scientificOptions':preparation.get('scientificOptions'),'preparedTargets':inputs,'runtime':runtime,'scope':'Native execution/settings/source/checkpoint receipt correspondence. Upstream computational acceptance does not establish biological binding or inhibition.'}

def chain_roles(raw,structure,unbound=False):
 values={};tokens=iter(fe.mi.cif_tokens(raw.decode()))
 for token in tokens:
  if token in ('_bindcraft.binder_chains','_bindcraft.target_chains'):
   if token in values:raise ValueError('Ambiguous BindCraft chain-role metadata.')
   values[token]=next(tokens,'')
 if not values:return None
 def declared(name):
  value=values.get(name,'')
  return set() if value in ('','.','?') else set(value.split(','))
 binder=declared('_bindcraft.binder_chains');target=declared('_bindcraft.target_chains');available={chain['id'] for chain in structure['chains']}
 if not binder or (not target and not unbound) or '' in binder|target or binder&target or not (binder|target)<=available or (unbound and (target or binder!=available)):raise ValueError('BindCraft chain roles do not match the written molecular model.')
 return {chain:{'role':'candidate' if chain in binder else 'target' if chain in target else 'additional','identity':'BindCraft2 designed binder' if chain in binder else 'Prepared target' if chain in target else 'Additional chain','assignmentSource':'Explicit _bindcraft CIF chain-role metadata'} for chain in available}

def fab_chain_transport(preparation,state,row,structure,roles):
 """Check native Fab transport against its reported sequences, not new filters.

 This cannot establish scientific acceptance or framework quality. It prevents
 missing/truncated chains from silently acquiring a native result identity.
 """
 if preparation.get('modality')!='Fab':return None
 chains=structure['chains']
 if not roles or set(roles)!={c['id'] for c in chains} or any(v['role']=='additional' for v in roles.values()):raise ValueError('Native Fab coordinates require explicit complete binder and target chain roles.')
 binders=[c for c in chains if roles[c['id']]['role']=='candidate']
 targets=[c for c in chains if roles[c['id']]['role']=='target']
 reported=row.get('Binder_Sequence')
 sequences=reported.split('/') if isinstance(reported,str) else []
 if len(binders)!=2 or len(sequences)!=2 or any(not s or set(s)-set('ACDEFGHIKLMNPQRSTVWY') for s in sequences):raise ValueError('Native Fab output requires both antibody chains and their original reported sequences.')
 if sorted(c['sequence'] for c in binders)!=sorted(sequences):raise ValueError('Native Fab coordinate chains differ from the original reported antibody sequences.')
 expected={}
 for residue in state.get('residueMap',[]):expected[residue['chain']]=expected.get(residue['chain'],'')+residue['aminoAcid']
 if not expected or sorted(c['sequence'] for c in targets)!=sorted(expected.values()):raise ValueError('Native Fab target chains differ from the complete prepared target sequences.')
 return {'state':'reported_sequences_matched','binderChains':[{'id':c['id'],'residues':len(c['sequence'])} for c in binders],'targetChains':[{'id':c['id'],'residues':len(c['sequence'])} for c in targets],'scope':'Coordinate transport matches both reported antibody chains and the complete prepared target. Original upstream filters remain the authority for scaffold constraints and computational acceptance.'}

def prediction_context(preparation,filename,row,raw,structure,fmt):
 """Separate original conformational binder-alone output from target complexes."""
 from campaign_inputs import ranked_target
 design=row['design'];config=preparation['config']
 if pathlib.Path(filename).stem==design+'_monomer':
  conformational=preparation.get('modality') in ('induced_fit','fold_switch') or any(config.get(key) for key in ('weights_induced_fit_interface','weights_induced_fit_global','weights_fold_switching','binder_shapes'))
  if not conformational or fmt!='mmcif':raise ValueError('Unexpected binder-alone ranked output for this campaign.')
  roles=chain_roles(raw,structure,unbound=True)
  if not roles:raise ValueError('Binder-alone output requires explicit original chain-role metadata.')
  written=row.get('Binder_Sequence','').split('/');actual=[chain['sequence'] for chain in structure['chains']]
  if not all(written) or sorted(written)!=sorted(actual):raise ValueError('Binder-alone sequence differs from the accepted campaign row.')
  return {'kind':'binder_alone','name':'binder_alone','roles':roles,'metadata':{'nativePredictionState':{'name':'binder_alone','kind':'unbound_binder_prediction'},'rawMetricsContext':'Accepted parent-complex campaign row; binder-alone pLDDT comes only from its own coordinate confidence field.'}}
 state=ranked_target(preparation,filename,design);roles=chain_roles(raw,structure) if fmt=='mmcif' else None
 from sequence_targets import predicted_crop
 crop=predicted_crop(preparation,structure,roles)
 metadata={'nativeTargetState':state,'nativePredictionState':{'name':state['name'],'kind':'target_complex'}}
 if crop:metadata['sequenceTargetPrediction']=crop
 assembly=fab_chain_transport(preparation,state,row,structure,roles)
 if assembly:metadata['fabChainTransport']=assembly
 return {'kind':'target_complex','name':state['name'],'roles':roles,'metadata':metadata}

def enrich_existing(service,job,ids,receipt,folder):
 """Upgrade metadata idempotently after receipt verification; coordinate assets stay immutable."""
 if not receipt:return
 service.db.execute('BEGIN IMMEDIATE')
 try:
  for id in ids:
   row=service.db.execute('SELECT * FROM records WHERE id=? AND project_id=?',(id,job['project_id'])).fetchone()
   if not row:raise ValueError('Imported native output record is missing.')
   info=json.loads(row['data']);raw=(service.root/'assets'/info['asset']).read_bytes()
   if fe.checksum(raw)!=info['sha256']:raise ValueError('Imported native coordinate asset changed.')
   context=prediction_context(job['data']['preparation'],info['metadata']['sourceFilename'],info['metadata']['rawMetrics'],raw,fe.mi.parse_structure(raw.decode(),info['format']),info['format'])
   if context['kind']=='binder_alone':info['metadata'].pop('nativeTargetState',None)
   info['metadata'].update(context['metadata'])
   info['source']='Local BindCraft2 '+receipt['execution']+' '+('unbound binder prediction' if context['kind']=='binder_alone' else 'ranked prediction');info['confidenceKind']='BindCraft2 AlphaFold2 pLDDT';info['metadata'].update(provenanceMatch=receipt['state'],nativeRun=receipt,upstreamRevision=fe.PIN,reportedCampaignRevision=receipt.get('reportedCampaignRevision'))
   roles=context['roles']
   if roles:
    info['metadata']['chainRoles']=roles
    # Preserve explicit user assignments made after the original result import.
    service.db.execute('INSERT OR IGNORE INTO intelligence_assignments VALUES(?,?,?,?)',(id,job['project_id'],json.dumps(roles),fe.mi.now()))
   service.db.execute('UPDATE records SET data=? WHERE id=?',(json.dumps(info),id))
  (folder/'native-verification.json').write_text(json.dumps(receipt,indent=2)+'\n');service.db.commit()
 except Exception:service.db.rollback();raise
