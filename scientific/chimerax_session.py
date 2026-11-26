"""Original fold adapter, loaded into the user's ChimeraX installation.

Extends its official REST handler with authentication and introspection. The
official /run endpoint executes console commands. The measured-comparison route
calls the installed interpreter and serializes its actual atoms and fit results.
No ChimeraX source or executable is redistributed by fold.
"""
import hashlib, hmac, json, math, os, pathlib, re, sys, threading, time, urllib.parse
sys.dont_write_bytecode = True  # Packaged extensions must not mutate the signed app.
from queue import Queue
from chimerax.core import buildinfo
from chimerax.core.commands import run
from chimerax.rest_server import server as rest

config_path = pathlib.Path(sys.argv[1])
config = json.loads(config_path.read_text())
identity = config['sessionId']
token = config['token']
bridge_version = 4
sys.path.insert(0,str(pathlib.Path(__file__).parent))
from scene_bridge import SceneBridge
from capability_audit import assess
scene_bridge = SceneBridge(session,identity)

def on_main(function):
    queue = Queue()
    def work():
        try: queue.put((True, function()))
        except Exception as error: queue.put((False, str(error)))
    session.ui.thread_safe(work)
    ok, value = queue.get(timeout=120)
    if not ok: raise RuntimeError(value)
    return value

def catalog():
    from chimerax.core.commands.cli import registered_commands, Command, usage, command_url, _user_kw_cnt
    entries = []
    try:
        names = list(registered_commands(multiword=True))
    except Exception as error:
        return {'commands': [{'name':n, 'availability':'registered root; metadata unavailable'} for n in registered_commands()], 'completeMetadata':False, 'error':str(error)}
    for name in names:
        entry = {'name':name, 'availability':'registered in connected session'}
        try:
            command = Command(session); command.current_text = name
            command._find_command_name()
            description = command._ci
            entry.update({'description':description.synopsis or '', 'syntax':usage(session,name), 'documentation':command_url(name),
                          'required':[{'name':n,'type':getattr(t,'name',getattr(t,'__name__',str(t)))} for n,t in description._required.items()],
                          'optional':[{'name':n,'type':getattr(t,'name',getattr(t,'__name__',str(t)))} for n,t in description._optional.items()],
                          'options':[{'name':_user_kw_cnt(n)[0],'type':getattr(t,'name',getattr(t,'__name__',str(t)))} for n,t in description._keyword.items()],
                          'implementation':getattr(description.function,'__module__',None)})
        except Exception as error: entry['metadataError'] = str(error)
        entries.append(entry)
    fingerprint = hashlib.sha256(json.dumps(entries,sort_keys=True).encode()).hexdigest()
    return {'commands':entries,'completeMetadata':all('metadataError' not in e for e in entries),'fingerprint':fingerprint,'count':len(entries)}

def atom_data(atom):
    residue=atom.residue
    return {'chain':residue.chain_id,'residue':residue.number,'insertion':residue.insertion_code,'residueName':residue.name,'atom':atom.name,'element':atom.element.name,'serial':atom.serial_number,'altLoc':atom.alt_loc.strip(),'xyz':[float(v) for v in atom.scene_coord],'color':[int(v) for v in atom.color],'ribbonColor':[int(v) for v in residue.ribbon_color],
            'spec':atom.atomspec,'bFactor':float(atom.bfactor),'occupancy':float(atom.occupancy)}

def model_atoms(id):
    from chimerax.atomic import AtomicStructure
    models=[m for m in session.models.list(type=AtomicStructure) if m.id_string==id]
    if len(models)!=1:raise ValueError('The native model is missing or ambiguous.')
    return {'sessionId':identity,'modelId':id,'atoms':[atom_data(a) for a in models[0].atoms]}

def compare(parameters):
    from chimerax.atomic import AtomicStructure
    ids=[parameters.get(key,[''])[0] for key in ('moving','reference')]
    chains=[parameters.get(key,[''])[0] for key in ('movingChain','referenceChain')]
    if ids[0]==ids[1] or any(not re.fullmatch(r'\d+(?:\.\d+)*',id) for id in ids):raise ValueError('Choose two distinct native atomic model IDs.')
    if any(chain and not re.fullmatch(r'[A-Za-z0-9_]+',chain) for chain in chains):raise ValueError('Invalid native chain identifier.')
    cutoff=parameters.get('cutoff',['2'])[0]
    if cutoff!='none':
        value=float(cutoff)
        if not math.isfinite(value) or not 0.1<=value<=20:raise ValueError('Invalid pruning cutoff.')
        cutoff=str(value)
    for id,chain in zip(ids,chains):
        models=[m for m in session.models.list(type=AtomicStructure) if m.id_string==id]
        if len(models)!=1 or sum(a.name=='CA' and a.element.name=='C' and (not chain or a.residue.chain_id==chain) for a in models[0].atoms)<3:raise ValueError('Both selected models/chains need at least three protein Cα atoms.')
    specs=['#'+id+('/'+chain if chain else '')+'@CA' for id,chain in zip(ids,chains)]
    command='matchmaker '+specs[0]+' to '+specs[1]+' cutoffDistance '+cutoff+' showAlignment false'
    before=state()
    native=run(session,command)
    if not native:raise ValueError('ChimeraX found no fit with at least three aligned residues. Inspect its native log.')
    fits=[];remaining=1500
    for result in native:
        moving=result['full match atoms'];reference=result['full ref atoms']
        final=set(result['final match atoms'])
        pairs=[]
        for index,(a,b) in enumerate(zip(moving,reference)):
            if index>=remaining:break
            pairs.append({'moving':atom_data(a),'reference':atom_data(b),'distanceAngstrom':math.dist(a.scene_coord,b.scene_coord),'usedInFit':a in final})
        remaining-=len(pairs)
        fits.append({'fullRmsd':float(result['full RMSD']),'fitRmsd':float(result['final RMSD']),
                     'alignedPairs':len(moving),'fitPairs':len(final),'pairs':pairs,'pairsTruncated':len(pairs)<len(moving),
                     'transformation':result['transformation matrix'].matrix.tolist(),
                     'alignedMovingSequence':result['aligned match seq'].characters,'alignedReferenceSequence':result['aligned ref seq'].characters})
    return {'state':'completed','sessionId':identity,'version':buildinfo.version,'bridgeVersion':bridge_version,'command':command,
            'movingModelId':ids[0],'referenceModelId':ids[1],'cutoffAngstrom':None if cutoff=='none' else float(cutoff),'fits':fits,
            'before':before,'after':state(),'pairReportLimit':1500}

def state():
    from chimerax.atomic import AtomicStructure
    models = []
    for model in session.models.list(type=AtomicStructure):
        selected = []
        for atom in model.atoms:
            if atom.selected:
                selected.append(atom_data(atom))
        path = getattr(model,'filename',None)
        if isinstance(path,(list,tuple)): path=path[0] if path else None
        source_hash=None
        if path and pathlib.Path(path).is_file():
            file=pathlib.Path(path)
            if file.stat().st_size<100*1024**2: source_hash=hashlib.sha256(file.read_bytes()).hexdigest()
        models.append({'id':model.id_string,'name':model.name,'atoms':model.num_atoms,'residues':model.num_residues,'chains':[c.chain_id for c in model.chains],
                       'coordsets':model.num_coordsets,'sourcePath':path,'sourceSha256':source_hash,'selected':selected,
                       'positionsSha256':hashlib.sha256(model.atoms.scene_coords.tobytes()).hexdigest()})
    return {'sessionId':identity,'version':buildinfo.version,'bridgeVersion':bridge_version,'integrated':bool(getattr(session,'fold_studio',None)),'models':models,
            'camera':{'engine':'chimerax','name':session.main_view.camera.name,'matrix':session.main_view.camera.position.matrix.tolist()},
            'allModels':[{'id':m.id_string,'name':m.name,'type':type(m).__name__,'display':bool(m.display)} for m in session.models.list()]}

OfficialRESTHandler = rest.RESTHandler
class AuthenticatedRESTHandler(OfficialRESTHandler):
    def do_GET(self):
        # Browser origins are never accepted; only the native scientific service
        # holds the random token. Credentials are not exposed to the renderer.
        authorization = self.headers.get('Authorization','')
        if self.headers.get('Origin') or not hmac.compare_digest(authorization,'Bearer '+token):
            self.send_error(403,'fold session authorization required'); return
        path=urllib.parse.urlparse(self.path).path
        if path.startswith('/fold/'):
            try:
                payload={}
                if self.command=='POST':
                    size=int(self.headers.get('Content-Length','0'))
                    if not 0<=size<=4*1024**2:raise ValueError('Scientific request exceeds 4 MB.')
                    payload=json.loads(self.rfile.read(size)) if size else {}
                if path=='/fold/session': result={'sessionId':identity,'version':buildinfo.version,'bridgeVersion':bridge_version,'gui':session.ui.is_gui,'mode':'background_scientific_engine','integrated':False}
                elif path=='/fold/catalog': result=on_main(catalog)
                elif path=='/fold/scene': result=on_main(lambda:scene_bridge.scene(urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get('known',[None])[0]))
                elif path=='/fold/camera': result=on_main(lambda:scene_bridge.set_camera(payload))
                elif path=='/fold/select': result=on_main(lambda:scene_bridge.select(payload))
                elif path=='/fold/python': result=on_main(lambda:scene_bridge.python(payload))
                elif path=='/fold/measure': result=on_main(lambda:scene_bridge.measure(payload))
                elif path=='/fold/inventory':
                    from native_inventory import inventory
                    result=on_main(lambda:assess(inventory(session,catalog,False)))
                elif path=='/fold/focus':result={'refreshScene':True,'mode':'background_scientific_engine'}
                elif path=='/fold/state': result=on_main(state)
                elif path=='/fold/atoms': result=on_main(lambda:model_atoms(urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get('model',[''])[0]))
                elif path=='/fold/compare': result=on_main(lambda:compare(urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query,keep_blank_values=True)))
                else: self.send_error(404); return
                data=json.dumps(result).encode();self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
            except Exception as error:
                data=json.dumps({'error':str(error)}).encode();self.send_response(500);self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
        else:
            # Direct delegation, not a fold command subset or translation.
            super().do_GET()
    do_POST=do_GET
    def do_OPTIONS(self): self.send_error(403,'Browser command access is disabled')

rest.RESTHandler = AuthenticatedRESTHandler
run(session,'remotecontrol rest start port %d json true log true cors false'%config['port'])
session.logger.info('fold authenticated loopback bridge ready; session '+identity)
if not session.ui.is_gui:
    # Production scientific helper: no QApplication, window, native tools or GL
    # renderer. The official non-GUI thread_safe implementation runs callbacks.
    while True:
        threading.Event().wait(2)
        if config.get('ownerPid'):
            try:os.kill(int(config['ownerPid']),0)
            except ProcessLookupError:os._exit(0)
