import {Column} from 'molstar/lib/mol-data/db';
import {IndexPairBonds} from 'molstar/lib/mol-model-formats/structure/property/bonds/index-pair';
import type {EngineModel} from './engineScene';

export function nativeBondPairs(model:EngineModel){
 const bonds=model.bonds.filter(bond=>bond.shown);
 // Mol* compares this per-pair distance to the coordinates (within 0.3 Å).
 // It is an expected length, not a maximum cutoff. Only engine bonds enter.
 return IndexPairBonds.fromData({pairs:{
  indexA:Column.ofIntArray(Int32Array.from(bonds.map(bond=>bond.a))),
  indexB:Column.ofIntArray(Int32Array.from(bonds.map(bond=>bond.b))),
  distance:Column.ofFloatArray(Float32Array.from(bonds.map(bond=>{
   const a=model.atoms[bond.a].xyz,b=model.atoms[bond.b].xyz;
   return Math.hypot(a[0]-b[0],a[1]-b[1],a[2]-b[2]);
  })))
 },count:model.atoms.length},{cacheable:false});
}
