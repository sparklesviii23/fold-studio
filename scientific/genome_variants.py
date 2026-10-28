"""Forward-reference allele inspection; optional explicit CDS codon consequences."""
import hashlib,json,pathlib
def inspect(s,p,reference,sequences,features):
 from genome_products import assemble,translate
 from genome_workspace import reverse_complement
 if set(p)-{'projectId','id','replicon','position','ref','alt','flank','cdsFeatureIndex','translationTable'}:raise ValueError('Unsupported variant request field.')
 replicon=p.get('replicon');position=p.get('position');ref=p.get('ref');alt=p.get('alt');flank=p.get('flank',20)
 if replicon not in sequences or type(position) is not int or type(flank) is not int or not 0<=flank<=1000:raise ValueError('Choose a known replicon, integer 1-based position and 0–1,000 flanking bases.')
 if any(not isinstance(a,str) or not 1<=len(a)<=1000 or set(a)-set('ACGT') for a in (ref,alt)) or ref==alt:raise ValueError('Supply distinct explicit forward-reference REF/ALT alleles of 1–1,000 unambiguous uppercase DNA bases.')
 sequence=sequences[replicon];end=position+len(ref)-1
 if not 1<=position<=end<=len(sequence):raise ValueError('Variant reference interval exceeds this replicon. Origin-spanning alleles are not normalized implicitly.')
 if sequence[position-1:end]!=ref:raise ValueError('REF allele does not match the original forward reference.')
 left=max(1,position-flank);right=min(len(sequence),end+flank);context=sequence[left-1:right];offset=position-left
 variant_kind='SNV' if len(ref)==len(alt)==1 else 'MNV' if len(ref)==len(alt) else 'insertion_or_delins' if len(alt)>len(ref) else 'deletion_or_delins'
 result={'referenceId':reference['id'],'metadata':reference['metadata'],'sources':reference['sources'],'replicon':replicon,'position':position,'ref':ref,'alt':alt,'variantKind':variant_kind,'referenceContext':context,'alternateContext':context[:offset]+alt+context[offset+len(ref):],'referenceContextStart':left,'referenceContextEnd':right,'alleleOffsetZeroBased':offset,'coordinateConvention':'1-based inclusive forward-reference coordinates; ALT context is a derived string, not a new reference assembly. Alleles are not left-normalized or converted to HGVS.','codingConsequence':None,'scope':'Exact reference-allele verification and optional annotation-specific codon comparison. No splicing, expression, clinical pathogenicity, fitness or therapeutic consequence is inferred. Original sequences remain unchanged.'}
 if 'cdsFeatureIndex' in p:
  product=assemble(sequences,features,reference['circularReplicons'],p['cdsFeatureIndex'],'cds')
  if product['replicon']!=replicon:raise ValueError('Selected CDS belongs to a different replicon.')
  if set(product['dna'])-set('ACGT'):raise ValueError('Coding consequence requires an unambiguous CDS reference.')
  coords=[];length=len(sequence)
  for part in product['segments']:
   positions=list(range(part['start'],part['end']+1))
   if product['strand']=='-':positions.reverse()
   coords.extend((value-1)%length+1 for value in positions)
  coords=coords[product['initialPhaseBasesSkipped']:];lookup={value:i for i,value in enumerate(coords)}
  genomic=list(range(position,end+1));oriented=genomic if product['strand']=='+' else list(reversed(genomic))
  indices=[lookup.get(value) for value in oriented]
  if any(i is None for i in indices) or indices!=list(range(indices[0],indices[0]+len(indices))):
   result['codingConsequence']={'state':'not_supported_for_selected_interval','scope':'Allele is outside the selected assembled CDS, overlaps removed phase bases, or crosses an unsupported exon/intron boundary. No protein consequence inferred.'}
  else:
   start=indices[0];coding_ref=ref if product['strand']=='+' else reverse_complement(ref);coding_alt=alt if product['strand']=='+' else reverse_complement(alt)
   if product['dna'][start:start+len(coding_ref)]!=coding_ref:raise ValueError('CDS-to-genome allele correspondence differs.')
   changed=product['dna'][:start]+coding_alt+product['dna'][start+len(coding_ref):]
   a=translate(s,product,p.get('translationTable'),False);b=translate(s,{**product,'dna':changed},p.get('translationTable'),False)
   pa,pb=a['protein'],b['protein'];delta=len(alt)-len(ref)
   if start<3 and product['initialPhaseBasesSkipped']==0:effect='start_region_variant'
   elif delta%3:effect='frameshift'
   elif delta:effect='inframe_length_change'
   elif pa==pb:effect='synonymous_codon_change'
   elif '*' in pb and ('*' not in pa or pb.index('*')<pa.index('*')):effect='stop_gained'
   elif '*' in pa and ('*' not in pb or pb.index('*')>pa.index('*')):effect='stop_lost'
   else:effect='amino_acid_change'
   result['codingConsequence']={'state':'computed','effect':effect,'lengthChangeBases':delta,'readingFrameChanged':bool(delta%3),'annotationId':product['annotationId'],'cdsStrand':product['strand'],'cdsOffsetZeroBased':start,'referenceCDS':product['dna'],'alternateCDS':changed,'referenceTranslation':a,'alternateTranslation':b,'scope':'Codon comparison for this explicit CDS and genetic code. Partial codons are reported by the translation receipts. Initiation-region variants are not labelled synonymous or start-lost without a validated initiation model.'}
 result['implementationSha256']=hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest();result['inputSha256']=hashlib.sha256(json.dumps(p,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
 return result
