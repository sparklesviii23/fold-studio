"""Cursor-based PTY sessions inside an already-running Modal task container.

No credentials or network listener enter the task. A small Linux PTY broker
keeps shell state between provider RPCs; typed bytes are not stored in app logs.
"""
import base64
import json
import re
import uuid

DAEMON = r'''
import os,sys,pty,select,time,json,base64,fcntl,termios,struct,signal,pathlib
folder=pathlib.Path(sys.argv[1]); folder.mkdir(mode=0o700,exist_ok=True)
lock=folder/'lock'
try: fd=os.open(str(lock),os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
except FileExistsError: sys.exit(0)
os.close(fd)
pid,master=pty.fork()
if pid==0:
 os.environ['TERM']='xterm-256color';os.environ['PS1']='modal:\w\$ '
 os.chdir('/work' if os.path.isdir('/work') else '/tmp')
 os.execvp('bash',['bash','--noprofile','--norc','-i'])
(folder/'ready').write_text(str(pid)); (folder/'events').touch(mode=0o600)
seen=set();pos=0;last=time.monotonic()
try:
 with (folder/'output').open('ab',buffering=0) as out:
  while True:
   if select.select([master],[],[],0.08)[0]:
    try: chunk=os.read(master,65536)
    except OSError: break
    if not chunk:break
    out.write(chunk)
   with (folder/'events').open('rb') as inp:
    inp.seek(pos)
    for line in inp:
     if not line.endswith(b'\n'):break
     pos+=len(line);e=json.loads(line)
     if e['id'] in seen:continue
     seen.add(e['id']);last=time.monotonic()
     if e.get('close'):raise SystemExit()
     if 'cols' in e:fcntl.ioctl(master,termios.TIOCSWINSZ,struct.pack('HHHH',e['rows'],e['cols'],0,0))
     if e.get('data'):os.write(master,base64.b64decode(e['data']))
   if time.monotonic()-last>900:break
finally:
 try:os.killpg(pid,signal.SIGHUP)
 except ProcessLookupError:pass
 (folder/'closed').write_text('closed');os.close(master)
'''

POLL = r'''
import sys,pathlib,json,base64,os
folder=pathlib.Path(sys.argv[1]);offset=int(sys.argv[2]);event=json.loads(sys.argv[3])
if event:
 with (folder/'events').open('ab',buffering=0) as f:f.write((json.dumps(event)+'\n').encode())
path=folder/'output';size=path.stat().st_size if path.exists() else 0
if offset>size:raise ValueError('Terminal output cursor exceeds the stream.')
data=b''
if path.exists():
 with path.open('rb') as f:f.seek(offset);data=f.read(65536)
print(json.dumps({'data':base64.b64encode(data).decode(),'offset':offset+len(data),'closed':(folder/'closed').exists(),'ready':(folder/'ready').exists()}))
'''


def remote(p):
    import modal
    sb = modal.Sandbox.from_id(p['sandboxId'])
    if sb.poll() is not None: raise ValueError('This Modal container has finished; its shell is no longer available.')
    folder = '/tmp/fold-pty-' + p['sessionId']
    if p.get('start'):
        # O_EXCL in the broker makes a repeated start with the same session id inert.
        sb.exec('python', '-u', '-c', DAEMON, folder, timeout=3600)
    proc = sb.exec('python', '-c', POLL, folder, str(p.get('offset', 0)), json.dumps(p.get('event', {})), timeout=20)
    proc.wait()
    if proc.returncode: raise ValueError('The terminal broker could not be reached: ' + proc.stderr.read()[-500:])
    return json.loads(proc.stdout.read())


def dispatch(s, p):
    import gpu_tasks as gpu
    from cloud_accounts import get
    s.project(p.get('projectId'))
    rec = gpu._read(s, p.get('taskId'))
    if rec.get('projectId') != p['projectId'] or rec.get('provider') != 'modal': raise ValueError('Choose a Modal task in this project.')
    if rec.get('accountId') != get(s).get('activeId'): raise ValueError('Select the Modal account that owns this task before opening its terminal.')
    if rec.get('state') != 'running' or not rec.get('sandboxId'): raise ValueError('The terminal is available while the Modal container is running.')
    session = p.get('sessionId')
    d = gpu._folder(s) / rec['id']; path = d / 'pty-session.json'
    if p.get('start'):
        if p.get('approvedRemoteCommand') is not True: raise ValueError('Open the remote shell explicitly before sending input.')
        if path.is_file(): session = json.loads(path.read_text())['sessionId']
        else:
            session = uuid.uuid4().hex
            # Preserve the broker identity before contacting the provider; reconnect never starts a second shell.
            try:
                with path.open('x') as f: json.dump({'sessionId': session}, f)
            except FileExistsError: session = json.loads(path.read_text())['sessionId']
    if not isinstance(session, str) or not re.fullmatch('[a-f0-9]{32}', session): raise ValueError('Invalid terminal session.')
    if not path.is_file() or json.loads(path.read_text())['sessionId'] != session: raise ValueError('Terminal session does not belong to this task.')
    offset = p.get('offset', 0)
    if type(offset) is not int or not 0 <= offset <= 100_000_000: raise ValueError('Invalid terminal output cursor.')
    event = {}
    if p.get('data') or p.get('close') or p.get('cols') is not None:
        eid = p.get('eventId')
        if not isinstance(eid, str) or not re.fullmatch('[a-f0-9]{32}', eid): raise ValueError('Each terminal input needs an event identity.')
        event['id'] = eid
        if p.get('data'):
            try: raw = base64.b64decode(p['data'], validate=True)
            except Exception: raise ValueError('Invalid terminal input encoding.') from None
            if len(raw) > 16384: raise ValueError('Send at most 16 KB of terminal input at once.')
            event['data'] = p['data']
        if p.get('cols') is not None:
            cols, rows = p['cols'], p.get('rows')
            if type(cols) is not int or type(rows) is not int or not 20 <= cols <= 500 or not 5 <= rows <= 200: raise ValueError('Invalid terminal dimensions.')
            event.update(cols=cols, rows=rows)
        if p.get('close'): event['close'] = True
    out = gpu._rpc(s, 'gpu_task_terminal_remote', {'sandboxId': rec['sandboxId'], 'sessionId': session,
                    'start': p.get('start') is True, 'offset': offset, 'event': event}, timeout=45)
    if out.get('closed') or p.get('close'): path.unlink(missing_ok=True)
    return {**out, 'sessionId': session}
