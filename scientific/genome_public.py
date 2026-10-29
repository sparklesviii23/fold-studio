"""Bounded public NCBI DNA-reference discovery and pinned GenBank retrieval."""
import base64,datetime,hashlib,json,pathlib,re,time,urllib.parse,urllib.request
BASE='https://eutils.ncbi.nlm.nih.gov/entrez/eutils/'
MAX_BASES=6000000
ACCESSION=re.compile(r'[A-Z][A-Z0-9_]{1,30}\.[0-9]{1,4}')

def retrieve(endpoint,parameters,limit):
 url=BASE+endpoint+'?'+urllib.parse.urlencode({**parameters,'tool':'foldstudio'})
 request=urllib.request.Request(url,headers={'User-Agent':'FoldStudio-Genome/1.0 public-reference research'})
 blocks=[];size=0;started=time.monotonic()
 with urllib.request.urlopen(request,timeout=25) as response:
  while block:=response.read(min(65536,limit-size+1)):
   size+=len(block)
   if size>limit or time.monotonic()-started>60:raise ValueError('Public reference transfer exceeded its bounded size/time; no reference was saved.')
   blocks.append(block)
 raw=b''.join(blocks)
 return raw,{'url':url,'sha256':hashlib.sha256(raw).hexdigest(),'retrievedUTC':datetime.datetime.now(datetime.timezone.utc).isoformat()}

def ncbi_json(endpoint,parameters):
 raw,receipt=retrieve(endpoint,{**parameters,'retmode':'json'},1024**2);value=json.loads(raw)
 if value.get('error'):raise ValueError('NCBI could not resolve this public reference request.')
 return value,receipt

def describe(row,receipt):
 accession=row.get('accessionversion');length=row.get('slen');organism=row.get('organism')
 if not isinstance(accession,str) or not ACCESSION.fullmatch(accession) or type(length)is not int or length<1 or not isinstance(organism,str) or not organism.strip():raise ValueError('NCBI summary lacks a versioned sequence identity, length or organism.')
 canonical=json.dumps(row,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
 return {'accession':accession,'organism':organism,'strain':row.get('strain'),'taxid':row.get('taxid'),'length':length,'title':row.get('title'),'topology':row.get('topology'),'geneticCodeReported':row.get('geneticcode'),'sequenceClass':row.get('genome'),'sourceDatabase':row.get('sourcedb'),'summarySha256':hashlib.sha256(canonical).hexdigest(),'originalSummary':row,'summaryReceipt':receipt,'downloadSupported':row.get('moltype','').lower()=='dna' and length<=MAX_BASES,'scope':'NCBI sequence-record metadata. A sequence accession is not a verified assembly accession; assembly quality and strain safety are not inferred.'}

def summary(accession):
 if not isinstance(accession,str) or not ACCESSION.fullmatch(accession):raise ValueError('Supply an explicit versioned NCBI sequence accession, for example NC_000913.3.')
 data,receipt=ncbi_json('esummary.fcgi',{'db':'nuccore','id':accession});result=data.get('result',{});ids=result.get('uids',[])
 if len(ids)!=1 or ids[0] not in result:raise ValueError('NCBI did not resolve exactly one sequence record.')
 described=describe(result[ids[0]],receipt)
 if described['accession']!=accession:raise ValueError('NCBI resolved a different sequence version; review its exact accession explicitly.')
 return described

def search(query):
 if not isinstance(query,str) or not 2<=len(query.strip())<=120 or any(ord(c)<32 for c in query):raise ValueError('Enter a bounded organism/strain/reference search of 2–120 characters.')
 data,receipt=ncbi_json('esearch.fcgi',{'db':'nuccore','term':'('+query.strip()+') AND biomol_genomic[PROP] AND srcdb_refseq[PROP]','retmax':10})
 result=data.get('esearchresult',{});ids=result.get('idlist',[])
 if not isinstance(ids,list) or len(ids)>10 or any(not isinstance(uid,str) or not uid.isdigit() for uid in ids):raise ValueError('NCBI search returned unsupported identities.')
 records=[]
 if ids:
  # Two public requests stay below NCBI's anonymous three-requests/second guidance.
  time.sleep(.35);values,summary_receipt=ncbi_json('esummary.fcgi',{'db':'nuccore','id':','.join(ids)})
  for uid in ids:records.append(describe(values.get('result',{}).get(uid,{}),summary_receipt))
 return {'query':query,'total':int(result.get('count',0)),'records':records,'searchReceipt':receipt,'scope':'Up to ten original NCBI genomic RefSeq metadata matches. Downloads require selecting and reviewing one versioned DNA record, at most 6,000,000 bases and 32 MiB annotated transfer. Large whole-human-genome indexing is not implemented.'}

def fetch(s,p):
 from genome_annotated import parse_annotated,publish_annotated
 from genome_workspace import fasta,references,LIMIT
 if p.get('approvedReferenceDownload')is not True:raise ValueError('Review and explicitly request this public-reference download first.')
 reviewed=summary(p.get('accession'))
 if reviewed['summarySha256']!=p.get('expectedSummarySha256'):raise ValueError('Public reference metadata changed; review the current sequence record before downloading.')
 if not reviewed['downloadSupported']:raise ValueError('This importer supports DNA sequence records up to 6,000,000 bases; no large/unsupported transfer started.')
 time.sleep(.35);raw,receipt=retrieve('efetch.fcgi',{'db':'nuccore','id':reviewed['accession'],'rettype':'gbwithparts','retmode':'text'},LIMIT)
 value=parse_annotated(s,raw.decode('utf-8'), 'genbank');seqs=fasta(value['fasta'])
 if list(seqs)!=[reviewed['accession']] or len(seqs[reviewed['accession']])!=reviewed['length'] or value['reportedRecords'][0].get('organism')!=reviewed['organism']:raise ValueError('Downloaded GenBank identity/length/organism differs from the reviewed record; nothing was saved.')
 for existing in references(s,p['projectId']):
  if any(source['kind']=='genbank' and source['sha256']==receipt['sha256'] for source in existing['sources']):return {**existing,'publicFetchState':'already_imported'}
 metadata={'organism':reviewed['organism'],'assembly':'Sequence '+reviewed['accession']+'; assembly accession unresolved','source':receipt['url'],'taxid':reviewed['taxid'],'strain':reviewed['strain'],'publicReferenceReview':reviewed,'originalDownloadReceipt':receipt}
 result=publish_annotated(s,{'projectId':p['projectId'],'metadata':metadata},reviewed['accession']+'.gbff',raw,value)
 return {**result,'publicFetchState':'imported'}
