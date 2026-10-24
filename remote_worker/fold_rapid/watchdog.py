"""Evidence rules, not an inferred diagnosis or automatic expensive recovery."""
def diagnose(state,error='',log='',probe=None):
    observations=[];text=(error+'\n'+log).lower()
    rules=[('gpu_out_of_memory',('cuda out of memory','resource_exhausted: out of memory','cuda_error_out_of_memory')),
           ('host_allocation_failure',('std::bad_alloc','cannot allocate memory','memoryerror')),
           ('missing_checkpoint',('checkpoint not found','missing checkpoint','weights not found')),
           ('cuda_runtime_failure',('no cuda gpus are available','cuda_error','unable to initialize backend','failed to initialize cublas')),
           ('sequence_or_coordinate_integrity',('checksum mismatch','sequence and coordinates disagree','fixed residue changed'))]
    for category,patterns in rules:
        matched=[p for p in patterns if p in text]
        if matched:observations.append({'category':category,'matchedEvidence':matched,'confidence':'literal_error_signature'})
    if state=='deadline_exceeded':observations.append({'category':'stage_timeout','matchedEvidence':['enforced supervisor deadline'],'confidence':'observed'})
    if 'cuda startup exceeded' in text:observations.append({'category':'cuda_startup_timeout','matchedEvidence':['120-second supervised CUDA startup limit'],'confidence':'observed'})
    return {'schemaVersion':1,'stageState':state,'observations':observations,'diagnosis':'evidence_available' if observations else 'cause_unresolved','numericalCUDAProbePassed':bool((probe or {}).get('passed')),'scientificModelReferenceQualified':False,'automaticRetry':False,'recovery':{'preserveArtifacts':True,'reuseCompletedParentOutputs':True,'exactOptimizerResume':False,'newPaidStageRequiresApproval':True},'limits':['Device visibility or a numerical probe alone does not certify model performance.','A timeout does not identify whether compilation or inference was slow.']}
