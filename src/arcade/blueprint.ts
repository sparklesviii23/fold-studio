import {expectedGraph,initialGraph,sequenceGraph,type GraphState,type Templates} from './graph';
export interface Challenge {id:string;name:string;sequence:string;method:'atoms'|'blocks';variation?:'missing'|'order';lesson:string;hint:string}
export const molecularChallenges:Challenge[]=[
 {id:'gly-atoms',name:'Meet Glycine',sequence:'G',method:'atoms',lesson:'Glycine is achiral. Two hydrogens share its α carbon.',hint:'Start with Cα in the middle. Add N on one side and carbonyl C on the other.'},
 {id:'ala-atoms',name:'A little side chain',sequence:'A',method:'atoms',lesson:'Alanine adds a methyl side chain. Its CCD stereochemistry stays locked.',hint:'CB is the side-chain carbon. Its three hydrogen sites are equivalent pieces.'},
 {id:'first-peptide',name:'Two become one',sequence:'AG',method:'blocks',lesson:'A peptide connection removes one H₂O equivalent from two neutral free amino acids.',hint:'Place both detailed blocks. Select the left carbonyl C, then the right amino N.'},
 {id:'proline-ring',name:'A ring to the backbone',sequence:'P',method:'atoms',variation:'missing',lesson:'Proline’s side chain closes onto N. Its leaving hydrogen is different.',hint:'Follow the five-member ring back to N. Add the missing atoms and bonds.'},
 {id:'cys-sulfur',name:'Find the thiol',sequence:'C',method:'atoms',variation:'missing',lesson:'Cysteine has S–H and its CCD Cα assignment is R.',hint:'Sulfur connects to CB and HG. This is neutral thiol chemistry, without disulfides.'},
 {id:'met-sulfur',name:'Sulfur in the chain',sequence:'M',method:'atoms',variation:'missing',lesson:'Methionine’s thioether S connects to two carbons.',hint:'SD bridges CG and CE. It does not carry a hydrogen in this template.'},
 {id:'his-order',name:'Repair the ring',sequence:'H',method:'atoms',variation:'order',lesson:'Histidine’s imidazole has distinct CCD bond orders and aromatic flags.',hint:'Select the highlighted wrong bond, break it, then use the order shown by its guide.'},
 {id:'trp-ring',name:'Two rings, one side chain',sequence:'W',method:'atoms',variation:'missing',lesson:'Tryptophan contains a fused indole ring.',hint:'The fused rings share atoms. No extra connection is needed across the center.'},
 {id:'thr-stereo',name:'Two chiral centers',sequence:'T',method:'atoms',variation:'missing',lesson:'Threonine preserves both Cα and Cβ CCD assignments.',hint:'Inspect CA and CB. Board rotation changes the picture, never the template handedness.'},
 {id:'ile-stereo',name:'A branching puzzle',sequence:'I',method:'atoms',variation:'missing',lesson:'Isoleucine and Leucine have different branching; Ile has two stereocenters.',hint:'Follow CB to CG1 and CG2. Do not merge the two branches.'},
 {id:'repair-peptide',name:'Complete the short chain',sequence:'AGSTL',method:'blocks',lesson:'Each ordinary linear C → N attachment updates termini and the whole graph.',hint:'Join neighboring fragments left to right. Use undo to compare their free and incorporated atoms.'}
];
export function blueprint(sequence:string,t:Templates){const s=sequenceGraph(sequence,t,false);return s;}
export function startChallenge(c:Challenge,t:Templates,previous:GraphState,learn=false):GraphState {
 const target=blueprint(c.sequence,t);
 let s:GraphState={...initialGraph(),challengeId:c.id,blueprintSequence:c.sequence,mode:learn?'learn':'challenge',name:c.name,completed:previous.completed,legacyCompleted:previous.legacyCompleted,legacyChallengeIds:previous.legacyChallengeIds};
 if(c.method==='atoms')s.residues=target.residues;
 if(c.variation==='missing'){
  const missing=new Set(target.atoms.filter((a,i)=>i%3===0).map(a=>a.id));
  s.atoms=target.atoms.filter(a=>!missing.has(a.id));s.bonds=target.bonds.filter(b=>!missing.has(b.a)&&!missing.has(b.b));
 }
 if(c.variation==='order'){s={...s,residues:target.residues,atoms:target.atoms,bonds:target.bonds.map(b=>({...b}))};const b=s.bonds.find(b=>b.order===2)!;b.order=1;}
 return s;
}
export function targetFor(s:GraphState,t:Templates){
 const c=molecularChallenges.find(c=>c.id===s.challengeId);if(s.mode==='free'||(!c&&!s.blueprintSequence))return null;
 const target=blueprint(c?.sequence??s.blueprintSequence!,t);
 // Target free neutral terminal groups disappear only when the actual peptide link exists.
 const connected=s.bonds.filter(b=>b.kind==='peptide').map(b=>({from:s.atoms.find(a=>a.id===b.a)!.residueId!,to:s.atoms.find(a=>a.id===b.b)!.residueId!}));
 return {...target,...expectedGraph(target.residues,connected,t)};
}
