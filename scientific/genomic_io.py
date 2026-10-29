"""Managed indexed FASTA and HTSlib genomic-alignment inspection."""
import collections,fcntl,hashlib,json,os,pathlib,signal,subprocess,sys,tempfile

ACTIONS={'genomic_io_status','indexed_genome_import','indexed_genomes','indexed_genome_region','indexed_genome_region_save','indexed_genome_export','genomic_alignment_import','genomic_alignments','genomic_io_jobs'}
MAX_FASTA=8*1024**3
MAX_ALIGNMENT=32*1024**2
VERSION='indexed-genomic-io-v1'
def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)
def checksum(path):
 with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def fingerprint(path):
 st=path.stat();return [st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns,st.st_ctime_ns]
def records(s,project,domain):return [{**row,'data':json.loads(row['data'])} for row in s.rows("SELECT * FROM records WHERE project_id=? AND kind='analysis' AND json_extract(data,'$.domain')=? ORDER BY created DESC",(project,domain))]
def runtime(s,request,job=None):
 command=[s.engine_python(),'-I','-B',str(pathlib.Path(__file__).resolve())]+(['--job-id',job['id']] if job else [])
 process=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True,env={**os.environ,'REF_PATH':'','REF_CACHE':'','HTS_ALLOW_REMOTE':'0','OMP_NUM_THREADS':'1'})
 if job:s.job_metadata(job['id'],{'pid':process.pid,'workerPath':str(pathlib.Path(__file__).resolve())})
 try:stdout,stderr=process.communicate(canonical(request),timeout=600 if request['operation']=='index' else 60)
 except subprocess.TimeoutExpired:
  os.killpg(process.pid,signal.SIGKILL);process.communicate();raise ValueError('Genomic I/O timed out; the owned worker was stopped and no partial result published.') from None
 if process.returncode:raise ValueError('Genomic I/O failed: '+stderr[-1500:].strip())
 return json.loads(stdout)
def pinned(s):
 result=runtime(s,{'operation':'status'})
 if result.get('pysam')!='0.24.1' or result.get('architecture')!='arm64':raise ValueError('The qualified ARM CPU pysam 0.24.1 runtime is unavailable.')
 return result
def managed(s,source,key='asset'):
 name=source.get(key)
 if not isinstance(name,str) or pathlib.Path(name).name!=name:raise ValueError('Invalid managed genomic source identity.')
 path=s.root/'assets'/name
 if path.is_symlink() or not path.is_file():raise ValueError('Managed genomic source is missing or is a symbolic link.')
 return path
def verified_reference(s,row):
 source=row['data']['sourceFile'];path=managed(s,source);index=managed(s,source,'indexAsset')
 if checksum(index)!=source['indexSha256']:raise ValueError('The FASTA index checksum changed; original reference was not queried.')
 stamp=fingerprint(path);cache=s.root/'cache'/('indexed-reference-'+hashlib.sha256((source['asset']+source['sha256']).encode()).hexdigest()+'.json')
 cached=json.loads(cache.read_text()) if cache.is_file() else None
 if cached!=stamp:
  if checksum(path)!=source['sha256'] or fingerprint(path)!=stamp:raise ValueError('The managed reference bytes changed; no interval returned.')
  import uuid
  temporary=cache.with_name(cache.name+'.'+str(uuid.uuid4())+'.tmp');temporary.write_text(canonical(stamp));os.replace(temporary,cache)
 return path,index,stamp
def chosen(s,p):
 row=next((r for r in records(s,p['projectId'],'indexed_genome') if r['id']==p.get('id')),None)
 if not row:raise ValueError('Choose an indexed reference in this project.')
 return row
def dispatch(s,action,p):
 s.project(p['projectId'])
 if action=='indexed_genomes':return records(s,p['projectId'],'indexed_genome')
 if action=='genomic_alignments':return records(s,p['projectId'],'genomic_alignment')
 if action=='genomic_io_jobs':return [{**r,'data':json.loads(r['data'])} for r in s.rows("SELECT * FROM jobs WHERE project_id=? AND engine='genomic_io' ORDER BY created DESC LIMIT 20",(p['projectId'],))]
 if action=='genomic_io_status':
  try:return {**pinned(s),'available':True}
  except Exception as error:return {'available':False,'error':str(error)}
 if action=='indexed_genome_region_save':
  value=dispatch(s,'indexed_genome_region',{k:v for k,v in p.items() if k not in ('name','expectedSequenceSha256')})
  if value['sequenceSha256']!=p.get('expectedSequenceSha256'):raise ValueError('Indexed interval changed since inspection; inspect it again.')
  return s.record_save({'projectId':p['projectId'],'kind':'analysis','name':str(p.get('name') or 'Indexed reference interval')[:200],'data':{'domain':'indexed_genomic_interval','result':value}})
 if action=='indexed_genome_region':
  if set(p)-{'projectId','id','replicon','start','end','strand'}:raise ValueError('Unsupported indexed-reference interval field.')
  row=chosen(s,p);data=row['data'];ref=next((r for r in data['replicons'] if r['id']==p.get('replicon')),None)
  start,end,strand=p.get('start'),p.get('end'),p.get('strand')
  if ref is None or type(start)is not int or type(end)is not int or strand not in ('+','-') or not 1<=start<=ref['length'] or not 1<=end<=ref['length']:raise ValueError('Choose a known replicon, explicit strand and integer 1-based inclusive coordinates.')
  circular=ref['topology']=='circular';length=end-start+1 if end>=start else end+ref['length']-start+1
  if end<start and not circular or length>100000:raise ValueError('Origin traversal needs explicit circular topology; one interval is limited to 100,000 bases.')
  path,index,stamp=verified_reference(s,row);result=runtime(s,{'operation':'fetch','path':str(path),'index':str(index),'replicon':ref['id'],'start':start,'end':end,'strand':strand})
  if fingerprint(path)!=stamp:raise ValueError('Reference changed while fetching the interval.')
  if len(result['dna'])!=length:raise ValueError('HTSlib returned an interval of unexpected length.')
  return {**result,'storageKind':'indexed_fasta','referenceId':row['id'],'metadata':data['metadata'],'sourceFile':data['sourceFile'],'replicon':ref['id'],'start':start,'end':end,'strand':strand,'coordinateConvention':'1-based inclusive, explicit circular origin traversal','sequenceSha256':hashlib.sha256(result['dna'].encode()).hexdigest(),'scope':'Exact indexed reference interval. Original bytes were hashed at import and are rehashed after source metadata changes; index bytes are checked per query. No genes, annotation, transcript processing, expression or biological effect inferred.'}
 if action=='indexed_genome_export':
  row=chosen(s,p);source,_,stamp=verified_reference(s,row);target=pathlib.Path(p['path'])
  if target.resolve()==source.resolve() or target.is_symlink() or target.exists():raise ValueError('Choose a new local FASTA destination; existing research files are not overwritten.')
  import uuid
  temporary=target.with_name('.'+target.name+'.genomic-export.'+str(uuid.uuid4())+'.tmp')
  try:
   with source.open('rb') as original,temporary.open('xb') as saved:
    while block:=original.read(1024**2):saved.write(block)
   if fingerprint(source)!=stamp or checksum(temporary)!=row['data']['sourceFile']['sha256']:raise ValueError('Original FASTA changed during export.')
   os.link(temporary,target)
  finally:temporary.unlink(missing_ok=True)
  return {'path':str(target),'sha256':row['data']['sourceFile']['sha256']}
 if action not in ('indexed_genome_import','genomic_alignment_import'):raise ValueError('Unsupported genomic I/O action.')
 allowed={'projectId','path','name','metadata','circularReplicons'} if action=='indexed_genome_import' else {'projectId','path','name','format'}
 if set(p)-allowed:raise ValueError('Unsupported genomic import field.')
 source=pathlib.Path(p['path']);limit=MAX_FASTA if action=='indexed_genome_import' else MAX_ALIGNMENT
 if source.is_symlink() or not source.is_file() or not 0<source.stat().st_size<=limit:raise ValueError('Choose a regular FASTA up to 8 GiB or SAM/BAM up to 32 MiB.')
 if action=='indexed_genome_import':
  if source.suffix.lower() not in ('.fa','.fna','.fasta'):raise ValueError('Indexed references currently require uncompressed FASTA; gzip is not silently expanded.')
  metadata=p.get('metadata');circular=p.get('circularReplicons',[])
  if not isinstance(metadata,dict) or any(not isinstance(metadata.get(k),str) or not 1<=len(metadata[k].strip())<=500 for k in ('organism','assembly','source')) or not isinstance(circular,list) or any(not isinstance(v,str) for v in circular) or len(set(circular))!=len(circular):raise ValueError('Supply explicit organism/strain, assembly/version, source and distinct circular replicon IDs.')
 else:
  if p.get('format') not in ('sam','bam'):raise ValueError('Choose SAM or BAM explicitly. CRAM requires separately qualified reference handling and is not enabled.')
 with (s.root/'cache/genomic-io.lock').open('a') as lease:
  try:fcntl.flock(lease,fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError:raise ValueError('A genomic import is already running in this Library.') from None
  versions=pinned(s)
  s.db.execute('BEGIN IMMEDIATE')
  if s.active():s.db.rollback();raise ValueError('Finish the active local scientific job before importing genomic data.')
  job=s.job_new({'projectId':p['projectId'],'name':str(p.get('name') or source.name)[:200],'sourcePath':str(source),'runtime':versions,'scope':'Owned local genomic I/O, no remote reference fetch.'},'genomic_io','running');published=[]
  try:
   with tempfile.TemporaryDirectory(prefix='genomic-io-',dir=s.root/'cache') as tmp:
    request={'operation':'index' if action=='indexed_genome_import' else 'alignment','source':str(source),'folder':tmp,'format':p.get('format'),'maximumBytes':limit};result=runtime(s,request,job)
    domain='indexed_genome' if action=='indexed_genome_import' else 'genomic_alignment';sha=result['sourceSha256'];old=next((r for r in records(s,p['projectId'],domain) if r['data']['sourceFile']['sha256']==sha and (domain!='indexed_genome' or r['data']['metadata']==metadata and r['data']['circularReplicons']==circular)),None)
    if old:
     s.db.execute('BEGIN IMMEDIATE')
     if s.job(job['id'])['state']!='running':raise ValueError('Genomic import was cancelled before duplicate review completed.')
     s.job_update(job['id'],'completed',{'recordId':old['id'],'duplicateOriginal':True});return old
    if domain=='indexed_genome':
     if any(name not in {r['id'] for r in result['replicons']} for name in circular):raise ValueError('Circular IDs must match actual FASTA identifiers.')
     for ref in result['replicons']:ref['topology']='circular' if ref['id'] in circular else 'linear'
    suffix='.fasta' if domain=='indexed_genome' else '.'+p['format'];asset='genomic-'+sha+suffix;origin=pathlib.Path(tmp)/'original';target=s.root/'assets'/asset
    if target.exists():
     if target.is_symlink() or checksum(target)!=sha:raise ValueError('Managed genomic asset checksum conflict.')
    else:os.link(origin,target);published.append(target)
    receipt={'asset':asset,'sha256':sha,'bytes':result.pop('sourceBytes'),'originalName':source.name};result.pop('sourceSha256')
    if domain=='indexed_genome':
     index=pathlib.Path(tmp)/'original.fai';index_asset='genomic-'+sha+'.fai';index_target=s.root/'assets'/index_asset;index_sha=checksum(index)
     if index_target.exists():
      if index_target.is_symlink() or checksum(index_target)!=index_sha:raise ValueError('Managed FASTA index conflict.')
     else:os.link(index,index_target);published.append(index_target)
     receipt.update(indexAsset=index_asset,indexSha256=index_sha)
     origin.unlink();index.unlink();cache=s.root/'cache'/('indexed-reference-'+hashlib.sha256((asset+sha).encode()).hexdigest()+'.json');cache.write_text(canonical(fingerprint(target)))
    data={'domain':domain,'sourceFile':receipt,'result':result,'runtime':versions,'implementationSha256':hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest()}
    if domain=='indexed_genome':data.update(metadata=metadata,circularReplicons=circular,replicons=result['replicons'])
    s.db.execute('BEGIN IMMEDIATE')
    if s.job(job['id'])['state']!='running':raise ValueError('Genomic import was cancelled; no research record published.')
    import uuid,datetime
    record={'id':str(uuid.uuid4()),'project_id':p['projectId'],'kind':'analysis','name':str(p.get('name') or source.name)[:200],'data':data};date=datetime.datetime.now(datetime.timezone.utc).isoformat();s.db.execute('INSERT INTO records VALUES(?,?,?,?,?,?)',(record['id'],p['projectId'],'analysis',record['name'],canonical(data),date));s.db.execute('UPDATE projects SET updated=? WHERE id=?',(date,p['projectId']));s.job_update(job['id'],'completed',{'recordId':record['id']});published=[];return record
  except Exception as error:
   s.db.rollback()
   if s.job(job['id'])['state']!='cancelled':s.job_update(job['id'],'failed',{'error':str(error)})
   for path in published:path.unlink(missing_ok=True)
   raise

def worker(p):
 import pysam,platform
 versions={'pysam':pysam.__version__,'samtools':pysam.__samtools_version__,'architecture':platform.machine()}
 if p['operation']=='status':return versions
 if p['operation']=='fetch':
  with pysam.FastaFile(p['path'],filepath_index=p['index']) as ref:
   dna=ref.fetch(p['replicon'],p['start']-1,p['end']) if p['end']>=p['start'] else ref.fetch(p['replicon'],p['start']-1)+ref.fetch(p['replicon'],0,p['end'])
  dna=dna.upper()
  if p['strand']=='-':dna=dna.translate(str.maketrans('ACGTRYSWKMBDHVN','TGCAYRSWMKVHDBN'))[::-1]
  return {'dna':dna,'rnaAlphabet':dna.replace('T','U'),'runtime':versions}
 source=pathlib.Path(p['source'])
 if source.is_symlink() or not source.is_file():raise ValueError('Source must remain a regular local file.')
 original_stamp=fingerprint(source);copy=pathlib.Path(p['folder'])/'original';size=0;digest=hashlib.sha256();refs=[];current=None;names=set();blank_after_sequence=False
 with source.open('rb') as original,copy.open('xb') as saved:
  if p['operation']=='index':
   while raw:=original.readline(1024**2+1):
    size+=len(raw)
    if size>p['maximumBytes'] or len(raw)>1024**2:raise ValueError('FASTA exceeded the 8 GiB source or 1 MiB line bound.')
    digest.update(raw);saved.write(raw);line=raw.rstrip(b'\r\n')
    if not line:
     blank_after_sequence=bool(current and current['length']);continue
    if line.startswith(b'>'):
     blank_after_sequence=False
     if current and current['length']==0:raise ValueError('Empty reference sequence.')
     title=line[1:].decode('utf-8');name=title.split()[0] if title.split() else ''
     if not name or name in names or any(ord(c)<33 for c in name) or len(title)>4096:raise ValueError('FASTA needs distinct bounded printable sequence identifiers.')
     names.add(name);current={'id':name,'description':title,'length':0,'GC':0};refs.append(current)
     if len(refs)>10000:raise ValueError('Indexed FASTA currently supports at most 10,000 replicons.')
    else:
     sequence=line.upper()
     if blank_after_sequence:raise ValueError('Embedded blank sequence rows are not supported by this fixed-width FASTA index; trailing/inter-record blank rows are preserved.')
     if current is None or not sequence or set(sequence)-set(b'ACGTRYSWKMBDHVN'):raise ValueError('Indexed FASTA requires nonempty unwrapped/consistently wrapped IUPAC DNA rows without embedded whitespace.')
     current['length']+=len(sequence);current['GC']+=sequence.count(b'G')+sequence.count(b'C')
  else:
   while block:=original.read(1024**2):
    size+=len(block)
    if size>p['maximumBytes']:raise ValueError('Alignment source grew beyond 32 MiB.')
    digest.update(block);saved.write(block)
 if fingerprint(source)!=original_stamp:raise ValueError('Original genomic file changed during import; no snapshot published.')
 if p['operation']=='index':
  if not refs or not current['length']:raise ValueError('No complete FASTA reference supplied.')
  pysam.faidx(str(copy))
  with pysam.FastaFile(str(copy)) as check:
   if list(check.references)!=[r['id'] for r in refs] or list(check.lengths)!=[r['length'] for r in refs]:raise ValueError('HTSlib index differs from the streamed FASTA sequence identities/lengths.')
  for r in refs:r['GCPercent']=100*r.pop('GC')/r['length']
  return {'sourceSha256':digest.hexdigest(),'sourceBytes':size,'replicons':refs,'scope':'Managed uncompressed FASTA and HTSlib index; source is retained exactly. No inferred assembly annotations, gene identities or transcript models. Whole-source hashing is streamed; interval fetching is indexed and bounded.'}
 counts=collections.Counter();mapq=collections.Counter();refs_count=collections.Counter();cigar=collections.Counter();records=0
 with pysam.AlignmentFile(str(copy),'r' if p['format']=='sam' else 'rb',check_sq=False) as stream:
  if stream.is_cram:raise ValueError('CRAM/remote reference resolution is not enabled.')
  if p['format']=='bam' and not stream.is_bam or p['format']=='sam' and not stream.is_sam:raise ValueError('Detected alignment format differs from the explicit choice.')
  header=stream.header.to_dict()
  for read in stream.fetch(until_eof=True):
   records+=1
   if records>1000000 or read.query_length>100000:raise ValueError('Alignment inspection exceeded one million records or a 100,000-base read; no partial result saved.')
   for key,flag in [('unmapped',read.is_unmapped),('secondary',read.is_secondary),('supplementary',read.is_supplementary),('duplicateFlag',read.is_duplicate),('QCFailFlag',read.is_qcfail),('pairedFlag',read.is_paired),('reverseFlag',read.is_reverse)]:counts[key]+=bool(flag)
   if not read.is_unmapped:
    if read.reference_id<0 or read.reference_start<0 or read.reference_id>=len(stream.references) or (read.reference_end or read.reference_start)>stream.lengths[read.reference_id]:raise ValueError('Alignment coordinates exceed the supplied reference header.')
    mapq[str(read.mapping_quality)]+=1;refs_count[stream.references[read.reference_id]]+=1
   for operation,length in read.cigartuples or []:cigar[str(operation)]+=length
 if not records:raise ValueError('No alignment records supplied.')
 return {'sourceSha256':digest.hexdigest(),'sourceBytes':size,'records':records,'header':header,'flagCounts':dict(counts),'mappedRecordCountsByHeaderReference':dict(refs_count),'mappedMAPQHistogram':dict(mapq),'CIGAROperationBaseTotals':dict(cigar),'CIGARCodes':{'0':'M','1':'I','2':'D','3':'N','4':'S','5':'H','6':'P','7':'=','8':'X','9':'B'},'MAPQ255Meaning':'Unavailable, not high mapping confidence.','scope':'Descriptive supplied alignment records and flags, including secondary/supplementary records separately. Counts are not unique fragments, expression, coverage or variant calls. Header identities do not prove reference assembly/sequence identity; MAPQ is not measured mapping accuracy. No alignment, realignment, variant calling or remote reference fetch performed.'}

if __name__=='__main__':print(canonical(worker(json.load(sys.stdin))))
