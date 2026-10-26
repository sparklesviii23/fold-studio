import type {AtomRecord} from './types';
export interface PolymerResidue {id:string;authorNumber:number;insertionCode:string;labelPosition:number|null;component:string;canonicalSymbol:string|null;polymerType:string;modified:boolean;parentComponent:string|null;identityResolved:boolean;observedPosition:number|null;sourceAtomCount:number;atomNames:string[];alternateLocations:string[]}
export interface PolymerChain {id:string;model:string;authorChain:string;labelChain:string;polymerType:string;observedSequence:string;mappingComplete:boolean;residues:PolymerResidue[];sourceAtomCount:number;sequenceScope:string;sequenceDirection?:string}
export interface PolymerInspection {schemaVersion:number;structureId:string;sourceSha256:string;sourceAtomCount:number;models:string[];chains:PolymerChain[];origin:string;title:string|null;experimentalMethods:string[];resolutionAngstrom:string[];coordinatePolicy:string}
export function mappedPolymerAtoms(info:PolymerInspection,chain:PolymerChain,residue:PolymerResidue,atoms:AtomRecord[],state:any):AtomRecord[]{
 if(info.models.length!==1)throw new Error('This source has multiple coordinate models. An explicit source-model correspondence is required before sequence selection.');
 if(!info.chains.some(c=>c.id===chain.id&&c.residues.some(r=>r.id===residue.id)))throw new Error('The residue does not belong to this source.');
 const duplicate=info.chains.flatMap(c=>c.model===chain.model&&c.authorChain===chain.authorChain?c.residues:[]).filter(r=>r.authorNumber===residue.authorNumber&&r.insertionCode===residue.insertionCode&&r.component===residue.component);
 if(duplicate.length!==1)throw new Error('Author numbering is ambiguous across source chains; selection was not guessed.');
 const links=(state?.mapping??[]).filter((m:any)=>m.structureId===info.structureId&&m.sourceSha256===info.sourceSha256&&m.sessionId===state.sessionId);
 if(links.length!==1)throw new Error('The current source has no unique native model mapping.');
 const link=links[0],model=state.models?.find((m:any)=>m.id===link.modelId);
 if(!model||model.positionsSha256!==link.positionsSha256)throw new Error('Native coordinates changed. Import a new coordinate asset to establish a fresh sequence mapping.');
 const matches=atoms.filter(a=>a.nativeModelId===link.modelId&&a.authChain===chain.authorChain&&a.auth===residue.authorNumber&&a.insertion===residue.insertionCode&&a.name===residue.component);
 if(!matches.length||matches.some(a=>!residue.atomNames.includes(a.atomName)||!residue.alternateLocations.includes(a.altLoc)))throw new Error('This exact source residue is absent from the active molecular scene.');
 return matches;
}
export function matchingRNAChains(info:PolymerInspection,sequence:string):PolymerChain[]{
 const value=sequence.replace(/\s/g,'').toUpperCase();
 if(!value||!/^[ACGUI]+$/.test(value))return [];
 // Deliberately no fuzzy alignment or implicit T/U conversion.
 return info.chains.filter(c=>c.polymerType==='RNA'&&c.mappingComplete&&c.observedSequence===value);
}

export function dotBracketPairs(structure:string):[number,number][]{
 const stack:number[]=[],pairs:[number,number][]=[];
 for(let i=0;i<structure.length;i++){const c=structure[i];if(c==='(')stack.push(i+1);else if(c===')'){const start=stack.pop();if(start===undefined)throw new Error('Unbalanced secondary structure.');pairs.push([start,i+1]);}else if(c!=='.')throw new Error('Unsupported dot-bracket notation.');}
 if(stack.length)throw new Error('Unbalanced secondary structure.');return pairs;
}
