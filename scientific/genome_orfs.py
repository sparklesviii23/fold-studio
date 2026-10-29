"""Complete start-to-stop ORF enumeration; no inferred gene/function/essentiality."""
import hashlib,json,pathlib,subprocess,sys

def analyze(s,p,reference,sequences):
 from genome_workspace import region
 table=p.get('translationTable');minimum=p.get('minimumResidues',20);replicon=p.get('replicon')
 if type(table) is not int or table not in (1,11) or type(minimum) is not int or not 1<=minimum<=1000 or replicon not in sequences:raise ValueError('Choose genetic code 1/11, a known replicon and minimum length of 1–1,000 residues.')
 dna=region(sequences[replicon],p.get('start'),p.get('end'),'+',replicon in reference['circularReplicons'])
 if set(dna)-set('ACGT'):raise ValueError('ORF enumeration requires an unambiguous selected DNA window.')
 child=subprocess.run([s.engine_python(),'-I','-B',str(pathlib.Path(__file__).resolve())],input=json.dumps({'dna':dna,'table':table,'minimum':minimum}),text=True,capture_output=True,timeout=30)
 if child.returncode:raise ValueError('Biopython ORF calculation failed: '+child.stderr.strip()[-1000:])
 result=json.loads(child.stdout);n=len(sequences[replicon])
 for row in result['orfs']:
  row['replicon']=replicon;row['genomicStart']=(p['start']+row['windowStart']-2)%n+1;row['genomicEnd']=row['genomicStart']+row['windowEnd']-row['windowStart']
 result.update(referenceId=reference['id'],metadata=reference['metadata'],sources=reference['sources'],window={'replicon':replicon,'start':p['start'],'end':p['end'],'length':len(dna),'strand':'+'},sequenceSha256=hashlib.sha256(dna.encode()).hexdigest(),implementationSha256=hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(),scope='Complete start-to-stop ORFs in six frames of this supplied window, using recorded Biopython codon tables. Every eligible nested start is counted; partial boundary ORFs are not reported. This is sequence enumeration, not gene prediction, expression, protein-function or essentiality evidence. No ORF is designed or optimized.')
 return result

def scan(dna,table,minimum):
 import Bio
 from Bio.Seq import Seq
 from Bio.Data import CodonTable
 code=CodonTable.unambiguous_dna_by_id[table];starts=set(code.start_codons);stops=set(code.stop_codons);result=[];total=0;n=len(dna)
 for strand,text in [('+',dna),('-',str(Seq(dna).reverse_complement()))]:
  for frame in range(3):
   pending=[]
   for at in range(frame,len(text)-2,3):
    codon=text[at:at+3]
    if codon in stops:
     for start in pending:
      residues=(at-start)//3
      if residues<minimum:continue
      total+=1
      if len(result)<200:result.append({'strand':strand,'windowFrameOffsetZeroBased':frame,'windowStart':start+1 if strand=='+' else n-at-2,'windowEnd':at+3 if strand=='+' else n-start,'startCodon':text[start:start+3],'terminalStopCodon':codon,'residuesExcludingTerminalStop':residues})
     pending=[]
    if codon in starts:pending.append(at)
 return {'translationTable':table,'biopythonVersion':Bio.__version__,'eligibleStartCodons':sorted(starts),'stopCodons':sorted(stops),'minimumResidues':minimum,'orfs':result,'total':total,'omitted':max(0,total-len(result)),'displayOrder':'first 200 in strand/frame/terminal-stop discovery order; not ranked','coordinateConvention':'Window coordinates are 1-based inclusive on its forward DNA. Strand and frame refer to this supplied window, not the absolute assembly frame. Genomic end may be unrolled across an explicitly circular origin.'}

if __name__=='__main__':
 p=json.load(sys.stdin);print(json.dumps(scan(p['dna'],p['table'],p['minimum']),allow_nan=False))
