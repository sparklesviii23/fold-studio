import {describe,it,expect} from 'vitest';
import {CIF} from 'molstar/lib/mol-io/reader/cif';
import {trajectoryFromMmCIF} from 'molstar/lib/mol-model-formats/structure/mmcif';
import {IndexPairBonds} from 'molstar/lib/mol-model-formats/structure/property/bonds/index-pair';
import {Structure,Unit} from 'molstar/lib/mol-model/structure';
import {nativeBondPairs} from './engineBonds';
import type {EngineModel} from './engineScene';

// Artificial coordinates test explicit topology transport, not molecular quality.
const positions=[[0,0,0],[1.54,0,0],[2.63,0,0],[1.54,1.2,0]];
const fixture={atoms:positions.map(xyz=>({xyz})),bonds:[{a:0,b:1,shown:true},{a:1,b:2,shown:true},{a:1,b:3,shown:false}]} as EngineModel;
async function graph(model:EngineModel){
 const fields=['group_PDB','id','type_symbol','label_atom_id','label_alt_id','label_comp_id','label_asym_id','label_entity_id','label_seq_id','pdbx_PDB_ins_code','Cartn_x','Cartn_y','Cartn_z','occupancy','B_iso_or_equiv','auth_seq_id','auth_asym_id','auth_comp_id','auth_atom_id','pdbx_PDB_model_num'];
 const rows=positions.map((xyz,i)=>['HETATM',i+1,i===2?'H':'C','X'+i,'.','UNL','L',1,'.','?',...xyz,1,0,1,'L','UNL','X'+i,1].join(' '));
 const cif=await CIF.parse('data_QA\nloop_\n'+fields.map(field=>'_atom_site.'+field).join('\n')+'\n'+rows.join('\n')+'\n#\n').run();
 if(cif.isError)throw new Error(cif.message);
 const trajectory=await trajectoryFromMmCIF(cif.result.blocks[0]).run();
 const parsed=trajectory.representative;IndexPairBonds.Provider.set(parsed,nativeBondPairs(model));
 const structure=Structure.ofModel(parsed);const pairs:string[]=[];
 for(const unit of structure.units){if(!Unit.isAtomic(unit))continue;const {a,b,edgeCount}=unit.bonds;for(let i=0;i<edgeCount*2;i++)if(a[i]<b[i])pairs.push([unit.elements[a[i]],unit.elements[b[i]]].sort().join(':'));}
 return pairs.sort();
}
describe('native bonds in the actual Mol* structure graph',()=>{
 it('retains engine C–C and C–H bonds and excludes hidden or merely nearby pairs',async()=>{expect(await graph(fixture)).toEqual(['0:1','1:2']);});
 it('does not infer a chemical bond when the engine supplies none',async()=>{expect(await graph({...fixture,bonds:[]})).toEqual([]);});
});
