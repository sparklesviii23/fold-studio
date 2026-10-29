"""Streaming, explicitly Phred+33 FASTQ inspection; no alignment or trimming."""
import collections,gzip,hashlib,json,math,pathlib,tempfile

ACTIONS={'reads_import','reads_list'}
MAX_SOURCE=32*1024**2
MAX_EXPANDED=256*1024**2
MAX_READS=1000000
MAX_LENGTH=4096
VERSION='strict-four-line-phred33-v1'
SCOPE=('Descriptive base calls and supplied Phred+33 quality values for every read in this file. '
       'Quality scores describe the base caller’s error estimates, not observed errors. '
       'No encoding auto-detection, trimming, alignment, contamination, expression, variant or paired-read inference.')

def summarize(stream):
    count=bases=quality_sum=0;expected_errors=0.0;expanded=0
    lengths=collections.Counter();qualities=collections.Counter();composition=collections.Counter();cycles=[]
    def line():
        nonlocal expanded
        raw=stream.readline(MAX_LENGTH+1025)
        expanded+=len(raw)
        if len(raw)>MAX_LENGTH+1024 or expanded>MAX_EXPANDED:raise ValueError('FASTQ line/expanded-file limit exceeded; no partial summary is saved.')
        return raw.rstrip(b'\r\n') if raw else None
    while (header:=line()) is not None:
        sequence,plus,quality=line(),line(),line()
        if not header.startswith(b'@') or len(header)<2 or any(c<32 or c>126 for c in header):raise ValueError('FASTQ requires a printable @identifier header for each four-line record.')
        if sequence is None or plus is None or quality is None:raise ValueError('Truncated four-line FASTQ record.')
        if not plus.startswith(b'+') or plus[1:] not in (b'',header[1:]):raise ValueError('FASTQ separator must be + or repeat the exact header identifier.')
        if not 1<=len(sequence)<=MAX_LENGTH or len(sequence)!=len(quality):raise ValueError('Read lengths must be 1–4096 with one quality character per base; wrapped records are unsupported.')
        sequence=sequence.upper()
        if set(sequence)-set(b'ACGTRYSWKMBDHVN'):raise ValueError('FASTQ supports IUPAC DNA bases only.')
        scores=[q-33 for q in quality]
        if any(q<0 or q>93 for q in scores):raise ValueError('Quality characters must be printable Phred+33 (0–93); encoding must be selected explicitly.')
        count+=1
        if count>MAX_READS:raise ValueError('FASTQ exceeds one million reads; no partial summary is saved.')
        lengths[len(sequence)]+=1;bases+=len(sequence);quality_sum+=sum(scores);qualities.update(scores);composition.update(chr(c) for c in sequence)
        expected_errors+=math.fsum(10**(-q/10) for q in scores)
        while len(cycles)<len(sequence):cycles.append({'bases':0,'qualitySum':0,'q20':0,'q30':0,'ambiguous':0,'GC':0})
        for cycle,base,q in zip(cycles,sequence,scores):
            cycle['bases']+=1;cycle['qualitySum']+=q;cycle['q20']+=q>=20;cycle['q30']+=q>=30;cycle['ambiguous']+=base not in b'ACGT';cycle['GC']+=base in b'GC'
    if not count:raise ValueError('No FASTQ reads supplied.')
    unambiguous=sum(composition[c] for c in 'ACGT')
    return {'algorithm':VERSION,'qualityEncoding':'Phred+33','reads':count,'bases':bases,'expandedBytes':expanded,
            'lengthHistogram':{str(k):v for k,v in sorted(lengths.items())},'qualityHistogram':{str(k):v for k,v in sorted(qualities.items())},
            'baseCounts':dict(sorted(composition.items())),'GCPercentOfACGT':100*(composition['G']+composition['C'])/unambiguous if unambiguous else None,
            'ambiguousBases':bases-unambiguous,'arithmeticMeanPhred':quality_sum/bases,
            'Q20BaseFraction':sum(n for q,n in qualities.items() if q>=20)/bases,'Q30BaseFraction':sum(n for q,n in qualities.items() if q>=30)/bases,
            'sumReportedBaseErrorProbabilities':expected_errors,'meanReportedBaseErrorProbability':expected_errors/bases,
            'perCycle':[{'position1Based':i+1,**row,'meanPhred':row['qualitySum']/row['bases']} for i,row in enumerate(cycles)],'scope':SCOPE}

def dispatch(s,action,p):
    s.project(p['projectId'])
    rows=lambda:[{**r,'data':json.loads(r['data'])} for r in s.rows("SELECT * FROM records WHERE project_id=? AND kind='analysis' AND json_extract(data,'$.domain')='sequencing_reads' ORDER BY created DESC",(p['projectId'],))]
    if action=='reads_list':return rows()
    if set(p)-{'projectId','path','name','qualityEncoding'} or p.get('qualityEncoding')!='Phred+33':raise ValueError('Explicitly choose Phred+33; unsupported quality encodings are never guessed.')
    source=pathlib.Path(p['path'])
    if source.is_symlink() or not source.is_file() or source.stat().st_size>MAX_SOURCE:raise ValueError('Choose a regular FASTQ/FASTQ.gz file up to 32 MiB.')
    assets=s.root/'assets'
    if assets.is_symlink():raise ValueError('Read storage must be a real directory.')
    with tempfile.TemporaryDirectory(prefix='reads-',dir=s.root/'cache') as temp:
        snapshot=pathlib.Path(temp)/'source';digest=hashlib.sha256();size=0
        with source.open('rb') as original,snapshot.open('xb') as saved:
            while block:=original.read(1024**2):
                size+=len(block)
                if size>MAX_SOURCE:raise ValueError('FASTQ source grew beyond the 32 MiB limit.')
                digest.update(block);saved.write(block)
        sha=digest.hexdigest()
        for existing in rows():
            if existing['data']['sourceFile']['sha256']==sha and existing['data']['summary']['algorithm']==VERSION:
                path=assets/existing['data']['sourceFile']['asset']
                if not path.is_file() or path.is_symlink():raise ValueError('Previously retained original read file is missing.')
                with path.open('rb') as stream:
                    if hashlib.file_digest(stream,'sha256').hexdigest()!=sha:raise ValueError('Previously retained original read file changed.')
                return existing
        with snapshot.open('rb') as raw:
            compressed=raw.read(2)==b'\x1f\x8b';raw.seek(0)
            if compressed:
                with gzip.GzipFile(fileobj=raw) as decoded:summary=summarize(decoded)
            else:summary=summarize(raw)
        name=str(p.get('name') or source.name).strip()
        if not name or len(name)>200:raise ValueError('Use a read dataset name of 1–200 characters.')
        asset='reads-'+sha+('.fastq.gz' if compressed else '.fastq');target=assets/asset;published=False
        try:
            if target.exists():
                if target.is_symlink():raise ValueError('Invalid original-read asset.')
                with target.open('rb') as stream:
                    if hashlib.file_digest(stream,'sha256').hexdigest()!=sha:raise ValueError('Original-read asset checksum conflict.')
            else:
                import os
                os.link(snapshot,target);published=True
            return s.record_save({'projectId':p['projectId'],'kind':'analysis','name':name,'data':{'domain':'sequencing_reads','sourceFile':{'asset':asset,'sha256':sha,'bytes':size,'originalName':source.name,'gzip':compressed},'implementationSha256':hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(),'summary':summary}})
        except Exception:
            if published:target.unlink(missing_ok=True)
            raise
