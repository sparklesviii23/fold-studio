"""Versioned redacted presentation events; original scientific files stay intact."""
import datetime, hashlib, json, re

SCHEMA=1
ANSI=re.compile(r'\x1b\[[0-?]*[ -/]*[@-~]')
SECRET=re.compile(r'(?i)((?:token[_-]?(?:id|secret)|api[_-]?key|authorization|password)\s*[=:]\s*[\"\']?)([^\s\"\',;}]+)')
TOKEN=re.compile(r'\b(?:ak|as|sk|pk)-[A-Za-z0-9_-]{16,}\b')
def redact(text):
    return TOKEN.sub('[redacted]',SECRET.sub(r'\1[redacted]',ANSI.sub('',str(text))))

def normalize(value, *, campaign='', stage='', engine='', call='', cursor=0, timestamp=None, source='structured'):
    message=redact(value.get('message',value.get('line',json.dumps(value,sort_keys=True,default=str))))
    kind=value.get('kind',value.get('category','activity'))
    severity=value.get('severity') or ('error' if kind in ('failed','deadline_exceeded','packaging_failed') else 'warning' if kind in ('cancelled','interrupted') else 'info')
    stamp=timestamp if timestamp is not None else datetime.datetime.now(datetime.timezone.utc).isoformat()
    identity=hashlib.sha256(json.dumps([campaign,stage,call,cursor,stamp,source,message],ensure_ascii=False).encode()).hexdigest()
    return {'schemaVersion':SCHEMA,'eventId':identity,'timestamp':stamp,'campaignId':campaign,'stageId':stage,'engine':engine,'functionCallId':call,'cursor':cursor,'source':value.get('source',source),'category':kind,'severity':severity,'message':message[:32768],'metrics':value.get('metrics'),'resources':value if kind=='resources' else None,'rawReference':value.get('rawReference'),'candidateId':value.get('candidateId')}

def append(path,event):
    """Hash-linked append-only record; status snapshots remain separate."""
    import fcntl,os
    from .contracts import canonical,digest
    path=__import__('pathlib').Path(path)
    with path.open('a+b') as out:
        fcntl.flock(out,fcntl.LOCK_EX)
        # Reading just the last bounded record keeps long campaigns linear.
        out.seek(0,os.SEEK_END);size=out.tell();out.seek(max(0,size-262144));tail=out.read().splitlines()
        previous=json.loads(tail[-1].decode('utf-8'))['eventHash'] if tail else None
        record={**event,'previousHash':previous}
        record['eventHash']=digest(canonical(record).encode())
        out.seek(0,os.SEEK_END);out.write((canonical(record)+'\n').encode('utf-8'));out.flush()
    return record
