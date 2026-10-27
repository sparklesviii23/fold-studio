import {describe,it,expect,vi,beforeEach} from 'vitest';
import {renderToStaticMarkup} from 'react-dom/server';
import type {Job} from '../lib/types';
import LigandResultDetails,{exportPreparedLigand} from './LigandResultDetails';
import {chooseSave,rpc} from '../lib/api';
vi.mock('../lib/api',()=>({chooseSave:vi.fn(),rpc:vi.fn(),exportFile:vi.fn()}));
const job:Job={id:'job-1',project_id:'project-1',engine:'rdkit',name:'Ethanol / reference',state:'completed',created:'',updated:'',data:{outputs:['structure-1'],requestSha256:'a'.repeat(64),runnerSha256:'b'.repeat(64),resultSummary:{formula:'C2H6O',canonicalIsomericSmiles:'CCO',molecularWeightDa:46.069,formalCharge:0,energyKcalMol:-1.25,conformers:{requested:3,embedded:3,converged:2,selectedId:2,energies:[{id:0,status:0,energyKcalMol:-1.1},{id:1,status:1,energyKcalMol:null},{id:2,status:0,energyKcalMol:-1.25}]},method:{embedding:'RDKit ETKDGv3',forceField:'MMFF94s',seed:42,stereochemistryFrom3D:'verified'},runtime:{rdkit:'2026.09.1'},limitations:['Generated conformer; no activity validation.']}}};
describe('prepared ligand inspection',()=>{
 beforeEach(()=>vi.clearAllMocks());
 it('shows actual sampled energies, convergence, units and provenance without inferring activity',()=>{
  const html=renderToStaticMarkup(<LigandResultDetails job={job} onError={()=>{}}/>);
  expect(html).toContain('CCO');expect(html).toContain('46.0690');expect(html).toContain('kcal/mol');expect(html).toContain('-1.2500');expect(html).toContain('Iteration limit');expect(html).toContain('Not recorded');expect(html).toContain('selected conformer 2');expect(html).toContain('2026.09.1');expect(html).toContain('Request SHA-256');expect(html).toContain('a'.repeat(64));expect(html).toContain('Export verified conformer');expect(html).toContain('not binding affinities');
 });
 it('keeps historical absent fields explicit and hides incomplete jobs',()=>{
  const html=renderToStaticMarkup(<LigandResultDetails job={{...job,data:{resultSummary:{formula:'Recorded formula'}}}} onError={()=>{}}/>);
  expect(html).toContain('Not recorded');expect(html).not.toContain('selected conformer');
  expect(renderToStaticMarkup(<LigandResultDetails job={{...job,state:'failed'}} onError={()=>{}}/>)).toBe('');
 });
 it('exports the exact saved record through project/hash-verifying backend and honors cancellation',async()=>{
  vi.mocked(chooseSave).mockResolvedValueOnce('/tmp/prepared.sdf');
  await exportPreparedLigand(job);
  expect(chooseSave).toHaveBeenCalledWith('Ethanol _ reference.sdf');expect(rpc).toHaveBeenCalledWith('ligand_export',{projectId:'project-1',structureId:'structure-1',path:'/tmp/prepared.sdf'});
  vi.clearAllMocks();vi.mocked(chooseSave).mockResolvedValueOnce(null);await exportPreparedLigand(job);expect(rpc).not.toHaveBeenCalled();
  await expect(exportPreparedLigand({...job,data:{outputs:[]}})).rejects.toThrow('one saved conformer');expect(rpc).not.toHaveBeenCalled();
 });
});
