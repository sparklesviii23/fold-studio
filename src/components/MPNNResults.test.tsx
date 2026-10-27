import {describe,it,expect,vi} from 'vitest';
import {renderToStaticMarkup} from 'react-dom/server';
vi.mock('../lib/api',()=>({exportFile:vi.fn()}));
import MPNNResults,{predictionDraft} from './MPNNResults';
import type {Job} from '../lib/types';

const sample={candidateId:'a'.repeat(64),sample:1,chains:{X:'AKDL'},metrics:{score:.8,seqid:.5},fixedContextChains:['Y'],duplicateOfSample:null,requiresFreshStructuralPrediction:true};
const job:Job={id:'fixture',project_id:'project',name:'Software fixture',engine:'proteinmpnn',state:'completed',created:'now',updated:'now',data:{source:{structureId:'source',sha256:'b'.repeat(64)},sequences:{X:'ACDE',Y:'ACDE'},variant:'neutral',checkpointSha256:'c'.repeat(64),candidateSummaries:[sample]}};

describe('verified ProteinMPNN sequences and fresh prediction handoff',()=>{
 it('retains every fixed context chain and makes predictor chain mapping explicit',()=>{
  const draft=predictionDraft(job,sample);
  expect(draft.fasta).toBe('>source_chain_X\nAKDL\n>source_chain_Y\nACDE');
  expect(draft.origin.originalChainToPredictionChain).toEqual([{sourceChain:'X',predictionChain:'A',role:'redesigned'},{sourceChain:'Y',predictionChain:'B',role:'fixed_sequence_context'}]);
  expect(draft.origin.coordinatesTransferred).toBe(false);expect(draft.origin.freshPredictionRequired).toBe(true);
 });
 it('uses the saved immutable sample rather than caller-supplied replacement sequences',()=>{
  const replacement={...sample,chains:{X:'WWWW'}};expect(predictionDraft(job,replacement).fasta).toContain('AKDL');
  expect(()=>predictionDraft(job,{candidateId:'different'})).toThrow('verified completed');
  expect(()=>predictionDraft({...job,state:'failed'},sample)).toThrow('verified completed');
 });
 it('does not silently discard chains or accept a length change',()=>{
  expect(()=>predictionDraft({...job,data:{...job.data,sequences:{}}},sample)).toThrow('context chains');
  expect(()=>predictionDraft({...job,data:{...job.data,candidateSummaries:[{...sample,chains:{X:'AAA'}}]}},sample)).toThrow('correspondence');
 });
 it('shows inspectable sequence evidence without calling the original backbone a new prediction',()=>{
  const html=renderToStaticMarkup(<MPNNResults job={job} onBackbone={()=>{}} onPreparePrediction={()=>{}}/>);
  expect(html).toContain('Fresh structural prediction required');expect(html).toContain('Open original fixed backbone');
  expect(html).toContain('Prepare fresh prediction · no computation');expect(html).toContain('Export reproducibility report');expect(html).toContain('Fixed sequence context: Y');
 });
});
