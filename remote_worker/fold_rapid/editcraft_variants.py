"""Assembly-checked Ensembl VEP annotation. No pathogenicity/efficacy inference.

Official REST contracts:
https://rest.ensembl.org/documentation/info/vep_region_post
https://rest.ensembl.org/documentation/info/sequence_region
The GRCh37 host is distinct; coordinates are never silently lifted over.
"""
import datetime,hashlib,json,re,urllib.request,urllib.parse
HOSTS={'GRCh38':'https://rest.ensembl.org','GRCh37':'https://grch37.rest.ensembl.org'}
def validate_input(p):
 if not isinstance(p,dict) or p.get('assembly') not in HOSTS:raise ValueError('Select GRCh38 or GRCh37 explicitly. No coordinate conversion is inferred.')
 if not isinstance(p.get('chromosome'),str) or not re.fullmatch('(?:[1-9]|1[0-9]|2[0-2]|X|Y|MT)',p['chromosome']):raise ValueError('Use an explicit human primary chromosome (1–22, X, Y or MT).')
 if type(p.get('position'))is not int or not 1<=p['position']<=300000000:raise ValueError('Variant position must be 1-based on the selected forward reference.')
 if any(not isinstance(p.get(k),str) or not re.fullmatch('[ACGT]',p[k]) for k in ('ref','alt')) or p['ref']==p['alt']:raise ValueError('This annotation contract accepts one explicit SNV; indels, normalization and structural variants require separate supported workflows.')
 return p
def request(host,path,body=None):
 if host not in HOSTS.values():raise ValueError('Reference host is not an official reviewed Ensembl endpoint.')
 raw_body=json.dumps(body,sort_keys=True,separators=(',',':')).encode() if body is not None else None
 req=urllib.request.Request(host+path,data=raw_body,headers={'Content-Type':'application/json','Accept':'application/json','User-Agent':'FoldStudio-EditCraft/0.3 research'})
 with urllib.request.urlopen(req,timeout=30) as response:raw=response.read(2*1024**2+1)
 if len(raw)>2*1024**2:raise ValueError('Ensembl response exceeds the bounded variant annotation size.')
 return json.loads(raw),{'url':host+path,'method':'POST' if body is not None else 'GET','requestBodySha256':hashlib.sha256(raw_body).hexdigest() if raw_body is not None else None,'responseSha256':hashlib.sha256(raw).hexdigest(),'retrieved':datetime.datetime.now(datetime.timezone.utc).isoformat(),'rawResponseJSON':raw.decode('utf-8')}
def annotate(p):
 validate_input(p);host=HOSTS[p['assembly']];receipts=[]
 assembly,r=request(host,'/info/assembly/homo_sapiens?content-type=application/json');receipts.append(r)
 name=assembly.get('assembly_name','')
 if name!=p['assembly'] and not name.startswith(p['assembly']+'.'):raise ValueError('The selected reference service no longer serves this assembly; do not reinterpret the coordinates.')
 releases,r=request(host,'/info/data?content-type=application/json');receipts.append(r)
 region=p['chromosome']+':'+str(p['position'])+'..'+str(p['position'])+':1'
 base,r=request(host,'/sequence/region/homo_sapiens/'+region+'?content-type=application/json');receipts.append(r)
 if base.get('seq','').upper()!=p['ref']:raise ValueError('Reference allele does not match this assembly at the requested coordinate; no VEP annotation was submitted.')
 original=' '.join([p['chromosome'],str(p['position']),'fold_variant',p['ref'],p['alt'],'.','.','.'])
 results,r=request(host,'/vep/homo_sapiens/region?hgvs=1&transcript_version=1',{'variants':[original]});receipts.append(r)
 if not isinstance(results,list) or len(results)!=1:raise ValueError('VEP did not return exactly the submitted variant.')
 result=results[0]
 if result.get('assembly_name')!=p['assembly'] or str(result.get('seq_region_name'))!=p['chromosome'] or result.get('start')!=p['position'] or result.get('end')!=p['position'] or result.get('strand')!=1 or result.get('allele_string')!=p['ref']+'/'+p['alt']:raise ValueError('VEP result identity, assembly, strand or alleles differ from the approved input.')
 if not isinstance(result.get('transcript_consequences',[]),list):raise ValueError('Unexpected VEP transcript consequence schema.')
 return {'method':'Ensembl Variant Effect Predictor REST','variant':p,'assemblyName':name,'referenceAlleleVerified':True,'referenceSequenceRecord':base,'ensemblDataReleases':releases,'mostSevereConsequence':result.get('most_severe_consequence'),'transcriptConsequences':result.get('transcript_consequences',[]),'originalVEPResult':result,'sources':receipts,'evidence':'computational_prediction','coordinateConvention':'1-based forward genomic SNV coordinates, explicitly selected assembly; transcript consequences retain original transcript IDs, versions, strand and HGVSc/HGVSp where returned.','scope':'Reference-checked VEP consequence annotation for a human SNV. Consequence terms and IMPACT labels are annotations, not measured molecular effects, calibrated pathogenicity, editor performance or treatment efficacy. No indel normalization, liftover, haplotype, clinical interpretation or structural variant support inferred.'}
