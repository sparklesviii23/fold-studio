import {useEffect, useState} from 'react';
import {rpc} from './api';

export const scales = [100, 110, 125, 150] as const;
export type Backdrop = 'living'|'still'|'off';
export type Glass = 'liquid'|'frosted'|'solid';
export interface InterfacePreferences {scale: number; density: 'comfortable'|'compact'; transparency: boolean; motion: boolean; backdrop: Backdrop; glass: Glass}
export const defaults: InterfacePreferences = {scale:100, density:'comfortable', transparency:true, motion:true, backdrop:'living', glass:'liquid'};
const key = 'fold-interface-v1';
function read(): InterfacePreferences {
  try { const p=JSON.parse(localStorage.getItem(key)??'{}'); return normalize(p); } catch {return defaults;}
}
export function normalize(p: Partial<InterfacePreferences>): InterfacePreferences {
  return {scale:scales.includes(p.scale as any)?p.scale!:100, density:p.density==='compact'?'compact':'comfortable', transparency:p.transparency!==false, motion:p.motion!==false,
    backdrop:p.backdrop==='still'||p.backdrop==='off'?p.backdrop:'living', glass:p.glass==='frosted'||p.glass==='solid'?p.glass:'liquid'};
}
function apply(p: InterfacePreferences) {
  const root=document.documentElement;
  root.style.setProperty('--ui-scale',String(p.scale/100));
  root.dataset.uiScale=String(p.scale); root.dataset.density=p.density;
  root.dataset.transparency=String(p.transparency); root.dataset.motion=String(p.motion);
  root.dataset.glass=p.glass; root.dataset.cosmos='';
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
function Segment<T extends string|number>({value,options,onChange,label}:{value:T;options:[T,string][];onChange:(v:T)=>void;label:string}){
  return <div className="cosmos-segment" role="radiogroup" aria-label={label}>{options.map(([v,text])=><button key={String(v)} role="radio" aria-checked={value===v} className={value===v?'active':''} onClick={()=>onChange(v)}>{text}</button>)}</div>;
}
export function InterfaceControls() {
  const {preferences:p,update,error}=useInterface();
  const row=(title:string,note:string,control:React.ReactNode)=><div className="setting-line"><div><h3>{title}</h3><p>{note}</p></div>{control}</div>;
  return <section className="settings-card">
    {row('Background','A living galaxy behind the glass, one still exposure, or none.',<Segment label="Background" value={p.backdrop} options={[['living','Living'],['still','Still'],['off','Off']]} onChange={backdrop=>update({backdrop})}/>)}
    {row('Glass','Liquid glass lets the galaxy through; solid panels are calmest for long sessions.',<Segment label="Glass" value={p.glass} options={[['liquid','Liquid'],['frosted','Frosted'],['solid','Solid']]} onChange={glass=>update({glass})}/>)}
    {row('Interface size','Text and controls. Camera zoom is separate · ⌘+ ⌘− ⌘0',<Segment label="Interface size" value={p.scale} options={scales.map(s=>[s,s+'%'] as [number,string])} onChange={scale=>update({scale})}/>)}
    {row('Density','Compact fits more rows into tables and navigation.',<Segment label="Density" value={p.density} options={[['comfortable','Comfortable'],['compact','Compact']]} onChange={density=>update({density})}/>)}
    {row('Accessibility','System preferences are always respected as well.',<div className="setting-checks"><label className="checkbox-label"><input type="checkbox" checked={!p.transparency} onChange={e=>update({transparency:!e.target.checked})}/>Reduce transparency</label><label className="checkbox-label"><input type="checkbox" checked={!p.motion} onChange={e=>update({motion:!e.target.checked})}/>Reduce motion</label></div>)}
    {row('Defaults','Return every appearance setting to its original value.',<button className="button" onClick={()=>update(defaults)}>Restore defaults</button>)}
    {error&&<p role="alert" className="error">{error}</p>}
  </section>;
}
