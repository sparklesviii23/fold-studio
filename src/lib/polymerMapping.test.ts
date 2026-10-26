import {describe,it,expect} from 'vitest';
import {dotBracketPairs,mappedPolymerAtoms,matchingRNAChains,type PolymerInspection,type PolymerChain,type PolymerResidue} from './polymerMapping';
import type {AtomRecord} from './types';
const residue={id:'source-residue',authorNumber:20,insertionCode:'A',labelPosition:1,component:'PSU',polymerType:'RNA',canonicalSymbol:'U',observedPosition:1,atomNames:["C1'"],alternateLocations:['B']} as PolymerResidue;
const chain={id:'source-chain',model:'1',authorChain:'Q',labelChain:'RNA',polymerType:'RNA',observedSequence:'U',mappingComplete:true,residues:[residue]} as PolymerChain;
const info={models:['1'],structureId:'saved',sourceSha256:'sha',chains:[chain]} as PolymerInspection;
const state={sessionId:'current',mapping:[{structureId:'saved',sourceSha256:'sha',sessionId:'current',modelId:'7',positionsSha256:'xyz'}],models:[{id:'7',positionsSha256:'xyz'}]};
const atom={key:'real',nativeModelId:'7',authChain:'Q',auth:20,insertion:'A',name:'PSU',atomName:"C1'",altLoc:'B'} as AtomRecord;
describe('source polymer sequence to native atoms',()=>{
 it('uses original component, author insertion, altLoc and exact native model',()=>{expect(mappedPolymerAtoms(info,chain,residue,[atom,{...atom,nativeModelId:'8',key:'wrong-model'}],state)).toEqual([atom]);});
 it('refuses mutated coordinates and stale source hashes',()=>{expect(()=>mappedPolymerAtoms(info,chain,residue,[atom],{...state,models:[{id:'7',positionsSha256:'edited'}]})).toThrow('coordinates changed');expect(()=>mappedPolymerAtoms({...info,sourceSha256:'different'},chain,residue,[atom],state)).toThrow('no unique');});
 it('refuses author chain collisions and unestablished model correspondence',()=>{expect(()=>mappedPolymerAtoms({...info,chains:[chain,{...chain,id:'second',labelChain:'other'}]},chain,residue,[atom],state)).toThrow('ambiguous');expect(()=>mappedPolymerAtoms({...info,models:['1','2']},chain,residue,[atom],state)).toThrow('multiple coordinate models');});
 it('refuses absent residues, changed chemistry and alternate locations',()=>{for(const altered of [{...atom,name:'U'},{...atom,insertion:''},{...atom,altLoc:'A'}])expect(()=>mappedPolymerAtoms(info,chain,residue,[altered],state)).toThrow('absent');});
 it('does not claim a DNA or unresolved sequence as an RNA 3D map',()=>{expect(matchingRNAChains(info,' U\n')).toEqual([chain]);expect(matchingRNAChains(info,'T')).toEqual([]);expect(matchingRNAChains({...info,chains:[{...chain,polymerType:'DNA'}]},'U')).toEqual([]);expect(matchingRNAChains({...info,chains:[{...chain,mappingComplete:false}]},'U')).toEqual([]);});
 it('retains duplicate RNA matches for the UI to block ambiguous mapping',()=>{expect(matchingRNAChains({...info,chains:[chain,{...chain,id:'second'}]},'U')).toHaveLength(2);});
 it('derives MFE pairs from dot bracket, never the whole ensemble probability set',()=>{expect(dotBracketPairs('((...))')).toEqual([[2,6],[1,7]]);expect(dotBracketPairs('....')).toEqual([]);for(const bad of ['(()','())','[..]'])expect(()=>dotBracketPairs(bad)).toThrow();});
});
