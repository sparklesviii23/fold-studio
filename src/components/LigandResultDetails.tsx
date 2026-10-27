import {chooseSave,exportFile,rpc} from '../lib/api';
import type {Job} from '../lib/types';

export interface LigandPreparationSummary {
 canonicalIsomericSmiles?:string;
 formula?:string;
 molecularWeightDa?:number;
 formalCharge?:number;
 energyKcalMol?:number;
 conformers?:{requested:number;embedded:number;converged:number;selectedId:number;energies:{id:number;status:number;energyKcalMol:number|null}[]};
 method?:{embedding?:string;forceField?:string;maxIterations?:number;threads?:number;seed?:number;stereochemistryFrom3D?:string};
 runtime?:{rdkit?:string;python?:string;architecture?:string};
 seconds?:number;
 limitations?:string[];
}
const number=(value:unknown,digits=4)=>typeof value==='number'&&Number.isFinite(value)?value.toFixed(digits):'Not recorded';
export async function exportPreparedLigand(job:Job){
 const outputs=job.data?.outputs;
 if(job.engine!=='rdkit'||job.state!=='completed'||!Array.isArray(outputs)||outputs.length!==1||typeof outputs[0]!=='string'||!outputs[0])throw Error('Choose a completed ligand job with one saved conformer.');
 const path=await chooseSave(job.name.replace(/[\\/:]/g,'_')+'.sdf');
 if(path)await rpc('ligand_export',{projectId:job.project_id,structureId:outputs[0],path});
}
export default function LigandResultDetails({job,onError}:{job:Job;onError:(error:string)=>void}){
 const result=job.data?.resultSummary as LigandPreparationSummary|undefined;
 if(job.engine!=='rdkit'||job.state!=='completed'||!result)return null;
 const conformers=result.conformers;
 return <details><summary>Inspect prepared ligand and conformer sampling</summary>
 <dl><dt>Canonical isomeric SMILES</dt><dd style={{overflowWrap:'anywhere'}}>{result.canonicalIsomericSmiles??'Not recorded'}</dd><dt>Formula</dt><dd>{result.formula??'Not recorded'}</dd><dt>Molecular weight · Da</dt><dd>{number(result.molecularWeightDa)}</dd><dt>Formal charge · elementary charges</dt><dd>{number(result.formalCharge,0)}</dd><dt>Selected MMFF94s energy · kcal/mol</dt><dd>{number(result.energyKcalMol)}</dd><dt>Geometry-derived stereochemistry</dt><dd>{result.method?.stereochemistryFrom3D??'Not recorded'}</dd></dl>
 {conformers&&<><p>{conformers.requested} requested · {conformers.embedded} embedded · {conformers.converged} converged · selected conformer {conformers.selectedId}</p><div style={{overflowX:'auto'}}><table><thead><tr><th>Conformer ID</th><th>MMFF status</th><th>Energy · kcal/mol</th><th>Selection</th></tr></thead><tbody>{conformers.energies.map(row=><tr key={row.id}><td>{row.id}</td><td>{row.status===0?'Converged':row.status===1?'Iteration limit':`Unsuccessful (${row.status})`}</td><td>{number(row.energyKcalMol)}</td><td>{row.id===conformers.selectedId?'Selected':'Not selected'}</td></tr>)}</tbody></table></div><p className="caption">These sampled energies compare the same atom and protonation state under the recorded force field. They are not binding affinities or proof of the global minimum.</p></>}
 <details><summary>Preparation provenance</summary><dl><dt>Embedding</dt><dd>{result.method?.embedding??'Not recorded'}</dd><dt>Force field</dt><dd>{result.method?.forceField??'Not recorded'}</dd><dt>Seed</dt><dd>{number(result.method?.seed,0)}</dd><dt>Iteration limit</dt><dd>{number(result.method?.maxIterations,0)}</dd><dt>RDKit version</dt><dd>{result.runtime?.rdkit??'Not recorded'}</dd><dt>Elapsed execution · s</dt><dd>{number(result.seconds)}</dd><dt>Request SHA-256</dt><dd style={{overflowWrap:'anywhere'}}>{job.data.requestSha256??'Not recorded'}</dd><dt>Runner SHA-256</dt><dd style={{overflowWrap:'anywhere'}}>{job.data.runnerSha256??'Not recorded'}</dd></dl><pre className="ec-output">{JSON.stringify({jobId:job.id,projectId:job.project_id,outputs:job.data.outputs,requestSha256:job.data.requestSha256,runnerSha256:job.data.runnerSha256,resultSummary:result},null,2)}</pre></details>
 <div className="button-row"><button className="button" onClick={()=>exportPreparedLigand(job).catch(e=>onError(String(e)))}>Export verified conformer · SDF</button><button className="button" onClick={()=>exportFile('fold-ligand-preparation-'+job.id+'.json',{text:JSON.stringify({jobId:job.id,projectId:job.project_id,outputs:job.data.outputs,requestSha256:job.data.requestSha256,runnerSha256:job.data.runnerSha256,resultSummary:result},null,2)}).catch(e=>onError(String(e)))}>Export preparation receipt · JSON</button></div>
 {result.limitations&&<ul className="caption">{result.limitations.map((text,i)=><li key={i}>{text}</li>)}</ul>}
 </details>;
}
