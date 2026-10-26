import {dotBracketPairs} from './polymerMapping';
export interface RNAFeature {id:string;kind:'stem'|'hairpin'|'bulge'|'internal loop'|'multiloop'|'external loop';positions:number[];pairs:[number,number][]}
/** Topological annotations of an existing pseudoknot-free dot-bracket result.
 * This performs no folding, coordinate prediction or experimental base-pair inference.
 */
export function rnaFeatures(structure:string):RNAFeature[]{
 const pairs=dotBracketPairs(structure),nodes=new Map<number,{i:number;j:number;children:number[]}>(),stack:number[]=[],roots:number[]=[];
 for(const [i,j] of pairs)nodes.set(i,{i,j,children:[]});
 for(let n=1;n<=structure.length;n++){
  if(structure[n-1]==='('){if(stack.length)nodes.get(stack.at(-1)!)!.children.push(n);else roots.push(n);stack.push(n);}
  else if(structure[n-1]===')')stack.pop();
 }
 const features:RNAFeature[]=[],range=(a:number,b:number)=>Array.from({length:Math.max(0,b-a+1)},(_,i)=>a+i);
 for(const node of [...nodes.values()].sort((a,b)=>a.i-b.i)){
  if(!pairs.some(([i,j])=>i===node.i-1&&j===node.j+1)){
   const stem:[number,number][]=[];let n:typeof node|undefined=node;
   while(n){stem.push([n.i,n.j]);const child=nodes.get(n.i+1);n=child&&child.j===n.j-1?child:undefined;}
   features.push({id:'stem:'+node.i,kind:'stem',positions:stem.flat().sort((a,b)=>a-b),pairs:stem});
  }
  const children=node.children.map(i=>nodes.get(i)!);
  if(children.length===1&&children[0].i===node.i+1&&children[0].j===node.j-1)continue;
  let cursor=node.i+1;const unpaired:number[]=[];
  for(const child of children){unpaired.push(...range(cursor,child.i-1));cursor=child.j+1;}
  unpaired.push(...range(cursor,node.j-1));
  const kind=!children.length?'hairpin':children.length>1?'multiloop':children[0].i>node.i+1&&children[0].j<node.j-1?'internal loop':'bulge';
  features.push({id:kind+':'+node.i,kind,positions:unpaired,pairs:[[node.i,node.j],...children.map(c=>[c.i,c.j] as [number,number])]});
 }
 let cursor=1;const outside:number[]=[];for(const i of roots){const node=nodes.get(i)!;outside.push(...range(cursor,i-1));cursor=node.j+1;}outside.push(...range(cursor,structure.length));
 if(outside.length)features.push({id:'external',kind:'external loop',positions:outside,pairs:[]});
 return features;
}
