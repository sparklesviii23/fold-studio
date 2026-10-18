import {useEffect,useState} from 'react';
import {rpc} from '../lib/api';
import type {Item} from '../lib/types';

export type AdditionalTarget={structureId:string;targetChains:string[];hotspots:string[];coldspots:string[];objective:'target'|'detarget';weight:number};

export default function CampaignTarget({projectId,structures,value,index,onChange,onRemove}:{projectId:string;structures:Item[];value:AdditionalTarget;index:number;onChange:(value:AdditionalTarget)=>void;onRemove:()=>void}){
 const [structure,setStructure]=useState<any>(null),[error,setError]=useState('');
 useEffect(()=>{let active=true;setStructure(null);setError('');if(value.structureId)rpc<any>('fold_structure',{projectId,structureId:value.structureId}).then(r=>{if(active)setStructure(r.structure);}).catch(e=>{if(active)setError(String(e));});return()=>{active=false;};},[projectId,value.structureId]);
 const update=(patch:Partial<AdditionalTarget>)=>onChange({...value,...patch});
 const residues=(structure?.residues??[]).filter((r:any)=>value.targetChains.includes(r.chain)&&r.polymer);
 return <fieldset><legend>Additional target {index}</legend>
  <label>Saved structure<select value={value.structureId} onChange={e=>update({structureId:e.target.value,targetChains:[],hotspots:[],coldspots:[]})}><option value="">Choose a saved structure</option>{structures.map(r=><option key={r.id} value={r.id}>{r.name}</option>)}</select></label>
  <label>Design objective<select value={value.objective} onChange={e=>update({objective:e.target.value as AdditionalTarget['objective']})}><option value="target">Bind this target</option><option value="detarget">Avoid this target</option></select></label>
  <label>Relative objective weight<input type="number" min={.01} max={10} step={.1} value={value.weight} onChange={e=>update({weight:Number(e.target.value)})}/></label>
  {structure?.chains.map((c:any)=><label className="checkbox-label" key={c.id}><input type="checkbox" checked={value.targetChains.includes(c.id)} onChange={()=>update({targetChains:value.targetChains.includes(c.id)?value.targetChains.filter(id=>id!==c.id):[...value.targetChains,c.id],hotspots:[],coldspots:[]})}/>Chain {c.id} · {c.sequence.length} observed residues</label>)}
  <label>Hotspots · observed source numbering<select multiple value={value.hotspots} onChange={e=>{const selected=Array.from(e.target.selectedOptions,o=>o.value);update({hotspots:selected,coldspots:value.coldspots.filter(id=>!selected.includes(id))});}}>{residues.map((r:any)=><option key={r.id} value={r.id}>{r.chain}:{r.num}{r.ins} {r.name}</option>)}</select></label>
  <label>Coldspots<select multiple value={value.coldspots} onChange={e=>{const selected=Array.from(e.target.selectedOptions,o=>o.value);update({coldspots:selected,hotspots:value.hotspots.filter(id=>!selected.includes(id))});}}>{residues.map((r:any)=><option key={r.id} value={r.id}>{r.chain}:{r.num}{r.ins} {r.name}</option>)}</select></label>
  <p className="caption">Weights guide the original design objective; they do not measure affinity. Residue identities refer to this saved coordinate model.</p>
  {error&&<p className="error" role="alert">{error}</p>}<button className="button" onClick={onRemove}>Remove target state</button>
 </fieldset>;
}
