"""Versioned provider profiles. Initial resources are hypotheses, not fit claims."""
SCHEMA=1
CHECKED='2026-10-24'
SOURCES=['https://modal.com/docs/guide/gpu','https://modal.com/pricing','https://developer.nvidia.com/cuda/gpus','https://modal.com/blog/introducing-b200-h200']
# Explicit identifiers avoid provider opt-in upgrade aliases.
PROFILES=[
 ('T4',16,'7.5',.000164,2,16),('L4',24,'8.9',.000222,4,24),('A10',24,'8.6',.000306,4,24),
 ('A100-40GB',40,'8.0',.000583,4,32),('L40S',48,'8.9',.000542,4,32),('A100-80GB',80,'8.0',.000694,4,64),
 ('H100',80,'9.0',.001097,4,64),('RTX-PRO-6000',96,'12.0',.000842,4,64),('H200',141,'9.0',.001261,8,96),
 ('B200',180,'10.0',.001736,8,96),('B300',288,'10.3',.001972,8,128)]
ENGINES=['bindcraft2','proteinmpnn','solublempnn','af2_multimer','boltzgen','esmfold2_fast','esmfold2','rfdiffusion','esmc','rosetta','structure_screen']

def catalog():
 rows=[]
 for id,vram,cc,rate,cpu,ram in PROFILES:
  matrix=[]
  for engine in ENGINES:
   status='supported_not_gpu_qualified';reason='No controlled scientific benchmark on this GPU; peak VRAM and fit remain unverified.'
   if engine in ('esmfold2','esmfold2_fast','boltzgen'):status='blocked_missing_checkpoint';reason='Adapter exists; complete checkpoint-backed cloud inference qualification remains required.'
   if engine=='esmc':status='blocked_missing_execution_path';reason='Design execution has not been completed.'
   if engine=='rfdiffusion':status='blocked_workflow_handoff';reason='Atomic motif handoff and full campaign qualification remain incomplete.'
   if engine=='rosetta':status='blocked_license';reason='Authorized private licensed runtime is required.'
   if id=='A100-80GB' and engine in ('bindcraft2','proteinmpnn','solublempnn'):
    status='inference_observed';reason='Real 174-residue campaign outputs exist; task peak VRAM and numerical reference qualification remain incomplete.'
   if id=='A100-80GB' and engine=='af2_multimer':status='partial_inference_observed';reason='One actual model output; the reviewed two-model stage exceeded 480 seconds. Full evaluation incomplete.'
   if id=='B300' and engine not in ('rosetta','structure_screen'):
    status='requires_different_runtime';reason='Modal B300 requires CUDA 13.1+; the current pinned recipe uses CUDA 13.0.2.'
   if engine=='structure_screen':status='cpu_analysis';reason='Remote CPU structural inspection; GPU qualification is not applicable.'
   matrix.append({'engine':engine,'state':status,'reason':reason,'measuredPeakVRAMMiB':None})
  rows.append({'id':id,'provider':'modal','vramGiB':vram,'computeCapability':cc,'gpuSecondUSD':rate,'gpuHourUSD':rate*3600,'initialCPUsPhysical':cpu,'initialHostMemoryGiB':ram,'resourceBasis':'provisional_not_measured','runtime':'rapid-cuda13-core-v1','concurrency':1,'cachePolicy':'Separate scientific workers; no cross-architecture compilation cache reuse.','engines':matrix})
 return {'schemaVersion':SCHEMA,'checked':CHECKED,'sources':SOURCES,'profiles':rows,'priceScope':'Snapshot; review current provider rates before paid approval. GPU only; CPU, host RAM and storage are additional.','lowestMeasuredCostGPU':None,'cpuUnit':'Modal physical cores (2 vCPU equivalent)','smallerGPUCampaignQualified':False}

def preflight(gpu,engines):
 found=next((r for r in catalog()['profiles'] if r['id']==gpu),None)
 if not found:raise ValueError('Unknown explicit GPU identifier.')
 return {**found,'selectedEngines':[r for r in found['engines'] if r['engine'] in engines],'scientificFitValidated':False,'automaticGPUUpgrade':False}
