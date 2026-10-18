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
 preparation=data['preparation'];original=preparation['config'];input_path=folder/original['targets'][0]['target_path']
 if fe.checksum(input_path.read_bytes())!=preparation['source']['sha256']:raise ValueError('Native target snapshot changed.')
 if preparation.get('scaffold'):
  scaffold=preparation['scaffold']
  if fe.checksum((folder/scaffold['file']).read_bytes())!=scaffold['sha256']:raise ValueError('Native scaffold snapshot changed.')
 checkpoints=metadata.get('checkpoints',{})
 for model,expected in data.get('checkpointSha256',{}).items():
  values=[sha for name,sha in checkpoints.items() if pathlib.Path(name).name=='params_'+model+'.npz']
  if values!=[expected]:raise ValueError('Native campaign checkpoint receipt mismatch: '+model)
 if not data.get('checkpointSha256'):raise ValueError('No native model checkpoint pins were recorded.')
 return {'state':'native_receipts_verified','execution':data['execution'],'precision':data['precision'],'upstreamSource':source,'reportedCampaignRevision':metadata.get('revision'),'executionSettingsSha256':fe.checksum(raw),'runtimeReceiptSha256':fe.checksum(runtime_path.read_bytes()),'checkpointSha256':data['checkpointSha256'],'preparedSource':preparation['source'],'runtime':runtime,'scope':'Native execution/settings/source/checkpoint receipt correspondence. Upstream computational acceptance does not establish biological binding or inhibition.'}

def chain_roles(raw,structure):
 values={};tokens=iter(fe.mi.cif_tokens(raw.decode()))
 for token in tokens:
  if token in ('_bindcraft.binder_chains','_bindcraft.target_chains'):
   if token in values:raise ValueError('Ambiguous BindCraft chain-role metadata.')
   values[token]=next(tokens,'')
 if not values:return None
 binder=set(values.get('_bindcraft.binder_chains','').split(','));target=set(values.get('_bindcraft.target_chains','').split(','));available={chain['id'] for chain in structure['chains']}
 if not binder or not target or '' in binder|target or binder&target or not (binder|target)<=available:raise ValueError('BindCraft chain roles do not match the written molecular model.')
 return {chain:{'role':'candidate' if chain in binder else 'target' if chain in target else 'additional','identity':'BindCraft2 designed binder' if chain in binder else 'Prepared target' if chain in target else 'Additional chain','assignmentSource':'Explicit _bindcraft CIF chain-role metadata'} for chain in available}

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
   info['source']='Local BindCraft2 '+receipt['execution']+' ranked prediction';info['confidenceKind']='BindCraft2 AlphaFold2 pLDDT';info['metadata'].update(provenanceMatch=receipt['state'],nativeRun=receipt,upstreamRevision=fe.PIN,reportedCampaignRevision=receipt.get('reportedCampaignRevision'))
   roles=chain_roles(raw,fe.mi.parse_structure(raw.decode(),info['format'])) if info['format']=='mmcif' else None
   if roles:
    info['metadata']['chainRoles']=roles
    # Preserve explicit user assignments made after the original result import.
    service.db.execute('INSERT OR IGNORE INTO intelligence_assignments VALUES(?,?,?,?)',(id,job['project_id'],json.dumps(roles),fe.mi.now()))
   service.db.execute('UPDATE records SET data=? WHERE id=?',(json.dumps(info),id))
  (folder/'native-verification.json').write_text(json.dumps(receipt,indent=2)+'\n');service.db.commit()
 except Exception:service.db.rollback();raise
