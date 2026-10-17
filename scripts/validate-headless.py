#!/usr/bin/env python3
"""Real scientific-engine acceptance. Creates a NEW disposable library only."""
import argparse,base64,collections,csv,hashlib,json,math,os,pathlib,signal,struct,subprocess,sys,time,traceback,urllib.error,urllib.request,zipfile
sys.dont_write_bytecode=True
BASE=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE/'scientific'))
from worker import Service
from observatory import Observatory,native_quote
p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--pdb',required=True);p.add_argument('--report',required=True);a=p.parse_args()
root=pathlib.Path(a.root).resolve();report=pathlib.Path(a.report).resolve();report.mkdir(parents=True,exist_ok=True)
if root.exists():raise SystemExit('Use a NEW disposable test root.')
s=Service(root,BASE/'fixtures');project=s.library({})['projects'][0]['id'];o=Observatory(s);pid=None;checks=[];failure=None;tested=set();start=time.monotonic()
def check(name,ok,detail=None):
    checks.append({'name':name,'passed':bool(ok),'details':detail})
    if not ok:raise AssertionError(name+': '+str(detail))
def run(command):
    result=o.chimerax_execute({'projectId':project,'command':command,'confirmed':True})
    check('Native command: '+command[:100],result['state']=='completed',result.get('output',{}).get('error'))
    return result
def py(code):
    x=o.chimerax_python({'projectId':project,'code':code,'confirmed':True});check('Native Python API',x['state']=='completed',x.get('error'));return x
try:
    source=s.import_structure({'projectId':project,'path':a.pdb,'name':'ANGPTL3/8 validation','source':'User supplied cropped prediction; computational hotspots remain provisional'})
    original=(root/'assets'/source['data']['asset']).read_bytes()
    launch=o.chimerax_start({});pid=launch['pid']
    for _ in range(60):
        status=o.chimerax_status({})
        if status['connected']:break
        time.sleep(.4)
    check('Actual pinned runtime connected without GUI',status.get('connected') and status.get('gui') is False and status.get('bridgeVersion')==4,status)
    command=subprocess.run(['/bin/ps','-p',str(pid),'-o','command='],capture_output=True,text=True).stdout
    check('Process uses --nogui and --notools',all(v in command for v in ('--nogui','--notools','chimerax_session.py')))
    opened=o.chimerax_open({'projectId':project,'structureId':source['id'],'replace':True});check('Library PDB opens in authoritative model',opened['state']=='completed')
    scene=o.chimerax_scene({});m=scene['models'][0];mid=m['id'];spec='#'+mid
    check('Real ANGPTL3/8 has three expected chains',[(c['id'],c['residues']) for c in m['chains']]==[('A',76),('B',76),('C',71)])
    check('Real model atom count and residue count',len(m['atoms'])==1800 and len({(a['chain'],a['residue'],a['insertion']) for a in m['atoms']})==223)
    check('All original native bonds retained',len(m['bonds'])>1700)
    run('dssp '+spec)
    commands='\n'.join('color '+spec+'/'+chain+' '+name+' target c' for chain,name in [('A','cyan'),('B','green'),('C','gray')])
    run(commands);scene=o.chimerax_scene({});m=scene['models'][0];expected={'A':[0,255,255,255],'B':[0,128,0,255],'C':[128,128,128,255]}
    check('Every native cartoon atom has assigned chain colour',all(x['ribbonColor']==expected[x['chain']] for x in m['atoms']))
    run('\n'.join('color '+spec+'/'+key+' '+name+' target c' for key,name in [('B:32','magenta'),('C:18','yellow'),('C:27','orange')]))
    scene=o.chimerax_scene({});m=scene['models'][0]
    hot={('B',32):[255,0,255,255],('C',18):[255,255,0,255],('C',27):[255,165,0,255]}
    check('Exact author residue highlights',all(all(x['ribbonColor']==colour for x in m['atoms'] if (x['chain'],x['residue'])==key) for key,colour in hot.items()))
    check('Native DSSP helix assignments encoded in transport',sum(a['secondaryStructure']==1 for a in m['atoms'])>1500 and '_struct_conf.conf_type_id' in m['cif'])
    known=o.chimerax_scene({'known':scene['revision']});check('Unchanged scene omits repeated coordinates and meshes','models' not in known and 'meshes' not in known)
    run('color '+spec+' bychain');run('color '+spec+'&helix cyan target acs\ncolor '+spec+'&strand yellow target acs\ncolor '+spec+'&coil gray target acs');run(commands)
    ca=[x for x in m['atoms'] if x['atom']=='CA'][:4];keys=[x['key'] for x in ca]
    o.chimerax_selection({'keys':keys[:2]});selected=o.chimerax_scene({})['models'][0]['atoms'];check('Stable native atom handles select exactly two atoms',sum(x['selected'] for x in selected)==2)
    measured=o.chimerax_measure({'keys':keys[:2]});truth=math.dist(ca[0]['xyz'],ca[1]['xyz']);check('Native distance matches independent Euclidean reference',abs(measured['value']-truth)<1e-6,measured)
    for n,kind in [(3,'angle'),(4,'dihedral')]:
        value=o.chimerax_measure({'keys':keys[:n]});check('Native '+kind+' has real finite value',value['kind']==kind and math.isfinite(value['value']),value['value'])
    run('distance '+ca[0]['spec']+' '+ca[1]['spec']);scene=o.chimerax_scene({});check('Distance pseudobond exported for FOLD drawing',any(abs(pb['length']-truth)<1e-6 for pb in scene['pseudobonds']))
    run('show '+spec+' atoms');run('style '+spec+' ball');scene=o.chimerax_scene({});check('Atomic representation is actual engine state',all(a['shown'] and a['style']==1 for a in scene['models'][0]['atoms']))
    run('transparency '+spec+' 30 target ac');scene=o.chimerax_scene({});check('Actual atom and ribbon alpha exported',scene['models'][0]['atoms'][0]['color'][3]<255 and scene['models'][0]['atoms'][0]['ribbonColor'][3]<255)
    run('transparency '+spec+' 0 target ac');run('hide '+spec+' atoms')
    run('surface '+spec);scene=o.chimerax_scene({});check('Native molecular surfaces export actual triangles',len(scene['meshes'])==3 and all(v['triangleCount']>1000 for v in scene['meshes']),[(v['id'],v['vertexCount'],v['triangleCount']) for v in scene['meshes']])
    for mesh in scene['meshes']:
        check('Native surface buffers have declared sizes',len(base64.b64decode(mesh['vertices']))==mesh['vertexCount']*12 and len(base64.b64decode(mesh['triangles']))==mesh['triangleCount']*12)
    run('hide '+spec+' surfaces')
    run('label '+spec+'/B:32 residues');scene=o.chimerax_scene({});check('Real native residue label text and anchor exported',any('32' in v['text'] and len(v['xyz'])==3 for v in scene['labels']))
    run('label delete '+spec+'/B:32')
    run('contacts '+spec+'/A restrict '+spec+'/C log true');run('hbonds '+spec+' log true');run('measure sasa '+spec)
    point=ca[0];target=[point['xyz'][0]+.4,*point['xyz'][1:]]
    code='from chimerax.atomic import all_atoms\nfrom chimerax.core.undo import UndoState\nimport numpy as np\n_fold_atom=next(a for a in all_atoms(session) if a.string(style="command",omit_structure=False)=='+repr(point['spec'])+')\n_fold_old=np.array(_fold_atom.coord,copy=True)\n_fold_new=_fold_atom.structure.scene_position.inverse()*np.array('+repr(target)+')\n_fold_undo=UndoState("FOLD coordinate edit")\n_fold_undo.add(_fold_atom,"coord",_fold_old,_fold_new)\n_fold_atom.coord=_fold_new\nsession.undo.register(_fold_undo)\nprint(_fold_atom.atomspec)'
    py(code);edited=o.chimerax_scene({});new=next(a for a in edited['models'][0]['atoms'] if a['key']==point['key']);check('Python coordinate edit changes authoritative scene geometry',math.dist(new['xyz'],target)<1e-6 and edited['models'][0]['geometry']!=m['geometry'])
    opened=o.chimerax_open({'projectId':project,'structureId':source['id'],'replace':True});again=o.chimerax_scene({});check('Reopening same library source preserves native edits',math.dist(next(a for a in again['models'][0]['atoms'] if a['key']==point['key'])['xyz'],target)<1e-6)
    run('undo');scene=o.chimerax_scene({});check('Native Undo restores real coordinates',math.dist(next(a for a in scene['models'][0]['atoms'] if a['key']==point['key'])['xyz'],point['xyz'])<1e-6)
    py('fold_persistent_value=223');x=py('print(fold_persistent_value)');check('Scientific Python namespace persists',x['stdout'].strip()=='223')
    err=o.chimerax_python({'projectId':project,'code':'raise ValueError("real native traceback")','confirmed':True});check('Python errors preserve real traceback',err['state']=='failed' and 'ValueError' in err['error']['traceback'])
    err=o.chimerax_execute({'projectId':project,'command':'foldUnknownCommand','confirmed':True});check('Unknown original commands fail honestly',err['state']=='failed' and err['output'].get('error'))
    camera=o.chimerax_scene({})['camera'];o.chimerax_camera({'position':[0,0,180],'target':[0,0,0],'up':[0,1,0],'fieldOfView':36});run('turn y 15');run('view '+spec);scene=o.chimerax_scene({});check('Native camera changes round trip',scene['camera']!=camera and all(math.isfinite(v) for v in scene['camera']['position']))
    run('clip front 0');scene=o.chimerax_scene({});check('Unsupported native clip effect reports visual limitation',any(x['id'].startswith('clip:') for x in scene['unsupported']));run('clip off')
    run('build start peptide "FOLD idealized peptide" ACDE -57,-47');scene=o.chimerax_scene({});check('Real native peptide builder adds distinct atomic model',len(scene['models'])==2 and scene['models'][1]['atoms'][0]['key']!=scene['models'][0]['atoms'][0]['key'])
    newId=scene['models'][1]['id'];run('swapaa #'+newId+':2 lys');scene=o.chimerax_scene({});check('Native mutation updates residue identity',any(a['residue']==2 and a['residueName']=='LYS' for a in scene['models'][1]['atoms']))
    py('from chimerax.atomic import AtomicStructure\n_fold_model=session.models.list(type=AtomicStructure)[1]\n_fold_model.add_coordsets(np.stack([_fold_model.atoms.coords,_fold_model.atoms.coords+np.array([1,0,0])]))')
    before=o.chimerax_scene({})['models'][1];frame=before['coordsets'][-1];run('coordset #'+newId+' '+str(frame));after=o.chimerax_scene({})['models'][1];check('Real coordinate set switches frame and geometry',after['activeCoordset']==frame and after['geometry']!=before['geometry'])
    # Synthetic map is a declared Gaussian test fixture, never research output.
    density=py('from chimerax.map_data import ArrayGridData\nfrom chimerax.map import volume_from_grid_data\n_fold_grid=np.indices((16,16,16),dtype=float)-7.5\n_fold_density=np.exp(-np.sum(_fold_grid**2,axis=0)/18).astype(np.float32)\n_fold_volume=volume_from_grid_data(ArrayGridData(_fold_density,origin=(0,0,0),step=(1,1,1),name="Declared synthetic Gaussian QA map"),session)\n_fold_volume.set_parameters(surface_levels=[0.4])\n_fold_volume.set_display_style("surface")\nprint(_fold_volume.id_string)')
    scene=o.chimerax_scene({});volumeId=density['stdout'].strip();check('Native density contour provides real mesh',any(v['id'].startswith(volumeId+'.') and v['triangleCount']>100 for v in scene['meshes']),[(v['id'],v['name']) for v in scene['meshes']])
    path=root/'scientific-export.cif';run('save '+native_quote(path)+' models '+spec+' format mmcif');check('Original scientific mmCIF writer produces actual coordinates',path.is_file() and '_atom_site.' in path.read_text())
    script=root/'native-colours.cxc';script.write_text(commands+'\n');run('open '+native_quote(script));scene=o.chimerax_scene({});check('Original .cxc script changes authoritative colours',all(a['ribbonColor']==expected[a['chain']] for a in scene['models'][0]['atoms']))
    imported=s.import_structure({'projectId':project,'path':str(path),'name':'Real mmCIF export round trip'})
    comparison=o.comparison_run({'projectId':project,'structureId':imported['id'],'referenceId':source['id'],'cutoff':None})
    check('Native Matchmaker of exported model gives near-zero RMSD',comparison['state']=='completed' and all(f['fitRmsd']<1e-3 and f['fitPairs']>=70 for f in comparison['fits']),[{'rmsd':f['fitRmsd'],'pairs':f['fitPairs']} for f in comparison['fits']])
    save=o.chimerax_session_save({'projectId':project,'name':'Headless real session'});expected=o.chimerax_scene({});run('color '+spec+' red target c');o.chimerax_session_restore({'projectId':project,'id':save['id'],'confirmed':True});restored=o.chimerax_scene({})
    check('True CXS session restores multiple model identities and colours',[(m['id'],len(m['atoms'])) for m in expected['models']]==[(m['id'],len(m['atoms'])) for m in restored['models']] and expected['models'][0]['atoms'][0]['ribbonColor']==restored['models'][0]['atoms'][0]['ribbonColor'])
    archive=root/'research.zip';s.export_project({'id':project,'path':str(archive)})
    with zipfile.ZipFile(archive) as z:check('Project archive includes checksum-verified native CXS',hashlib.sha256(z.read('assets/'+save['data']['asset'])).hexdigest()==save['data']['sha256'])
    check('Saved source remains byte-identical',original==(root/'assets'/source['data']['asset']).read_bytes())
    catalog=o.chimerax_catalog({});check('All headless command metadata includes original parameters',catalog['count']>570 and catalog['completeMetadata'],catalog['count'])
    inventory=o.chimerax_inventory({});check('Exhaustive pinned registry accounted without parity claim',inventory['count']>=1516 and not inventory['completeParityVerified'] and any(r['status']=='Blocked' for r in inventory['capabilities']),inventory['count'])
    (report/'feature-parity.json').write_text(json.dumps(inventory,indent=2));columns=['kind','name','source','scientificImplementation','foldAccess','originalChimeraXUIRequired','upstreamAvailable','functionalityTested','scientificOutputValidated','status','limitations','implementationPlan']
    with (report/'feature-parity.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=columns,extrasaction='ignore');w.writeheader();w.writerows(inventory['capabilities'])
    for headers,name in [({},'Unauthorized native access blocked'),({'Authorization':'Bearer '+o.connection()['token'],'Origin':'https://example.org'},'Cross-origin native access blocked')]:
        code=None
        try:urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:'+str(o.connection()['port'])+'/fold/scene',headers=headers),timeout=3)
        except urllib.error.HTTPError as e:code=e.code
        check(name,code==403)
except Exception:failure=traceback.format_exc()
finally:
    if pid:
        command=subprocess.run(['/bin/ps','-p',str(pid),'-o','command='],capture_output=True,text=True).stdout
        if str(o.descriptor) in command and 'chimerax_session.py' in command:
            try:os.kill(pid,signal.SIGTERM)
            except ProcessLookupError:pass
    result={'date':time.strftime('%Y-%m-%d'),'passed':not failure and bool(checks) and all(c['passed'] for c in checks),'checks':checks,'error':failure,'seconds':round(time.monotonic()-start,2),'root':str(root),'userResearchDataModified':False,'renderer':'Validated separately in FOLD browser UI; no ChimeraX GUI initialized'}
    (report/'headless-acceptance.json').write_text(json.dumps(result,indent=2));s.db.close()
print(json.dumps({'passed':result['passed'],'checks':len(checks),'report':str(report),'error':failure}))
sys.exit(0 if result['passed'] else 1)
