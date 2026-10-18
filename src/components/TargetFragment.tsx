import {useEffect,useState} from 'react';
import {rpc} from '../lib/api';
import type {Item} from '../lib/types';

export default function TargetFragment({projectId,structureId,inspection,onCreated}:{projectId:string;structureId:string;inspection:any;onCreated:(item:Item)=>Promise<void>}){
 const [chain,setChain]=useState(''),[start,setStart]=useState(''),[end,setEnd]=useState(''),[name,setName]=useState('Target fragment'),[busy,setBusy]=useState(false),[error,setError]=useState('');
 const residues=(inspection?.structure.residues??[]).filter((r:any)=>r.chain===chain&&r.polymer);
 useEffect(()=>{setError('');setStart(residues.length?String(residues[0].num):'');setEnd(residues.length?String(residues[residues.length-1].num):'');},[chain,structureId]);
 const first=Number(start),last=Number(end),selected=residues.filter((r:any)=>r.num>=first&&r.num<=last);
 const valid=!!chain&&start.trim()!==''&&end.trim()!==''&&Number.isInteger(first)&&Number.isInteger(last)&&first<=last&&selected.length>0&&selected.length<=600&&!!name.trim();
 return <details><summary>Save a separate target fragment</summary><p className="caption">Choose a continuous observed segment for a smaller design target. Original coordinates and author residue numbers are retained in a new library structure.</p>
  <label>Fragment chain<select value={chain} onChange={e=>setChain(e.target.value)}><option value="">Choose explicitly</option>{inspection.structure.chains.map((c:any)=><option value={c.id} key={c.id}>Chain {c.id} · {c.sequence.length} observed residues</option>)}</select></label>
  <label>First observed author residue<input type="number" value={start} onChange={e=>setStart(e.target.value)}/></label><label>Last observed author residue<input type="number" value={end} onChange={e=>setEnd(e.target.value)}/></label><label>Fragment name<input maxLength={160} value={name} onChange={e=>setName(e.target.value)}/></label>
  <p className="caption">{selected.length} observed residues selected. Removing protein context can change folding and binding. Termini are not capped; whole-complex confidence metrics are not copied.</p>
  <button className="button" disabled={busy||!valid} onClick={async()=>{setBusy(true);setError('');try{const item=await rpc<Item>('fold_fragment',{projectId,structureId,name,residues:selected.map((r:any)=>r.id)});await onCreated(item);}catch(e){setError(String(e));}finally{setBusy(false);}}}>{busy?'Saving target fragment…':'Save fragment and use as target'}</button>
  {error&&<p className="error" role="alert">{error}</p>}
 </details>;
}
