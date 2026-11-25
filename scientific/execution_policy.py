"""Client dispatch firewall: selecting cloud never invokes a Mac scientific stage."""
import json
import scientific_capabilities

ACTIONS={'execution_backend_get','execution_backend_select'}
# File preparation, editing and viewer rendering remain native. Scientific
# computation is refused here rather than redirected through a local fallback.
LOCAL_SCIENCE={
 'qwen_rna_start',
 'bio_controller_local_run',
 'genomic_coverage','periodic_lj_run','genomic_alignment_import','chemical_screen','sequence_align','reads_import','quantum_reaction','quantum_calculate','research_assay_fit',
 'prediction_start','install_engine','mpnn_start','dynamics_start','dynamics_continue','ligand_start',
 'bindcraft_start','bindcraft_repeat','bindcraft_resume','bindcraft_prepare','fold_compute','fold_structure','fold_fragment','fold_target',
 'biology_pipeline_start','biology_counterfactual_start','biology_bindcraft_prepare','biology_agent_start','biology_agent_ask','biology_peptide_chemistry_start',
 'intelligence_start','intelligence_auto','intelligence_prioritize','intelligence_screen','intelligence_scramble','intelligence_prepare','intelligence_compare','intelligence_hotspots',
 'research_candidate','research_contacts','research_variants','research_full_target','research_screen_plan','evolution_compare','peptide_geometry','peptide_structure','peptide_transfer','comparison_run','chimerax_measure','chimerax_python',
}


def selected(s):
    value=s.setting('executionBackend',{'mode':'local'})
    if not isinstance(value,dict) or value.get('mode') not in ('local','modal','vast'):raise ValueError('Invalid execution backend selection; choose the backend explicitly.')
    return value


def enforce(s,action,payload):
    scientific_capabilities.enforce(s,action,payload)
    mode=selected(s)['mode'];requested=payload.get('executionMode') if isinstance(payload,dict) else None
    cloud=mode!='local' or requested in ('cloud','modal','vast')
    if not cloud:return
    if action in LOCAL_SCIENCE:raise ValueError('Cloud Mode prohibits local scientific execution ('+action+'). Submit a complete remote campaign through Cloud Compute. No local fallback was invoked.')
    if action=='chimerax_execute':
        # Arbitrary console commands can launch calculations or Python. Native
        # scene/camera/selection APIs still support client-side rendering.
        raise ValueError('Cloud Mode permits the viewer scene/camera controls but blocks arbitrary local molecular commands. Submit scientific commands to the remote backend.')


def dispatch(s,action,p):
    if action=='execution_backend_get':return {**selected(s),'localScientificFallback':False,'cloudControllerLocation':'remote','fullFab':scientific_capabilities.FAB_POLICY}
    if action=='execution_backend_select':
        mode=p.get('mode')
        if mode not in ('local','modal','vast'):raise ValueError('Choose Local Apple Metal, Cloud Modal or Cloud Vast.')
        if mode!=selected(s)['mode'] and s.active():raise ValueError('Finish or cancel the currently active local scientific job before switching execution backends.')
        if mode=='vast' and not p.get('profileId'):raise ValueError('Select an existing secure Vast/SSH profile.')
        if mode=='vast':
            import cloud_compute
            cloud_compute.CloudCompute(s).profile(p['profileId'])
        value={'mode':mode,**({'profileId':p['profileId']} if mode=='vast' else {})}
        with s.db:s.db.execute('INSERT OR REPLACE INTO settings VALUES(?,?)',('executionBackend',json.dumps(value)))
        return {**value,'localScientificFallback':False,'existingRemoteCampaignsCancelled':False}
    raise ValueError('Unsupported execution policy action.')
