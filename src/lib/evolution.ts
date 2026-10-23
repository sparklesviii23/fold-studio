export interface EvolutionCandidate {
 id:string; name:string; sequence:string; parentId:string|null; rootId:string;
 constraints:{fixed:number[];mutable:number[]};
 structure:null|{recordId:string;sha256:string;chain:string};
 reference:Record<string,string|number>;
 residueMap:Array<{position:number;wildType:string;structureResidueId?:string;referenceNumber?:number}>;
 descriptors:{gravy:number|null;formalSideChainCharge:number;flags:Array<{position:number;type:string}>};
 validation:string;changes?:Array<{position:number;from:string;to:string}>;
}
export interface EvolutionEvent {id:string;candidate_id:string;kind:string;data:any;created:string}
export function substitutions(value:string){
 const tokens=value.trim().split(/[\s,;]+/).filter(Boolean);
 if(!tokens.length)throw Error('Enter at least one substitution, for example D3A. Positions refer to this candidate sequence.');
 const result=tokens.map(token=>{const match=/^([ACDEFGHIKLMNPQRSTVWY])([1-9]\d*)([ACDEFGHIKLMNPQRSTVWY])$/.exec(token.toUpperCase());if(!match)throw Error('Use substitutions such as D3A, with a 1-based sequence position.');return{position:Number(match[2]),from:match[1],to:match[3]};});
 if(new Set(result.map(r=>r.position)).size!==result.length)throw Error('Each residue can be changed once per proposal.');
 return result;
}
export function fixedPositions(value:string){
 if(!value.trim())return [];
 const tokens=value.split(/[\s,;]+/).filter(Boolean);
 if(tokens.some(v=>!/^([1-9]\d*)$/.test(v)))throw Error('Fixed positions must be 1-based sequence integers separated by commas.');
 return tokens.map(Number);
}
