import {memo} from 'react';
import {layoutComponent,sequenceGraph,type Templates,type GraphAtom,type GraphBond} from './graph';
import type {Component} from './engine';
export const elementColors:Record<string,string>={H:'#ecf4ff',C:'#bad3ee',N:'#8db5ff',O:'#ffafbc',S:'#ffe0a0'};
export function BondLines({a,b,bond,ghost=false,onClick}:{a:number[];b:number[];bond:GraphBond;ghost?:boolean;onClick?:()=>void}) {
 const dx=b[0]-a[0],dy=b[1]-a[1],len=Math.max(1,Math.hypot(dx,dy)),nx=-dy/len*3,ny=dx/len*3,offsets=bond.order===3?[-1.6,0,1.6]:bond.order===2?[-.7,.7]:[0];
 return <g className={'molecule-bond '+(ghost?'ghost-bond':'')} onClick={onClick}>
 {onClick&&<line x1={a[0]} y1={a[1]} x2={b[0]} y2={b[1]} stroke="transparent" strokeWidth={18}/>}
 {offsets.map((v,i)=><line key={i} x1={a[0]+nx*v} y1={a[1]+ny*v} x2={b[0]+nx*v} y2={b[1]+ny*v} stroke={bond.kind==='peptide'?'#a8e2cc':'#94b3d7'} strokeWidth={ghost?1.4:2} strokeDasharray={ghost?'4 5':bond.aromatic&&i===offsets.length-1?'5 3':undefined}/>)}
 </g>;
}
export const MoleculeDiagram=memo(function MoleculeDiagram({component,hydrogens=false,label=true}:{component:Component;hydrogens?:boolean;label?:boolean}) {
 const all=layoutComponent(component),atoms=component.atoms.filter(a=>hydrogens||a.element!=='H'),points=atoms.map(a=>all.get(a.id)!),xs=points.map(p=>p[0]),ys=points.map(p=>p[1]),x=Math.min(...xs)-22,y=Math.min(...ys)-22,w=Math.max(...xs)-x+22,h=Math.max(...ys)-y+22,lookup=new Map(atoms.map(a=>[a.id,all.get(a.id)!]));
 return <svg className="molecule-diagram" viewBox={`${x} ${y} ${w} ${h}`} role="img" aria-label={component.name+' · actual CCD '+(hydrogens?'full':'heavy')+' atom graph'}>
 {component.bonds.map((b,i)=>lookup.has(b.a)&&lookup.has(b.b)?<BondLines key={i} a={lookup.get(b.a)!} b={lookup.get(b.b)!} bond={{...b,kind:'component'}}/>:null)}
 {atoms.map(a=>{const p=lookup.get(a.id)!;return <g key={a.id}><circle cx={p[0]} cy={p[1]} r={a.element==='H'?10:13} fill="#10243c" stroke={elementColors[a.element]} strokeWidth="1.4"/>{label&&<text x={p[0]} y={p[1]+4} fill={elementColors[a.element]} textAnchor="middle" fontSize={13} fontWeight={600}>{a.element}</text>}</g>;})}
 </svg>;
});
export function graphMolecule(atoms:GraphAtom[],bonds:GraphBond[],residues:{id:string;one:string}[],templates:Map<string,Component>){return {atoms:atoms.map(a=>{const r=residues.find(r=>r.id===a.residueId),index=residues.findIndex(r=>r.id===a.residueId),source=r?templates.get(r.one)?.atoms.find(v=>v.id===a.templateAtom):null;return {...a,atomName:a.templateAtom??a.element,backbone:source?.backbone??false,leaving:source?.leaving??false,xyz:[a.xyz[0]+Math.max(0,index)*9,a.xyz[1],a.xyz[2]]};}),bonds};}

export const FragmentDiagram=memo(function FragmentDiagram({sequence,templates,hydrogens=true}:{sequence:string;templates:Templates;hydrogens?:boolean}) {
 const g=sequenceGraph(sequence,templates),atoms=g.atoms.filter(a=>hydrogens||a.element!=='H'),lookup=new Map(atoms.map(a=>[a.id,a])),xs=atoms.map(a=>a.board[0]),ys=atoms.map(a=>a.board[1]),x=Math.min(...xs)-20,y=Math.min(...ys)-20,w=Math.max(...xs)-x+20,h=Math.max(...ys)-y+20;
 return <svg className="molecule-diagram" viewBox={`${x} ${y} ${w} ${h}`} role="img" aria-label={`Complete ${sequence.length}-residue canonical fragment atom graph`}>{g.bonds.filter(b=>lookup.has(b.a)&&lookup.has(b.b)).map((b,i)=><BondLines key={i} a={lookup.get(b.a)!.board} b={lookup.get(b.b)!.board} bond={b}/>)}{atoms.map(a=><g key={a.id}><circle cx={a.board[0]} cy={a.board[1]} r={a.element==='H'?10:13} fill="#10243c" stroke={elementColors[a.element]}/><text x={a.board[0]} y={a.board[1]+4} textAnchor="middle" fontSize="13" fill={elementColors[a.element]}>{a.element}</text></g>)}</svg>;
});
