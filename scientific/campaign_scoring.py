"""Original coordinate scoring; keep missing prediction/site evidence explicit."""
import pathlib
import fold_engine as fe
SITE_METRICS={'Hotspot_Contact_Fraction','Off_Epitope_Contact_Fraction','Epitope_Residues_Contacted','Coldspot_Contact_Fraction'}
def score(snapshot,accepted_rows):
 from bindcraft.score import score_design
 from bindcraft.filters import REGISTERED_FILTER_METRICS
 from bindcraft.campaign_output import design_model_scores
 from bindcraft_provenance import chain_roles
 snapshot=pathlib.Path(snapshot);paths=sorted((snapshot/'3_Ranked').glob('*.cif'));paths=[path for path in paths if not path.stem.endswith('_monomer')]
 if not paths or len(paths)>4:raise ValueError('Original coordinate scoring currently supports one to four saved accepted complex CIF files per review.')
 rows=[];details=[]
 for path in paths:
  matches=[row for row in accepted_rows if path.stem==row['design'] or path.stem.startswith(row['design']+'_')]
  if len(matches)!=1:raise ValueError('Scored coordinate file has no unique accepted-table identity.')
  raw=path.read_bytes();structure=fe.mi.parse_structure(raw.decode(),'mmcif')
  if len(structure['models'])!=1 or len(structure['residues'])>384:raise ValueError('Coordinate scoring is bounded to one model and 384 residues per complex.')
  roles=chain_roles(raw,structure)
  if not roles or any(value['role']=='additional' for value in roles.values()):raise ValueError('Scoring requires explicit original binder/target chain roles for every written chain.')
  binder=','.join(sorted(name for name,value in roles.items() if value['role']=='candidate'));target=','.join(sorted(name for name,value in roles.items() if value['role']=='target'))
  original=score_design(str(path),binder=binder,target=target);scores={key:value for key,value in original.items() if key not in SITE_METRICS};missing=sorted(set(REGISTERED_FILTER_METRICS)-set(scores));rows.append({'design':path.stem,**scores,'coordinate_sha256':fe.checksum(raw)})
  details.append({'file':path.name,'acceptedRowIdentity':matches[0]['design'],'binderChains':binder,'targetChains':target,'coordinateSha256':fe.checksum(raw),'unavailableMetricNames':missing,'recordedModelReadings':design_model_scores(str(path)),'omissions':'Hotspot/coldspot metrics are omitted because this review does not reconstruct source-to-written site identities. Missing unbound states, PAE/confidence arrays and campaign-only metrics are unavailable, not zero or recomputed predictions.'})
 return rows,details
