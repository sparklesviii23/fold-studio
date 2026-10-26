"""EditCraft CPU scientific operations. Production execution is cloud-only.

No trained editor scores or invented structures. Coordinate convention is explicitly
1-based inclusive except exported BED intervals. Model outputs retain their scope.
"""
import csv,datetime,hashlib,io,json,math,re,statistics,urllib.parse,urllib.request,xml.etree.ElementTree as ET
VERSION='0.3.0'
OPS={
 'annotated_import':('annotated_sequence','construct_annotations','Biopython GenBank parser'),
 'motif_find':('sequence_motif','motif_annotations','Exact IUPAC motif enumeration; no activity score'),
 'annotation_parse':('genomic_annotation_file','genomic_annotations','Explicit BED/GFF3/VCF coordinate normalization'),
 'gene_context':('gene_symbol','gene_context','Ensembl REST curated annotation'),
 'sequence_analyze':('sequence','sequence_analysis','Biopython standard genetic code'),
 'rna_fold':('rna','rna_secondary_structure','ViennaRNA minimum free energy'),
 'rna_ensemble':('rna','rna_ensemble','ViennaRNA partition function, centroid, MEA and marginal accessibility'),
 'rs3_activity':('guide_contexts','guide_activity','Rule Set 3 sequence-only trained model'),
 'bedict_per_base':('base_editor_contexts','per_base_edit_predictions','BE-DICT complete five-run ensemble'),
 'pridict2_design':('prime_edit_context','prime_edit_predictions','PRIDICT2 original dual-model five-fold ensembles'),
 'cas_offinder':('guide_reference_search','off_target_matches','Cas-OFFinder 2.4.1 OpenCL CPU sequence-match enumeration'),
 'reference_window':('reference_interval','reference_sequence','Exact pinned assembly sequence and strand-aware coordinates'),
 'variant_vep':('genomic_snv','variant_annotation','Assembly- and allele-checked Ensembl VEP consequence annotation'),
 'variant_cds':('coding_variant','variant_consequence','Reference-checked coding-sequence comparison'),
 'coordinate_map':('genomic_position','transcript_position','Strand-aware exon coordinate mapping'),
 'sequence_align':('sequence_pair','alignment','Biopython PairwiseAligner'),
 'fastq_qc':('fastq','read_quality','Biopython FASTQ parser'),
 'experimental_compare':('matched_measurements','model_assessment','Matched-context numeric comparison'),
 'literature':('literature_query','citations','NCBI PubMed E-utilities'),
}
def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)
def sha(value):return hashlib.sha256(canonical(value).encode()).hexdigest()
def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def bounded(text,limit=200000):
 if not isinstance(text,str) or not 0<len(text)<=limit:raise ValueError('Input is empty or exceeds this operation’s bounded input size.')
 return text

def sequence(text,kind='DNA'):
 from Bio import SeqIO
 text=bounded(text)
 if text.lstrip().startswith('>'):
  records=list(SeqIO.parse(io.StringIO(text),'fasta'))
  if len(records)!=1:raise ValueError('Select one FASTA record for this operation.')
  text=str(records[0].seq)
 value=re.sub(r'\s+','',text).upper()
 alphabets={'DNA':'ACGTRYSWKMBDHVN','RNA':'ACGURYSWKMBDHVN','protein':'ACDEFGHIKLMNPQRSTVWYBXZJUO*'}
 if kind not in alphabets or not value or set(value)-set(alphabets[kind]):raise ValueError('Sequence alphabet does not match the selected molecule type.')
 return value

def request(path,params=None):
 url='https://rest.ensembl.org/'+path
 if params:url+='?'+urllib.parse.urlencode(params)
 req=urllib.request.Request(url,headers={'Accept':'application/json','User-Agent':'FoldStudio-EditCraft/0.1 research'})
 with urllib.request.urlopen(req,timeout=30) as response:
  raw=response.read(8*1024**2+1)
 if len(raw)>8*1024**2:raise ValueError('Reference response exceeds its size limit.')
 return json.loads(raw),{'url':url,'sha256':hashlib.sha256(raw).hexdigest(),'retrieved':utc(),'evidence':'curated_annotation'}

def gene_context(p):
 species=p.get('species','homo_sapiens');symbol=p.get('symbol','').strip()
 if not re.fullmatch('[A-Za-z0-9_.-]{1,80}',symbol) or not re.fullmatch('[a-z_]{3,60}',species):raise ValueError('Enter a gene symbol and supported species identifier.')
 gene,receipt=request('lookup/symbol/'+species+'/'+symbol,{'expand':1})
 if gene.get('object_type')!='Gene':raise ValueError('The reference did not resolve to a gene.')
 transcripts=gene.get('Transcript',[]);wanted=p.get('transcriptId')
 selected=next((t for t in transcripts if (wanted and t['id']==wanted) or (not wanted and t.get('is_canonical'))),None)
 if wanted and selected is None:raise ValueError('Requested transcript is absent from this gene.')
 if selected is None and transcripts:selected=transcripts[0]
 sources=[receipt];sequences={}
 if selected:
  for key in ('cdna','cds','protein'):
   if key!='cdna' and not selected.get('Translation'):continue
   data,source=request('sequence/id/'+selected['id'],{'type':key});sequences[key]=data;sources.append(source)
 return {'gene':gene,'selectedTranscript':selected,'sequences':sequences,'coordinateConvention':'1-based inclusive, reference assembly and strand retained','sources':sources,'expression':None,'expressionStatus':'No expression atlas retrieved; RNA and protein abundance are not inferred.'}

def sequence_analyze(p):
 from Bio.Seq import Seq
 kind=p.get('kind','DNA');s=sequence(p['sequence'],kind)
 out={'kind':kind,'sequence':s,'length':len(s),'sequenceSha256':hashlib.sha256(s.encode()).hexdigest(),'ambiguousPositions':[i+1 for i,c in enumerate(s) if c not in ('ACGU' if kind=='RNA' else 'ACGT' if kind=='DNA' else 'ACDEFGHIKLMNPQRSTVWY')]}
 if kind=='protein':return out
 frame=p.get('frame',0)
 if type(frame)is not int or frame not in (0,1,2):raise ValueError('Frame must be 0, 1 or 2.')
 usable=(len(s)-frame)//3*3;coding=s[frame:frame+usable]
 out.update(reverseComplement=str(Seq(s).reverse_complement()),rna=s.replace('T','U'),gcFraction=sum(c in 'GC' for c in s)/len(s),translation=str(Seq(coding).translate(table=1)),frame=frame,trailingUntranslatedBases=len(s)-frame-usable,geneticCode='NCBI standard table 1; no start-codon inference',codons=[{'sequenceStart':frame+i+1,'codon':coding[i:i+3],'residue':i//3+1,'aminoAcid':str(Seq(coding[i:i+3]).translate())} for i in range(0,len(coding),3)])
 return out

def coordinate_map(p):
 t=p['transcript'];pos=p['position']
 if p['assembly']!=t['assembly_name']:raise ValueError('Reference assembly mismatch.')
 if type(pos)is not int or t['strand'] not in (-1,1):raise ValueError('Invalid genomic position or strand.')
 exons=sorted(t.get('Exon',[]),key=lambda e:e['start'],reverse=t['strand']==-1)
 intervals=sorted((e['start'],e['end']) for e in exons)
 if not exons or any(a>b for a,b in intervals) or any(b>=c for (_,b),(c,_) in zip(intervals,intervals[1:])):raise ValueError('Transcript exons must be non-overlapping inclusive intervals.')
 offset=0
 for e in exons:
  if e['start']<=pos<=e['end']:
   at=offset+(pos-e['start'] if t['strand']==1 else e['end']-pos)+1
   return {'genomicPosition':pos,'transcriptPosition':at,'transcriptId':t['id'],'transcriptVersion':t.get('version'),'assembly':p['assembly'],'strand':t['strand'],'exonId':e.get('id'),'proteinResidue':None,'scope':'Transcript position only; CDS mapping required before assigning a protein residue.'}
  offset+=e['end']-e['start']+1
 return {'genomicPosition':pos,'transcriptPosition':None,'assembly':p['assembly'],'scope':'Position is outside the observed exons; no protein consequence inferred.'}

def variant_cds(p):
 from Bio.Seq import Seq
 s=sequence(p['sequence']);pos=p['position'];ref=p.get('ref','').upper();alt=p.get('alt','').upper()
 if type(pos)is not int or pos<1 or not ref or set(ref+alt)-set('ACGT') or pos+len(ref)-1>len(s):raise ValueError('Supply a bounded, unambiguous CDS variant in 1-based coordinates.')
 if s[pos-1:pos-1+len(ref)]!=ref:raise ValueError('Reference allele does not match this CDS version.')
 if len(s)%3:raise ValueError('CDS must have complete codons; partial CDS is not inferred.')
 changed=s[:pos-1]+alt+s[pos-1+len(ref):];a=str(Seq(s).translate());b=str(Seq(changed[:len(changed)//3*3]).translate())
 first=next((i for i,(x,y) in enumerate(zip(a,b)) if x!=y),min(len(a),len(b)))
 effect='frameshift' if (len(alt)-len(ref))%3 else 'synonymous' if a==b else 'stop_gained' if '*' in b and ('*' not in a or b.index('*')<a.index('*')) else 'protein_sequence_changed'
 return {'referenceCDS':s,'alternateCDS':changed,'position':pos,'ref':ref,'alt':alt,'referenceProtein':a,'alternateProtein':b,'firstChangedResidue':None if a==b else first+1,'consequence':effect,'transcriptId':p.get('transcriptId'),'transcriptVersion':p.get('transcriptVersion'),'assembly':p.get('assembly'),'scope':'Standard-code CDS sequence consequence only; no splicing, pathogenicity, expression or treatment inference.'}

def rna_fold(p):
 import RNA
 s=sequence(p['sequence'],'RNA')
 if len(s)>2000:raise ValueError('This bounded RNAfold worker accepts at most 2,000 nucleotides.')
 temp=p.get('temperatureC',37)
 if type(temp)not in (int,float) or not math.isfinite(temp) or not 0<=temp<=60:raise ValueError('Temperature must be 0–60 °C.')
 model=RNA.md();model.temperature=temp;fc=RNA.fold_compound(s,model);structure,energy=fc.mfe();stack=[];pairs=[]
 for i,c in enumerate(structure,1):
  if c=='(':stack.append(i)
  elif c==')':pairs.append([stack.pop(),i])
 return {'sequence':s,'dotBracket':structure,'mfeKcalMol':float(energy),'pairs':pairs,'temperatureC':temp,'model':'ViennaRNA','version':RNA.__version__,'scope':'Thermodynamic secondary-structure prediction; not a measured structure or 3D atomic coordinates.'}

def sequence_align(p):
 from Bio.Align import PairwiseAligner
 kind=p.get('kind','DNA');a=sequence(p['sequenceA'],kind);b=sequence(p['sequenceB'],kind)
 if max(len(a),len(b))>3000:raise ValueError('Pairwise alignment is limited to 3,000 symbols per sequence.')
 aligner=PairwiseAligner(mode='global',match_score=1,mismatch_score=-1,open_gap_score=-2,extend_gap_score=-.5);result=aligner.align(a,b)[0]
 return {'score':result.score,'alignment':str(result),'coordinates':result.coordinates.tolist(),'method':'Biopython global affine-gap alignment','parameters':{'match':1,'mismatch':-1,'openGap':-2,'extendGap':-.5},'scope':'Sequence similarity; no functional equivalence inferred.'}

def fastq_qc(p):
 from Bio import SeqIO
 text=bounded(p['text'],4*1024**2);records=list(SeqIO.parse(io.StringIO(text),'fastq'))
 if not records:raise ValueError('No valid FASTQ reads.')
 quality=[q for r in records for q in r.letter_annotations['phred_quality']]
 return {'reads':len(records),'bases':len(quality),'meanPhred':statistics.mean(quality),'q30Fraction':sum(q>=30 for q in quality)/len(quality),'meanReadLength':statistics.mean(len(r) for r in records),'scope':'Observed FASTQ quality summary only; no alignment or editing-outcome inference.'}

def experimental_compare(p):
 context=p['context'];other=p['predictionContext']
 keys=('organism','cellType','assay','editor','endpoint','units')
 if any(not context.get(k) or context.get(k)!=other.get(k) for k in keys):raise ValueError('Organism, cell type, assay, editor, endpoint and units must match explicitly.')
 rows=p['rows']
 if not isinstance(rows,list) or not 2<=len(rows)<=10000:raise ValueError('Provide 2–10,000 paired observations.')
 if any(type(r.get(k))not in(int,float) or not math.isfinite(r[k]) for r in rows for k in ('observed','predicted')):raise ValueError('Paired measurements must be finite numbers.')
 x=[r['observed'] for r in rows];y=[r['predicted'] for r in rows];error=[a-b for a,b in zip(x,y)]
 correlation=statistics.correlation(x,y) if len(rows)>2 and statistics.pstdev(x)>0 and statistics.pstdev(y)>0 else None
 return {'count':len(rows),'mae':statistics.mean(abs(e) for e in error),'rmse':math.sqrt(statistics.mean(e*e for e in error)),'pearsonR':correlation,'context':context,'scope':'Paired descriptive model assessment. No independent calibration, confidence interval or held-out status inferred.'}

def literature(p):
 query=bounded(p['query'],300);base='https://eutils.ncbi.nlm.nih.gov/entrez/eutils/'
 url=base+'esearch.fcgi?'+urllib.parse.urlencode({'db':'pubmed','term':query,'retmode':'json','retmax':5})
 with urllib.request.urlopen(url,timeout=30) as response:r=json.load(response)
 ids=r['esearchresult']['idlist']
 if not ids:return {'citations':[],'query':query,'source':url}
 url=base+'esummary.fcgi?'+urllib.parse.urlencode({'db':'pubmed','id':','.join(ids),'retmode':'json'})
 with urllib.request.urlopen(url,timeout=30) as response:r=json.load(response)
 return {'query':query,'source':url,'citations':[{'pmid':id,'title':r['result'][id]['title'],'journal':r['result'][id].get('fulljournalname'),'date':r['result'][id].get('pubdate'),'url':'https://pubmed.ncbi.nlm.nih.gov/'+id+'/'} for id in ids],'scope':'Retrieved citations; no LLM-generated bibliographic records.'}

def annotated_import(p):
 from Bio import SeqIO
 records=list(SeqIO.parse(io.StringIO(bounded(p['text'],4*1024**2)),'genbank'))
 if len(records)!=1:raise ValueError('Select one GenBank construct at a time.')
 record=records[0]
 if len(record)>200000 or len(record.features)>5000:raise ValueError('Construct exceeds the bounded annotation limit.')
 return {'id':record.id,'sequence':str(record.seq),'topology':record.annotations.get('topology','unknown'),'features':[{'type':f.type,'location':str(f.location),'segments':[{'start':int(part.start)+1,'end':int(part.end),'strand':part.strand} for part in f.location.parts] if f.location else [],'qualifiers':f.qualifiers} for f in record.features],'coordinateConvention':'1-based inclusive display; original possibly fuzzy GenBank location retained','scope':'Imported annotations, not experimentally validated construct assembly.'}

def motif_find(p):
 from Bio.Seq import Seq
 s=sequence(p['sequence']);motif=p['motif'].upper()
 if not re.fullmatch('[ACGTRYSWKMBDHVN]{1,60}',motif):raise ValueError('Use a 1–60 base IUPAC DNA motif.')
 codes={'A':'A','C':'C','G':'G','T':'T','R':'AG','Y':'CT','S':'GC','W':'AT','K':'GT','M':'AC','B':'CGT','D':'AGT','H':'ACT','V':'ACG','N':'ACGT'}
 pattern=re.compile(''.join('['+codes[c]+']' for c in motif));sites=[]
 for strand,seq in [(1,s),(-1,str(Seq(s).reverse_complement()))]:
  for i in range(len(seq)-len(motif)+1):
   match=seq[i:i+len(motif)]
   if pattern.fullmatch(match):
    sites.append({'start':i+1 if strand==1 else len(s)-i-len(motif)+1,'end':i+len(motif) if strand==1 else len(s)-i,'strand':strand,'observedSequence':match})
    if len(sites)>10000:raise ValueError('Motif is too broad; narrow the sequence or motif.')
 return {'motif':motif,'sites':sites,'coordinateConvention':'1-based inclusive on supplied forward sequence','scope':'Sequence-pattern matches only. No guide activity, specificity, genomic off-target enumeration or editing outcome predicted.'}

def annotation_parse(p):
 fmt=p['format'];text=bounded(p['text'],4*1024**2);assembly=p.get('assembly')
 if not isinstance(assembly,str) or not assembly.strip():raise ValueError('Reference assembly must be explicit.')
 if fmt not in ('BED','GFF3','VCF'):raise ValueError('Select BED, GFF3 or VCF explicitly.')
 records=[]
 for line in text.splitlines():
  if not line.strip() or line.startswith(('#','track ','browser ')):continue
  fields=line.split('\t')
  if fmt=='BED':
   if len(fields)<3:raise ValueError('BED requires chromosome, zero-based start and exclusive end.')
   start=int(fields[1])+1;end=int(fields[2]);record={'chromosome':fields[0],'start':start,'end':end,'name':fields[3] if len(fields)>3 else None}
  elif fmt=='GFF3':
   if len(fields)!=9:raise ValueError('GFF3 requires nine columns.')
   start=int(fields[3]);end=int(fields[4]);record={'chromosome':fields[0],'type':fields[2],'start':start,'end':end,'strand':fields[6],'phase':fields[7],'attributesRaw':fields[8]}
  else:
   if len(fields)<8:raise ValueError('VCF requires eight or more columns.')
   start=int(fields[1]);end=start+len(fields[3])-1;record={'chromosome':fields[0],'start':start,'end':end,'id':fields[2],'ref':fields[3],'alt':fields[4].split(','),'filter':fields[6],'infoRaw':fields[7]}
  if start<1 or end<start:raise ValueError('Invalid genomic interval.')
  records.append(record)
  if len(records)>10000:raise ValueError('Annotation view accepts at most 10,000 records.')
 return {'format':fmt,'assembly':assembly,'records':records,'coordinateConvention':'1-based inclusive normalized display; BED input converted explicitly','scope':'Format/coordinate parsing, not reference-allele verification or variant-effect prediction.'}

def rna_ensemble(p):
 import RNA
 s=sequence(p['sequence'],'RNA')
 if len(s)>1000 or set(s)-set('ACGU'):raise ValueError('RNA ensemble analysis requires 1–1,000 unambiguous RNA bases.')
 temp=p.get('temperatureC',37)
 if type(temp)not in(int,float) or not math.isfinite(temp) or not 0<=temp<=60:raise ValueError('Temperature must be 0–60 °C.')
 threshold=p.get('pairProbabilityThreshold',.01)
 if type(threshold)not in(int,float) or not math.isfinite(threshold) or not 0<=threshold<=1:raise ValueError('Pair-probability display threshold must be between 0 and 1.')
 md=RNA.md();md.temperature=temp;fc=RNA.fold_compound(s,md);mfe_structure,mfe=fc.mfe();fc.exp_params_rescale(mfe);_,energy=fc.pf()
 centroid,distance=fc.centroid();mea,mea_score=fc.MEA();bpp=fc.bpp();pairs=[];paired=[0.0]*len(s)
 for i in range(1,len(s)+1):
  for j in range(i+1,len(s)+1):
   prob=float(bpp[i][j]);paired[i-1]+=prob;paired[j-1]+=prob
   if prob>0 and prob>=threshold:pairs.append({'i':i,'j':j,'probability':prob})
 if len(pairs)>20000:raise ValueError('Too many displayed base pairs; increase the probability threshold.')
 if any(not math.isfinite(v) or v < -1e-6 or v > 1.00001 for v in paired):raise ValueError('Partition-function marginal probabilities are invalid.')
 return {'sequence':s,'dotBracket':mfe_structure,'mfeKcalMol':float(mfe),'ensembleFreeEnergyKcalMol':float(energy),'centroid':centroid,'centroidMeanBasePairDistance':float(distance),'meaStructure':mea,'meaScore':float(mea_score),'meanBasePairDistance':float(fc.mean_bp_distance()),'mfeEnsembleProbability':float(fc.pr_structure(mfe_structure)),'pairProbabilities':pairs,'pairProbabilityThreshold':threshold,'unpairedProbabilities':[max(0.,min(1.,1-v)) for v in paired],'temperatureC':temp,'model':'ViennaRNA','version':RNA.__version__,'coordinateConvention':'1-based pair positions; array index + 1 for per-base marginals','scope':'Thermodynamic equilibrium secondary structure. Per-base unpaired marginals are not joint accessibility of an entire oligo-binding window, in-cell structure, RNA half-life or translation rate.'}

def rs3_activity(p):
 from .editcraft_models import run_external
 return run_external('rs3_activity',p)
def bedict_per_base(p):
 from .editcraft_models import run_external
 return run_external('bedict_per_base',p)
def pridict2_design(p):
 from .editcraft_models import run_external
 return run_external('pridict2_design',p)
def cas_offinder(p):
 from .editcraft_offtargets import execute
 return execute(p)
def reference_window(p):
 from .editcraft_offtargets import reference_window as retrieve
 return retrieve(p)
def variant_vep(p):
 from .editcraft_variants import annotate
 return annotate(p)

FUNCTIONS={name:globals()[name] for name in OPS}
def validate_plan(plan):
 if not isinstance(plan,dict) or plan.get('schemaVersion')!=1:raise ValueError('Unsupported EditCraft plan schema.')
 stages=plan.get('stages')
 if not isinstance(stages,list) or not 1<=len(stages)<=12:raise ValueError('Use 1–12 bounded scientific stages.')
 seen={}
 for stage in stages:
  if not isinstance(stage,dict) or not re.fullmatch('[A-Za-z0-9_-]{1,60}',str(stage.get('id',''))) or stage['id'] in seen:raise ValueError('Stage identities must be unique.')
  op=stage.get('operation')
  if op not in OPS:raise ValueError('Operation is not executable: '+str(op))
  link=stage.get('inputFrom')
  if not isinstance(stage.get('parameters'),dict):raise ValueError('Stage parameters must be an object.')
  if op in ('rs3_activity','bedict_per_base','pridict2_design'):
   from .editcraft_models import validate_input
   validate_input(op,stage['parameters'])
  if op=='cas_offinder':
   from .editcraft_offtargets import validate_input
   validate_input(stage['parameters'])
  if op=='reference_window':
   from .editcraft_offtargets import validate_window
   validate_window(stage['parameters'])
  if op=='variant_vep':
   from .editcraft_variants import validate_input
   validate_input(stage['parameters'])
  if link:
   if link not in seen:raise ValueError('Dependency must refer to an earlier stage; cycles are prohibited.')
   compatible={('gene_context','sequence_analyze'),('sequence_analyze','rna_fold'),('sequence_analyze','rna_ensemble')}
   if (seen[link],op) not in compatible:raise ValueError('No explicit scientific conversion exists for this handoff.')
  elif not isinstance(stage.get('parameters'),dict):raise ValueError('Stage parameters must be an object.')
  seen[stage['id']]=op
 if type(plan.get('seconds'))is not int or not 30<=plan['seconds']<=600:raise ValueError('Set a 30–600 second CPU deadline.')
 return plan

def run_plan(plan,checkpoint=lambda event:None,cancelled=lambda:False):
 import platform,sys,time,importlib.metadata,importlib.util
 validate_plan(plan);started=time.monotonic();results={}
 for stage in plan['stages']:
  if cancelled():raise InterruptedError('EditCraft job cancelled before the next stage.')
  if time.monotonic()-started>=plan['seconds']:raise TimeoutError('EditCraft scientific deadline reached.')
  params=dict(stage.get('parameters',{}));link=stage.get('inputFrom')
  if link:
   previous=results[link]['result']
   if stage['operation']=='sequence_analyze':
    cds=previous.get('sequences',{}).get('cds',{}).get('seq')
    if not cds:raise ValueError('Selected reference has no retrieved CDS.')
    params.update(sequence=cds,kind='DNA')
   else:params.update(sequence=previous['rna'],kind='RNA')
  checkpoint({'stageId':stage['id'],'operation':stage['operation'],'state':'running'})
  value=FUNCTIONS[stage['operation']](params)
  results[stage['id']]={'operation':stage['operation'],'inputSha256':sha(params),'result':value,'completed':utc()}
  checkpoint({'stageId':stage['id'],'operation':stage['operation'],'state':'completed'})
 return {'schemaVersion':1,'results':results,'provenance':{'engine':'EditCraft','version':VERSION,'inputSha256':sha(plan),'python':sys.version.split()[0],'platform':platform.platform(),'host':platform.node(),'packages':{name:importlib.metadata.version(name) for name in ('biopython','ViennaRNA') if importlib.util.find_spec('Bio' if name=='biopython' else 'RNA')},'completed':utc(),'elapsedSeconds':time.monotonic()-started,'scientificQualification':'Operation-specific tests; trained-model execution and independent scientific qualification are tracked separately.'}}
