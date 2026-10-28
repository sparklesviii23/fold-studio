"""Lossless original GTF/BED retention and explicit bounded GFF3 normalization."""
import re,urllib.parse

def gtf_attributes(text):
 result={};position=0
 while text[position:].strip():
  match=re.match(r'\s*([A-Za-z][\w.:]*)\s+"((?:[^"\\]|\\["\\])*)"\s*;',text[position:])
  if not match:raise ValueError('GTF attributes require quoted key "value"; fields.')
  key,value=match.groups();value=re.sub(r'\\(["\\])',r'\1',value)
  if key in result and key in ('gene_id','transcript_id','exon_id'):raise ValueError('Ambiguous duplicate GTF identity attribute.')
  result[key]=result[key]+' | '+value if key in result else value;position+=match.end()
 return result

def normalize(text,fmt):
 if fmt not in ('gtf','bed'):raise ValueError('Choose GTF or bounded BED3–BED6 explicitly.')
 lines=['##gff-version 3'];columns=None;count=0
 quote=lambda value:urllib.parse.quote(str(value),safe=':._-')
 for number,line in enumerate(text.splitlines(),1):
  if not line.strip() or line.startswith('#') or fmt=='bed' and line.startswith(('track ','browser ')):continue
  cells=line.split('\t');attrs={};count+=1
  if count>100000:raise ValueError('At most 100,000 annotation rows are supported.')
  if fmt=='gtf':
   if len(cells)!=9:raise ValueError('GTF requires nine tab-separated fields.')
   seqid,source,kind,left,right,score,strand,phase,raw=cells;attrs=gtf_attributes(raw)
   gene=attrs.get('gene_id');transcript=attrs.get('transcript_id')
   if not gene:raise ValueError('Every supported GTF row needs an explicit gene_id.')
   if kind=='gene':attrs['ID']='gene:'+gene
   elif kind in ('transcript','mRNA'):
    if not transcript:raise ValueError('Transcript rows require transcript_id.')
    attrs.update(ID='rna:'+transcript,Parent='gene:'+gene)
   else:
    if kind in ('CDS','exon') and not transcript:raise ValueError('CDS/exon rows require transcript_id; transcript identity is not guessed.')
    attrs['ID']='cds:'+transcript if kind=='CDS' else 'row:'+str(number)
    attrs['Parent']='rna:'+transcript if transcript else 'gene:'+gene
   attrs['Name']=attrs.get('gene_name') or attrs.get('transcript_name') or attrs['ID']
  else:
   if not 3<=len(cells)<=6:raise ValueError('This BED import supports BED3–BED6 intervals only; block/thick/CDS semantics are not discarded silently.')
   if columns is None:columns=len(cells)
   if columns!=len(cells):raise ValueError('BED rows must use a consistent column count.')
   seqid,left,right=cells[:3];left=str(int(left)+1);source='BED';kind='region';strand=cells[5] if len(cells)==6 else '.';score=cells[4] if len(cells)>=5 else '.';phase='.'
   if score!='.' and (not score.isdigit() or not 0<=int(score)<=1000):raise ValueError('BED score must be an integer 0–1000 or missing.')
   if strand not in ('+','-','.'):raise ValueError('BED strand must be +, - or missing.')
   attrs={'ID':'bed:'+str(number),'Name':cells[3] if len(cells)>=4 else 'interval:'+str(number),'originalCoordinateConvention':'0-based half-open'}
  if int(left)<1 or int(right)<int(left):raise ValueError('Unsupported empty/reversed annotation interval.')
  lines.append('\t'.join((seqid,source,kind,left,right,score,strand,phase,';'.join(key+'='+quote(value) for key,value in attrs.items()))))
 if not count:raise ValueError('No supported annotation rows supplied.')
 return '\n'.join(lines)+'\n',{'format':fmt,'rows':count,'scope':'Original bytes retained. GTF uses explicit gene/transcript identifiers without inventing absent parent records; separate stop-codon rows are not appended to CDS. BED3–BED6 is normalized from 0-based half-open to 1-based inclusive regions; no genes/exons/CDS are inferred. Unsupported variants are rejected.'}
