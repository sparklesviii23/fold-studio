import {describe,it,expect} from 'vitest';
import {campaignResultMessage,firstJobOutput,jobPresentation} from './jobs';
import type {Item,Job} from './types';

const job={id:'job',project_id:'project',engine:'proteinmpnn',state:'completed',data:{outputs:['output']}} as Job;
const sequence={id:'output',project_id:'project',kind:'sequence',name:'Redesigned chain',data:{sequence:'ACD'}} as Item;
describe('Scientific result routing',()=>{
 it('keeps genuine sequence results out of the coordinate viewer',()=>{
  const output=firstJobOutput(job,[sequence]);expect(output?.kind).toBe('sequence');expect(output?.record).toBe(sequence);
 });
 it('opens coordinate predictions using their saved record kind',()=>{
  expect(firstJobOutput({...job,engine:'bindcraft2'},[{...sequence,kind:'structure'}])?.kind).toBe('coordinates');
 });
 it('refuses missing, unrelated-project and unsupported first outputs',()=>{
  expect(firstJobOutput(job,[])).toBeNull();
  expect(firstJobOutput(job,[{...sequence,project_id:'other'}])).toBeNull();
  expect(firstJobOutput(job,[{...sequence,kind:'protein'}])).toBeNull();
 });
 it('labels local scientific jobs and cloud notebook jobs accurately',()=>{
  expect(jobPresentation('proteinmpnn')).toEqual({label:'ProteinMPNN',location:'local'});
  expect(jobPresentation('bindcraft2')).toEqual({label:'BindCraft2',location:'local'});
  expect(jobPresentation('rdkit')).toEqual({label:'RDKit',location:'local'});
  expect(jobPresentation('colabfold')).toEqual({label:'ColabFold',location:'cloud'});
 });
 it('distinguishes valid scientific rejection from runtime failure and preparation',()=>{
  expect(campaignResultMessage({...job,engine:'bindcraft2',data:{preparation:{},outcome:'no_accepted_designs'}})).toContain('No candidate passed');
  expect(campaignResultMessage({...job,engine:'bindcraft2',state:'running',data:{preparation:{}}})).toContain('running');
  expect(campaignResultMessage({...job,engine:'bindcraft2',state:'failed',data:{preparation:{}}})).toContain('failed');
  expect(campaignResultMessage({...job,engine:'bindcraft2',state:'prepared',data:{preparation:{}}})).toContain('prepared');
 });
});
