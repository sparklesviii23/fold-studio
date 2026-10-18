import type {Item,Job} from './types';

export function jobPresentation(engine:Job['engine']){
 return ({boltz2:{label:'Boltz-2',location:'local'},colabfold:{label:'ColabFold',location:'cloud'},setup:{label:'Engine setup',location:'local'},proteinmpnn:{label:'ProteinMPNN',location:'local'},bindcraft2:{label:'BindCraft2',location:'local'}} as const)[engine]??{label:String(engine),location:'unknown'};
}

/** A saved sequence is never a coordinate asset, even when it came from a job. */
export function firstJobOutput(job:Job,records:Item[]){
 const record=records.find(r=>r.id===job.data.outputs?.[0]&&r.project_id===job.project_id);
 if(record?.kind==='structure')return {kind:'coordinates' as const,record};
 if(record?.kind==='sequence')return {kind:'sequence' as const,record};
 return null;
}
