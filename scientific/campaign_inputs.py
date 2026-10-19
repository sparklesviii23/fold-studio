"""Immutable multi-target inputs; source identities are never inferred from names."""
import math,pathlib
import fold_engine as fe

def extend(engine,request,checked):
 extras=request.get('additionalTargets',[])
 if not isinstance(extras,list) or len(extras)>3:raise ValueError('Choose at most three additional saved target states.')
 primary=checked['config']['targets'][0]
 snapshots=[{'name':primary['name'],'file':primary['target_path'],'source':checked['source'],'residueMap':checked['residueMap'],'objective':'target','weight':1.0}]
 identities={(checked['source']['sha256'],','.join(sorted(primary['chains'].split(','))))}
 targets=[]
 for index,value in enumerate(extras,2):
  allowed={'structureId','targetChains','hotspots','coldspots','objective','weight'}
  if not isinstance(value,dict) or set(value)-allowed:raise ValueError('Unsupported additional-target fields.')
  if not value.get('structureId') or not value.get('targetChains'):raise ValueError('Each additional state needs a saved structure and explicit chains.')
  objective=value.get('objective','target');weight=value.get('weight',1.0)
  if objective not in ('target','detarget'):raise ValueError('Choose a positive target or a negative target objective.')
  if type(weight) not in (int,float) or not math.isfinite(weight) or not .01<=weight<=10:raise ValueError('Target weight magnitude must be finite and from 0.01 to 10.')
  # Reuse precisely the same coordinate/chain/backbone/hotspot checks as the
  # primary target. Recursive validation has no additional states.
  sub={k:v for k,v in request.items() if k not in ('additionalTargets','structureId','targetChains','hotspots','coldspots')}
  sub.update({k:v for k,v in value.items() if k in ('structureId','targetChains','hotspots','coldspots')})
  secondary=engine.bindcraft_validate(sub)
  target=dict(secondary['config']['targets'][0]);identity=(secondary['source']['sha256'],','.join(sorted(value['targetChains'])))
  if identity in identities:raise ValueError('Duplicate target coordinates/chains cannot be weighted twice or given contradictory objectives.')
  identities.add(identity);name='target'+str(index);file=name+pathlib.Path(target['target_path']).suffix
  signed_weight=-weight if objective=='detarget' else weight
  target.update(name=name,target_path=file,objective=objective,weight=signed_weight);targets.append(target)
  snapshots.append({'name':name,'file':file,'source':secondary['source'],'residueMap':secondary['residueMap'],'objective':objective,'weight':signed_weight})
 checked['targetSources']=snapshots
 if targets:
  checked['config']['targets'].extend(targets);checked['settingsSha256']=fe.checksum(fe.canonical(checked['config']).encode())
  checked['warnings'].append('Multiple target states retain original upstream selection, weighting and rejection behavior. Preparation does not establish cross-reactivity or specificity.')
 return checked

def snapshots(preparation):
 # Previously prepared single-target jobs stay reproducible and executable.
 return preparation.get('targetSources') or [{'name':preparation['config']['targets'][0]['name'],'file':preparation['config']['targets'][0]['target_path'],'source':preparation['source'],'residueMap':preparation['residueMap'],'objective':'target','weight':1.0}]

def verify(folder,preparation,label='Prepared source changed.',scaffold_label='Prepared scaffold changed.'):
 from sequence_targets import verify_preparation
 verify_preparation(preparation)
 inputs=snapshots(preparation);targets=preparation['config']['targets']
 if len(inputs)!=len(targets):raise ValueError('Prepared target input manifest is incomplete.')
 seen=set()
 for item,target in zip(inputs,targets):
  name=item['file'];path=pathlib.Path(name)
  if path.name!=name or path.is_absolute() or name in seen or name!=target['target_path'] or item['name']!=target['name']:raise ValueError('Prepared target path or identity is inconsistent.')
  weight=target.get('weight',1.0);objective='detarget' if target.get('objective')=='detarget' or weight<0 else 'target';weight=-abs(weight) if objective=='detarget' else weight
  if item['objective']!=objective or item['weight']!=weight:raise ValueError('Prepared target objective or weight is inconsistent.')
  seen.add(name);path=folder/name
  if path.is_symlink() or not path.is_file() or fe.checksum(path.read_bytes())!=item['source']['sha256']:raise ValueError(label)
 if preparation.get('scaffold'):
  scaffold=preparation['scaffold'];name=scaffold['file'];path=pathlib.Path(name)
  if path.name!=name or name!=preparation['config'].get('binder_scaffold') or (folder/name).is_symlink() or not (folder/name).is_file() or fe.checksum((folder/name).read_bytes())!=scaffold['sha256']:raise ValueError(scaffold_label)
 return inputs

def ranked_target(preparation,filename,design):
 """Pinned writer convention for observed-structure states (no FASTA crops)."""
 states=snapshots(preparation);stem=pathlib.Path(filename).stem
 matches=[state for state in states if stem==design+('' if len(states)==1 else '_'+state['name'])]
 if len(matches)!=1:raise ValueError('Native ranked output does not identify a unique prepared target state: '+filename)
 return matches[0]
