"""Annotation-directed sequence assembly and isolated Biopython translation."""
import hashlib,json,pathlib,re,subprocess,sys

def assemble(sequences,features,circular,index,kind):
 from genome_workspace import region
 if type(index) is not int or not 0<=index<len(features) or kind not in ('cds','transcript'):raise ValueError('Choose an existing CDS or transcript annotation.')
 selected=features[index];identifier=selected['attributes'].get('ID')
 if kind=='cds':
  if selected['type']!='CDS':raise ValueError('Select a CDS annotation explicitly; gene/isoform choice is not inferred.')
  parts=[f for f in features if f['type']=='CDS' and f['attributes'].get('ID')==identifier] if identifier else [selected]
 else:
  if selected['type'] not in ('mRNA','transcript','ncRNA','rRNA','tRNA') or not identifier:raise ValueError('Select a named transcript/RNA annotation.')
  parts=[f for f in features if f['type']=='exon' and identifier in f.get('parents',[])]
  if not parts:raise ValueError('This transcript has no explicit exon annotations; a mature transcript cannot be inferred.')
 replicons={f['replicon'] for f in parts};strands={f['strand'] for f in parts}
 if len(replicons)!=1 or len(strands)!=1 or selected['strand'] not in ('+','-'):raise ValueError('Product segments must share one explicit replicon and strand.')
 replicon=parts[0]['replicon'];strand=parts[0]['strand']
 if strand!=selected['strand'] or replicon!=selected['replicon']:raise ValueError('Product identity differs from the selected annotation.')
 if len(parts)>1 and (replicon in circular or any('part' in f['attributes'] for f in parts)):
  ranks=[]
  for part in parts:
   value=part['attributes'].get('part','');match=re.fullmatch(r'(\d+)/(\d+)',value)
   if not match or int(match[2])!=len(parts):raise ValueError('Multiple segments on a circular replicon require explicit complete part=rank/count ordering.')
   ranks.append(int(match[1]))
  if sorted(ranks)!=list(range(1,len(parts)+1)):raise ValueError('Segment ranks are duplicated or incomplete.')
  parts=[p for _,p in sorted(zip(ranks,parts),key=lambda v:v[0])]
 else:parts=sorted(parts,key=lambda f:f['start'],reverse=strand=='-')
 intervals=sorted((f['start'],f['end']) for f in parts)
 if any(right[0]<=left[1] for left,right in zip(intervals,intervals[1:])):raise ValueError('Overlapping product segments require an explicit exceptional translation model.')
 if sum(f['end']-f['start']+1 for f in parts)>100000:raise ValueError('Product assembly supports at most 100,000 bases.')
 dna='';initial_phase=0
 for number,part in enumerate(parts):
  segment=region(sequences[replicon],part['start'],part['end'],strand,replicon in circular)
  if kind=='cds':
   if part['phase'] not in ('0','1','2'):raise ValueError('Every CDS segment requires an explicit GFF3 phase.')
   phase=int(part['phase'])
   if number==0:
    initial_phase=phase
    if phase>=len(segment):raise ValueError('Initial phase removes the complete segment.')
    segment=segment[phase:]
   elif phase!=(3-len(dna)%3)%3:raise ValueError('CDS segment phase is inconsistent with the preceding coding bases.')
  dna+=segment
 exceptional=any(any(key in f['attributes'] for key in ('transl_except','exception','pseudo','pseudogene')) for f in parts)
 return {'kind':kind,'selectedFeatureIndex':index,'annotationId':identifier,'replicon':replicon,'strand':strand,'segments':parts,'initialPhaseBasesSkipped':initial_phase,'dna':dna,'rna':dna.replace('T','U'),'sequenceSha256':hashlib.sha256(dna.encode()).hexdigest(),'trailingIncompleteCodonBases':len(dna)%3 if kind=='cds' else None,'exceptionalAnnotation':exceptional,'scope':'Assembled exclusively from supplied annotation segments. Initial CDS phase is skipped once; internal phases are validated without discarding junction bases. No expression or mature RNA/protein measurement is inferred. Circular multi-segment ordering must be explicit.'}

def translate(s,product,table,complete):
 if type(table) is not int or table not in (1,11) or type(complete) is not bool:raise ValueError('Choose genetic code 1 or 11 and an explicit complete-CDS option.')
 if product['kind']!='cds' or product['exceptionalAnnotation']:raise ValueError('Translation requires an ordinary CDS without annotated exceptions or pseudogene flags.')
 if complete and product['initialPhaseBasesSkipped']:raise ValueError('An initial nonzero phase cannot be treated as a complete CDS.')
 request={'dna':product['dna'],'table':table,'complete':complete}
 result=subprocess.run([s.engine_python(),'-I','-B',str(pathlib.Path(__file__).resolve())],input=json.dumps(request),text=True,capture_output=True,timeout=30)
 if result.returncode:raise ValueError('Biopython translation failed: '+result.stderr.strip()[-1000:])
 value=json.loads(result.stdout);value['runnerSha256']=hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest();return value

if __name__=='__main__':
 import Bio
 from Bio.Seq import Seq
 request=json.load(sys.stdin);dna=request['dna'];complete=request['complete'];coding=dna if complete else dna[:len(dna)//3*3]
 protein=str(Seq(coding).translate(table=request['table'],cds=complete,to_stop=False))
 print(json.dumps({'protein':protein,'proteinSha256':hashlib.sha256(protein.encode()).hexdigest(),'biopythonVersion':Bio.__version__,'translationTable':request['table'],'completeCDSValidated':complete,'trailingBasesNotTranslated':len(dna)-len(coding),'scope':'Complete mode checks start/stop/frame and applies code-specific initiation. Partial mode translates complete codons only, retains internal stops, and does not infer initiator methionine or mature protein processing.'},allow_nan=False))
