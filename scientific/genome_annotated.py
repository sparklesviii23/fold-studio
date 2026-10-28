"""Original GenBank/EMBL preserved; Biopython supplies reference/feature parsing."""
import json,pathlib,subprocess,sys,tempfile

def import_annotated(s,p):
 from genome_workspace import raw_file,import_reference
 fmt=p.get('format')
 if fmt not in ('genbank','embl'):raise ValueError('Choose explicit GenBank or EMBL format.')
 name,raw,text=raw_file(p['path'],('.gb','.gbk','.gbff') if fmt=='genbank' else ('.embl',))
 result=subprocess.run([s.engine_python(),'-I','-B',str(pathlib.Path(__file__).resolve())],input=json.dumps({'text':text,'format':fmt}),text=True,capture_output=True,timeout=60)
 if result.returncode:raise ValueError('Biopython annotated-reference parsing failed: '+result.stderr.strip()[-1500:])
 value=json.loads(result.stdout)
 with tempfile.TemporaryDirectory(prefix='genome-format-',dir=s.root/'cache') as tmp:
  fasta=pathlib.Path(tmp)/'derived.fasta';gff=pathlib.Path(tmp)/'derived.gff3';fasta.write_text(value['fasta']);gff.write_text(value['gff3'])
  metadata={**p.get('metadata',{}),'annotatedFormatConversion':{key:value[key] for key in ('format','biopythonVersion','reportedRecords','warnings','scope')}}
  return import_reference(s,{'projectId':p['projectId'],'metadata':metadata,'fastaPath':str(fasta),'gffPath':str(gff),'circularReplicons':value['circular']},[(fmt,name,raw)])

def normalize(text,fmt):
 import Bio,io,urllib.parse
 from Bio import SeqIO
 from Bio.SeqFeature import ExactPosition
 fasta=[];gff=['##gff-version 3'];reported=[];circular=[];warnings=[];ids=set();total=0;row_count=0
 quote=lambda text:urllib.parse.quote(str(text),safe=':._-')
 for record in SeqIO.parse(io.StringIO(text),fmt):
  if len(ids)>=1000 or record.id in ids or not record.id or any(c.isspace() for c in record.id):raise ValueError('Reference records must have distinct bounded identifiers.')
  ids.add(record.id);sequence=str(record.seq).upper();total+=len(sequence)
  if not sequence or set(sequence)-set('ACGTRYSWKMBDHVN') or total>32*1024**2:raise ValueError('Annotated DNA is empty, unsupported or exceeds 32 MiB.')
  fasta.append('>'+record.id+'\n'+sequence)
  topology=record.annotations.get('topology','unknown')
  if topology=='circular':circular.append(record.id)
  reported.append({'id':record.id,'description':record.description,'organism':record.annotations.get('organism'),'topology':topology,'accessions':record.annotations.get('accessions',[])})
  for number,feature in enumerate(record.features):
   if feature.type=='source':continue
   location=feature.location
   if not location or any(type(position) is not ExactPosition for part in location.parts for position in (part.start,part.end)) or any(part.ref is not None for part in location.parts):
    warnings.append({'record':record.id,'featureIndex':number,'reason':'Unresolved/fuzzy or remote location retained only in original source.'});continue
   strands={part.strand for part in location.parts}
   if len(strands)!=1 or next(iter(strands)) not in (-1,1):
    warnings.append({'record':record.id,'featureIndex':number,'reason':'Unoriented feature retained only in original source.'});continue
   strand='+' if location.strand==1 else '-';identifier=record.id+':feature:'+str(number);qual=feature.qualifiers
   attrs={'ID':identifier,'Name':(qual.get('gene') or qual.get('locus_tag') or qual.get('product') or [feature.type])[0]}
   for key in ('gene','locus_tag','protein_id','product','translation','transl_table','pseudo','pseudogene','exception','transl_except','experiment','inference','note'):
    if key in qual:attrs[key]=' | '.join(qual[key])
   phase=int(qual.get('codon_start',['1'])[0])-1 if feature.type=='CDS' else 0
   if phase not in (0,1,2):raise ValueError('Unsupported annotated codon_start.')
   assembled=0
   for rank,part in enumerate(location.parts,1):
    if not 0<=int(part.start)<int(part.end)<=len(sequence):raise ValueError('Feature lies outside its annotated record.')
    current_phase=phase if rank==1 else (3-assembled%3)%3
    extra={**attrs,'part':str(rank)+'/'+str(len(location.parts))}
    gff.append('\t'.join((record.id,'Biopython_'+fmt,feature.type,str(int(part.start)+1),str(int(part.end)),'.',strand,str(current_phase) if feature.type=='CDS' else '.', ';'.join(key+'='+quote(value) for key,value in extra.items()))))
    assembled+=int(part.end)-int(part.start)-(phase if rank==1 and feature.type=='CDS' else 0);row_count+=1
    if row_count>100000:raise ValueError('Feature expansion exceeds 100,000 annotation rows.')
 if not ids:raise ValueError('No annotated reference record parsed.')
 gff_text='\n'.join(gff)+'\n'
 if len(gff_text.encode())>32*1024**2:raise ValueError('Derived annotation exceeds 32 MiB.')
 return {'format':fmt,'biopythonVersion':Bio.__version__,'fasta':'\n'.join(fasta)+'\n','gff3':gff_text,'reportedRecords':reported,'circular':circular,'warnings':warnings,'scope':'Biopython parsed original annotated records. Exact oriented locations are mapped to ranked GFF3 segments; unresolved locations are not guessed. Original bytes and qualifiers remain available. No inferred exon/transcript structure, essentiality or expression.'}

if __name__=='__main__':
 request=json.load(sys.stdin);print(json.dumps(normalize(request['text'],request['format']),allow_nan=False))
