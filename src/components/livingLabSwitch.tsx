/** Laboratories inside Analyse → Living Biology Lab. Append an entry here to add a laboratory; each renders its own page. */
export const livingLabs=[
 {id:'capillary',label:'Demo D · Capillary tracer'},
 {id:'blood',label:'Blood & Circulation · Demo 6'},
] as const;
export type LivingLabId=typeof livingLabs[number]['id'];

export function LivingLabSwitch({value,onChange}:{value:LivingLabId;onChange:(id:LivingLabId)=>void}){
 return <nav className="cosmos-segment ll-lab-switch" role="tablist" aria-label="Laboratory">
  {livingLabs.map(l=><button key={l.id} role="tab" aria-selected={l.id===value} className={l.id===value?'active':''} onClick={()=>onChange(l.id)}>{l.label}</button>)}
 </nav>;
}
