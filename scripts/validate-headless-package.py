#!/usr/bin/env python3
"""Launch the actual signed FOLD app in a NEW QA root; no OS UI automation."""
import argparse,hashlib,json,os,pathlib,plistlib,signal,subprocess,sys,time,traceback
sys.dont_write_bytecode=True
p=argparse.ArgumentParser();p.add_argument('--app',required=True);p.add_argument('--root',required=True);p.add_argument('--pdb',required=True);p.add_argument('--report',required=True);a=p.parse_args()
app=pathlib.Path(a.app).resolve();root=pathlib.Path(a.root).resolve();report=pathlib.Path(a.report).resolve();report.mkdir(parents=True,exist_ok=True)
if root.exists():raise SystemExit('Use a NEW disposable root.')
resources=app/'Contents/Resources';sys.path.insert(0,str(resources/'scientific'))
from worker import Service
from observatory import Observatory
s=Service(root,resources/'fixtures');project=s.library({})['projects'][0]['id'];source=s.import_structure({'projectId':project,'path':a.pdb,'name':'Native packaged ANGPTL3/8 QA'})
s.setting_set({'key':'onboarded','value':True});s.setting_set({'key':'lastStructureId','value':source['id']});o=Observatory(s)
process=None;helper=None;checks=[];failure=None;start=time.monotonic()
def check(name,ok,detail=None):
    checks.append({'name':name,'passed':bool(ok),'details':detail})
    if not ok:raise AssertionError(name+': '+str(detail))
def alive(pid):
    state=subprocess.run(['/bin/ps','-p',str(pid),'-o','stat='],capture_output=True,text=True).stdout.strip()
    return bool(state) and not state.startswith('Z')
try:
    info=plistlib.loads((app/'Contents/Info.plist').read_bytes());check('Own FOLD macOS bundle identity',info['CFBundleIdentifier']=='org.foldstudio.observatory' and info['CFBundleShortVersionString']==json.loads((pathlib.Path(__file__).resolve().parents[1]/'package.json').read_text())['version'],info.get('CFBundleName'))
    binary=app/'Contents/MacOS'/info['CFBundleExecutable'];arch=subprocess.run(['/usr/bin/lipo','-archs',str(binary)],capture_output=True,text=True).stdout.strip();check('Native Apple Silicon executable',arch=='arm64',arch)
    required=['intelligence.py','scene_bridge.py','chimerax_session.py','capability_audit.py','validation-evidence-4.2.json','pinned-capabilities-1.12.json']
    check('Scientific adapter resources complete',all((resources/'scientific'/name).is_file() for name in required))
    check('Former Qt host is absent',not any((resources/'scientific'/name).exists() for name in ['native_launcher.py','native_shell.py','qt_bootstrap.js']))
    signature=subprocess.run(['/usr/bin/codesign','--verify','--deep','--strict',str(app)],capture_output=True,text=True);check('Signature valid before launch',signature.returncode==0,signature.stderr)
    with (root/'packaged.log').open('wb') as log:
        process=subprocess.Popen([str(binary)],env={**os.environ,'FOLD_DATA_DIR':str(root)},stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
    status={};scene={};history=[]
    for _ in range(90):
        if process.poll() is not None:break
        status=o.chimerax_status({})
        if status.get('connected'):
            helper=status['pid'];scene=o.chimerax_scene({});history=o.console_history({'projectId':project})
            if scene.get('models') and any(r['data'].get('syncStatus','').startswith('synchronized') and r['data'].get('viewerSyncVerified') for r in history):break
        time.sleep(.4)
    check('FOLD primary process stays running',process.poll() is None)
    check('Real packaged frontend starts GUI-free scientific helper',status.get('connected') and not status.get('gui') and status.get('bridgeVersion')==4,status)
    check('Helper belongs to the FOLD process',str(o.connection().get('ownerPid'))==str(process.pid))
    check('Native frontend renders actual imported project PDB',scene.get('models') and len(scene['models'][0]['atoms'])==1800 and any(r['data'].get('syncStatus','').startswith('synchronized') and r['data'].get('viewerSyncVerified') for r in history))
    native=o.chimerax_python({'projectId':project,'confirmed':True,'code':'print(session.ui.is_gui, hasattr(session.ui, "main_window"), session.main_view._render is None)'})
    check('No original GUI or original rendering context initialized',native['stdout'].strip()=='False False True',native['stdout'].strip())
    check('Source bytes preserved',hashlib.sha256((root/'assets'/source['data']['asset']).read_bytes()).hexdigest()==source['data']['sha256'])
    signature=subprocess.run(['/usr/bin/codesign','--verify','--deep','--strict',str(app)],capture_output=True,text=True);check('Signature stays valid after runtime use',signature.returncode==0,signature.stderr)
    check('No bytecode caches mutate the signed package',not list((resources/'scientific').rglob('__pycache__')))
    process.terminate();process.wait(timeout=10)
    for _ in range(30):
        if not alive(helper):break
        time.sleep(.2)
    check('Owned background engine exits with FOLD',not alive(helper))
except Exception:failure=traceback.format_exc()
finally:
    if process and process.poll() is None:process.terminate();process.wait(timeout=10)
    if helper and alive(helper):
        command=subprocess.run(['/bin/ps','-p',str(helper),'-o','command='],capture_output=True,text=True).stdout
        if str(o.descriptor) in command and 'chimerax_session.py' in command:os.kill(helper,signal.SIGTERM)
    s.db.close()
    result={'date':time.strftime('%Y-%m-%d'),'passed':not failure and bool(checks) and all(c['passed'] for c in checks),'checks':checks,'error':failure,'seconds':round(time.monotonic()-start,2),'app':str(app),'root':str(root),'physicalNativeUIInteractionVerified':False,'manualChecksPending':['macOS menu interaction','detached windows','native accessibility and window gestures']}
    (report/'packaged-app-acceptance.json').write_text(json.dumps(result,indent=2))
print(json.dumps({'passed':result['passed'],'checks':len(checks),'error':failure,'report':str(report)}));sys.exit(0 if result['passed'] else 1)
