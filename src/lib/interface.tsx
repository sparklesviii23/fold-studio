import {useEffect, useState} from 'react';
import {rpc} from './api';

export const scales = [100, 110, 125, 150] as const;
export interface InterfacePreferences {scale: number; density: 'comfortable'|'compact'; transparency: boolean; motion: boolean}
export const defaults: InterfacePreferences = {scale:100, density:'comfortable', transparency:true, motion:true};
const key = 'fold-interface-v1';
function read(): InterfacePreferences {
  try { const p=JSON.parse(localStorage.getItem(key)??'{}'); return normalize(p); } catch {return defaults;}
}
export function normalize(p: Partial<InterfacePreferences>): InterfacePreferences {
  return {scale:scales.includes(p.scale as any)?p.scale!:100, density:p.density==='compact'?'compact':'comfortable', transparency:p.transparency!==false, motion:p.motion!==false};
}
function apply(p: InterfacePreferences) {
  const root=document.documentElement;
  root.style.setProperty('--ui-scale',String(p.scale/100));
  root.dataset.uiScale=String(p.scale); root.dataset.density=p.density;
  root.dataset.transparency=String(p.transparency); root.dataset.motion=String(p.motion);
}
export function useInterface(keyboard=false) {
  const [preferences,setPreferences]=useState(read), [error,setError]=useState('');
  useEffect(()=>{apply(preferences);},[preferences]);
  useEffect(()=>{
    let active=true;
    rpc<any>('library').then(l=>{if(active&&l.settings.interface){const p=normalize(l.settings.interface);localStorage.setItem(key,JSON.stringify(p));setPreferences(p);}}).catch(()=>{});
    const storage=(e:StorageEvent)=>{if(e.key===key)setPreferences(read());};
    const custom=()=>setPreferences(read());
    window.addEventListener('storage',storage);window.addEventListener('fold-interface',custom);
    return()=>{active=false;window.removeEventListener('storage',storage);window.removeEventListener('fold-interface',custom);};
  },[]);
  function update(change: Partial<InterfacePreferences>) {
    const next=normalize({...read(),...change});
    try{localStorage.setItem(key,JSON.stringify(next));setPreferences(next);window.dispatchEvent(new Event('fold-interface'));}
    catch(e){setError('Appearance could not be saved locally: '+String(e));}
    rpc('setting_set',{key:'interface',value:next}).then(()=>setError('')).catch(e=>setError('Local appearance retained; library sync failed: '+String(e)));
  }
  useEffect(()=>{
    if(!keyboard)return;
    const onKey=(e:KeyboardEvent)=>{
      if(!(e.metaKey||e.ctrlKey)||!['+','=','-','0'].includes(e.key)||(e.target as HTMLElement).closest('input,textarea,[contenteditable=true]'))return;
      e.preventDefault();const index=scales.indexOf(read().scale as any);
      update({scale:e.key==='0'?100:scales[Math.max(0,Math.min(scales.length-1,index+(e.key==='-'?-1:1)))]});
    };
    window.addEventListener('keydown',onKey);return()=>window.removeEventListener('keydown',onKey);
  },[keyboard]);
  return {preferences,update,error};
}
export function InterfaceControls() {
  const {preferences:p,update,error}=useInterface();
  return <section className="quiet-panel interface-controls"><h3>Interface comfort</h3>
    <p>Interface size changes text and controls. Molecular camera zoom is separate.</p>
    <label>Interface size<select aria-label="Interface size" value={p.scale} onChange={e=>update({scale:Number(e.target.value)})}>{scales.map(s=><option key={s} value={s}>{s}%</option>)}</select></label>
    <label>Density<select value={p.density} onChange={e=>update({density:e.target.value as any})}><option value="comfortable">Comfortable</option><option value="compact">Compact</option></select></label>
    <label className="checkbox-label"><input type="checkbox" checked={!p.transparency} onChange={e=>update({transparency:!e.target.checked})}/>Reduce transparency</label>
    <label className="checkbox-label"><input type="checkbox" checked={!p.motion} onChange={e=>update({motion:!e.target.checked})}/>Reduce motion</label>
    <button className="button" onClick={()=>update(defaults)}>Reset interface · 100%</button>
    <p className="caption">⌘+ / ⌘− adjusts size. ⌘0 resets. System accessibility preferences are also respected.</p>
    {error&&<p role="alert" className="error">{error}</p>}
  </section>;
}
