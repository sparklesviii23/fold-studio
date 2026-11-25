export interface RnaBase {position:number;base:string;partner:number|null;unpairedProbability:number;entropyBits:number;confidence:number}
export interface RnaResult {
 schema:string;sequence:string;length:number;structure:string;sha256:string;runId:string;seconds:number;
 basePairProbabilities:[number,number,number][];bases:RnaBase[];
 regions:{start:number;end:number;meanEntropyBits:number}[];
 provenance:{engine:string;version:string;weightsSha256:string;splitSha256:string;device:string;externalEngines:unknown[]};
 comparison:null|{reference:string;f1:number;precision:number;recall:number;missed:number[][];extra:number[][]};
 uncertainty:{calibrated:boolean;note:string};
 verification:{enabled:boolean;ran:boolean;reason:string;structure?:string;pairDisagreement?:number;energyKcalMol?:number;referenceAccuracy?:{f1:number}};
}
export function pairedPositions(structure:string):[number,number][] {
 const stack:number[]=[],out:[number,number][]=[];
 for(let i=0;i<structure.length;i++){if(structure[i]==='(')stack.push(i+1);else if(structure[i]===')'){const j=stack.pop();if(j===undefined)throw new Error('Unbalanced structure');out.push([j,i+1]);}else if(structure[i]!=='.')throw new Error('Invalid structure');}
 if(stack.length)throw new Error('Unbalanced structure');return out;
}
export function partners(result:RnaResult,position:number){
 return result.basePairProbabilities.filter(([i,j])=>i===position||j===position).map(([i,j,p])=>({position:i===position?j:i,probability:p})).sort((a,b)=>b.probability-a.probability).slice(0,5);
}
