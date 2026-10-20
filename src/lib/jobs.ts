import type {Item,Job} from './types';

export function jobPresentation(engine:Job['engine']){
 return ({boltz2:{label:'Boltz-2',location:'local'},colabfold:{label:'ColabFold',location:'cloud'},setup:{label:'Engine setup',location:'local'},proteinmpnn:{label:'ProteinMPNN',location:'local'},bindcraft2:{label:'BindCraft2',location:'local'},rdkit:{label:'RDKit',location:'local'},openmm:{label:'OpenMM',location:'local'}} as const)[engine]??{label:String(engine),location:'unknown'};
}

/** A saved sequence is never a coordinate asset, even when it came from a job. */
export function firstJobOutput(job:Job,records:Item[]){
 const record=records.find(r=>r.id===job.data.outputs?.[0]&&r.project_id===job.project_id);
 if(record?.kind==='structure')return {kind:'coordinates' as const,record};
 if(record?.kind==='sequence')return {kind:'sequence' as const,record};
 return null;
}

export function campaignResultMessage(result:any):string{
 if(result.engine==='bindcraft2'){
  if(result.state==='completed')return result.data?.outcome==='no_accepted_designs'?'Campaign finished. No candidate passed the original scientific filters.':'Campaign finished. Saved coordinate outputs are available in Research Library.';
  if(result.state==='running')return 'Campaign is running. Observed optimizer updates appear below.';
  if(result.state==='queued')return 'Campaign queued for calculation.';
  if(result.state==='failed')return 'Campaign failed. Review the saved error and execution log.';
  if(result.state==='cancelled')return 'Campaign cancelled.';
  if(result.state==='interrupted')return 'Campaign interrupted. Saved inputs and outputs remain available; continuation uses the remaining attempt budget.';
  if(result.state==='imported')return 'Ranked coordinate outputs imported.';
  return 'Campaign prepared. Original inputs and settings are saved.';
 }
 if(result.engine==='proteinmpnn')return 'ProteinMPNN job '+result.state+'.';
 if(result.valid)return 'Configuration checked for preparation.';
 if(result.state==='imported')return 'Ranked structures imported.';
 if(result.state==='already_imported')return 'These ranked structures are already saved.';
 return 'Compute diagnostics completed.';
}
