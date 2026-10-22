"""Versioned presentation timelines and bounded, incremental local movie encoding."""
import base64
import hashlib
import json
import os
import pathlib
import shutil
import signal
import struct
import subprocess
import uuid
import zipfile

import intelligence as mi

ACTIONS={'cinema_save','cinema_list','cinema_begin','cinema_frame','cinema_finish','cinema_cancel','cinema_status','cinema_validate_views'}
MAX_BYTES=1024**3


def encoder():
    candidates=[shutil.which('ffmpeg'), '/opt/homebrew/bin/ffmpeg', '/Applications/ChimeraX-1.12.app/Contents/bin/ffmpeg', '/Applications/ChimeraX.app/Contents/bin/ffmpeg']
    return next((str(p) for p in candidates if p and pathlib.Path(p).is_file() and os.access(p,os.X_OK)),None)


def timeline(value):
    if not isinstance(value,dict) or value.get('schemaVersion')!=1 or value.get('mode')!='presentation':
        raise ValueError('Only a versioned presentation timeline is supported by this exporter.')
    if len(json.dumps(value,allow_nan=False))>250000:raise ValueError('Timeline exceeds the 250 KB limit.')
    duration=value.get('duration');keys=value.get('keyframes')
    if type(duration) not in (int,float) or not 1<=duration<=120 or not isinstance(keys,list) or not 2<=len(keys)<=100:
        raise ValueError('Choose 1–120 seconds and 2–100 keyframes.')
    last=-1
    for key in keys:
        t=key.get('time');camera=key.get('camera',{})
        if type(t) not in (int,float) or not 0<=t<=duration or t<=last:raise ValueError('Keyframe times must be ordered, unique and inside the movie duration.')
        last=t
        for name in ('position','target','up'):
            v=camera.get(name)
            if not isinstance(v,list) or len(v)!=3 or any(type(n) not in (int,float) or not __import__('math').isfinite(n) for n in v):raise ValueError('Camera vectors must contain three finite coordinates.')
        if sum(x*x for x in camera['up'])<1e-10 or sum((a-b)**2 for a,b in zip(camera['position'],camera['target']))<1e-10:raise ValueError('Camera direction and up vector must be nonzero.')
        direction=[a-b for a,b in zip(camera['position'],camera['target'])];up=camera['up']
        if sum(v*v for v in (direction[1]*up[2]-direction[2]*up[1],direction[2]*up[0]-direction[0]*up[2],direction[0]*up[1]-direction[1]*up[0]))<1e-10:raise ValueError('Camera up must not be parallel to its view direction.')
        offsets=key.get('offsets',{})
        if not isinstance(offsets,dict) or len(offsets)>26:raise ValueError('Use explicit peptide-chain presentation translations.')
        for chain,offset in offsets.items():
            if chain not in value.get('style',{}).get('binderChains',[]) or not isinstance(offset,list) or len(offset)!=3 or any(type(n) not in (int,float) or not __import__('math').isfinite(n) or abs(n)>500 for n in offset):raise ValueError('Presentation translations require an assigned peptide chain and finite offsets up to 500 Å.')
    if keys[0]['time']!=0 or keys[-1]['time']!=duration:raise ValueError('Timeline must cover both endpoints.')
    return json.loads(json.dumps(value,allow_nan=False))


class Cinema:
    def __init__(self,s):
        self.s=s;self.lab=mi.Lab(s);self.root=s.root/'cinema';self.root.mkdir(exist_ok=True)
        s.db.execute('CREATE TABLE IF NOT EXISTS cinema_timelines(id TEXT PRIMARY KEY,project_id TEXT,structure_id TEXT,name TEXT,data TEXT,created TEXT)')

    def source(self,p):
        r,path=self.lab.record(p['structureId'])
        if p.get('projectId') and r['project_id']!=p['projectId']:raise ValueError('Choose a structure in the current project.')
        return r

    def session(self,p):
        id=str(uuid.UUID(p['id']));folder=self.root/id
        if folder.is_symlink() or not (folder/'export.json').is_file():raise ValueError('Movie export not found.')
        data=json.loads((folder/'export.json').read_text())
        if (folder/'cancelled').exists():data['state']='cancelled'
        return folder,data

    def write(self,folder,data):
        temp=folder/('export.'+uuid.uuid4().hex+'.pending');temp.write_text(json.dumps(data,allow_nan=False));temp.replace(folder/'export.json')

    def cinema_save(self,p):
        r=self.source(p);value=timeline(p['timeline']);name=str(p.get('name','')).strip()
        if not name or len(name)>200:raise ValueError('Enter a scene name of 1–200 characters.')
        value.update(structureId=r['id'],sourceSha256=r['data']['sha256'])
        self.context(value,r)
        id=str(uuid.uuid4());self.s.db.execute('INSERT INTO cinema_timelines VALUES(?,?,?,?,?,?)',(id,r['project_id'],r['id'],name,json.dumps(value),mi.now()));self.s.db.commit()
        return {'id':id,'name':name,'data':value}

    def cinema_list(self,p):
        r=self.source(p)
        return [{**dict(row),'data':json.loads(row['data'])} for row in self.s.db.execute('SELECT * FROM cinema_timelines WHERE structure_id=? ORDER BY created DESC',(r['id'],))]

    def cinema_begin(self,p):
        r=self.source(p);value=timeline(p['timeline']);fps=p.get('fps',15);width=p.get('width',1920);height=p.get('height',1080)
        if type(fps)!=int or not 1<=fps<=30 or type(width)!=int or type(height)!=int or width%2 or height%2 or not 320<=width<=3840 or not 180<=height<=2160:
            raise ValueError('Use 1–30 fps and even dimensions up to 3840×2160.')
        self.context(value,r)
        count=round(value['duration']*fps)
        if count>1800:raise ValueError('This bounded exporter supports at most 1,800 frames.')
        output=pathlib.Path(str(p['path'])).expanduser().resolve()
        if output.exists() or output.with_suffix(output.suffix+'.provenance.json').exists() or not output.parent.is_dir() or output.suffix.lower() not in ('.mp4','.zip'):raise ValueError('Choose a new .mp4 or .zip output in an existing folder.')
        if output.suffix.lower()=='.mp4' and not encoder():raise ValueError('FFmpeg is unavailable. Export a PNG frame archive (.zip) instead.')
        if shutil.disk_usage(self.root).free<2*1024**3 or shutil.disk_usage(output.parent).free<2*1024**3:raise ValueError('Keep at least 2 GiB free for this movie export.')
        # One staging export at a time; abandoned work can be explicitly cancelled.
        for folder in self.root.iterdir():
            if folder.is_dir() and (folder/'export.json').is_file():
                old=json.loads((folder/'export.json').read_text())
                if old.get('state') in ('rendering','encoding') and not (folder/'cancelled').exists():raise ValueError('Finish or cancel the existing movie export first: '+folder.name)
        id=str(uuid.uuid4());folder=self.root/id;folder.mkdir()
        data={'id':id,'state':'rendering','structureId':r['id'],'projectId':r['project_id'],'sourceSha256':r['data']['sha256'],'timeline':value,'fps':fps,'width':width,'height':height,'frames':count,'received':0,'bytes':0,'output':str(output),'created':mi.now(),'claim':'Presentation movie of saved coordinates; not a physical binding trajectory.'}
        self.write(folder,data)
        return data

    def context(self,value,record):
        metadata=record['data'].get('metadata',{})
        if metadata.get('poseTransfer'):
            pose=metadata['poseTransfer'];value['sourceContext']={key:metadata.get(key) for key in ('parentStructureId','sourceSha256','referenceStructureId','referenceSha256','poseAssessmentId')}
            value['sourceContext'].update(registrationState=pose['registrationState'],rmsdAngstrom=pose['transform']['rmsd'],claim=metadata['scientificClaim'])
            value.setdefault('style',{})['disclosure']=metadata['presentationDisclosure']

    def cinema_frame(self,p):
        folder,data=self.session(p)
        if data['state']!='rendering' or type(p.get('index'))!=int or p['index']!=data['received'] or data['received']>=data['frames']:raise ValueError('Movie frames must arrive once, in order, during rendering.')
        encoded=p.get('png','')
        if not isinstance(encoded,str) or len(encoded)>24*1024**2:raise ValueError('Frame exceeds the encoded size limit.')
        raw=base64.b64decode(encoded,validate=True)
        if len(raw)<24 or raw[:8]!=b'\x89PNG\r\n\x1a\n' or raw[12:16]!=b'IHDR' or struct.unpack('>II',raw[16:24])!=(data['width'],data['height']):raise ValueError('PNG dimensions differ from the export manifest.')
        if data['bytes']+len(raw)>MAX_BYTES:raise ValueError('Frame staging reached its 1 GiB ceiling. Cancel and choose lower resolution, duration or frame rate.')
        frame=folder/('%06d.png'%data['received']);frame.write_bytes(raw)
        if (folder/'cancelled').exists():
            frame.unlink(missing_ok=True);raise ValueError('Movie export cancelled.')
        data['received']+=1;data['bytes']+=len(raw);self.write(folder,data)
        return {'received':data['received'],'frames':data['frames'],'bytes':data['bytes']}

    def cinema_finish(self,p):
        folder,data=self.session(p)
        if data['state']!='rendering' or data['received']!=data['frames']:raise ValueError('All requested frames must be present before encoding.')
        self.source(data);output=pathlib.Path(data['output'])
        if output.exists() or output.with_suffix(output.suffix+'.provenance.json').exists():raise ValueError('The chosen output or provenance file now exists. It will not be overwritten.')
        partial=output.with_name(output.stem+'.'+data['id']+'.partial'+output.suffix)
        data.update(state='encoding',partial=str(partial));self.write(folder,data)
        try:
            if output.suffix.lower()=='.zip':
                with zipfile.ZipFile(partial,'w',compression=zipfile.ZIP_STORED) as archive:
                    archive.writestr('provenance.json',json.dumps(data,indent=2))
                    for frame in sorted(folder.glob('*.png')):archive.write(frame,frame.name)
            else:
                with (folder/'encoding.log').open('w') as log:
                    process=subprocess.Popen([encoder(),'-nostdin','-v','error','-framerate',str(data['fps']),'-i',str(folder/'%06d.png'),'-frames:v',str(data['frames']),'-c:v','libx264','-pix_fmt','yuv420p','-crf','18','-movflags','+faststart',str(partial)],stdout=log,stderr=log,start_new_session=True)
                    data['pid']=process.pid;self.write(folder,data)
                    if (folder/'cancelled').exists():
                        os.killpg(process.pid,signal.SIGTERM)
                    try:code=process.wait(timeout=600)
                    except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGTERM);process.wait(timeout=10);raise ValueError('Movie encoding exceeded ten minutes.')
                if code:raise ValueError('Encoding failed: '+(folder/'encoding.log').read_text()[-3000:])
            latest=json.loads((folder/'export.json').read_text())
            if (folder/'cancelled').exists() or latest['state']=='cancelled':raise ValueError('Movie export cancelled.')
            # Hard-link publication fails safely if a competing file appeared.
            os.link(partial,output);partial.unlink()
            h=hashlib.sha256()
            with output.open('rb') as stream:
                while block:=stream.read(4*1024**2):h.update(block)
            data.update(state='completed',finished=mi.now(),sha256=h.hexdigest());data.pop('pid',None)
            self.write(folder,data)
            with output.with_suffix(output.suffix+'.provenance.json').open('x') as stream:json.dump(data,stream,indent=2)
            return data
        except Exception as error:
            data.update(state='cancelled' if (folder/'cancelled').exists() else 'failed',error=str(error));self.write(folder,data);raise
        finally:
            partial.unlink(missing_ok=True)
            for frame in folder.glob('*.png'):frame.unlink(missing_ok=True)

    def cinema_cancel(self,p):
        folder,data=self.session(p)
        if data['state'] not in ('rendering','encoding'):return data
        (folder/'cancelled').touch(exist_ok=True)
        if data['state']=='encoding':
            # The owned encoding process is verified before any signal is sent.
            pid=data.get('pid')
            if pid:
                cmd=subprocess.run(['/bin/ps','-p',str(pid),'-o','command='],capture_output=True,text=True).stdout
                if cmd.strip().startswith(str(encoder())+' ') and str(folder/'%06d.png') in cmd:
                    try:os.killpg(pid,signal.SIGTERM)
                    except ProcessLookupError:pass
        data.update(state='cancelled',finished=mi.now());self.write(folder,data)
        for frame in folder.glob('*.png'):frame.unlink(missing_ok=True)
        return data

    def cinema_status(self,p):
        if p.get('id'):return self.session(p)[1]
        return {'encoder':encoder(),'frameBudgetBytes':MAX_BYTES,'exports':[self.session({'id':path.parent.name})[1] for path in self.root.glob('*/export.json')]}

    def cinema_validate_views(self,p):
        record=self.source(p);frames=p.get('frames',[])
        if not isinstance(frames,list) or not 1<=len(frames)<=200:raise ValueError('Supply 1–200 actual renderer observations.')
        for frame in frames:
            n=frame.get('foregroundFraction')
            if type(n) not in (int,float) or not __import__('math').isfinite(n) or not 0<=n<=1 or frame.get('axis') not in ('x','y','z'):
                raise ValueError('Invalid renderer observation.')
            edge=frame.get('edgeForegroundFraction',0)
            if type(edge) not in (int,float) or not __import__('math').isfinite(edge) or not 0<=edge<=1:raise ValueError('Invalid edge observation.')
        report={'state':'passed' if all(.002<f['foregroundFraction']<.95 and f.get('edgeForegroundFraction',0)<.005 for f in frames) else 'failed','created':mi.now(),'structureId':record['id'],'sourceSha256':record['data']['sha256'],'frames':frames,'method':'Actual 512×288 renderer PNGs, labels/ghosts disabled; foreground differs from known background by >36 summed RGB units; require 0.2–95% foreground and <0.5% foreground on image edges when supplied. Original coordinate checksum reverified.','scope':'Software frame visibility check only; does not prove every atom is visible through occluding molecular surfaces or establish any biological result.'}
        path=self.root/('visibility-'+uuid.uuid4().hex+'.json');path.write_text(json.dumps(report,indent=2));return {**report,'path':str(path)}


def dispatch(s,action,p):
    instance=Cinema(s)
    if action in ('cinema_begin','cinema_frame','cinema_cancel'):
        import fcntl
        with (instance.root/'.render.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX)
            return getattr(instance,action)(p)
    return getattr(instance,action)(p)

