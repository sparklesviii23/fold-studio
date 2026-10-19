"""Immutable sequence inputs; never present unresolved residues as coordinates."""
import json
import fold_engine as fe

AMINO_ACIDS=set('ACDEFGHIKLMNPQRSTVWY')

def inspect(engine,p):
 row=engine.s.db.execute('SELECT * FROM records WHERE id=?',(p['structureId'],)).fetchone()
 if not row or not any(item['id']==p['structureId'] for item in engine.s.library({})['records']):raise ValueError('Choose an available library target.')
 if p.get('projectId') and row['project_id']!=p['projectId']:raise ValueError('Structure belongs to another project.')
 if row['kind']=='structure':return engine.fold_structure(p)
 if row['kind']!='sequence':raise ValueError('Choose a saved structure or canonical protein sequence.')
 data=json.loads(row['data']);sequence=data.get('sequence')
 if not isinstance(sequence,str) or not 1<=len(sequence)<=4000 or set(sequence)-AMINO_ACIDS:raise ValueError('Sequence target requires 1–4000 canonical uppercase amino acids.')
 sequence_sha=fe.checksum(sequence.encode())
 if sequence_sha!=data.get('sha256'):raise ValueError('Sequence checksum changed. Save a new immutable sequence target.')
 raw=fasta(sequence)
 return {'schemaVersion':1,'reference':{'structureId':row['id'],'projectId':row['project_id'],'sha256':fe.checksum(raw),'format':'fasta','inputKind':'sequence','sequenceSha256':sequence_sha},'sequence':sequence,'inputKind':'sequence','scope':'Sequence input without observed coordinates. Original BindCraft2 disordered-target cropping/preparation applies.'}

def fasta(sequence):return ('>A\n'+sequence+'\n').encode()

def verify_preparation(preparation):
 target=preparation.get('sequenceTarget');source=preparation['source']
 if source.get('format')!='fasta':
  if target:raise ValueError('Sequence-target receipt has no FASTA input.')
  return
 if not target or preparation.get('residueMap') or target.get('sequenceSha256')!=source.get('sequenceSha256') or fe.checksum(target.get('sequence','').encode())!=source.get('sequenceSha256') or fe.checksum(fasta(target.get('sequence','')))!=source.get('sha256'):raise ValueError('Sequence-target preparation differs from the immutable FASTA receipt.')

def snapshot_bytes(engine,source):
 if source.get('format')!='fasta':return engine.lab.record(source['structureId'])[1].read_bytes()
 current=inspect(engine,{'structureId':source['structureId'],'projectId':source['projectId']})
 if current['reference']!=source:raise ValueError('Sequence target changed during preparation.')
 return fasta(current['sequence'])

def predicted_crop(preparation,structure,roles):
 """Exact original FASTA positions, rather than guessed geometric alignment."""
 target=preparation.get('sequenceTarget')
 if not target:return None
 verify_preparation(preparation)
 if not roles:raise ValueError('Sequence-target predictions require explicit original chain roles.')
 chains=[name for name,entry in roles.items() if entry['role']=='target']
 if len(chains)!=1:raise ValueError('A sequence-target prediction must contain exactly one predicted target chain.')
 residues=[r for r in structure['residues'] if r['chain']==chains[0]];sequence=target['sequence']
 if not residues or any(not r['polymer'] or r['ins'] or not 1<=r['num']<=len(sequence) or r['one']!=sequence[r['num']-1] for r in residues):raise ValueError('Predicted target crop differs from the saved FASTA positions.')
 positions=[r['num'] for r in residues]
 if positions!=list(range(positions[0],positions[-1]+1)):raise ValueError('Predicted FASTA target crop is not a contiguous source interval.')
 return {'basis':'predicted_sequence_target','chain':chains[0],'sequenceSha256':target['sequenceSha256'],'sourceLength':len(sequence),'start':positions[0],'end':positions[-1],'coordinateProvenance':'AlphaFold prediction of an original upstream FASTA crop; no observed target coordinates were provided.'}
