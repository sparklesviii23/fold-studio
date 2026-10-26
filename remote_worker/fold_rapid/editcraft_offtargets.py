"""Cas-OFFinder 2.4.1 CPU adapter, with checked reference coordinates.

Enumerates sequence matches, not cutting probabilities, functional effects or
measured editing. Never substitutes a home-grown scanner for the upstream tool.
"""
import hashlib,json,os,pathlib,re,subprocess,tempfile,time
from .editcraft_toolchain import MANIFEST,cloud_only,verify_reference,verify_tool
IUPAC={'A':'A','C':'C','G':'G','T':'T','R':'AG','Y':'CT','S':'GC','W':'AT','K':'GT','M':'AC','B':'CGT','D':'AGT','H':'ACT','V':'ACG','N':'ACGT'}
MAX_HITS=10000
def reverse_complement(text):return text.translate(str.maketrans('ACGTN','TGCAN'))[::-1]
def fasta_records(text,limit=2*1024**2):
 if not isinstance(text,str) or not 0<len(text)<=limit or '\x00' in text:raise ValueError('Provide a bounded reference FASTA.')
 records={};key=None
 for line in text.splitlines():
  line=line.strip()
  if not line:continue
  if line.startswith('>'):
   key=line[1:].split()[0] if line[1:].split() else ''
   if not re.fullmatch('[A-Za-z0-9_.:-]{1,120}',key) or key in records:raise ValueError('FASTA contig identifiers must be safe and unique.')
   records[key]=[]
  else:
   if key is None or set(line.upper())-set('ACGTN'):raise ValueError('Reference FASTA must contain A/C/G/T/N; no implicit conversion or ambiguity expansion.')
   records[key].append(line.upper())
 if not records or len(records)>1000:raise ValueError('Provide 1–1,000 reference contigs.')
 out={key:''.join(parts) for key,parts in records.items()}
 if any(not value for value in out.values()):raise ValueError('Empty FASTA contigs are not supported.')
 return out

def validate_input(p):
 if not isinstance(p,dict) or p.get('nuclease')!='SpCas9':raise ValueError('This adapter supports explicit 20-nt SpCas9 spacers with a 3′ PAM; other nucleases need their own validated contract.')
 pam=p.get('pam')
 if not isinstance(pam,str) or not re.fullmatch('[ACGTRYSWKMBDHVN]{2,8}',pam) or set(pam)=={'N'}:raise ValueError('Specify a restrictive 2–8 base IUPAC 3′ PAM.')
 mm=p.get('mismatches')
 if type(mm)is not int or not 0<=mm<=6:raise ValueError('Choose 0–6 spacer mismatches; bulges are not supported by this pinned version.')
 guides=p.get('guides');ids=set();sequences=set()
 if not isinstance(guides,list) or not 1<=len(guides)<=64:raise ValueError('Provide 1–64 unique spacers.')
 for g in guides:
  if not isinstance(g,dict) or not re.fullmatch('[A-Za-z0-9_-]{1,60}',str(g.get('id',''))) or g['id'] in ids:raise ValueError('Guide identifiers must be safe and unique.')
  value=g.get('sequence')
  if not isinstance(value,str) or not re.fullmatch('[ACGT]{20}',value) or value in sequences:raise ValueError('Each guide must be a unique, unambiguous 20-base DNA spacer.')
  ids.add(g['id']);sequences.add(value)
 reference=p.get('reference',{})
 if not isinstance(reference,dict):raise ValueError('Choose a structured reference snapshot.')
 if reference.get('kind')=='inline':
  if not isinstance(reference.get('assembly'),str) or not 1<=len(reference['assembly'].strip())<=120:raise ValueError('Name the exact assembly or synthetic reference; inline FASTA is not automatically genome-wide.')
  if reference.get('topology') not in ('linear','circular'):raise ValueError('Declare reference topology explicitly.')
  fasta_records(reference.get('fasta'))
 elif reference.get('kind')=='catalog':
  if reference.get('id') not in MANIFEST['references'] or not re.fullmatch('[a-f0-9]{64}',str(reference.get('fastaSha256',''))):raise ValueError('Choose an installed reference and its exact FASTA SHA-256 receipt.')
 else:raise ValueError('Choose an explicit FASTA or a reviewed installed reference.')
 return p

def search_reference(records,width,topology):
 # Real circular contigs need wrap-around windows. Extra bases are only a
 # disposable search view; the source reference and reported coordinates stay intact.
 return {key:value+(value[:width-1] if topology=='circular' and len(value)>=width else '') for key,value in records.items()}

def validate_window(p):
 ref=p.get('reference',{})
 if not isinstance(ref,dict) or ref.get('id') not in MANIFEST['references'] or not re.fullmatch('[a-f0-9]{64}',str(ref.get('fastaSha256',''))):raise ValueError('Select a reviewed installed reference and its exact checksum.')
 size=MANIFEST['references'][ref['id']]['contigs'].get(p.get('contig'))
 if size is None or type(p.get('start'))is not int or type(p.get('end'))is not int or not 1<=p['start']<=p['end']<=size or p['end']-p['start']>=10000 or type(p.get('strand'))is not int or p['strand'] not in (-1,1):raise ValueError('Select an existing contig, 1-based inclusive window of up to 10,000 bases and explicit strand.')
 return p

def reference_window(p):
 cloud_only();validate_window(p);ref=p['reference'];path,receipt=verify_reference(ref['id'],ref['fastaSha256'])
 records=fasta_records(path.read_text(),limit=MANIFEST['references'][ref['id']]['maximumUncompressedBytes']);sequence=records[p['contig']][p['start']-1:p['end']]
 if p['strand']==-1:sequence=reverse_complement(sequence)
 return {'sequence':sequence,'contig':p['contig'],'start':p['start'],'end':p['end'],'strand':p['strand'],'reference':receipt,'sequenceSha256':hashlib.sha256(sequence.encode()).hexdigest(),'evidence':'curated_annotation','coordinateConvention':'1-based inclusive on original forward contig; returned sequence follows the requested strand.','scope':'Observed bases from this pinned reference assembly. No guide quality, gene annotation or functional interpretation inferred.'}
def input_text(reference_path,p):
 return str(reference_path)+'\n'+'N'*20+p['pam']+'\n'+''.join(g['sequence']+'N'*len(p['pam'])+' '+str(p['mismatches'])+' '+g['id']+'\n' for g in p['guides'])
def parse_output(text,p,records):
 width=20+len(p['pam']);topology=p['reference'].get('topology') if p['reference']['kind']=='inline' else MANIFEST['references'][p['reference']['id']]['topology']
 searched=search_reference(records,width,topology);by_id={g['id']:g for g in p['guides']};rows=[];seen=set()
 for line in text.splitlines():
  if not line.strip():continue
  fields=line.split('\t')
  if len(fields)!=7:raise ValueError('Cas-OFFinder output differs from the pinned seven-column format.')
  query,contig,offset,dna,strand,mismatch,identity=fields
  if identity not in by_id or query!=by_id[identity]['sequence']+'N'*len(p['pam']) or contig not in records or strand not in ('+','-'):raise ValueError('Unexpected guide, contig or strand in upstream output.')
  start=int(offset);mm=int(mismatch);source=records[contig]
  if start<0 or start>=len(source) or start+width>len(searched[contig]):raise ValueError('Upstream coordinates exceed the supplied reference.')
  actual=searched[contig][start:start+width];actual=actual if strand=='+' else reverse_complement(actual)
  if actual!=dna.upper() or not re.fullmatch('[ACGTN]{'+str(width)+'}',actual):raise ValueError('Upstream sequence does not match the original reference coordinates.')
  observed_mm=sum(x!=y for x,y in zip(actual[:20],by_id[identity]['sequence']))
  # Ambiguous reference bases are never evidence of a definite match.
  if 'N' in actual:raise ValueError('Upstream returned an ambiguous reference site; no definite match can be assigned.')
  if mm!=observed_mm or mm>p['mismatches'] or any(base not in IUPAC[code] for base,code in zip(actual[20:],p['pam'])):raise ValueError('Upstream mismatch/PAM result failed independent sequence checks.')
  key=(identity,contig,start,strand)
  if key in seen:raise ValueError('Duplicate upstream site; enumeration is not accepted.')
  seen.add(key);wrap=start+width>len(source)
  intervals=[{'start':start+1,'end':len(source)},{'start':1,'end':start+width-len(source)}] if wrap else [{'start':start+1,'end':start+width}]
  rows.append({'guideId':identity,'spacer':by_id[identity]['sequence'],'contig':contig,'start':start+1,'end':(start+width-1)%len(source)+1,'strand':strand,'intervals':intervals,'wrapsOrigin':wrap,'sequence5to3':actual,'rawSequence':dna,'mismatches':mm,'mismatchPositions':[i+1 for i,(x,y) in enumerate(zip(actual[:20],by_id[identity]['sequence'])) if x!=y],'pam':actual[20:],'upstreamStart0':start})
  if len(rows)>MAX_HITS:raise ValueError('More than 10,000 matches; narrow the workload. Partial output is preserved remotely but is not a complete result.')
 return sorted(rows,key=lambda r:(r['guideId'],r['mismatches'],r['contig'],r['start'],r['strand']))

def execute(p):
 cloud_only();validate_input(p);binary,tool=verify_tool();ref=p['reference']
 if ref['kind']=='inline':
  raw=ref['fasta'].encode();records=fasta_records(ref['fasta']);receipt={'assembly':ref['assembly'],'coverage':'supplied_sequence_only','topology':ref['topology'],'fastaSha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw),'source':'approved_inline_fasta','contigs':{k:{'length':len(v),'sequenceSha256':hashlib.sha256(v.encode()).hexdigest()} for k,v in records.items()}}
 else:
  source,receipt=verify_reference(ref['id'],ref['fastaSha256']);records=fasta_records(source.read_text(),limit=MANIFEST['references'][ref['id']]['maximumUncompressedBytes'])
 width=20+len(p['pam']);searched=search_reference(records,width,receipt['topology'])
 parent=pathlib.Path(os.environ['FOLD_EDITCRAFT_JOB_DIR']);folder=pathlib.Path(tempfile.mkdtemp(prefix='cas-offinder-',dir=parent))
 reference=folder/'search-reference.fa';reference.write_text(''.join('>'+key+'\n'+value+'\n' for key,value in searched.items()))
 input_file=folder/'input.txt';input_file.write_text(input_text(reference,p));output=folder/'output.tsv';log=folder/'execution.log';started=time.monotonic()
 env={**os.environ,'OMP_NUM_THREADS':'2','POCL_MAX_PTHREAD_COUNT':'2'}
 with log.open('wb') as stream:
  child=subprocess.Popen([str(binary),str(input_file),'C',str(output)],stdout=stream,stderr=stream,env=env)
  try:
   while child.poll() is None:
    if output.exists() and output.stat().st_size>4*1024**2 or log.stat().st_size>4*1024**2:raise ValueError('Scientific output exceeded its explicit storage bound; no partial enumeration accepted.')
    time.sleep(.1)
   if child.returncode:raise RuntimeError('Pinned Cas-OFFinder CPU calculation failed. Original logs are retained remotely.')
  finally:
   if child.poll() is None:child.terminate();child.wait(timeout=5)
 # Upstream does not necessarily create a file for zero matches. A successful
 # process with an empty file or no file is a genuine zero; nonzero exit never is.
 raw=output.read_text() if output.is_file() else '';rows=parse_output(raw,p,records)
 return {'method':'Cas-OFFinder '+MANIFEST['casOffinder']['version'],'endpoint':'Potential sequence matches, including any intended sites','units':'Enumerated sites; not a cutting/activity probability','rows':rows,'siteCount':len(rows),'reference':receipt,'parameters':{'nuclease':p['nuclease'],'pam':p['pam'],'mismatches':p['mismatches'],'bulges':False,'device':'CPU'},'rawOutputTSV':raw,'rawOutputSha256':hashlib.sha256(raw.encode()).hexdigest(),'elapsedSeconds':time.monotonic()-started,'coordinateConvention':'1-based inclusive on original forward contig; upstream zero-based start retained. Circular sites use explicit split intervals; sequences are guide-oriented 5′→3′.','provenance':tool,'artifacts':{'folder':str(folder),'logSha256':hashlib.sha256(log.read_bytes()).hexdigest()},'scope':'Sequence-match enumeration within this exact reference and mismatch/PAM limit. Includes intended and unintended sites. No bulge search, variant/pangenome search, cleavage likelihood, genomic annotation, measured editing or clinical safety inferred. N-masked bases are unresolved. Complete-assembly coverage is reported only for an installed assembly whose full contig manifest was verified.'}
