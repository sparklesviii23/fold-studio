import type {Job} from './types';
export const architectSections=['Overview','Target & Design','Scientific Settings','Compute & Run','Campaign Library','Biology-Guided Design'] as const;
export const designFormats=[
 ['binder','Miniprotein binder','Compact protein binders','Validated bounded workflow'],['peptide','Linear peptide binder','Flexible peptide backbones','Experimental · memory bounded'],['Fab','Fab antibody','Complete heavy and light chains','Cloud-only · qualification pending'],['VHH','Nanobody','Original VHH scaffold and CDR preset','Experimental'],['ARP','Ankyrin repeat','Original repeat scaffold','Experimental'],['scFv','Paired antibody domains','Heavy and light variable domains; no designed linker','Resource limited'],['cyclic_peptide','Cyclic peptide','Head-to-tail peptide design','Experimental'],['homo_oligomer','Homodimer','Two identical designed chains','Experimental'],['large_binder','Large binder','Extended upstream optimization preset','Resource limited'],['multidomain','Multidomain binder','Original domain and linker objectives','Resource limited'],['induced_fit','Induced fit','Bound and unbound interface change','Experimental · bounded'],['fold_switch','Fold switch','Bound and unbound global fold change','Experimental · bounded']
] as const;
export const propertyNames:Record<string,string>={bigbang:'Dispersed initialization',disulfide_staple:'Disulfide stabilization',forced_targeting:'Directed epitope targeting',humanize:'Human sequence preference'};
export function observedProgress(job:Job){
 const p=job.data.executionProgress;
 if(!p?.trajectory)return job.state==='prepared'?'Inputs saved · not started':'No upstream stage result recorded';
 const last=p.lastReportedStage?`${p.lastReportedStage} ${p.stageOutcome}`:'no completed stage recorded';
 return `${['running','queued'].includes(job.state)?'Current':'Last observed'} trajectory ${p.trajectory} · ${last}`;
}
export function resumeEligibility(job:Job){
 if(job.data.preparation?.modality==='Fab'||job.data.profile==='experimental-cpu-fab-amme')return false;
 const c=job.data.preparation?.config;const attempts=job.data.executionProgress?.trajectory;
 return ['failed','cancelled','interrupted'].includes(job.state)&&!!job.data.profile&&!(typeof attempts==='number'&&typeof c?.max_trajectories==='number'&&attempts>=c.max_trajectories);
}
export const architectDraftKey=(projectId:string)=>'fold-bindcraft-draft-v1:'+projectId;
