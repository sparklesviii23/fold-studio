import {useEffect,useMemo,useRef,useState} from 'react';
import {exportFile} from '../lib/api';
import {evidenceCategories} from '../lib/engineContract';
import {capillaryEngine,capillaryPresets,capillaryRecord,solveCapillary,taylorArisCoefficient,type CapillaryInputs,type CapillaryResult} from '../lib/taylorAris';
import '../living-lab.css';
import BloodLab from './blood/BloodLab';
import {LivingLabSwitch,type LivingLabId} from './livingLabSwitch';

// Reference dataviz steps validated for a dark surface: numerical (blue) vs analytic (orange, dashed).
const NUMERICAL='#3987e5',ANALYTIC='#d95926',TIME_RAMP=['#184f95','#1c5cab','#2a78d6','#5598e7','#86b6ef','#cde2fb'];
type Series={name:string;color:string;dashed?:boolean;points:[number,number][]};
const fmt=(v:number,digits=3)=>!Number.isFinite(v)?'—':Math.abs(v)>=1e6||Math.abs(v)<1e-2&&v!==0?v.toExponential(digits-1):Math.abs(v)>=10**digits?Math.round(v).toString():String(Number(v.toPrecision(digits)));
function ticks(min:number,max:number,count=5){const span=max-min||1,step=10**Math.floor(Math.log10(span/count)),nice=[1,2,5,10].map(m=>m*step).find(s=>span/s<=count)!;const out=[];for(let v=Math.ceil(min/nice)*nice;v<=max+1e-12*span;v+=nice)out.push(v);return out;}

/** Track the rendered width so SVG text stays at its CSS size instead of scaling with the viewBox. */
function useWidth(){const ref=useRef<HTMLDivElement>(null),[width,setWidth]=useState(560);
 useEffect(()=>{const el=ref.current;if(!el)return;const observer=new ResizeObserver(([entry])=>setWidth(Math.max(280,Math.round(entry.contentRect.width))));observer.observe(el);return()=>observer.disconnect();},[]);
 return [ref,width] as const;}

function LineChart({title,xLabel,yLabel,series,height=230}:{title:string;xLabel:string;yLabel:string;series:Series[];height?:number}){
 const [hover,setHover]=useState<number|null>(null),[ref,W]=useWidth();
 const H=height,L=58,R=14,T=12,B=40,all=series.flatMap(s=>s.points).filter(p=>Number.isFinite(p[1]));
 if(!all.length)return null;
 const x0=Math.min(...all.map(p=>p[0])),x1=Math.max(...all.map(p=>p[0])),y1=Math.max(...all.map(p=>p[1]))*1.05,y0=Math.min(0,...all.map(p=>p[1]));
 const sx=(x:number)=>L+(x-x0)/(x1-x0||1)*(W-L-R),sy=(y:number)=>T+(1-(y-y0)/(y1-y0||1))*(H-T-B);
 const path=(s:Series)=>s.points.filter(p=>Number.isFinite(p[1])).map((p,i)=>(i?'L':'M')+sx(p[0]).toFixed(1)+' '+sy(p[1]).toFixed(1)).join('');
 const nearest=(s:Series,x:number)=>s.points.reduce((a,p)=>Math.abs(p[0]-x)<Math.abs(a[0]-x)?p:a,s.points[0]);
 return <figure className="ll-chart">
  <figcaption>{title}</figcaption>
  {series.length>1&&<div className="ll-legend">{series.map(s=><span key={s.name}><svg width="18" height="6"><line x1="0" y1="3" x2="18" y2="3" stroke={s.color} strokeWidth="2" strokeDasharray={s.dashed?'4 3':undefined}/></svg>{s.name}</span>)}</div>}
  <div className="ll-plot" ref={ref}>
   <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={title}
    onPointerMove={e=>{const box=e.currentTarget.getBoundingClientRect(),px=(e.clientX-box.left)/box.width*W;setHover(px<L||px>W-R?null:x0+(px-L)/(W-L-R)*(x1-x0));}} onPointerLeave={()=>setHover(null)}>
    {ticks(y0,y1).map(v=><g key={'y'+v}><line className="ll-grid" x1={L} x2={W-R} y1={sy(v)} y2={sy(v)}/><text className="ll-tick" x={L-6} y={sy(v)+3} textAnchor="end">{fmt(v,2)}</text></g>)}
    {ticks(x0,x1).map(v=><text key={'x'+v} className="ll-tick" x={sx(v)} y={H-B+14} textAnchor="middle">{fmt(v,3)}</text>)}
    <line className="ll-axis" x1={L} x2={W-R} y1={H-B} y2={H-B}/>
    <text className="ll-axis-label" x={(L+W-R)/2} y={H-6} textAnchor="middle">{xLabel}</text>
    <text className="ll-axis-label" transform={`translate(12 ${(T+H-B)/2}) rotate(-90)`} textAnchor="middle">{yLabel}</text>
    {series.map(s=><path key={s.name} d={path(s)} fill="none" stroke={s.color} strokeWidth="2" strokeDasharray={s.dashed?'5 4':undefined} strokeLinejoin="round"/>)}
    {hover!==null&&<line className="ll-crosshair" x1={sx(hover)} x2={sx(hover)} y1={T} y2={H-B}/>}
   </svg>
   {hover!==null&&<div className="ll-tooltip" style={{left:`${(sx(hover)/W)*100}%`}}>
    <span className="ll-tip-x">{xLabel.split(' (')[0]} {fmt(hover,4)}</span>
    {series.map(s=>{const p=nearest(s,hover);return <span key={s.name} className="ll-tip-row"><svg width="12" height="4"><line x1="0" y1="2" x2="12" y2="2" stroke={s.color} strokeWidth="2"/></svg><strong>{fmt(p[1],4)}</strong><em>{s.name}</em></span>;})}
   </div>}
  </div>
 </figure>;
}

function Heatmap({result}:{result:CapillaryResult}){
 const {rCentresUm,zLabUm,concentrationMolPerM3:c}=result.field,peak=Math.max(...c.flat()),columns=Math.min(zLabUm.length,160),stride=zLabUm.length/columns;
 const shade=(v:number)=>{const t=Math.max(0,Math.min(1,v/peak)),a=[10,18,38],b=[57,135,229],d=[205,226,251],[p,q,u]=t<.6?[a,b,t/.6]:[b,d,(t-.6)/.4];return `rgb(${p.map((x,i)=>Math.round(x+(q[i]-x)*u)).join(',')})`;};
 const [hover,setHover]=useState<{i:number;k:number}|null>(null);
 return <figure className="ll-chart">
  <figcaption>Concentration c(r, z) at t = {fmt(result.inputs.durationS)} s · axis at the bottom row, wall at the top</figcaption>
  <div className="ll-plot">
   <svg viewBox={`0 0 ${columns} ${rCentresUm.length}`} preserveAspectRatio="none" className="ll-heat" role="img" aria-label="Final concentration field" onPointerLeave={()=>setHover(null)}>
    {rCentresUm.map((_,i)=>Array.from({length:columns},(_,j)=>{const k=Math.floor(j*stride);return <rect key={i+'-'+j} x={j} y={rCentresUm.length-1-i} width="1.02" height="1.02" fill={shade(c[i][k])} onPointerEnter={()=>setHover({i,k})}/>;}))}
   </svg>
   {hover&&<div className="ll-tooltip ll-tooltip-static"><strong>{fmt(result.field.concentrationMolPerM3[hover.i][hover.k],4)} mol/m³</strong><em>r = {fmt(rCentresUm[hover.i],3)} µm · z = {fmt(zLabUm[hover.k],4)} µm</em></div>}
  </div>
  <div className="ll-scale"><span>0</span><i/><span>{fmt(peak,3)} mol/m³</span></div>
 </figure>;
}

const fields:[keyof CapillaryInputs,string,string,number][]=[
 ['radiusUm','Radius R','µm',.5],['meanVelocityMmPerS','Mean velocity U','mm/s',.1],['diffusivityUm2PerS','Diffusivity D','µm²/s',10],
 ['durationS','Duration','s',.05],['initialWidthUm','Initial width σ₀','µm',1],['amountFmol','Amount','fmol',.1],
 ['detectorUm','Detector position','µm',10],['radialCells','Radial cells','',1],['axialCells','Axial cells','',10]];

export default function LivingBiologyLab(){
 const [lab,setLab]=useState<LivingLabId>('capillary');
 return lab==='blood'?<BloodLab onSwitch={setLab}/>:<CapillaryDemo onSwitch={setLab}/>;
}

function CapillaryDemo({onSwitch}:{onSwitch:(id:LivingLabId)=>void}){
 const [presetId,setPresetId]=useState(capillaryPresets[0].id),preset=capillaryPresets.find(p=>p.id===presetId)!;
 const [inputs,setInputs]=useState<CapillaryInputs>(preset.inputs),[result,setResult]=useState<CapillaryResult|null>(null),[error,setError]=useState(''),[busy,setBusy]=useState(false),[saved,setSaved]=useState('');
 const preview=useMemo(()=>taylorArisCoefficient(inputs.radiusUm*1e-6,inputs.meanVelocityMmPerS*1e-3,inputs.diffusivityUm2PerS*1e-12),[inputs]);
 const evidence=evidenceCategories[preset.evidence];
 function choose(id:string){const p=capillaryPresets.find(q=>q.id===id)!;setPresetId(id);setInputs(p.inputs);setResult(null);setError('');setSaved('');}
 function run(){setBusy(true);setError('');setSaved('');setTimeout(()=>{try{setResult(solveCapillary(inputs));}catch(e){setResult(null);setError(String((e as Error).message??e));}finally{setBusy(false);}},20);}
 async function save(){if(!result)return;try{const record=await capillaryRecord(result,preset.evidence);await exportFile('capillary-taylor-aris-record.json',{text:JSON.stringify(record,null,2)});setSaved('Record exported · SHA-256 '+record.reproducibility.contentSha256!.slice(0,12)+'…');}catch(e){setError(String((e as Error).message??e));}}
 const b=result?.benchmark,d=result?.derived;
 const profiles:Series[]=result?[...result.snapshots.map((s,i)=>({name:`t = ${fmt(s.t,3)} s`,color:TIME_RAMP[Math.round(i*(TIME_RAMP.length-1)/Math.max(1,result.snapshots.length-1))],points:s.zLabUm.map((z,k)=>[z,s.meanMolPerM3[k]] as [number,number])})),
  {name:'Taylor–Aris Gaussian (final t, no transient correction)',color:ANALYTIC,dashed:true,points:result.snapshots[result.snapshots.length-1].zLabUm.map((z,k)=>[z,result.finalAnalyticMeanMolPerM3[k]] as [number,number])}]:[];
 const variance:Series[]=result?[{name:'Numerical σ²(t)',color:NUMERICAL,points:result.series.map(s=>[s.t,s.varianceM2*1e12])},
  {name:'σ₀² + 2·K_TA·t',color:ANALYTIC,dashed:true,points:result.series.map(s=>[s.t,(inputs.initialWidthUm**2)+2*result.derived.taylorArisM2PerS*1e12*s.t])}]:[];
 const detector:Series[]=result?[{name:'Detector',color:NUMERICAL,points:result.series.map(s=>[s.t,s.detectorMolPerM3??NaN])}]:[];
 const status=(pass:boolean|undefined,applicable=true)=>!applicable?<span className="ll-status warn">⚠ not applicable</span>:pass?<span className="ll-status pass">✓ pass</span>:<span className="ll-status fail">✕ fail</span>;
 return <div className="page-content living-lab">
  <LivingLabSwitch value="capillary" onChange={onSwitch}/>
  <div className="page-heading"><div><span className="eyebrow">ANALYSE · LIVING BIOLOGY LAB · DEMO D</span><h1>A tracer in a capillary, <em>actually solved.</em></h1><p>Finite-volume advection–diffusion in Poiseuille flow, checked against the Taylor–Aris analytical result.</p></div></div>

  <section className="quiet-panel ll-evidence">
   <span className={'ll-badge cat-'+preset.evidence}>Evidence {preset.evidence} · {evidence.name}</span>
   <p>{evidence.meaning} {preset.note}</p>
  </section>

  <section className="quiet-panel">
   <div className="cosmos-segment" role="radiogroup" aria-label="Scenario">{capillaryPresets.map(p=><button key={p.id} role="radio" aria-checked={p.id===presetId} className={p.id===presetId?'active':''} onClick={()=>choose(p.id)}>{p.label}</button>)}</div>
   <div className="ll-fields">{fields.map(([key,label,unit,step])=><label key={key}><span>{label}{unit&&<em> · {unit}</em>}</span>
    <input type="number" step={step} value={inputs[key]} onChange={e=>{setInputs({...inputs,[key]:e.target.valueAsNumber});setResult(null);setSaved('');}}/></label>)}</div>
   <div className="ll-run">
    <p>Pe = U·R/D = <strong>{fmt(preview.peclet)}</strong> · K_TA = D(1 + Pe²/48) = <strong>{fmt(preview.effectiveDispersion*1e12)} µm²/s</strong> · radial time R²/D = <strong>{fmt((inputs.radiusUm**2)/inputs.diffusivityUm2PerS)} s</strong></p>
    <button className="button primary" disabled={busy} onClick={run}>{busy?'Solving…':'Run solver'}</button>
    {result&&<button className="button" onClick={()=>void save()}>Export research record (JSON)</button>}
   </div>
   {error&&<p className="ll-error" role="alert">{error}</p>}{saved&&<p className="ll-saved">{saved}</p>}
  </section>

  {result&&b&&d&&<>
   <section className="ll-tiles">
    <div className="quiet-panel"><span>Effective dispersion · numerical</span><strong>{fmt(b.effectiveDispersion.numericalM2PerS*1e12,4)} <em>µm²/s</em></strong><small>Taylor–Aris {fmt(d.taylorArisM2PerS*1e12,4)} µm²/s · K/D = {fmt(d.enhancement)}</small></div>
    <div className="quiet-panel"><span>Benchmark residual |ΔK|/K</span><strong>{(b.effectiveDispersion.relativeError*100).toFixed(3)} <em>%</em></strong><small>{status(b.effectiveDispersion.pass,b.effectiveDispersion.applicable)} tolerance 1% · {b.effectiveDispersion.fitPoints} points, t ∈ [{fmt(b.effectiveDispersion.fitWindowS[0])}, {fmt(b.effectiveDispersion.fitWindowS[1])}] s</small></div>
    <div className="quiet-panel"><span>Mass conservation</span><strong>{b.mass.maxRelativeDrift.toExponential(1)}</strong><small>{status(b.mass.pass)} max relative drift, tolerance 1e-10</small></div>
    <div className="quiet-panel"><span>Domain / centroid</span><strong>{fmt(b.centroidVelocity.numericalMPerS*1e3,6)} <em>mm/s</em></strong><small>{status(b.domain.pass)} boundary mass {b.domain.maxBoundaryMassFraction.toExponential(1)} · expected U {fmt(d.meanVelocityMPerS*1e3,6)}</small></div>
   </section>
   {!b.effectiveDispersion.applicable&&<p className="ll-error">{b.effectiveDispersion.note}</p>}
   <section className="ll-charts">
    <div className="quiet-panel"><LineChart title="Cross-sectional mean concentration vs position" xLabel="Lab position z (µm)" yLabel="c̄ (mol/m³)" series={profiles}/></div>
    <div className="quiet-panel"><LineChart title="Axial variance vs time — slope is 2K" xLabel="Time t (s)" yLabel="σ² (µm²)" series={variance}/></div>
    <div className="quiet-panel"><LineChart title={`Concentration vs time at the detector, z = ${inputs.detectorUm} µm`} xLabel="Time t (s)" yLabel="c̄ (mol/m³)" series={detector}/>{result.series.every(s=>s.detectorMolPerM3===null)&&<p className="ll-note">The detector never lies inside the solved, co-moving domain during this run; no values are invented.</p>}</div>
    <div className="quiet-panel"><Heatmap result={result}/></div>
   </section>
   <section className="quiet-panel ll-meta">
    <details><summary>Solver settings</summary><dl>
     <dt>Method</dt><dd>{capillaryEngine.numericalMethod}</dd>
     <dt>Grid</dt><dd>{result.inputs.radialCells} × {result.inputs.axialCells} cells · Δr = {fmt(d.drM*1e6)} µm · Δz = {fmt(d.dzM*1e6)} µm · domain ±{fmt(d.domainHalfLengthM*1e6)} µm (co-moving)</dd>
     <dt>Time</dt><dd>{d.steps} steps · Δt = {fmt(d.dtS*1e3)} ms · Courant {result.settings.courant} · radial θ = {result.settings.radialImplicitness} · limiter {result.settings.limiter}</dd>
     <dt>Runtime</dt><dd>{fmt(d.elapsedMs)} ms in this window, deterministic (no random numbers, seed not applicable)</dd>
    </dl></details>
    <details><summary>Assumptions and limitations</summary><ul>{[...capillaryEngine.assumptions,...capillaryEngine.limits].map(t=><li key={t}>{t}</li>)}</ul></details>
    <details><summary>Data table · time series</summary><div className="ll-table"><table><thead><tr><th>t (s)</th><th>σ² (µm²)</th><th>centroid (µm)</th><th>mass (fmol)</th><th>detector (mol/m³)</th></tr></thead>
     <tbody>{result.series.filter((_,i)=>i%5===0).map(s=><tr key={s.t}><td>{fmt(s.t,4)}</td><td>{fmt(s.varianceM2*1e12,5)}</td><td>{fmt(s.centroidLabM*1e6,5)}</td><td>{fmt(s.massMol*1e15,8)}</td><td>{s.detectorMolPerM3===null?'—':fmt(s.detectorMolPerM3,4)}</td></tr>)}</tbody></table></div></details>
   </section>
  </>}
 </div>;
}
