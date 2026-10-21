export type StageCoordinate={file:string;sha256:string;bytes:number};

export default function CampaignCoordinates({entries,enabled,busy,onSave}:{entries:StageCoordinate[];enabled:boolean;busy:boolean;onSave:(entry:StageCoordinate)=>void}){
 if(!entries.length)return null;
 return <div><div className="button-row">{entries.map((entry,index)=><button className="button" key={entry.file} disabled={busy||!enabled} onClick={()=>onSave(entry)}>Save structure{entries.length>1?` ${index+1}`:''} to library</button>)}</div><p className="caption">Saved stage coordinates can be opened in Research Library. Saving a preview preserves its recorded outcome and does not add an accepted design.{!enabled?' Available after this campaign finishes or stops.':''}</p></div>;
}
