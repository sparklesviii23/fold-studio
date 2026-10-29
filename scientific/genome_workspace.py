"""Local reference inspection. No inferred genes, essentiality or RNA-target design."""
import hashlib,json,pathlib,uuid,datetime,urllib.parse,gzip,io
LIMIT=32*1024**2
ACTIONS={'genome_import','genome_list','genome_region','genome_features','genome_search','genome_region_save','genome_product','genome_product_save','genome_import_annotated','genome_evidence_import','genome_evidence','genome_variant','genome_variant_save','genome_vcf_import','genome_orfs'}
COMPLEMENT=str.maketrans('ACGTRYSWKMBDHVN','TGCAYRSWMKVHDBN')
def reverse_complement(text):return text.translate(COMPLEMENT)[::-1]
def fasta(text):
 result={};name=None
 for line in text.splitlines():
  if line.startswith('>'):
   name=line[1:].split()[0] if line[1:].split() else ''
   if not name or name in result:raise ValueError('FASTA replicon identifiers must be nonempty and unique.')
   result[name]=[]
  elif line.strip():
   if name is None:raise ValueError('FASTA must start with a named record.')
   sequence=''.join(line.split()).upper()
   if set(sequence)-set('ACGTRYSWKMBDHVN'):raise ValueError('Reference FASTA must contain supported IUPAC DNA symbols.')
   result[name].append(sequence)
 result={key:''.join(parts) for key,parts in result.items()}
 if not result or any(not sequence for sequence in result.values()):raise ValueError('FASTA contains no complete sequence records.')
 return result
def annotations(text,sequences,circular):
 result=[]
 for number,line in enumerate(text.splitlines(),1):
  if line=='##FASTA':break
  if not line or line.startswith('#'):continue
  cells=line.split('\t')
  if len(cells)!=9:raise ValueError('GFF3 rows require nine tab-separated fields (line '+str(number)+').')
  seqid,source,kind,left,right,score,strand,phase,attributes=cells
  try:start,end=int(left),int(right)
  except ValueError:raise ValueError('GFF3 coordinates must be integers.') from None
  if seqid not in sequences or strand not in ('+','-','.','?') or phase not in ('0','1','2','.') or start<1 or end<start:raise ValueError('Invalid GFF3 sequence, coordinates, strand or phase.')
  length=len(sequences[seqid])
  if start>length or end>length and (seqid not in circular or end-start+1>length):raise ValueError('GFF3 coordinates exceed the declared replicon/topology.')
  attrs={};parents=[]
  for field in attributes.split(';'):
   if field and field!='.':
    if '=' not in field:raise ValueError('GFF3 attributes require key=value; GTF is a separate format.')
    key,value=field.split('=',1)
    if key in attrs:raise ValueError('Duplicate GFF3 attribute key.')
    attrs[key]=urllib.parse.unquote(value)
    if key=='Parent':parents=[urllib.parse.unquote(parent) for parent in value.split(',')]
  result.append({'index':len(result),'sourceLine':number,'replicon':seqid,'type':kind,'start':start,'end':end,'strand':strand,'phase':phase,'attributes':attrs,'parents':parents,'annotationSource':source})
  if len(result)>100000:raise ValueError('At most 100,000 annotation rows per reference are supported.')
 return result
def region(sequence,start,end,strand,circular=False):
 if type(start) is not int or type(end) is not int or strand not in ('+','-'):raise ValueError('Choose integer 1-based inclusive coordinates and + or - strand.')
 length=len(sequence)
 if not 1<=start<=length or end<1:raise ValueError('Coordinates are outside the reference.')
 if end<start:
  if not circular:raise ValueError('Origin-spanning coordinates require an explicitly circular replicon.')
  end+=length
 if end>length and not circular or end-start+1>length:raise ValueError('The requested interval exceeds one reference traversal.')
 if end-start+1>100000:raise ValueError('Sequence inspection is bounded to 100,000 bases per window.')
 value=(sequence+sequence)[start-1:end]
 return reverse_complement(value) if strand=='-' else value
def decode_reference(raw,encoding=None):
 if encoding not in (None,'gzip'):raise ValueError('Unsupported reference encoding.')
 if encoding=='gzip':
  with gzip.GzipFile(fileobj=io.BytesIO(raw)) as stream:decoded=stream.read(LIMIT+1)
 else:decoded=raw
 if len(decoded)>LIMIT:raise ValueError('Expanded reference exceeds 32 MiB.')
 return decoded.decode('utf-8-sig')

def window_annotations(features,replicon,start,length,replicon_length,circular):
 """Clip supplied annotation spans to an unrolled, oriented-independent window."""
 end=start+length-1;visible=[];total=0
 for feature in features:
  if feature['replicon']!=replicon:continue
  fragments=[]
  for shift in (-replicon_length,0,replicon_length) if circular else (0,):
   left=max(start,feature['start']+shift);right=min(end,feature['end']+shift)
   if left<=right:fragments.append({'startOffsetZeroBased':left-start,'endOffsetExclusive':right-start+1,'continuesBeforeWindow':feature['start']+shift<start,'continuesAfterWindow':feature['end']+shift>end})
  if fragments:
   total+=1
   if len(visible)<200:visible.append({'feature':feature,'fragments':fragments})
 return {'features':visible,'total':total,'omitted':max(0,total-len(visible)),'windowStart':start,'unrolledWindowEnd':end,'length':length,'repliconLength':replicon_length,'orientation':'forward-reference coordinates regardless of sequence inspection strand','scope':'Supplied annotation intervals only, clipped to this coordinate window. No inferred regulatory activity, operons or variant/essentiality evidence.'}
def raw_file(path,extensions):
 path=pathlib.Path(path)
 suffix=path.with_suffix('').suffix.lower() if path.suffix.lower()=='.gz' else path.suffix.lower()
 if suffix not in extensions or path.is_symlink() or not path.is_file() or path.stat().st_size>LIMIT:raise ValueError('Choose a supported regular reference file up to 32 MiB.')
 raw=path.read_bytes()
 if len(raw)>LIMIT:raise ValueError('Reference file exceeds 32 MiB.')
 return path.name,raw,decode_reference(raw,'gzip' if path.suffix.lower()=='.gz' else None)
def references(s,project):
 if not s.db.execute("SELECT 1 FROM sqlite_master WHERE name='genome_references'").fetchone():return []
 return [json.loads(row['data']) for row in s.rows('SELECT data FROM genome_references WHERE project_id=?',(project,))]
def load(s,p):
 row=next((row for row in references(s,p['projectId']) if row['id']==p.get('id')),None)
 if row is None:raise ValueError('Choose a reference in this project.')
 texts={}
 for source in row['sources']:
  name=source['asset']
  if pathlib.Path(name).name!=name:raise ValueError('Invalid reference asset.')
  path=s.root/'genome-assets'/name
  if path.is_symlink():raise ValueError('Reference asset must not be a symbolic link.')
  raw=path.read_bytes()
  if len(raw)>LIMIT or hashlib.sha256(raw).hexdigest()!=source['sha256']:raise ValueError('Original reference checksum changed.')
  texts[source['kind']]=decode_reference(raw,source.get('encoding'))
 sequences=fasta(texts['fasta']);features=annotations(texts.get('gff3',''),sequences,row['circularReplicons'])
 return row,sequences,features
def dispatch(s,action,p):
 s.project(p['projectId'])
 if action=='genome_list':return references(s,p['projectId'])
 if action=='genome_import':return import_reference(s,p)
 if action=='genome_import_annotated':
  from genome_annotated import import_annotated
  return import_annotated(s,p)
 if action=='genome_variant_save':
  value=dispatch(s,'genome_variant',{key:value for key,value in p.items() if key not in ('expectedInputSha256','name')})
  if value['inputSha256']!=p.get('expectedInputSha256'):raise ValueError('Variant differs from its inspected request.')
  return s.record_save({'projectId':p['projectId'],'kind':'analysis','name':str(p.get('name','Reference-checked genomic variant'))[:200],'data':{'domain':'genome_variant','result':value}})
 if action=='genome_product_save':
  value=dispatch(s,'genome_product',{key:value for key,value in p.items() if key not in ('expectedSequenceSha256','name')})
  if value['sequenceSha256']!=p.get('expectedSequenceSha256'):raise ValueError('Product differs from its inspected source.')
  return s.record_save({'projectId':p['projectId'],'kind':'analysis','name':str(p.get('name','Annotated sequence product'))[:200],'data':{'domain':'genome_product','result':value}})
 if action=='genome_region_save':
  request={key:value for key,value in p.items() if key not in ('expectedSequenceSha256','name')}
  value=dispatch(s,'genome_region',request)
  if value['sequenceSha256']!=p.get('expectedSequenceSha256'):raise ValueError('Region differs from the inspected sequence; inspect it again.')
  return s.record_save({'projectId':p['projectId'],'kind':'analysis','name':str(p.get('name','Saved genomic interval'))[:200],'data':{'domain':'genome_interval','result':value}})
 row,sequences,features=load(s,p)
 if action=='genome_orfs':
  from genome_orfs import analyze
  return analyze(s,p,row,sequences)
 if action=='genome_vcf_import':
  from genome_vcf import import_vcf
  return import_vcf(s,p,row,sequences)
 if action=='genome_variant':
  from genome_variants import inspect
  return inspect(s,p,row,sequences,features)
 if action in ('genome_evidence_import','genome_evidence'):
  from genome_evidence import dispatch as evidence_dispatch
  return evidence_dispatch(s,action,p,row,features)
 if action=='genome_product':
  from genome_products import assemble,translate
  value=assemble(sequences,features,row['circularReplicons'],p.get('featureIndex'),p.get('kind'))
  value.update(referenceId=row['id'],metadata=row['metadata'],sources=row['sources'])
  if 'translationTable' in p:value['translation']=translate(s,value,p['translationTable'],p.get('completeCDS',False))
  return value
 if action=='genome_features':
  query=p.get('query','').strip()
  if len(query)>200:raise ValueError('Feature query exceeds 200 characters.')
  matches=[f for f in features if (not p.get('replicon') or f['replicon']==p['replicon']) and (not query or query.casefold() in json.dumps(f['attributes']).casefold())]
  return {'features':matches[:200],'total':len(matches),'omitted':max(0,len(matches)-200),'referenceId':row['id']}
 if action=='genome_region':
  feature=None
  if 'featureIndex' in p:
   index=p['featureIndex']
   if type(index) is not int or not 0<=index<len(features):raise ValueError('Choose an existing annotation row.')
   feature=features[index];replicon=feature['replicon'];start,end,strand=feature['start'],feature['end'],feature['strand']
   if strand not in ('+','-'):raise ValueError('The annotation has no oriented strand; inspect an explicit region instead.')
  else:replicon,start,end,strand=p.get('replicon'),p.get('start'),p.get('end'),p.get('strand','+')
  if replicon not in sequences:raise ValueError('Choose a known reference replicon.')
  value=region(sequences[replicon],start,end,strand,replicon in row['circularReplicons'])
  from genome_vcf import window as variant_window
  return {'referenceId':row['id'],'metadata':row['metadata'],'sources':row['sources'],'replicon':replicon,'variantWindow':variant_window(s,p['projectId'],row['id'],replicon,start,len(value),len(sequences[replicon]),replicon in row['circularReplicons']),'start':start,'end':end,'strand':strand,'coordinateConvention':'1-based inclusive; origin traversal only for explicitly circular references','feature':feature,'annotationWindow':window_annotations(features,replicon,start,len(value),len(sequences[replicon]),replicon in row['circularReplicons']),'dna':value,'rnaAlphabet':value.replace('T','U'),'sequenceSha256':hashlib.sha256(value.encode()).hexdigest(),'scope':'Exact oriented genomic interval. RNA alphabet conversion is not evidence of a mature/spliced or expressed transcript. GFF CDS phase is reported, not silently used to infer protein products.'}
 if action=='genome_search':
  query=p.get('sequence','').upper()
  if not 1<=len(query)<=1000 or set(query)-set('ACGT'):raise ValueError('Exact sequence search requires 1–1,000 unambiguous DNA bases.')
  hits=[];total=0
  for name,sequence in sequences.items():
   if p.get('replicon') and p['replicon']!=name:continue
   searchable=sequence+(sequence[:len(query)-1] if name in row['circularReplicons'] else '')
   for strand,pattern in [('+',query),('-',reverse_complement(query))]:
    position=searchable.find(pattern)
    while position!=-1 and position<len(sequence):
     total+=1
     if len(hits)<200:hits.append({'replicon':name,'start':position+1,'end':position+len(pattern),'strand':strand})
     if total>=10000:return {'hits':hits,'total':total,'countIsLowerBound':True,'omittedAtLeast':total-len(hits),'scope':'Search stopped at 10,000 matches; counts are lower bounds, not genome-wide specificity estimates.'}
     position=searchable.find(pattern,position+1)
  return {'hits':hits,'total':total,'omitted':max(0,total-len(hits)),'scope':'Exact matches on both strands, including explicit circular origins. Ambiguous reference symbols are not treated as wildcard matches; palindromes are reported on each strand.'}
 raise ValueError('Unsupported genome inspection operation.')


def export_references(s,project_id,archive):
 result=[]
 for reference in references(s,project_id):
  load(s,{'projectId':project_id,'id':reference['id']})
  saved=json.loads(json.dumps(reference))
  for source in saved['sources']:
   path=s.root/'genome-assets'/source['asset'];raw=path.read_bytes()
   if hashlib.sha256(raw).hexdigest()!=source['sha256']:raise ValueError('Genome changed during project export.')
   source['file']='genomes/'+source['asset'];source['bytes']=len(raw);archive.writestr(source['file'],raw)
  result.append(saved)
 return result


def import_reference(s,p,extra_sources=()):
 metadata=p.get('metadata',{})
 required=('organism','assembly','source')
 if not isinstance(metadata,dict) or any(not isinstance(metadata.get(k),str) or not metadata[k].strip() or len(metadata[k])>500 for k in required):raise ValueError('Supply explicit organism, assembly/version identity and reference source. Unknown values must be labelled unknown.')
 name,raw,text=raw_file(p['fastaPath'],('.fa','.fasta','.fna'));sequences=fasta(text);sources=[('fasta',name,raw)]
 circular=p.get('circularReplicons',[])
 if not isinstance(circular,list) or any(value not in sequences for value in circular) or len(set(circular))!=len(circular):raise ValueError('Circular replicons must be explicit distinct FASTA identifiers.')
 features=[]
 if p.get('gffPath'):
  annotation_format=p.get('annotationFormat','gff3')
  if annotation_format not in ('gff3','gtf','bed'):raise ValueError('Choose GFF3, GTF or BED explicitly.')
  gname,graw,gtext=raw_file(p['gffPath'],('.gff','.gff3') if annotation_format=='gff3' else ('.'+annotation_format,))
  if annotation_format=='gff3':sources.append(('gff3',gname,graw))
  else:
   from genome_tabular import normalize
   normalized,receipt=normalize(gtext,annotation_format);sources.extend([('gff3','derived-annotations.gff3',normalized.encode()),(annotation_format,gname,graw)]);metadata={**metadata,'tabularAnnotationConversion':receipt};gtext=normalized
  features=annotations(gtext,sequences,circular)
 sources.extend(extra_sources)
 id=str(uuid.uuid4());created=datetime.datetime.now(datetime.timezone.utc).isoformat();record={'id':id,'projectId':p['projectId'],'metadata':metadata,'created':created,'circularReplicons':circular,'replicons':[{'id':key,'length':len(value),'topology':'circular' if key in circular else 'linear','gcPercent':100*(value.count('G')+value.count('C'))/len(value),'sha256':hashlib.sha256(value.encode()).hexdigest()} for key,value in sequences.items()],'featureCount':len(features),'sources':[],'scope':'Imported reference sequences and supplied GFF3 annotations; identity/topology are user-supplied. No inferred genes, essentiality, transcript expression or antimicrobial activity.'}
 folder=s.root/'genome-assets';folder.mkdir(exist_ok=True)
 if folder.is_symlink():raise ValueError('Genome storage must be a real local directory.')
 created_paths=[]
 try:
  s.db.execute('BEGIN IMMEDIATE');s.db.execute('CREATE TABLE IF NOT EXISTS genome_references(id TEXT PRIMARY KEY,project_id TEXT,data TEXT)')
  for kind,filename,content in sources:
   encoding='gzip' if filename.lower().endswith('.gz') else None
   asset=str(uuid.uuid4())+({'fasta':'.fasta','gff3':'.gff3','genbank':'.gb','embl':'.embl','gtf':'.gtf','bed':'.bed'}[kind])+('.gz' if encoding else '');path=folder/asset
   with path.open('xb') as stream:stream.write(content)
   created_paths.append(path);record['sources'].append({'kind':kind,'fileName':filename,'asset':asset,'encoding':encoding,'sha256':hashlib.sha256(content).hexdigest()})
  s.db.execute('INSERT INTO genome_references VALUES(?,?,?)',(id,p['projectId'],json.dumps(record)))
  s.db.execute('INSERT INTO records VALUES(?,?,?,?,?,?)',(str(uuid.uuid4()),p['projectId'],'analysis','Genome reference · '+metadata['organism'],json.dumps({'domain':'genome_reference','reference':record}),created));s.db.commit()
 except Exception:
  s.db.rollback()
  for path in created_paths:path.unlink(missing_ok=True)
  raise
 return record
