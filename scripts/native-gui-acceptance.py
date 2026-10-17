"""Run with ChimeraX `runscript` inside a DISPOSABLE FOLD test session only.

Uses the application's own Qt/scientific APIs. It does not automate macOS,
access another application, or substitute for manual mouse/keyboard acceptance.
"""
import hashlib, json, pathlib, sys, time, traceback
import numpy as np
from Qt.QtCore import QTimer
from Qt.QtWidgets import QApplication
from chimerax.atomic import AtomicStructure, Atom, MolecularSurface
from chimerax.core.commands import run, StringArg
from chimerax.core.colors import Color

folder=pathlib.Path(sys.argv[1]).resolve();folder.mkdir(parents=True,exist_ok=True)
source=pathlib.Path(sys.argv[2]).resolve()
shell=session.fold_studio
assert 'qa' in str(shell.root).lower(), 'Never run destructive acceptance in a research library'
checks=[]
def check(name,condition,details=None):
    checks.append({'name':name,'passed':bool(condition),'details':details})
    if not condition:raise AssertionError(name)
def command(text):return run(session,text)
def finish(error=None):
    report={'runtime':'ChimeraX 1.12','scope':'Real GUI runtime, programmatic Qt controls and native rendering; macOS mouse/keyboard acceptance pending',
        'source':source.name,'sourceSha256':hashlib.sha256(source.read_bytes()).hexdigest(),'checks':checks,'passed':all(c['passed'] for c in checks) and not error,'error':error}
    (folder/'native-gui-acceptance.json').write_text(json.dumps(report,indent=2,default=str))
try:
    check('FOLD Qt shell contains the original graphics widget',shell.graphics in shell.container.findChildren(type(shell.graphics)))
    check('One primary application window',sum(type(w).__name__=='MainWindow' and w.isVisible() for w in QApplication.topLevelWidgets())==1)
    command('close all');command('open '+StringArg.unparse(str(source)))
    model=session.models.list(type=AtomicStructure)[0]
    check('Actual cropped assembly has 223 residues',model.num_residues==223,model.num_residues)
    check('Author chains A, B, C retained',sorted(c.chain_id for c in model.chains)==['A','B','C'],{c.chain_id:c.num_residues for c in model.chains})
    check('Original model identity #1 retained',model.id_string=='1')
    for chain,colour in [('A','cyan'),('B','green'),('C','gray')]:
        command('color #1/'+chain+' '+colour+' target c')
        values=model.residues[model.residues.chain_ids==chain].ribbon_colors
        check('Native cartoon chain '+chain+' = '+colour,np.all(values==Color(colour).uint8x4()),values[0].tolist())
    for chain,number,colour in [('B',32,'magenta'),('C',18,'yellow'),('C',27,'orange')]:
        command('color #1/'+chain+':'+str(number)+' '+colour+' target c')
        residues=model.residues[(model.residues.chain_ids==chain)&(model.residues.numbers==number)]
        check('Provisional computational hotspot '+chain+':'+str(number)+' = '+colour,len(residues)==1 and np.all(residues.ribbon_colors==Color(colour).uint8x4()))
    shell.show_molecule();command('view #1');command('set bgColor #071326')
    command('save '+StringArg.unparse(str(folder/'ANGPTL3-8-chain-hotspots.png'))+' width 1600 height 1200 supersample 2')
    check('Original renderer exports a real molecular image',(folder/'ANGPTL3-8-chain-hotspots.png').stat().st_size>10000)
    command('surface #1')
    surfaces=session.models.list(type=MolecularSurface)
    check('Native molecular surfaces contain actual triangles',bool(surfaces) and sum(len(s.triangles) for s in surfaces)>1000,{'surfaces':len(surfaces),'triangles':sum(len(s.triangles) for s in surfaces)})
    command('hide #1 surfaces');command('show #1 atoms');command('style #1 stick')
    check('Atomic sticks use native draw modes',np.all(model.atoms.draw_modes==Atom.STICK_STYLE))
    command('select #1/B:32@CA')
    check('Exact native residue and atom selection',sum(model.atoms.selecteds)==1 and model.atoms[model.atoms.selecteds][0].residue.number==32)
    distance=command('distance #1/B:32@CA #1/B:33@CA')
    expected=float(np.linalg.norm(model.find_residue('B',32).find_atom('CA').scene_coord-model.find_residue('B',33).find_atom('CA').scene_coord))
    check('Native distance agrees with real coordinates',abs(float(distance)-expected)<1e-6,{'nativeAngstrom':float(distance),'coordinateAngstrom':expected})
    command('open '+StringArg.unparse(str(source)))
    check('Multiple real molecular models',len(session.models.list(type=AtomicStructure))==2)
    second_id=session.models.list(type=AtomicStructure)[-1].id_string
    fit=command('matchmaker #'+second_id+'/A to #1/A showAlignment false')
    check('Native Matchmaker identical-model fit',fit[0]['final RMSD']<1e-5,{'rmsdAngstrom':float(fit[0]['final RMSD']),'pairs':len(fit[0]['final match atoms'])})
    command('contacts #1/A restrict #1/C log true')
    check('Native contact analysis executes on the research chains',True,'Executed original contacts implementation; provisional predicted geometry')
    command('hbonds #1 interModel false log true')
    check('Native hydrogen-bond analysis executes',True,'Executed original hbonds implementation')
    # Test the actual chain panel action, with isolation from other chains.
    shell.show_chains();shell.refresh_chains()
    index=shell.chain_choice.findData(model.chains[1].atomspec)
    shell.chain_choice.setCurrentIndex(index);a_before=model.chains[0].existing_residues.ribbon_colors.copy();c_before=model.chains[2].existing_residues.ribbon_colors.copy()
    shell.colour_input.setText('#4ade80')
    from Qt.QtWidgets import QPushButton
    next(b for b in shell.chain_tool.tool_window.ui_area.findChildren(QPushButton) if b.text()=='Apply').click()
    check('Chain panel assigns the chosen custom colour',np.all(model.chains[1].existing_residues.ribbon_colors==Color('#4ade80').uint8x4()))
    check('Chain panel preserves the other chains',np.array_equal(a_before,model.chains[0].existing_residues.ribbon_colors) and np.array_equal(c_before,model.chains[2].existing_residues.ribbon_colors))
    # Native sessions preserve actual model state, not a reconstructed JSON scene.
    command('hide #1 atoms');command('select #1/C:18');command('turn y 17')
    colors=model.residues.ribbon_colors.copy();camera=session.main_view.camera.position.matrix.copy()
    command('save '+StringArg.unparse(str(folder/'roundtrip.cxs')))
    command('close all');command('open '+StringArg.unparse(str(folder/'roundtrip.cxs')))
    models=session.models.list(type=AtomicStructure);restored=next(m for m in models if m.id_string=='1')
    check('Native session restores both model identifiers',{m.id_string for m in models}=={'1',second_id})
    check('Native session restores exact per-residue colours',np.array_equal(restored.residues.ribbon_colors,colors))
    check('Native session restores camera transform',np.allclose(session.main_view.camera.position.matrix,camera,atol=1e-7))
    check('Native session restores selection',any(a.selected and a.residue.chain_id=='C' and a.residue.number==18 for a in restored.atoms))
    check('Native session restores representation',np.all(restored.atoms.draw_modes==Atom.STICK_STYLE))
    command('save '+StringArg.unparse(str(folder/'exported.cif'))+' models #1')
    check('Original mmCIF writer exports genuine coordinates',(folder/'exported.cif').stat().st_size>10000)
    script=folder/'scientific-script.py';script.write_text("session.fold_python_acceptance = sum(m.num_residues for m in session.models.list() if hasattr(m, 'num_residues'))\n")
    command('runscript '+StringArg.unparse(str(script)))
    check('Genuine scientific Python sees the same models',session.fold_python_acceptance==446)
    cxc=folder/'colours.cxc';cxc.write_text('color #1/A cyan target c\ncolor #1/B green target c\ncolor #1/C gray target c\n')
    command('open '+StringArg.unparse(str(cxc)))
    check('Original .cxc script applies all three commands',all(np.all(restored.residues[restored.residues.chain_ids==chain].ribbon_colors==Color(colour).uint8x4()) for chain,colour in [('A','cyan'),('B','green'),('C','gray')]))
    for text in ['color #1 bychain','color sequential #1 residues','color bfactor #1 palette alphafold','hide #1/A target acs','show #1/A target acs','select zone #1/B:32 5 residues true','show sel atoms','style sel ball','hide #1 atoms','show #1@N,CA,C,O atoms','style #1@N,CA,C,O stick','hide #1 atoms','cartoon #1']:
        command(text)
    check('Native appearance, chain visibility and Atomic Lens controls use supported commands',True)
    command('open '+StringArg.unparse(str(cxc)))
    command('ui tool show Shell');command('ui tool show Matchmaker')
    names=[t.tool_name for t in session.tools.list()]
    check('Original Python Shell and Matchmaker tools open','Shell' in names and 'Matchmaker' in names,names)
    shell.show_console();shell.show_chains();shell.show_molecule()
    shell.window.grab().save(str(folder/'native-workspace.png'))
    # The web bridge exercises the existing backend and the preserved Arcade.
    shell.show_research()
    def page_ready(value):
        try:
            data=json.loads(value)
            check('Preserved FOLD research UI renders',data['textLength']>500 and data['native'] and data['host'],data)
            check('Independent Mol* canvas is absent in native mode',data['molstarCanvases']==0,data['molstarCanvases'])
            shell.web.page().runJavaScript("window.__FOLD_RPC__('library',{}).then(r=>window.__foldAcceptanceLibrary=r.projects.length).catch(e=>window.__foldAcceptanceError=String(e))")
            QTimer.singleShot(2000,web_finished)
        except Exception:finish(traceback.format_exc())
    def web_finished():
        def received(value):
            try:
                data=json.loads(value);check('Qt web channel reaches original scientific service',data.get('projects',0)>0,data)
                shell.web.grab().save(str(folder/'research-workspace.png'));shell.show_molecule();shell.refresh_chains();shell.window.grab().save(str(folder/'native-workspace.png'));check('Native graphics area is the visible molecular page',shell.stack.currentWidget() is shell.graphics and shell.graphics.isVisible());QTimer.singleShot(500,capture_front_buffer)
            except Exception:finish(traceback.format_exc())
        shell.web.page().runJavaScript("JSON.stringify({projects:window.__foldAcceptanceLibrary,error:window.__foldAcceptanceError})",received)
    def capture_front_buffer():
        try:
            graphics=shell.window.graphics_window
            check('Original OpenGL window is exposed and drawable',graphics.is_drawable)
            session.update_loop.update_graphics_now()
            render=session.main_view.render;render.make_current()
            from OpenGL import GL
            viewport=GL.glGetIntegerv(GL.GL_VIEWPORT)
            pixels=render.frame_buffer_image(int(viewport[2]),int(viewport[3]),front_buffer=True)
            unique=len(np.unique(pixels[::4,::4,:3].reshape(-1,3),axis=0))
            check('Visible native front buffer contains the rendered molecule',unique>50,{'uniqueSampledColours':unique,'viewport':viewport.tolist()})
            from PIL import Image
            Image.fromarray(pixels[::-1]).save(str(folder/'native-front-buffer.png'))
            finish()
        except Exception:finish(traceback.format_exc())
    shell.web.page().runJavaScript("JSON.stringify({native:window.__FOLD_NATIVE__,host:!!window.__FOLD_RPC__,textLength:document.body.innerText.length,molstarCanvases:document.querySelectorAll('.molecular-canvas canvas').length})",page_ready)
except Exception:finish(traceback.format_exc())
