export function trackNavigation(window:any,action:'previous'|'next'|'in'|'out'){
 const n=window.repliconLength,length=window.length;
 const size=Math.min(n,100000,action==='in'?Math.max(1,Math.floor(length/2)):action==='out'?length*2:length);
 const shift=action==='previous'?-length:action==='next'?length:Math.floor((length-size)/2);
 // Navigation stays within the forward linear display; circular extraction remains explicit.
 const start=Math.max(1,Math.min(n-size+1,window.windowStart+shift));return {start,end:start+size-1,strand:'+'};
}
export default function GenomeTracks({window,busy,onNavigate,onFeature}:{window:any;busy:boolean;onNavigate:(value:any)=>void;onFeature:(index:number)=>void}){
 if(!window)return null;
 return <fieldset disabled={busy}><legend>Supplied annotation tracks · forward-reference view</legend><p>{window.windowStart}–{window.unrolledWindowEnd} · {window.total} overlapping annotations · {window.omitted} omitted. Circular-origin coordinates are shown unrolled; strand arrows describe the supplied annotations.</p>
 <div>{(['previous','next','in','out'] as const).map(action=><button className="button" key={action} onClick={()=>onNavigate(trackNavigation(window,action))}>{({previous:'Previous window',next:'Next window',in:'Zoom in',out:'Zoom out'})[action]}</button>)}</div>
 <div style={{maxHeight:400,overflow:'auto'}}><svg role="img" aria-label="Supplied genomic annotation interval tracks" viewBox={`0 0 900 ${Math.max(36,window.features.length*28+20)}`} style={{width:'100%',minWidth:400}}>
  {window.features.map(({feature,fragments}:any,i:number)=><g key={feature.index} transform={`translate(0,${i*28+8})`}><text x="0" y="13" fill="currentColor" fontSize="11">{String(feature.attributes.Name??feature.attributes.ID??feature.type).slice(0,22)} {feature.strand==='+'?'→':feature.strand==='-'?'←':'·'}</text><line x1="200" x2="890" y1="10" y2="10" stroke="currentColor" opacity=".2"/>{fragments.map((fragment:any,j:number)=><rect key={j} x={200+fragment.startOffsetZeroBased/window.length*690} y="3" width={Math.max(1,(fragment.endOffsetExclusive-fragment.startOffsetZeroBased)/window.length*690)} height="14" fill="currentColor" opacity={feature.type==='CDS'?.9:.5}><title>{`${feature.type} ${feature.start}–${feature.end} (${feature.strand}); ${fragment.continuesBeforeWindow?'continues before window; ':''}${fragment.continuesAfterWindow?'continues after window':''}`}</title></rect>)}</g>)}
 </svg></div><details><summary>Inspect an overlapping annotation</summary>{window.features.map(({feature}:any)=><button className="button" key={feature.index} disabled={!['+','-'].includes(feature.strand)||feature.end-feature.start+1>100000} onClick={()=>onFeature(feature.index)}>{feature.attributes.Name??feature.attributes.ID??feature.type} · {feature.type} · {feature.start}–{feature.end} ({feature.strand})</button>)}</details><p>{window.scope}</p></fieldset>;
}
