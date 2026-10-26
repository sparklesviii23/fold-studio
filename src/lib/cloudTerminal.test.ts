import {describe,it,expect} from 'vitest';
import {filterEvents,mergeEvents,metric,type CloudEvent} from './cloudTerminal';
const event=(i:number):CloudEvent=>({schemaVersion:1,eventId:String(i),cursor:i,timestamp:'2026-10-24T12:00:00Z',engine:i%2?'bindcraft2':'af2_multimer',stageId:'stage',source:'archived_stdout_stderr',category:'model_output',severity:i===3?'error':'info',message:'Actual fixture output '+i});
describe('cloud terminal transport',()=>{
 it('deduplicates reconnect overlap and bounds rendered history',()=>{const data=Array.from({length:12000},(_,i)=>event(i));const merged=mergeEvents(data.slice(0,7000),data.slice(6000),8000);expect(merged).toHaveLength(8000);expect(new Set(merged.map(e=>e.eventId)).size).toBe(8000);expect(merged[0].cursor).toBe(4000);});
 it('filters without deleting retained events',()=>{const data=[event(1),event(2),event(3)];expect(filterEvents(data,{search:'3',engine:'bindcraft2',severity:'error',stage:'stage',after:0,raw:true})).toEqual([event(3)]);expect(data).toHaveLength(3);expect(filterEvents(data,{search:'',engine:'',severity:'',stage:'',after:3,raw:true})).toEqual([]);});
 it('never converts missing scientific scores into zero',()=>{for(const absent of [null,undefined,'',NaN])expect(metric(absent)).toBe('—');expect(metric('0.90')).toBe('0.90');});
});

import {activityMessage,redactCommand} from './cloudTerminal';
it('renders recorded journal operations as readable activity without inventing metrics',()=>{expect(activityMessage({...event(1),message:JSON.stringify({operation:'REDESIGN',candidateId:'a'.repeat(64)})})).toBe('New sequence redesign retained · aaaaaaaaaaaa');expect(activityMessage(event(1))).toBe(event(1).message);expect(redactCommand('API_KEY=private-value')).not.toContain('private-value');});

describe('structured worker events inside genuine Modal stdout',()=>{
 const options={search:'',engine:'',severity:'',stage:'',after:0,raw:false};
 const wrapped=(category:string,message:string):CloudEvent=>({...event(1),campaignId:'campaign',message:'RAPID_EVENT '+JSON.stringify({campaignId:'campaign',stageId:'stage',engine:'bindcraft2',category,message,severity:'warning'})});
 it('hides resource envelopes only in Scientific Activity while preserving exact raw output',()=>{
  const row=wrapped('resources','{"observation":{"usedMiB":123}}'),original=JSON.stringify(row);
  expect(filterEvents([row],options)).toEqual([]);
  expect(filterEvents([row],{...options,raw:true})).toEqual([row]);expect(JSON.stringify(row)).toBe(original);
 });
 it('shows actual model text and severity with the original cursor and identity',()=>{
  const row=wrapped('model_output','Original trajectory rejected by i_pTM');
  const output=filterEvents([row],{...options,search:'rejected',severity:'warning'});
  expect(output).toHaveLength(1);expect(output[0].message).toBe('Original trajectory rejected by i_pTM');
  expect(output[0].eventId).toBe(row.eventId);expect(output[0].cursor).toBe(row.cursor);expect(output[0].timestamp).toBe(row.timestamp);
 });
 it('does not trust an envelope from another campaign or invalid JSON',()=>{
  const original=wrapped('resources','fixture');
  for(const message of [original.message.replace('"campaign"','"other"'),'RAPID_EVENT {invalid']){
   const row={...original,message};expect(filterEvents([row],options)).toEqual([row]);
  }
 });
});
