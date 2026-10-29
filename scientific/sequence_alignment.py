"""Bounded pairwise alignment through the bundled Biopython engine."""
import hashlib,json,pathlib,subprocess,sys
ACTIONS={'sequence_align','sequence_alignments'}
ALPHABETS={'DNA':set('ACGT'),'RNA':set('ACGU'),'protein':set('ACDEFGHIKLMNPQRSTVWY')}
def validate(p):
 alphabet=p.get('alphabet');mode=p.get('mode');target=p.get('target');query=p.get('query');orientation=p.get('queryOrientation')
 if alphabet not in ALPHABETS or mode not in ('global','local') or orientation not in ('forward','reverse_complement'):raise ValueError('Choose the alphabet, global/local mode and explicit query orientation.')
 if alphabet=='protein' and orientation!='forward':raise ValueError('Reverse complement is defined for DNA/RNA only.')
 for sequence in (target,query):
  if not isinstance(sequence,str) or not 1<=len(sequence)<=10000 or set(sequence)-ALPHABETS[alphabet]:raise ValueError('Supply 1–10,000 uppercase canonical residues per sequence without headers, ambiguity symbols or gaps.')
 if len(target)*len(query)>4000000:raise ValueError('Pairwise alignment is bounded to four million sequence-length products. This is not a genome-wide mapper.')
 scores={k:p.get(k) for k in ('matchScore','mismatchScore','gapOpenScore','gapExtendScore')}
 if any(type(v) not in (int,float) or not -20<=v<=20 for v in scores.values()) or scores['matchScore']<=0 or scores['mismatchScore']>0 or scores['gapOpenScore']>=0 or scores['gapExtendScore']>=0:raise ValueError('Use finite scores −20…20, positive matches, nonpositive mismatches and negative affine gap scores.')
 return {'target':target,'query':query,'alphabet':alphabet,'mode':mode,'queryOrientation':orientation,**scores}
def dispatch(s,action,p):
 s.project(p['projectId'])
 rows=lambda:[{**r,'data':json.loads(r['data'])} for r in s.rows("SELECT * FROM records WHERE project_id=? AND kind='analysis' AND json_extract(data,'$.domain')='sequence_alignment' ORDER BY created DESC",(p['projectId'],))]
 if action=='sequence_alignments':return rows()
 if set(p)-{'projectId','name','target','query','alphabet','mode','queryOrientation','matchScore','mismatchScore','gapOpenScore','gapExtendScore','targetReference'}:raise ValueError('Unsupported alignment field.')
 context=None
 if p.get('targetReference') is not None:
  import genome_workspace
  ref=p['targetReference']
  if not isinstance(ref,dict) or set(ref)-{'referenceId','replicon','start','end','strand','storageKind'} or not {'referenceId','replicon','start','end','strand'}.issubset(ref) or p.get('alphabet')!='DNA':raise ValueError('Reference alignment requires one explicit DNA coordinate interval.')
  coordinates={'projectId':p['projectId'],'id':ref['referenceId'],**{k:ref[k] for k in ('replicon','start','end','strand')}}
  if ref.get('storageKind')=='indexed_fasta':
   import genomic_io
   value=genomic_io.dispatch(s,'indexed_genome_region',coordinates)
  elif ref.get('storageKind') is None:value=genome_workspace.dispatch(s,'genome_region',coordinates)
  else:raise ValueError('Unknown target reference storage kind.')
  if p.get('target')!=value['dna']:raise ValueError('The selected reference interval differs from the target sequence; reload the interval.')
  context={**ref,'sequenceSha256':value['sequenceSha256'],'sources':value.get('sources') or [value['sourceFile']],'scope':'Target offsets refer to the exact oriented supplied interval, not to a genome-wide mapping or an inferred ortholog.'}
 request=validate(p);implementation=hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest()
 # Include the executing library version in the cache receipt returned by the runner.
 result=subprocess.run([s.engine_python(),'-I','-B',str(pathlib.Path(__file__).resolve())],input=json.dumps(request),capture_output=True,text=True,timeout=30)
 if result.returncode:raise ValueError('Biopython alignment failed: '+result.stderr.strip()[-1000:])
 output=json.loads(result.stdout);data={'domain':'sequence_alignment','request':request,'targetReference':context,'targetSha256':hashlib.sha256(request['target'].encode()).hexdigest(),'querySha256':hashlib.sha256(request['query'].encode()).hexdigest(),'implementationSha256':implementation,'result':output}
 identity=hashlib.sha256(json.dumps(data,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest();data['inputSha256']=identity
 existing=next((row for row in rows() if row['data']['inputSha256']==identity),None)
 return existing or s.record_save({'projectId':p['projectId'],'kind':'analysis','name':str(p.get('name') or 'Pairwise '+request['alphabet']+' alignment')[:200],'data':data})

if __name__=='__main__':
 import Bio
 from Bio import Align
 from Bio.Seq import Seq
 p=json.load(sys.stdin);query=str(Seq(p['query']).reverse_complement_rna() if p['alphabet']=='RNA' else Seq(p['query']).reverse_complement()) if p['queryOrientation']=='reverse_complement' else p['query'];aligner=Align.PairwiseAligner();aligner.mode=p['mode'];aligner.match_score=p['matchScore'];aligner.mismatch_score=p['mismatchScore'];aligner.open_gap_score=p['gapOpenScore'];aligner.extend_gap_score=p['gapExtendScore'];alignments=aligner.align(p['target'],query)
 try:a=alignments[0]
 except IndexError:print(json.dumps({'state':'no_positive_local_alignment','score':0,'biopythonVersion':Bio.__version__,'algorithm':aligner.algorithm,'scope':'No positive local alignment under the supplied scoring scheme; no homology or mapping conclusion.'}));sys.exit(0)
 coordinates=a.coordinates.tolist();blocks=[];identical=compared=gap_bases=0
 for i in range(len(coordinates[0])-1):
  t0,t1=coordinates[0][i:i+2];q0,q1=coordinates[1][i:i+2];blocks.append({'targetStart0':t0,'targetEnd0':t1,'orientedQueryStart0':q0,'orientedQueryEnd0':q1})
  if t1>t0 and q1>q0:compared+=t1-t0;identical+=sum(x==y for x,y in zip(p['target'][t0:t1],query[q0:q1]))
  else:gap_bases+=max(t1-t0,q1-q0)
 print(json.dumps({'state':'optimal_alignment_returned','score':float(a.score),'biopythonVersion':Bio.__version__,'algorithm':aligner.algorithm,'affineGapConvention':'Gap length n costs gapOpenScore + (n−1)*gapExtendScore; the same scoring applies to target/query and end/internal gaps.','orientedQuery':query,'targetCoordinateRange0BasedHalfOpen':[int(coordinates[0][0]),int(coordinates[0][-1])],'orientedQueryCoordinateRange0BasedHalfOpen':[int(coordinates[1][0]),int(coordinates[1][-1])],'alignedResiduePairs':compared,'identicalResiduePairs':identical,'gapBases':gap_bases,'identityFractionOfAlignedResiduePairs':identical/compared if compared else None,'blocks':blocks,'display':str(a),'scope':'First optimum returned by the recorded Biopython algorithm; ties may exist and uniqueness is not certified. All coordinates are zero-based half-open offsets in the supplied target and explicitly oriented query. Reverse-complement query offsets are not original forward-query coordinates. No genome-wide mapping, significance, evolutionary relationship or biological function is inferred.'},allow_nan=False))
