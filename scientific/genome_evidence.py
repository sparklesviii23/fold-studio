"""Attributed experimental/curated statements, without inferred essentiality or ranking."""
import base64,csv,hashlib,io,json,pathlib
FIELDS=('geneId','evidenceType','classification','organism','strain','assembly','condition','source','citation','statement')
TYPES={'experimental_essentiality','experimental_fitness','curated_annotation','hypothesis'}
CLASSES={'essential','nonessential','conditional','not_assessed'}
LIMIT=1024**2

def parse_evidence(raw,reference,features):
 if len(raw)>LIMIT:raise ValueError('Gene evidence CSV is limited to 1 MiB.')
 reader=csv.DictReader(io.StringIO(raw.decode('utf-8-sig')),strict=True)
 if reader.fieldnames!=list(FIELDS):raise ValueError('Use the exact template CSV columns in their original order.')
 gene_ids={f['attributes']['ID'] for f in features if f['type']=='gene' and f['attributes'].get('ID')}
 rows=[];seen=set()
 for row in reader:
  if None in row or any(not isinstance(row[key],str) or not row[key].strip() or len(row[key])>(4000 if key=='statement' else 500) for key in FIELDS):raise ValueError('Every evidence row requires complete bounded attribution and context.')
  if row['geneId'] not in gene_ids:raise ValueError('Evidence must name an exact supplied GFF gene ID; aliases are not inferred.')
  if row['organism']!=reference['metadata']['organism'] or row['assembly']!=reference['metadata']['assembly']:raise ValueError('Evidence organism/assembly must exactly match the selected reference.')
  if row['evidenceType'] not in TYPES or row['classification'] not in CLASSES:raise ValueError('Choose a supported evidence type and classification.')
  if row['classification']!='not_assessed' and row['evidenceType'] not in ('experimental_essentiality','experimental_fitness'):raise ValueError('Only explicitly attributed experimental evidence may carry an essentiality/fitness classification.')
  identity=json.dumps(row,sort_keys=True)
  if identity in seen:raise ValueError('Duplicate evidence rows must be resolved explicitly.')
  seen.add(identity);rows.append(row)
  if len(rows)>5000:raise ValueError('At most 5,000 explicit evidence rows are supported.')
 if not rows:raise ValueError('No evidence rows supplied.')
 return rows

def dispatch(s,action,p,reference,features):
 if action=='genome_evidence_import':
  path=pathlib.Path(p['path'])
  if path.suffix.lower()!='.csv' or path.is_symlink() or not path.is_file() or path.stat().st_size>LIMIT:raise ValueError('Choose a regular evidence CSV up to 1 MiB.')
  raw=path.read_bytes();rows=parse_evidence(raw,reference,features)
  data={'domain':'genome_evidence','referenceId':reference['id'],'referenceSources':reference['sources'],'metadata':reference['metadata'],'sourceFileName':path.name,'sourceFileSha256':hashlib.sha256(raw).hexdigest(),'originalFileBase64':base64.b64encode(raw).decode(),'rows':rows,'scope':'Supplied attributed statements, not independently verified evidence. Classifications apply only to the recorded strain, assembly and experimental condition. No extrapolation to other conditions or prediction of antimicrobial efficacy is made.'}
  return s.record_save({'projectId':p['projectId'],'kind':'analysis','name':'Gene evidence · '+path.name,'data':data})
 if action=='genome_evidence':
  gene=p.get('geneId')
  if gene not in {f['attributes']['ID'] for f in features if f['type']=='gene' and f['attributes'].get('ID')}:raise ValueError('Choose an exact annotated gene ID.')
  result=[]
  for record in s.rows("SELECT id,data FROM records WHERE project_id=? AND kind='analysis' AND json_extract(data,'$.domain')='genome_evidence'",(p['projectId'],)):
   data=json.loads(record['data'])
   if data.get('referenceId')!=reference['id']:continue
   for row in data['rows']:
    if row['geneId']==gene:result.append({**row,'recordId':record['id'],'sourceFileName':data['sourceFileName'],'sourceFileSha256':data['sourceFileSha256'],'scope':data['scope']})
  return {'referenceId':reference['id'],'geneId':gene,'rows':result,'scope':'No source means no essentiality claim. Conflicting supplied observations remain separate; no consensus score or target ranking is inferred.'}
 raise ValueError('Unsupported gene-evidence operation.')
