import type { AtomRecord } from './types';
type V = [number,number,number];
const sub=(a:V,b:V)=>a.map((x,i)=>x-b[i]) as V;
const dot=(a:V,b:V)=>a.reduce((v,x,i)=>v+x*b[i],0);
const cross=(a:V,b:V):V=>[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];
const norm=(a:V)=>Math.hypot(...a);
export const distance=(a:V,b:V)=>norm(sub(a,b));
export function angle(a:V,b:V,c:V){const u=sub(a,b),v=sub(c,b);if(!norm(u)||!norm(v))throw new Error('Coincident atoms do not define an angle.');return Math.acos(Math.max(-1,Math.min(1,dot(u,v)/(norm(u)*norm(v)))))*180/Math.PI;}
export function dihedral(a:V,b:V,c:V,d:V){const b0=sub(a,b),b1=sub(c,b),b2=sub(d,c),l=norm(b1);if(!l)throw new Error('Coincident central atoms do not define a dihedral.');const n=b1.map(x=>x/l) as V;const v=sub(b0,n.map(x=>x*dot(b0,n)) as V),w=sub(b2,n.map(x=>x*dot(b2,n)) as V);if(norm(v)<1e-9||norm(w)<1e-9)throw new Error('Collinear atoms do not define a dihedral.');return Math.atan2(dot(cross(n,v),w),dot(v,w))*180/Math.PI;}
export function contacts(atoms:AtomRecord[],selected:AtomRecord[],cutoff:number){const keys=new Set(selected.map(a=>a.key));return atoms.filter(a=>!keys.has(a.key)).map(atom=>({atom,distance:Math.min(...selected.map(b=>distance(atom.xyz,b.xyz)))})).filter(x=>Number.isFinite(x.distance)&&x.distance<=cutoff).sort((a,b)=>a.distance-b.distance);}
export const atomLabel=(a:AtomRecord)=>`${a.authChain || '∅'}:${a.auth}${a.insertion} ${a.name} ${a.atomName}${a.altLoc?' ['+a.altLoc+']':''}`;
