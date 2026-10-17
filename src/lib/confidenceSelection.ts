import { residueCorrespondence } from './sequence';
import type { Residue } from './types';

/** Map single-protein prediction tokens to actual Cα residue identities. */
export function confidenceResidues(sequence:string,residues:Residue[],positions:number[]):Residue[]{
 if(!sequence||!positions.length||positions.some(n=>!Number.isInteger(n)||n<1||n>sequence.length))throw new Error('Unsupported confidence token selection.');
 if(new Set(residues.map(r=>`${r.unit}:${r.authChain}`)).size!==1)throw new Error('Confidence selection requires one unambiguous coordinate chain and model.');
 const pairs=residueCorrespondence(sequence,residues.map(r=>r.one).join(''));
 const mapping=new Map(pairs.map(([token,index])=>[token,residues[index-1]]));
 const selected=[...new Set(positions)].map(position=>mapping.get(position));
 if(selected.some(r=>!r))throw new Error('A confidence token has no verified observed residue correspondence.');
 return selected as Residue[];
}
