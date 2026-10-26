"""Original FOLD presentation adapter for the installed, GUI-free ChimeraX.

This exports real engine objects, not commands reinterpreted as viewer actions.
The view CIF is a disposable transport encoding of native atoms in scene space.
Scientific imports, exports, calculations and sessions remain native ChimeraX.
"""
import base64, contextlib, hashlib, io, json, math, traceback
import numpy as np
from polymer_identity import chemical_identity

def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def packed(array,dtype):
    return base64.b64encode(np.ascontiguousarray(array,dtype=dtype).tobytes()).decode('ascii')
def visible(model):
    while model is not None:
        if not model.display:return False
        model=model.parent
    return True
def token(value):
    value=str(value)
    if '\n' in value or ('"' in value and "'" in value):return '\n;\n'+value+'\n;\n'
    if not value:return "''"
    if any(c.isspace() for c in value) or value[0] in '#_$;[]' or value in ('.','?') or '"' in value or "'" in value:
        quote='"' if "'" in value else "'"
        return quote+value+quote
    return value
def loop(names,rows):
    if not rows:return ''
    return 'loop_\n'+'\n'.join(names)+'\n'+'\n'.join(' '.join(token(v) if v is not None else '.' for v in row) for row in rows)+'\n#\n'

class SceneBridge:
    def __init__(self,session,identity):
        self.session=session;self.identity=identity;self.cache={};self.python_globals={'session':session,'__name__':'__fold_scientific__'}
        self.atoms={};self.models={};self.atom_handles={};self.atom_serial=0
        session.main_view.resize(1280,800)
    def camera(self):
        view=self.session.main_view;camera=view.camera
        return {'name':camera.name,'matrix':camera.position.matrix.tolist(),
            'position':list(map(float,camera.position.origin())),
            'direction':list(map(float,camera.view_direction())),
            'target':list(map(float,view.center_of_rotation)),
            'fieldOfView':float(getattr(camera,'field_of_view',30)),
            'fieldWidth':getattr(camera,'field_width',None)}
    def set_camera(self,p):
        from chimerax.geometry import Place
        position=np.asarray(p['position'],dtype=float);target=np.asarray(p['target'],dtype=float);up=np.asarray(p['up'],dtype=float)
        if any(v.shape!=(3,) or not np.isfinite(v).all() for v in (position,target,up)):raise ValueError('Camera requires three finite XYZ vectors.')
        z=position-target
        if np.linalg.norm(z)<1e-6:raise ValueError('Camera position and target overlap.')
        z/=np.linalg.norm(z);x=np.cross(up,z)
        if np.linalg.norm(x)<1e-6:raise ValueError('Camera up vector is degenerate.')
        x/=np.linalg.norm(x);y=np.cross(z,x)
        view=self.session.main_view;view.camera.position=Place(axes=(x,y,z),origin=position);view.center_of_rotation=target
        if hasattr(view.camera,'field_of_view'):
            fov=float(p.get('fieldOfView',30))
            if not 1<=fov<=150:raise ValueError('Invalid camera field of view.')
            view.camera.field_of_view=fov
        return {'state':'completed','camera':self.camera()}
    def atomic_model(self,model):
        from chimerax.atomic import Residue
        native_atoms=list(model.atoms);index={a:i for i,a in enumerate(native_atoms)}
        coords=model.atoms.scene_coords
        if not np.isfinite(coords).all():raise ValueError('Native model #'+model.id_string+' has nonfinite coordinates.')
        chains={};seq_index={};chain_specs={}
        for chain in model.chains:
            chain_specs[chain.chain_id]=chain.string(style='command',include_structure=True)
            for i,residue in enumerate(chain.residues,1):
                if residue is not None:seq_index[residue]=i
        rows=[];bonds=[];residues={};site=[];entities={};components={};identities={}
        for i,(a,xyz) in enumerate(zip(native_atoms,coords)):
            r=a.residue;chain=r.chain_id
            if r not in identities:
                identities[r]=chemical_identity(r.name,'L-peptide linking' if r.polymer_type==Residue.PT_AMINO else '',atom_names=[atom.name for atom in r.atoms])
            polymer_kind=identities[r]['polymerType']
            if chain not in chains:chains[chain]='C'+str(len(chains)+1)
            polymer=r.polymer_type!=Residue.PT_NONE
            entity_key=(chain,'polymer' if polymer else r.name)
            if entity_key not in entities:entities[entity_key]=str(len(entities)+1)
            entity=entities[entity_key];label=seq_index.get(r,r.number) if polymer else None
            pointer=hash(a);handle=self.atom_handles.get(pointer)
            if handle is None or handle[0].deleted:
                self.atom_serial+=1;handle=(a,self.identity+':atom:'+str(self.atom_serial));self.atom_handles[pointer]=handle
            key=handle[1];self.atoms[key]=a
            style=int(a.draw_mode)
            row={'key':key,'spec':a.string(style='command',omit_structure=False),'index':i,'chain':chain,'labelChain':chains[chain],
                'residue':r.number,'label':label,'insertion':r.insertion_code,'residueName':r.name,
                'polymerType':polymer_kind,'atom':a.name,'element':a.element.name,'serial':a.serial_number,'altLoc':a.alt_loc.strip(),
                'xyz':list(map(float,xyz)),'bFactor':float(a.bfactor),'occupancy':float(a.occupancy),
                'radius':float(a.radius),'color':[int(v) for v in a.color],
                'ribbonColor':[int(v) for v in r.ribbon_color],
                'shown':bool(a.display),'ribbonShown':bool(r.ribbon_display),
                'style':style,'selected':bool(a.selected),'secondaryStructure':int(r.ss_type)}
            rows.append(row);residues[r]=row
            components[r.name]={'Protein':'L-peptide linking','DNA':'DNA linking','RNA':'RNA linking'}.get(polymer_kind,'other') if polymer else 'non-polymer'
            site.append(['ATOM' if polymer else 'HETATM',i+1,a.element.name,a.name,a.alt_loc.strip() or None,r.name,chains[chain],entity,label,r.insertion_code or None,
                *(format(float(v),'.10g') for v in xyz),float(a.occupancy),float(a.bfactor),r.number,r.name,chain,a.name,1])
        for bond in model.bonds:
            a,b=bond.atoms
            if a in index and b in index:bonds.append({'a':index[a],'b':index[b],'shown':bool(bond.display),'radius':float(bond.radius)})
        geometry=digest({'atoms':[{k:a[k] for k in ('key','chain','labelChain','residue','label','insertion','residueName','atom','element','altLoc','xyz','bFactor','occupancy','secondaryStructure','polymerType')} for a in rows],'bonds':bonds})
        cache=self.cache.get(model.id_string)
        if not cache or cache['geometry']!=geometry:
            cif='data_fold_native_view\n#\n'
            cif+=loop(['_entity.id','_entity.type'],[(value,'polymer' if key[1]=='polymer' else 'non-polymer') for key,value in entities.items()])
            poly_types=[]
            for key,value in entities.items():
                if key[1]!='polymer':continue
                kinds={identities[r]['polymerType'] for r in residues if r.chain_id==key[0] and r.polymer_type!=Residue.PT_NONE}
                kind='Protein' if kinds=={'Protein'} else 'DNA' if kinds=={'DNA'} else 'RNA' if kinds=={'RNA'} else 'DNA/RNA hybrid' if kinds and kinds<={'DNA','RNA','DNA/RNA hybrid'} else 'other'
                poly_types.append((value,{'Protein':'polypeptide(L)','DNA':'polydeoxyribonucleotide','RNA':'polyribonucleotide','DNA/RNA hybrid':'polydeoxyribonucleotide/polyribonucleotide hybrid'}.get(kind,'other')))
            cif+=loop(['_entity_poly.entity_id','_entity_poly.type'],poly_types)
            cif+=loop(['_chem_comp.id','_chem_comp.type','_chem_comp.mon_nstd_flag','_chem_comp.name'],[(name,kind,'n',name) for name,kind in components.items()])
            names=['group_PDB','id','type_symbol','label_atom_id','label_alt_id','label_comp_id','label_asym_id','label_entity_id','label_seq_id','pdbx_PDB_ins_code','Cartn_x','Cartn_y','Cartn_z','occupancy','B_iso_or_equiv','auth_seq_id','auth_comp_id','auth_asym_id','auth_atom_id','pdbx_PDB_model_num']
            cif+=loop(['_atom_site.'+name for name in names],site)
            ssrows=[];sheetrows=[];segments=[]
            for r,a in residues.items():
                kind='helix' if r.is_helix else 'strand' if r.is_strand else None
                if not kind:continue
                if segments and segments[-1][0]==kind and segments[-1][2]['labelChain']==a['labelChain'] and segments[-1][2]['label']+1==a['label']:
                    segments[-1][2]=a
                else:segments.append([kind,a,a])
            for kind,start,end in segments:
                values=[start['residueName'],start['labelChain'],start['label'],end['residueName'],end['labelChain'],end['label']]
                if kind=='helix':ssrows.append(['HELX_P','H'+str(len(ssrows)+1),*values,1])
                else:sheetrows.append(['S'+str(len(sheetrows)+1),1,*values])
            cif+=loop(['_struct_conf.'+n for n in ['conf_type_id','id','beg_label_comp_id','beg_label_asym_id','beg_label_seq_id','end_label_comp_id','end_label_asym_id','end_label_seq_id','pdbx_PDB_helix_class']],ssrows)
            cif+=loop(['_struct_sheet_range.'+n for n in ['sheet_id','id','beg_label_comp_id','beg_label_asym_id','beg_label_seq_id','end_label_comp_id','end_label_asym_id','end_label_seq_id']],sheetrows)
            cache={'geometry':geometry,'cif':cif};self.cache[model.id_string]=cache
        appearance=digest({'display':visible(model),'atoms':[{k:a[k] for k in ('color','ribbonColor','shown','ribbonShown','style','selected','radius')} for a in rows]})
        return {'id':model.id_string,'instance':str(id(model)),'name':model.name,'geometry':geometry,'appearance':appearance,
            'display':visible(model),'atoms':rows,'bonds':bonds,'cif':cache['cif'],
            'chains':[{'id':c.chain_id,'spec':c.string(style='command',include_structure=True),'residues':c.num_residues} for c in model.chains],
            'coordsets':list(map(int,model.coordset_ids)),'activeCoordset':int(model.active_coordset_id)}
    def scene(self,known=None):
        from chimerax.atomic import AtomicStructure, MolecularSurface, check_for_changes
        check_for_changes(self.session)
        from chimerax.core.models import Surface
        self.atoms={};self.models={};models=[];meshes=[];labels=[];unsupported=[]
        # No GUI frame loop exists in this process. Invoke the original CPU
        # contour updater explicitly; never initialize an image/GL renderer.
        from chimerax.map import Volume
        for volume in self.session.models.list(type=Volume):
            if volume.surface_shown:volume._update_surfaces()
        native_models=self.session.models.list()
        for plane in self.session.main_view.clip_planes.planes():
            unsupported.append({'id':'clip:'+plane.name,'name':'Clip plane '+plane.name,'reason':'Native clipping plane is active but has no FOLD visual adapter yet. Turn it off with clip off.'})
        atomic=self.session.models.list(type=AtomicStructure)
        if sum(m.num_atoms for m in atomic)>250000:raise ValueError('The current renderer adapter supports at most 250,000 atoms per transfer. The engine models are retained; use a smaller selection/export.')
        for model in atomic:
            self.models[model.id_string]=model;models.append(self.atomic_model(model))
        for model in native_models:
            if type(model).__name__=='ObjectLabels':
                if not visible(model):continue
                for i,label in enumerate(model.labels()):
                    if label.custom_image is not None:
                        unsupported.append({'id':model.id_string,'name':'Custom image label','reason':'Image labels have no FOLD adapter.'});continue
                    location=label.location(model.scene_position)
                    if location is None or not label.visible():continue
                    xyz=model.scene_position*location
                    camera=self.session.main_view.camera.position
                    xyz=xyz+camera.transform_vector(label.offset)
                    labels.append({'id':model.id_string+':'+str(i),'text':label.text,'xyz':list(map(float,xyz)),
                        'color':list(map(int,label.color)),'height':float(label.height or 0.7)})
                continue
            if isinstance(model,Surface) and visible(model):
                if isinstance(model,MolecularSurface):model.calculate_surface_geometry()
                vertices,triangles=model.vertices,model.triangles
                if vertices is None or triangles is None:continue
                if len(triangles)>2000000:
                    unsupported.append({'id':model.id_string,'name':model.name,'reason':'Native mesh exceeds 2,000,000 triangle transfer limit.'});continue
                vertices=np.array(vertices,copy=True);model.scene_position.transform_points(vertices,in_place=True)
                normals=model.normals
                if normals is not None:
                    normals=np.array(normals,copy=True);model.scene_position.transform_vectors(normals,in_place=True)
                if model.triangle_mask is not None:triangles=triangles[model.triangle_mask]
                colours=model.vertex_colors
                mesh={'id':model.id_string,'name':model.name,'vertices':packed(vertices,'<f4'),'triangles':packed(triangles,'<u4'),
                    'normals':packed(normals,'<f4') if normals is not None else None,'color':[int(v) for v in model.color],
                    'colors':packed(colours,'u1') if colours is not None else None,'vertexCount':len(vertices),'triangleCount':len(triangles)}
                mesh['revision']=digest(mesh);meshes.append(mesh)
            elif not isinstance(model,AtomicStructure) and type(model).__name__ not in ('Model','PseudobondGroup'):
                if not isinstance(model,Surface):unsupported.append({'id':model.id_string,'name':model.name,'type':type(model).__name__,'reason':'Engine object has no complete FOLD visual adapter yet.'})
        pseudobonds=[]
        for model in native_models:
            for pb in getattr(model,'pseudobonds',[]):
                if not visible(model) or not pb.display:continue
                a,b=pb.atoms
                pseudobonds.append({'id':model.id_string,'name':model.name,'a':list(map(float,a.scene_coord)),'b':list(map(float,b.scene_coord)),'length':float(pb.length),'color':list(map(int,pb.color)),'radius':float(pb.radius)})
        camera=self.camera();lighting=self.session.main_view.lighting
        visual={'models':[(m['id'],m['instance'],m['geometry'],m['appearance']) for m in models],
            'meshes':[(m['id'],m['revision']) for m in meshes],'pseudobonds':pseudobonds,'labels':labels,'unsupported':unsupported}
        revision=digest(visual);result={'schemaVersion':1,'sessionId':self.identity,'revision':revision,'camera':camera,'cameraRevision':digest(camera),
            'models':models,'meshes':meshes,'pseudobonds':pseudobonds,'labels':labels,'unsupported':unsupported,'engineGui':bool(self.session.ui.is_gui),
            'lighting':{'ambient':float(lighting.ambient_light_intensity),'key':float(lighting.key_light_intensity),'fill':float(lighting.fill_light_intensity)},
            'rendering':'FOLD Mol* viewport; native atoms, bonds, colours and surface meshes; renderer-specific ribbons and lighting'}
        if known==revision:return {k:result[k] for k in ('schemaVersion','sessionId','revision','camera','cameraRevision','engineGui','lighting','unsupported')}
        return result
    def select(self,p):
        # Rebuild handle lookup if no scene has yet been requested.
        if not self.atoms:self.scene()
        keys=p.get('keys',[])
        if not isinstance(keys,list) or len(keys)>250000:raise ValueError('Invalid atom selection.')
        if any(key not in self.atoms or self.atoms[key].deleted for key in keys):raise ValueError('Selection refers to atoms from an expired scene. Refresh the structure.')
        self.session.selection.clear()
        for key in keys:self.atoms[key].selected=True
        return {'state':'completed','selected':len(keys)}
    def measure(self,p):
        if not self.atoms:self.scene()
        keys=p.get('keys',[])
        if not isinstance(keys,list) or not 2<=len(keys)<=4 or any(not isinstance(k,str) or k not in self.atoms or self.atoms[k].deleted for k in keys):raise ValueError('Choose 2–4 current native atoms.')
        if len(set(keys))!=len(keys):raise ValueError('Choose distinct atoms in measurement order.')
        points=[np.asarray(self.atoms[k].scene_coord,dtype=float) for k in keys]
        if any(point.shape!=(3,) or not np.isfinite(point).all() for point in points):raise ValueError('Measurement coordinates must be finite three-dimensional points.')
        if len(points)>=3:
            bonds=np.diff(np.asarray(points),axis=0);lengths=np.linalg.norm(bonds,axis=1)
            if np.any(lengths<=1e-12):raise ValueError('An angle or dihedral is undefined for coincident consecutive atoms.')
            if len(points)==4:
                directions=bonds/lengths[:,None]
                if any(np.linalg.norm(np.cross(directions[i],directions[i+1]))<=1e-12 for i in (0,1)):raise ValueError('A dihedral is undefined when three consecutive atoms are collinear.')
        from chimerax.geometry import distance,angle,dihedral
        function={2:distance,3:angle,4:dihedral}[len(points)]
        value=float(function(*points))
        if not math.isfinite(value):raise ValueError('The native engine returned a non-finite measurement.')
        return {'kind':{2:'distance',3:'angle',4:'dihedral'}[len(points)],'value':value,
            'unit':'Å' if len(points)==2 else 'degrees','method':'chimerax.geometry.'+function.__name__,
            'atoms':[{'key':key,'spec':self.atoms[key].string(style='command',omit_structure=False),'xyz':list(map(float,point))} for key,point in zip(keys,points)],'sessionId':self.identity}
    def python(self,p):
        code=str(p.get('code',''))
        if not code.strip() or len(code)>262144:raise ValueError('Enter a Python script below 256 KB.')
        from chimerax.core.commands import run
        from chimerax.core.logger import StringPlainTextLog
        self.python_globals.update(session=self.session,run=run)
        stdout=io.StringIO();stderr=io.StringIO();error=None
        with StringPlainTextLog(self.session.logger) as log,contextlib.redirect_stdout(stdout),contextlib.redirect_stderr(stderr):
            try:exec(compile(code,'<FOLD Scientific Python>','exec'),self.python_globals,self.python_globals)
            except Exception as exc:error={'type':type(exc).__name__,'message':str(exc),'traceback':traceback.format_exc()}
        return {'state':'failed' if error else 'completed','stdout':stdout.getvalue(),'stderr':stderr.getvalue(),'log':log.getvalue(),'error':error,'sessionId':self.identity}
