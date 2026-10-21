/** Output retention only; scientific objectives and acceptance stay upstream-owned. */
export function fabOutputOptions(modality:string,options:Record<string,unknown>){
 return modality==='Fab'?{save_design_trajectory:true,save_failed_trajectories:true,...options}:options;
}

export default function FabOutputOptions({options,disabled,onChange}:{options:Record<string,unknown>;disabled:boolean;onChange:(options:Record<string,unknown>)=>void}){
 const enabled=options.save_design_trajectory===true&&options.save_failed_trajectories===true;
 return <div><label className="checkbox-label"><input type="checkbox" checked={enabled} disabled={disabled} onChange={event=>onChange({...options,save_design_trajectory:event.target.checked,save_failed_trajectories:event.target.checked})}/>Keep final trajectory structures, including rejected attempts</label><p className="caption">Saves the final pose from each trajectory for inspection in the existing viewer. This output choice is recorded in the new campaign recipe; scientific settings and acceptance criteria stay unchanged. Existing campaigns keep their saved choices.</p></div>;
}
