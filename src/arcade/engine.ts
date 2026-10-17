export interface Block {id:string;one:string;rotation:number}
export interface Link {from:string;to:string}
export interface GameState {schemaVersion:1;blocks:Block[];links:Link[];challenge:number;mode:'challenge'|'free';completed:number[];name:string;notes:string;representation:'simple'|'chemical'|'atomic';scientific:boolean;autoConnect:boolean;selected:string|null;savedId?:string;savedRevision?:number;sourceRecordId?:string}
export interface TemplateAtom {id:string;element:string;charge:number;stereo:string;leaving:boolean;backbone:boolean;xyz:number[];atomName?:string;residue?:number;code?:string}
export interface Bond {a:string;b:string;order:number;aromatic:boolean;kind?:string}
export interface Component {code:string;one:string;name:string;formula:string;mass:number;source:string;sha256:string;atoms:TemplateAtom[];bonds:Bond[];protonation:string}
export interface Molecule {atoms:TemplateAtom[];bonds:Bond[];method?:string;geometryStatus?:string}
export const challenges=[{name:'First connection',sequence:'AG',hint:'Alanine then Glycine. Link the carbonyl C of A to the amino N of G.'},{name:'A small constellation',sequence:'AGSTL',hint:'Build A → G → S → T → L. Hydroxyl side chains belong to S and T.'},{name:'Sulfur & rings',sequence:'CMW',hint:'Cysteine and Methionine contain sulfur. Tryptophan has a fused aromatic ring.'},{name:'The Proline turn',sequence:'GPG',hint:'Proline’s side chain closes back onto N. Its peptide N has no hydrogen.'},{name:'Repair the chain',sequence:'KDSV',hint:'Replace a wrong block, reconnect adjacent C → N ends, then validate.'}];
export function initial():GameState{return {schemaVersion:1,blocks:[],links:[],challenge:0,mode:'challenge',completed:[],name:'Untitled peptide',notes:'',representation:'chemical',scientific:true,autoConnect:true,selected:null};}
export function connected(blocks:Block[]):Link[]{return blocks.slice(0,-1).map((b,i)=>({from:b.id,to:blocks[i+1].id}));}
export function sequence(s:GameState){return s.blocks.map(b=>b.one).join('');}
export function completeChain(s:GameState){return s.blocks.length>0&&s.links.length===s.blocks.length-1&&connected(s.blocks).every(l=>s.links.some(x=>x.from===l.from&&x.to===l.to));}
export function puzzleComplete(s:GameState){return s.mode==='challenge'&&sequence(s)===challenges[s.challenge]?.sequence&&completeChain(s);}
export type Command={type:'add';one:string;id:string;at?:number}|{type:'remove';id:string}|{type:'move';id:string;at:number}|{type:'replace';id:string;one:string}|{type:'link';from:string;to:string}|{type:'break';from:string;to:string}|{type:'connect'}|{type:'rotate';id:string}|{type:'sequence';sequence:string}|{type:'reset'};
export function edit(s:GameState,c:Command):GameState{
 const next=structuredClone(s),allowed='ACDEFGHIKLMNPQRSTVWY';
 if(c.type==='reset')return {...initial(),completed:s.completed,challenge:s.challenge,mode:s.mode};
 if(c.type==='add'){if(!allowed.includes(c.one)||c.one.length!==1||s.blocks.length>=128||s.blocks.some(b=>b.id===c.id))throw new Error('Choose a standard amino acid; the board supports 128 residues.');next.blocks.splice(Math.max(0,Math.min(c.at??next.blocks.length,next.blocks.length)),0,{id:c.id,one:c.one,rotation:0});next.selected=c.id;}
 if(c.type==='remove'){next.blocks=next.blocks.filter(b=>b.id!==c.id);if(next.selected===c.id)next.selected=null;}
 if(c.type==='move'){const index=next.blocks.findIndex(b=>b.id===c.id);if(index<0)throw new Error('Block is no longer present.');const b=next.blocks.splice(index,1)[0];next.blocks.splice(Math.max(0,Math.min(c.at,next.blocks.length)),0,b);}
 if(c.type==='replace'){if(!allowed.includes(c.one)||c.one.length!==1)throw new Error('Unsupported amino acid.');const b=next.blocks.find(b=>b.id===c.id);if(b)b.one=c.one;}
 if(c.type==='rotate'){const b=next.blocks.find(b=>b.id===c.id);if(b)b.rotation=(b.rotation+90)%360;}
 if(c.type==='sequence'){const seq=c.sequence.replace(/\s+/g,'').toUpperCase();if(!seq||seq.length>128||[...seq].some(o=>!allowed.includes(o)))throw new Error('Use 1–128 standard amino acids.');next.blocks=[...seq].map((one,i)=>({id:crypto.randomUUID()+'-'+i,one,rotation:0}));next.links=connected(next.blocks);next.selected=next.blocks[0].id;}
 const pairs=connected(next.blocks);next.links=next.links.filter(l=>pairs.some(p=>p.from===l.from&&p.to===l.to));
 if(c.type==='link'){if(!pairs.some(p=>p.from===c.from&&p.to===c.to))throw new Error('Use the carbonyl C end of a block and the N end of its next neighbor.');if(!next.links.some(l=>l.from===c.from&&l.to===c.to))next.links.push({from:c.from,to:c.to});}
 if(c.type==='break')next.links=next.links.filter(l=>!(l.from===c.from&&l.to===c.to));
 if(c.type==='connect'||(next.autoConnect&&['add','move','replace'].includes(c.type)))next.links=pairs;
 return next;
}
export interface History {present:GameState;past:GameState[];future:GameState[]}
export function commit(h:History,next:GameState):History{return {present:next,past:[...h.past,h.present].slice(-30),future:[]};}
export function undo(h:History):History{return !h.past.length?h:{present:h.past.at(-1)!,past:h.past.slice(0,-1),future:[h.present,...h.future]};}
export function redo(h:History):History{return !h.future.length?h:{present:h.future[0],past:[...h.past,h.present].slice(-30),future:h.future.slice(1)};}
