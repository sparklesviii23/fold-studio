"""Bounded explicit-allele VCF inspection; no genotype or clinical interpretation."""
import base64,hashlib,json,pathlib,math
LIMIT=1024**2

def parse(text,sequences):
 lines=text.splitlines();header=None;rows=[];metadata=[]
 if not lines or lines[0] not in ('##fileformat=VCFv4.2','##fileformat=VCFv4.3'):raise ValueError('This bounded importer supports explicit VCFv4.2/4.3 files.')
 for number,line in enumerate(lines,1):
  if line.startswith('##'):
   if header:raise ValueError('VCF metadata must precede its column header.')
   metadata.append(line);continue
  if line.startswith('#'):
   cells=line.split('\t')
   sample_header_invalid=len(cells)>8 and (cells[8]!='FORMAT' or len(cells)==9 or len(set(cells[9:]))!=len(cells[9:]) or any(not sample or any(c.isspace() for c in sample) for sample in cells[9:]))
   if header or cells[:8]!=['#CHROM','POS','ID','REF','ALT','QUAL','FILTER','INFO'] or sample_header_invalid:raise ValueError('VCF requires one valid tab-separated header; optional samples need FORMAT and unique sample IDs.')
   header=cells;continue
  if not line:continue
  cells=line.split('\t')
  if header is None or len(cells)!=len(header):raise ValueError('VCF data columns differ from the explicit header.')
  chrom,pos,identifier,ref,alts,quality,filters,info=cells[:8]
  if chrom not in sequences or not pos.isdigit() or int(pos)<1:raise ValueError('VCF contig/position does not match the selected reference; aliases are not inferred.')
  alternatives=alts.split(',');start=int(pos);end=start+len(ref)-1
  if any(not 1<=len(a)<=1000 or set(a)-set('ACGT') for a in [ref,*alternatives]) or ref in alternatives or len(set(alternatives))!=len(alternatives):raise ValueError('Supply distinct explicit uppercase REF/ALT alleles up to 1,000 bases. Symbolic, spanning-deletion, breakend and gVCF alleles need a separate adapter.')
  if end>len(sequences[chrom]) or sequences[chrom][start-1:end]!=ref:raise ValueError('VCF REF does not match the original forward reference at source line '+str(number)+'.')
  if quality!='.':
   try:q=float(quality)
   except ValueError:raise ValueError('VCF QUAL must be numeric or missing.') from None
   if not math.isfinite(q) or q<0:raise ValueError('VCF QUAL must be finite and nonnegative.')
  if not filters or not info or not identifier:raise ValueError('VCF missing fields must use a dot explicitly.')
  rows.append({'sourceLine':number,'replicon':chrom,'position':start,'end':end,'id':identifier,'ref':ref,'alts':alternatives,'qualRaw':quality,'filterRaw':filters,'infoRaw':info})
  if len(rows)>2000:raise ValueError('At most 2,000 supplied VCF rows are supported.')
 if header is None or not rows:raise ValueError('No supported VCF rows supplied.')
 return {'format':lines[0].split('=',1)[1],'metadataRaw':metadata,'header':header,'rows':rows,'sampleColumnsRetainedOnlyInOriginal':max(0,len(header)-9)}

def saved(s,project,reference):
 records=s.rows("SELECT id,data FROM records WHERE project_id=? AND kind='analysis' AND json_extract(data,'$.domain')='genome_variant_set' AND json_extract(data,'$.referenceId')=? LIMIT 21",(project,reference))
 if len(records)>20:raise ValueError('This bounded viewer supports up to 20 VCF sets per reference; choose a smaller project.')
 result=[]
 for record in records:
  data=json.loads(record['data']);raw=base64.b64decode(data['originalFileBase64'],validate=True)
  if len(raw)>LIMIT or hashlib.sha256(raw).hexdigest()!=data['sourceFileSha256'] or hashlib.sha256(json.dumps(data['rows'],sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()!=data.get('parsedRowsSha256'):raise ValueError('Saved VCF original bytes or parsed rows changed; preserve and inspect the record.')
  result.append({'recordId':record['id'],**data})
 return result

def import_vcf(s,p,reference,sequences):
 from genome_workspace import raw_file
 name,raw,text=raw_file(p['path'],('.vcf',))
 if len(raw)>LIMIT or len(text.encode())>LIMIT:raise ValueError('VCF import is limited to 1 MiB compressed and expanded.')
 parsed=parse(text,sequences);sha=hashlib.sha256(raw).hexdigest()
 sets=saved(s,p['projectId'],reference['id']);existing=next((row for row in sets if row['sourceFileSha256']==sha),None)
 if existing:return {'state':'already_imported','recordId':existing['recordId'],'rowCount':len(existing['rows']),'sourceFileSha256':sha}
 if len(sets)>=20:raise ValueError('This bounded viewer supports up to 20 VCF sets per reference.')
 data={'parsedRowsSha256':hashlib.sha256(json.dumps(parsed['rows'],sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest(),'domain':'genome_variant_set','referenceId':reference['id'],'referenceSources':reference['sources'],'metadata':reference['metadata'],'sourceFileName':name,'sourceFileSha256':sha,'originalFileBase64':base64.b64encode(raw).decode(),**parsed,'scope':'Supplied explicit alleles checked against this exact forward reference. Original VCF and sample/genotype fields retained without genotype/phase interpretation. FILTER/QUAL/INFO are original assertions, not independently validated calls. No allele normalization, liftover, haplotype, expression, clinical or fitness inference.'}
 record=s.record_save({'projectId':p['projectId'],'kind':'analysis','name':'Reference-checked VCF · '+name,'data':data})
 return {'state':'imported','recordId':record['id'],'rowCount':len(parsed['rows']),'sourceFileSha256':sha,'scope':data['scope']}

def window(s,project,reference,replicon,start,length,replicon_length,circular):
 from genome_workspace import window_annotations
 features=[]
 for record in saved(s,project,reference):
  for row in record['rows']:
   features.append({'index':len(features),'replicon':row['replicon'],'start':row['position'],'end':row['end'],'strand':'.','type':'supplied_variant','attributes':{'ID':row['id'],'Name':row['ref']+'→'+','.join(row['alts'])},'variant':row,'recordId':record['recordId'],'sourceFileSha256':record['sourceFileSha256']})
 result=window_annotations(features,replicon,start,length,replicon_length,circular)
 result['scope']='Reference-checked supplied VCF alleles, displayed over their REF span. Insertion anchors remain explicit. Filters and sample genotypes are not interpreted; no inferred clinical or functional consequences.'
 return result
