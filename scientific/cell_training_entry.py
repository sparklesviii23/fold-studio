"""Verify the grounded study before loading any model; offline CUDA only."""
import hashlib,json,signal,time,traceback
from pathlib import Path,PurePosixPath


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(8<<20),b''):h.update(b)
    return h.hexdigest()


def verify(root,manifest):
    seen=set()
    for row in manifest['files']:
        p=PurePosixPath(row['path'])
        if p.is_absolute() or '..' in p.parts or str(p)!=row['path'] or row['path'] in seen:raise ValueError('Unsafe upload path.')
        seen.add(row['path']);source=root/row['path']
        if not source.is_file() or source.stat().st_size!=row['bytes']:raise ValueError('Missing staged file: '+row['path'])
        if row.get('sha256'):
            if digest(source)!=row['sha256']:raise ValueError('Staged SHA mismatch: '+row['path'])
        else:
            if source.stat().st_size>10_000_000:raise ValueError('Large assets require an official SHA256.')
            blob=hashlib.sha1(b'blob '+str(source.stat().st_size).encode()+b'\0'+source.read_bytes()).hexdigest()
            if not row.get('gitBlob') or blob!=row['gitBlob']:raise ValueError('Pinned encoder file mismatch: '+row['path'])


def main(root,out,archive):
    root,out,archive=map(Path,[root,out,archive]);out.mkdir(parents=True,exist_ok=True);start=time.monotonic()
    def event(phase,**values):
        line=json.dumps({'phase':phase,'seconds':time.monotonic()-start,**values},allow_nan=False);print(line,flush=True)
        with (out/'events.jsonl').open('a') as f:f.write(line+'\n')
    def expired(*_):raise TimeoutError('Approved 90-minute grounded-study limit reached; no retry.')
    signal.signal(signal.SIGALRM,expired);signal.alarm(5370)
    try:
        meta=json.loads((root/'ASSET_MANIFEST.json').read_text())
        for name,path in [('checkpoint',Path('/cache/models/qwen-cell')/meta['checkpointRevision']),('biology',Path('/cache/models/cell-encoder')/meta['biologyRevision'])]:
            view=root/name
            if view.is_symlink():
                if view.resolve()!=path:raise ValueError('Unexpected staged model view.')
            elif view.exists():raise ValueError('Unexpected staged model directory.')
            else:view.symlink_to(path,target_is_directory=True)
        event('verifying_inputs');verify(root,meta)
        files={r['path'][8:]:digest(root/r['path']) for r in meta['files'] if r['path'].startswith('biology/')}
        (root/'biology/MODEL_RECEIPT.json').write_text(json.dumps({'model':meta['biologyModel'],'revision':meta['biologyRevision'],'downloaded':True,'localFiles':files}))
        from cell_training_engine import run
        event('study_started',maximumSeconds=5400,automaticRetry=False);run(root,out,archive,event)
    except BaseException as error:
        traceback.print_exc();(out/'FAILURE.json').write_text(json.dumps({'state':'failed','reason':str(error),'automaticRetry':False}));raise
    finally:signal.alarm(0)
