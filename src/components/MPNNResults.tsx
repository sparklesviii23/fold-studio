import {useState} from 'react';
import {exportFile} from '../lib/api';
import type {Job} from '../lib/types';

type Sample={candidateId:string;sample:number;chains:Record<string,string>;metrics:Record<string,number>;fixedContextChains:string[];duplicateOfSample:number|null;requiresFreshStructuralPrediction:boolean};
export type PredictionDraft={fasta:string;name:string;origin:Record<string,unknown>};

export function predictionDraft(job:Job,selection:Pick<Sample,'candidateId'>):PredictionDraft{
 const sample:Sample|undefined=job.data.candidateSummaries?.find((row:Sample)=>row.candidateId===selection.candidateId);
 if(job.state!=='completed'||!sample)throw Error('Choose a verified completed sequence sample.');
 const context=job.data.sequences as Record<string,string>,chains=Object.keys(context??{});
 if(!chains.length||chains.length>26||Object.keys(sample.chains).some(ch=>!chains.includes(ch)))throw Error('This prediction form requires 1–26 explicitly mapped original context chains.');
 const sequences={...context,...sample.chains};
 if(chains.some(ch=>!/^[ACDEFGHIKLMNPQRSTVWY]+$/.test(sequences[ch])||sequences[ch].length!==context[ch].length))throw Error('Redesign sequence/context correspondence changed.');
 const mapping=chains.map((sourceChain,index)=>({sourceChain,predictionChain:String.fromCharCode(65+index),role:sourceChain in sample.chains?'redesigned':'fixed_sequence_context'}));
 return {fasta:chains.map(ch=>`>source_chain_${ch}\n${sequences[ch]}`).join('\n'),name:`ProteinMPNN sample ${sample.sample} · fresh prediction`,
  origin:{source:'ProteinMPNN fixed-backbone sequence proposal',jobId:job.id,redesignCandidateId:sample.candidateId,sourceStructureId:job.data.source?.structureId,sourceSha256:job.data.source?.sha256,checkpointSha256:job.data.checkpointSha256,requestSha256:job.data.requestSha256,resultSha256:job.data.resultSha256,variant:job.data.variant,originalChainToPredictionChain:mapping,freshPredictionRequired:true,coordinatesTransferred:false,scope:'All observed source chains are included. Fixed context means unchanged sequence, not a coordinate restraint; the selected predictor generates a new structure.'}};
}

export default function MPNNResults({job,onBackbone,onPreparePrediction}:{job:Job;onBackbone?:()=>void;onPreparePrediction?:(value:PredictionDraft)=>void}){
 const [error,setError]=useState('');
 const samples=(job.data.candidateSummaries??[]) as Sample[];
 if(job.state!=='completed')return null;
 if(!job.data.candidateSummaries)return <p className="caption">Historical sequence records remain in Research Library. This earlier job has no verified multi-chain result receipt.</p>;
 async function save(kind:'fasta'|'json'){
  try{const text=kind==='fasta'?samples.flatMap(sample=>Object.entries(sample.chains).map(([chain,sequence])=>`>${sample.candidateId}|sample=${sample.sample}|chain=${chain}|family=ProteinMPNN\n${sequence}`)).join('\n')+'\n':JSON.stringify({jobId:job.id,source:job.data.source,sourceSequences:job.data.sequences,variant:job.data.variant,checkpointSha256:job.data.checkpointSha256,requestSha256:job.data.requestSha256,resultSha256:job.data.resultSha256,constraints:job.data.constraints,samples,structurePredicted:false},null,2);await exportFile(kind==='fasta'?'proteinmpnn-sequences.fasta':'proteinmpnn-redesign-provenance.json',{text});}catch(e){setError(String(e));}
 }
 return <details><summary>Inspect redesign sequences &amp; provenance</summary><p className="caption">Sequence proposals on the original fixed backbone. Model scores describe sequence likelihood; folding, binding and solubility improvement require separate evidence.</p>
  {samples.map(sample=><article key={sample.candidateId}><strong>Sample {sample.sample} · {sample.candidateId.slice(0,12)}</strong><p className="caption">{sample.duplicateOfSample?`Same sequence as sample ${sample.duplicateOfSample}; retained as a separate model sample. `:''}Fixed sequence context: {sample.fixedContextChains.join(', ')||'none'}. Fresh structural prediction required.</p><pre>{Object.entries(sample.chains).map(([chain,sequence])=>`${chain}: ${sequence}`).join('\n')}</pre><p className="caption">ProteinMPNN · {Object.entries(sample.metrics).map(([name,value])=>`${name}: ${value.toPrecision(5)}`).join(' · ')}</p>{onPreparePrediction&&<button className="button" onClick={()=>{try{onPreparePrediction(predictionDraft(job,sample));}catch(e){setError(String(e));}}}>Prepare fresh prediction · no computation</button>}</article>)}
  <div className="button-row">{onBackbone&&<button className="button" onClick={onBackbone}>Open original fixed backbone</button>}<button className="button" onClick={()=>void save('fasta')}>Export redesign FASTA</button><button className="button" onClick={()=>void save('json')}>Export reproducibility report</button></div>{error&&<p className="error" role="alert">{error}</p>}
 </details>;
}
