export type CloudEvent={schemaVersion:number;eventId:string;cursor:number;timestamp:string;engine:string;stageId:string;source:string;category:string;severity:string;message:string;candidateId?:string;campaignId?:string};
export const COMMANDS=['help','status','version','health','gpu status','gpu memory','gpu utilization','gpu processes','gpu info','worker status','worker resources','worker models','models list','models status','campaign list','campaign status','campaign stages','campaign logs','campaign candidates','campaign results','campaign stop','candidate list','candidate inspect','candidate metrics','candidate lineage','candidate compare','candidate structure','cloud account','cloud workspace','cloud gpu','cloud cost','cloud deployment','performance status','performance report','cuda status','cuda validate','memory status','runtime inspect','stage timings'];
export function mergeEvents(old:CloudEvent[],incoming:CloudEvent[],limit=8000){const seen=new Set(old.map(e=>e.eventId));return [...old,...incoming.filter(e=>{if(seen.has(e.eventId))return false;seen.add(e.eventId);return true;})].sort((a,b)=>a.cursor-b.cursor).slice(-limit);}
export function scientificEvent(event:CloudEvent):CloudEvent{
 // Modal returns structured worker events inside genuine stdout. Keep the raw
 // record untouched; decode only presentation fields in Scientific Activity.
 if(!event.message.startsWith('RAPID_EVENT '))return event;
 try{
  const value=JSON.parse(event.message.slice('RAPID_EVENT '.length));
  if(typeof value.message!=='string'||typeof value.category!=='string'||
   (value.campaignId&&value.campaignId!==event.campaignId)||
   (value.stageId&&value.stageId!==event.stageId)||
   (value.engine&&value.engine!==event.engine))return event;
  return {...event,message:value.message,category:value.category,severity:['info','warning','error'].includes(value.severity)?value.severity:event.severity};
 }catch{return event;}
}
export function filterEvents(events:CloudEvent[],options:{search:string;engine:string;severity:string;stage:string;after:number;raw:boolean}){const q=options.search.toLowerCase();return events.map(e=>options.raw?e:scientificEvent(e)).filter(e=>(!options.raw||e.source!=='campaign_journal')&&e.cursor>options.after&&(!options.engine||e.engine===options.engine)&&(!options.stage||e.stageId===options.stage)&&(!options.severity||e.severity===options.severity)&&(!q||e.message.toLowerCase().includes(q))&&(options.raw||(e.category!=='resources'&&!!e.message.trim()))).filter((e,i,a)=>options.raw||i===0||e.message!==a[i-1].message);}
export function metric(value:unknown){if(value===null||value===undefined||value==='')return '—';const n=Number(value);return Number.isFinite(n)?n.toFixed(2):'—';}

export function activityMessage(event:CloudEvent){
 try{const value=JSON.parse(event.message);if(value.operation&&value.candidateId){const action=({CREATE:'Candidate retained',REDESIGN:'New sequence redesign retained',REFOLD:'Fresh structure prediction retained',EVALUATE:'Structural assessment recorded',REJECT:'Candidate rejected'} as Record<string,string>)[value.operation]??value.operation;return `${action} · ${value.candidateId.slice(0,12)}`;}if(value.reason)return String(value.reason);}catch{/* Actual plain model output remains unchanged. */}return event.message;
}
export function redactCommand(text:string){return text.replace(/((?:token[_-]?(?:id|secret)|api[_-]?key|authorization|password)\s*[=:]\s*["']?)([^\s"',;}]+)/gi,'$1[redacted]').replace(/\b(?:ak|as|sk|pk)-[A-Za-z0-9_-]{16,}\b/g,'[redacted]');}
