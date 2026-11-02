import {Fragment,useEffect,useMemo,useRef,useState} from 'react';
import {Pause,Play} from 'lucide-react';
import {exportFile} from '../../lib/api';
import {crossCheckWithDemoD,describeBloodEngine,runBloodTransport,validateBloodEngine,type BloodDescriptor,type BloodInputs,type BloodPreset,type BloodResult,type CrossCheck,type InletMode,type ValidationReport} from '../../lib/bloodTransport';
import {fmt,SERIES,TimeChart} from '../mechanistic/MechCharts';
import {LivingLabSwitch,type LivingLabId} from '../livingLabSwitch';
import '../mechanistic/mechanistic.css';
import '../../living-lab.css';
import './blood-lab.css';

// Sequential ramp for concentration on the dark surface (navy → blue → pale), shared by the vessel and the cross-section.
const RAMP:[number,number,number][]=[[8,14,32],[22,52,110],[42,120,214],[110,182,240],[214,235,252],[255,246,222]];
function ramp(t:number){const x=Math.max(0,Math.min(1,t))*(RAMP.length-1),i=Math.min(RAMP.length-2,Math.floor(x)),f=x-i,a=RAMP[i],b=RAMP[i+1];return [0,1,2].map(k=>Math.round(a[k]+(b[k]-a[k])*f)) as [number,number,number];}
const css=(c:[number,number,number])=>`rgb(${c.join(',')})`;

const FIELDS:{key:keyof BloodInputs;label:string;unit:string;step:number;show?:(m:InletMode)=>boolean}[]=[
 {key:'radiusUm',label:'Radius R',unit:'µm',step:1},{key:'lengthUm',label:'Length L',unit:'µm',step:10},
 {key:'meanVelocityMmPerS',label:'Mean velocity U',unit:'mm/s',step:.1},{key:'diffusivityUm2PerS',label:'Diffusivity D',unit:'µm²/s',step:10},
 {key:'wallPermeabilityUmPerS',label:'Wall permeability P',unit:'µm/s',step:.5},{key:'durationS',label:'Duration',unit:'s',step:.05},
 {key:'inletAmplitude',label:'Inlet / slug peak',unit:'mol/m³',step:.1},
 {key:'pulseCentreS',label:'Pulse centre t₀',unit:'s',step:.01,show:m=>m==='pulse'},{key:'pulseWidthS',label:'Pulse width σₜ',unit:'s',step:.005,show:m=>m==='pulse'},
 {key:'slugCentreUm',label:'Slug centre z₀',unit:'µm',step:5,show:m=>m==='slug'},{key:'slugWidthUm',label:'Slug width σ₀',unit:'µm',step:1,show:m=>m==='slug'},
 {key:'plasmaViscosityMPaS',label:'Plasma viscosity μ',unit:'mPa·s',step:.05},
 {key:'radialCells',label:'Radial cells',unit:'',step:1},{key:'axialCells',label:'Axial cells',unit:'',step:10},
 {key:'particles',label:'Particles',unit:'',step:500},{key:'seed',label:'Particle seed',unit:'',step:1}];

const status=(pass:boolean|undefined,applicable=true)=>!applicable?<span className="ll-status warn">⚠ n/a</span>:pass?<span className="ll-status pass">✓ pass</span>:<span className="ll-status fail">✕ fail</span>;
const nearestIndex=(xs:number[],x:number)=>{let best=0;for(let i=1;i<xs.length;i++)if(Math.abs(xs[i]-x)<Math.abs(xs[best]-x))best=i;return best;};

function useWidth(min=320){const ref=useRef<HTMLDivElement>(null),[w,setW]=useState(900);
 useEffect(()=>{const el=ref.current;if(!el)return;const o=new ResizeObserver(([e])=>setW(Math.max(min,Math.round(e.contentRect.width))));o.observe(el);return()=>o.disconnect();},[min]);
 return [ref,w] as const;}

/** Longitudinal section of the vessel: the computed c(r, z) mirrored about the axis, with flow, boundary fluxes and optional particles. */
function VesselView({result,frame,showParticles,probe,setProbe}:{result:BloodResult;frame:number;showParticles:boolean;probe:number;setProbe:(k:number)=>void}){
 const canvas=useRef<HTMLCanvasElement>(null),[box,W]=useWidth();
 const {rUm,zUm,items,peakMolPerM3,levels}=result.frames,f=items[frame],nr=rUm.length,nz=zUm.length;
 const H=Math.round(Math.min(300,Math.max(170,W*.26))),padL=64,padR=64,padT=46,padB=52,vw=W-padL-padR,vh=H-padT-padB;
 const R=result.inputs.radiusUm,L=result.inputs.lengthUm,exaggeration=(vh/(2*R))/(vw/L);
 useEffect(()=>{
  const c=canvas.current;if(!c)return;const ctx=c.getContext('2d')!,img=ctx.createImageData(nz,2*nr);
  for(let row=0;row<2*nr;row++){const i=row<nr?nr-1-row:row-nr;for(let k=0;k<nz;k++){const [r,g,b]=ramp(f.field[i][k]/levels),o=(row*nz+k)*4;img.data[o]=r;img.data[o+1]=g;img.data[o+2]=b;img.data[o+3]=255;}}
  c.width=nz;c.height=2*nr;ctx.putImageData(img,0,0);
 },[f,nr,nz,levels]);
 const sx=(z:number)=>padL+z/L*vw,sy=(r:number)=>padT+vh/2-r/R*vh/2;
 const u=result.flow.pointVelocityMmPerS,uMax=Math.max(...u,1e-12);
 const row=result.series[nearestIndex(result.series.map(s=>s.t),f.t)];
 const tracks=result.particles?.tracks,pf=tracks?tracks[nearestIndex(tracks.map(t=>t.t),f.t)]:null;
 const wallFlux=row.wallFluxMolPerS*1e15,inFlux=row.inletFluxMolPerS*1e15,outFlux=row.outletFluxMolPerS*1e15;
 const parabola=(side:1|-1)=>Array.from({length:25},(_,j)=>{const r=side*R*j/24;return `${j?'L':'M'}${(padL-8-38*(1-(r/R)**2)).toFixed(1)} ${sy(r).toFixed(1)}`;}).join('');
 return <figure className="bl-vessel" ref={box}>
  <figcaption>
   <strong>Vessel section · c(r, z) at t = {fmt(f.t,4)} s</strong>
   <span>Computed field (mirrored about the axis). Radial scale exaggerated ×{fmt(exaggeration,2)} so a {fmt(2*R)} µm × {fmt(L)} µm tube is readable.</span>
  </figcaption>
  <div className="bl-vessel-stage" style={{height:H}}>
   <canvas ref={canvas} style={{left:padL,top:padT,width:vw,height:vh}} aria-hidden="true"/>
   <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Vessel concentration field with boundary fluxes"
    onPointerMove={e=>{const b=e.currentTarget.getBoundingClientRect(),x=e.clientX-b.left;if(x>=padL&&x<=padL+vw)setProbe(Math.min(nz-1,Math.max(0,Math.round((x-padL)/vw*(nz-1)))));}}>
    <defs><marker id="bl-arrow" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0L8 4L0 8z" fill="currentColor"/></marker></defs>
    <line className="bl-wall" x1={padL} x2={padL+vw} y1={padT} y2={padT}/><line className="bl-wall" x1={padL} x2={padL+vw} y1={padT+vh} y2={padT+vh}/>
    <line className="bl-axis" x1={padL} x2={padL+vw} y1={padT+vh/2} y2={padT+vh/2}/>
    {result.inputs.wallPermeabilityUmPerS>0&&Array.from({length:14},(_,j)=>{const x=padL+(j+.5)*vw/14,k=Math.min(nz-1,Math.round((j+.5)/14*(nz-1))),edge=f.field[nr-1][k]/levels,len=4+16*edge;
     return <g key={j} className="bl-wallflux" opacity={.25+.75*edge}><line x1={x} x2={x} y1={padT-2} y2={padT-2-len} markerEnd="url(#bl-arrow)"/><line x1={x} x2={x} y1={padT+vh+2} y2={padT+vh+2+len} markerEnd="url(#bl-arrow)"/></g>;})}
    <path className="bl-profile" d={parabola(1)+parabola(-1).replace('M','L')}/>
    {[-.66,0,.66].map(q=><line key={q} className="bl-flow" x1={padL-44} x2={padL-44+30*(1-q*q)} y1={sy(q*R)} y2={sy(q*R)} markerEnd="url(#bl-arrow)"/>)}
    <text className="bl-label" x={4} y={14}>u(r) · max {fmt(uMax,3)} mm/s</text>
    {result.inputs.inletMode!=='slug'&&<text className="bl-label" x={padL} y={H-2}>in {fmt(inFlux,3)} fmol/s</text>}
    {result.inputs.inletMode!=='slug'&&<text className="bl-label" x={padL+vw} y={H-2} textAnchor="end">out {fmt(outFlux,3)} fmol/s</text>}
    {result.inputs.inletMode==='slug'&&<text className="bl-label" x={padL} y={H-2}>closed ends (validation)</text>}
    {result.inputs.wallPermeabilityUmPerS>0&&<text className="bl-label bl-label-warm" x={padL+vw/2} y={14} textAnchor="middle">wall loss {fmt(wallFlux,3)} fmol/s · P = {fmt(result.inputs.wallPermeabilityUmPerS)} µm/s</text>}
    {result.inputs.wallPermeabilityUmPerS===0&&<text className="bl-label" x={padL+vw/2} y={padT-12} textAnchor="middle">impermeable rigid wall</text>}
    <text className="bl-label" x={padL-4} y={padT+vh/2+4} textAnchor="end">r=0</text>
    <line className="bl-probe" x1={sx(zUm[probe])} x2={sx(zUm[probe])} y1={padT} y2={padT+vh}/>
    {showParticles&&pf&&pf.zUm.map((z,i)=>pf.state[i]===1&&z>=0&&z<=L?<circle key={i} className="bl-particle" cx={sx(z)} cy={sy((i%2?1:-1)*Math.min(pf.rUm[i],R))} r="1.8"/>:null)}
    {[0,.25,.5,.75,1].map(q=><text key={q} className="bl-tick" x={padL+q*vw} y={padT+vh+36} textAnchor="middle">{fmt(q*L,3)}</text>)}
    <text className="bl-tick" x={padL+vw+6} y={padT+vh+36}>z (µm)</text>
   </svg>
  </div>
  <div className="ll-scale"><span>0</span><i className="bl-ramp"/><span>{fmt(peakMolPerM3,3)} mol/m³ (run peak)</span>{showParticles&&pf&&<span className="bl-particle-key">● particles shown at ±r (angle not drawn)</span>}</div>
  <p className="ll-note">Display frames are 16-bit levels of the run peak; profile u(r) is the verified Poiseuille field (dp/dz = {fmt(result.flow.pressureGradientPaPerM,4)} Pa/m, wall shear {fmt(result.flow.wallShearStressPa,3)} Pa for μ = {result.inputs.plasmaViscosityMPaS} mPa·s).</p>
 </figure>;
}

/** Cross-section at the probed axial position: rings coloured by the computed ring concentrations. */
function CrossSection({result,frame,probe}:{result:BloodResult;frame:number;probe:number}){
 const {rUm,zUm,items,peakMolPerM3,levels}=result.frames,f=items[frame],R=result.inputs.radiusUm,nr=rUm.length;
 const values=Array.from({length:nr},(_,i)=>f.field[i][probe]/levels*peakMolPerM3),S=200,c=S/2,scale=(S/2-10)/R;
 const mean=f.mean[probe];
 return <figure className="bl-cross">
  <figcaption><strong>Cross-section at z = {fmt(zUm[probe],4)} µm</strong><span>Move over the vessel to probe. c̄ = {fmt(mean,4)} mol/m³</span></figcaption>
  <svg viewBox={`0 0 ${S} ${S}`} role="img" aria-label={`Cross-section concentration at z = ${fmt(zUm[probe])} µm`}>
   {values.map((_,j)=>{const i=nr-1-j,outer=Math.min(R,rUm[i]+R/nr/2);return <circle key={i} cx={c} cy={c} r={outer*scale} fill={css(ramp(values[i]/peakMolPerM3))}/>;})}
   <circle cx={c} cy={c} r={R*scale} className="bl-cross-wall"/>
  </svg>
  <div className="bl-cross-scale">{[0,nr>>1,nr-1].map(i=><span key={i}>r {fmt(rUm[i],3)} µm · {fmt(values[i],3)}</span>)}</div>
 </figure>;
}

function VelocityChart({result}:{result:BloodResult}){
 const [ref,W]=useWidth(260),H=200,L=52,Rm=12,T=12,B=36,{rUm,pointVelocityMmPerS:u,fvPointVelocityMmPerS:fv}=result.flow,R=result.inputs.radiusUm,uMax=Math.max(...u,1e-9)*1.08;
 const sx=(v:number)=>L+v/uMax*(W-L-Rm),sy=(r:number)=>T+(1-r/R)*(H-T-B);
 const exact=Array.from({length:41},(_,j)=>{const r=R*j/40;return `${j?'L':'M'}${sx(2*result.inputs.meanVelocityMmPerS*(1-(r/R)**2)).toFixed(1)} ${sy(r).toFixed(1)}`;}).join('');
 return <figure className="ll-chart" ref={ref}>
  <figcaption>Velocity profile u(r) — Poiseuille vs finite-volume Stokes solve</figcaption>
  <div className="ll-legend"><span><svg width="18" height="6"><line x1="0" y1="3" x2="18" y2="3" stroke={SERIES[0]} strokeWidth="2"/></svg>u = 2U(1 − r²/R²)</span><span><svg width="10" height="10"><circle cx="5" cy="5" r="3.5" fill={SERIES[1]}/></svg>FV Stokes at ring centres</span></div>
  <svg viewBox={`0 0 ${W} ${H}`} className="bl-svg">
   {[0,.5,1].map(q=><g key={q}><line className="ll-grid" x1={L} x2={W-Rm} y1={sy(q*R)} y2={sy(q*R)}/><text className="ll-tick" x={L-6} y={sy(q*R)+3} textAnchor="end">{fmt(q*R,3)}</text></g>)}
   {[0,.5,1].map(q=><text key={q} className="ll-tick" x={sx(q*uMax/1.08)} y={H-B+14} textAnchor="middle">{fmt(q*uMax/1.08,3)}</text>)}
   <line className="ll-axis" x1={L} x2={W-Rm} y1={H-B} y2={H-B}/>
   <path d={exact} fill="none" stroke={SERIES[0]} strokeWidth="2"/>
   {fv.map((v,i)=><circle key={i} cx={sx(v)} cy={sy(rUm[i])} r="2.6" fill={SERIES[1]}/>)}
   <text className="ll-axis-label" x={(L+W-Rm)/2} y={H-4} textAnchor="middle">u (mm/s)</text>
   <text className="ll-axis-label" transform={`translate(12 ${(T+H-B)/2}) rotate(-90)`} textAnchor="middle">r (µm)</text>
  </svg>
  <p className="ll-note">FV error {fmt(result.flow.fvRelativeError,3)} of u_max (second order in Δr); ring-averaged flow rate error {fmt(result.flow.flowRateRelativeError,2)}.</p>
 </figure>;
}

const defaultInputs:BloodInputs={radiusUm:5,lengthUm:700,meanVelocityMmPerS:4,diffusivityUm2PerS:1000,wallPermeabilityUmPerS:0,durationS:.1,inletMode:'slug',inletAmplitude:1,pulseCentreS:0,pulseWidthS:.01,slugCentreUm:150,slugWidthUm:20,plasmaViscosityMPaS:1.2,radialCells:24,axialCells:500,particles:4000,seed:7};

export default function BloodLab({onSwitch}:{onSwitch:(id:LivingLabId)=>void}){
 const [engine,setEngine]=useState<BloodDescriptor|null>(null),[presetId,setPresetId]=useState('taylor-aris');
 const [inputs,setInputs]=useState<BloodInputs>(defaultInputs),[particles,setParticles]=useState(true);
 const [result,setResult]=useState<BloodResult|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState(''),[saved,setSaved]=useState('');
 const [frame,setFrame]=useState(0),[playing,setPlaying]=useState(false),[probe,setProbe]=useState(0),[showParticles,setShowParticles]=useState(true);
 const [report,setReport]=useState<ValidationReport|null>(null),[validating,setValidating]=useState(false),[cross,setCross]=useState<CrossCheck|null>(null);
 useEffect(()=>{describeBloodEngine().then(e=>{setEngine(e);const p=e.presets[0];setPresetId(p.id);setInputs(p.inputs);}).catch(e=>setError('The plasma-transport engine is unavailable: '+String(e?.message??e)));},[]);
 const preset:BloodPreset|undefined=engine?.presets.find(p=>p.id===presetId);
 const edited=!!preset&&JSON.stringify(preset.inputs)!==JSON.stringify(inputs);
 const evidence:'B'|'D'=preset?.evidence==='B'&&!edited?'B':'D';
 useEffect(()=>{if(!playing||!result)return;const n=result.frames.items.length;const id=setInterval(()=>setFrame(f=>{if(f>=n-1){setPlaying(false);return f;}return f+1;}),110);return()=>clearInterval(id);},[playing,result]);
 const live=useMemo(()=>{const R=inputs.radiusUm*1e-6,U=inputs.meanVelocityMmPerS*1e-3,D=inputs.diffusivityUm2PerS*1e-12,Pe=U*R/D;
  return {Pe,K:D*(1+Pe*Pe/48)*1e12,transit:U>0?inputs.lengthUm*1e-6/U:null,Bi:inputs.wallPermeabilityUmPerS*1e-6*R/D,radial:R*R/D,dpdz:-8*inputs.plasmaViscosityMPaS*1e-3*U/(R*R),tau:4*inputs.plasmaViscosityMPaS*1e-3*U/R};},[inputs]);
 function choose(p:BloodPreset){setPresetId(p.id);setInputs(p.inputs);setResult(null);setCross(null);setError('');setSaved('');}
 function set<K extends keyof BloodInputs>(k:K,v:BloodInputs[K]){setInputs({...inputs,[k]:v});setResult(null);setCross(null);setSaved('');}
 async function run(){setBusy(true);setError('');setSaved('');setCross(null);setPlaying(false);
  try{const r=await runBloodTransport(inputs,evidence,particles);setResult(r);setFrame(r.frames.items.length-1);const m=r.frames.items[r.frames.items.length-1].mean;setProbe(m.indexOf(Math.max(...m)));
   if(r.dispersion)setTimeout(()=>{try{setCross(crossCheckWithDemoD(r.inputs,r.dispersion!.numericalM2PerS,r.final));}catch(e){setCross({applicable:false,reason:String((e as Error).message??e)});}},0);
   else setCross(crossCheckWithDemoD(r.inputs,NaN,r.final));
  }catch(e){setResult(null);setError(String((e as Error)?.message??e));}finally{setBusy(false);}}
 async function validate(){setValidating(true);setError('');try{setReport(await validateBloodEngine());}catch(e){setError(String((e as Error)?.message??e));}finally{setValidating(false);}}
 async function save(){if(!result)return;try{await exportFile('blood-plasma-transport-record.json',{text:JSON.stringify(result.record,null,2)});setSaved('Record exported · SHA-256 '+result.record.reproducibility.contentSha256.slice(0,12)+'…');}catch(e){setError(String((e as Error)?.message??e));}}

 const series=result?.series??[],time=series.map(s=>s.t),f=result?.frames.items[frame],playhead=f?nearestIndex(time,f.t):undefined;
 const fluxSeries=result?[{id:'in',label:'Inlet',values:series.map(s=>s.inletFluxMolPerS*1e15)},{id:'out',label:'Outlet',values:series.map(s=>s.outletFluxMolPerS*1e15)},{id:'wall',label:'Wall',values:series.map(s=>s.wallFluxMolPerS*1e15)}]:[];
 const outletSeries=result?[{id:'cup',label:'Flow-weighted (cup)',values:series.map(s=>s.outletCupMolPerM3)},{id:'mean',label:'Area mean',values:series.map(s=>s.outletMeanMolPerM3)},{id:'mid',label:'Mid-vessel mean',values:series.map(s=>s.midMeanMolPerM3)}]:[];
 const varianceSeries=result?.dispersion?[{id:'num',label:'Numerical σ²',values:series.map(s=>(s.varianceM2??NaN)*1e12)},{id:'ta',label:'σ₀² + 2K_TA t',values:series.map(s=>result.inputs.slugWidthUm**2+2*result.derived.taylorArisM2PerS*1e12*s.t)}]:[];
 const particleRows=result?.particles?.stats??[];
 const b=result?.budget,d=result?.derived,st=result?.stability,summary=result?.particles?.summary,ps=summary&&'maxStandardScore' in summary?summary:null;

 return <div className="page-content living-lab blood-lab">
  <LivingLabSwitch value="blood" onChange={onSwitch}/>
  <div className="page-heading"><div><span className="eyebrow">ANALYSE · LIVING BIOLOGY LAB · BLOOD &amp; CIRCULATION · DEMO 6</span>
   <h1>Plasma transport in a modelled vessel, <em>computed and checked.</em></h1>
   <p>A dilute tracer carried by Poiseuille flow and spreading by diffusion, solved on an axisymmetric finite-volume grid with explicit inlet, outlet and wall boundary conditions. Every pixel below comes from the solver.</p></div></div>

  <section className="quiet-panel ll-evidence">
   <div className="bl-badges"><span className="ll-badge cat-B">Physics-simulated</span>{evidence==='D'&&<span className="ll-badge cat-D">Parameterised scenario · D</span>}</div>
   <div className="bl-assume">
    <p>{evidence==='B'?'Verification case: the numbers are checked against analytical results. Not a vessel.':'Parameters resemble a plasma-filled vessel. This is a modelled vessel, not validated human circulation; no physiological, clinical or dosing claim is made.'} {preset?.note}</p>
    <ul className="bl-chips" aria-label="Model assumptions">
     <li>Plasma only · hematocrit 0</li><li>Newtonian · μ = {inputs.plasmaViscosityMPaS} mPa·s</li><li>Rigid straight wall</li><li>Steady laminar Poiseuille</li>
     <li>{inputs.wallPermeabilityUmPerS>0?`Permeable wall · P = ${inputs.wallPermeabilityUmPerS} µm/s (Robin)`:'Impermeable wall'}</li><li>Dilute passive tracer</li>
    </ul>
   </div>
  </section>

  <section className="quiet-panel">
   <div className="cosmos-segment" role="radiogroup" aria-label="Experiment">{engine?.presets.map(p=><button key={p.id} role="radio" aria-checked={p.id===presetId} className={p.id===presetId?'active':''} onClick={()=>choose(p)}>{p.label}</button>)}</div>
   <div className="ll-fields">
    <label><span>Inlet condition</span><select className="bl-select" value={inputs.inletMode} onChange={e=>set('inletMode',e.target.value as InletMode)}>
     <option value="slug">Slug in a closed tube (validation)</option><option value="pulse">Gaussian pulse at the inlet</option><option value="step">Step at the inlet</option></select></label>
    {FIELDS.filter(x=>!x.show||x.show(inputs.inletMode)).filter(x=>particles||(x.key!=='particles'&&x.key!=='seed')).map(x=><label key={x.key}><span>{x.label}{x.unit&&<em> · {x.unit}</em>}</span>
     <input type="number" step={x.step} value={inputs[x.key] as number} onChange={e=>set(x.key,e.target.valueAsNumber as never)}/></label>)}
   </div>
   <div className="ll-run">
    <p>Pe = UR/D = <strong>{fmt(live.Pe)}</strong> · K_TA = <strong>{fmt(live.K)} µm²/s</strong> · R²/D = <strong>{fmt(live.radial)} s</strong>{live.transit!==null&&<> · transit L/U = <strong>{fmt(live.transit)} s</strong></>} · Bi = PR/D = <strong>{fmt(live.Bi)}</strong> · dp/dz = <strong>{fmt(live.dpdz)} Pa/m</strong> · wall shear <strong>{fmt(live.tau)} Pa</strong></p>
    <label className="bl-toggle"><input type="checkbox" checked={particles} onChange={e=>{setParticles(e.target.checked);setResult(null);}}/>Particle view (Lagrangian, seeded)</label>
    <button className="button primary" disabled={busy||!engine} onClick={()=>void run()}>{busy?'Solving…':'Run experiment'}</button>
    {result&&<button className="button" onClick={()=>void save()}>Export research record (JSON)</button>}
   </div>
   {error&&<p className="ll-error" role="alert">{error}</p>}{saved&&<p className="ll-saved">{saved}</p>}
  </section>

  {result&&f&&b&&d&&st&&<>
   <section className="quiet-panel bl-stage">
    <VesselView result={result} frame={frame} showParticles={showParticles&&!!result.particles} probe={probe} setProbe={setProbe}/>
    <div className="bl-scrubber">
     <button className="button" aria-label={playing?'Pause':'Play'} onClick={()=>{if(!playing&&frame>=result.frames.items.length-1)setFrame(0);setPlaying(!playing);}}>{playing?<Pause size={14}/>:<Play size={14}/>}</button>
     <input type="range" min={0} max={result.frames.items.length-1} value={frame} onChange={e=>{setPlaying(false);setFrame(Number(e.target.value));}} aria-label="Time"/>
     <span>t = {fmt(f.t,4)} / {fmt(result.inputs.durationS,4)} s</span>
     {result.particles&&<label className="bl-toggle"><input type="checkbox" checked={showParticles} onChange={e=>setShowParticles(e.target.checked)}/>Particles</label>}
    </div>
   </section>

   <section className="ll-tiles">
    <div className="quiet-panel"><span>Mass budget</span><strong>{b.maxRelativeResidual.toExponential(1)}</strong><small>{status(b.pass)} |M(t) − M₀ − in + out + wall| / scale, tolerance 1e-12{b.closedMassDrift!==undefined&&<> · closed drift {b.closedMassDrift.toExponential(1)}</>}</small></div>
    <div className="quiet-panel"><span>Through the boundaries</span><strong>{fmt((b.inMol)*1e15,4)} <em>fmol in</em></strong><small>out {fmt(b.outMol*1e15,4)} · wall {fmt(b.wallMol*1e15,4)} · held {fmt(b.finalMol*1e15,4)} fmol</small></div>
    <div className="quiet-panel"><span>Stability</span><strong>{fmt(st.courant.value,3)} <em>Courant</em></strong><small>{status(st.pass)} D Δt/Δz² = {fmt(st.axialDiffusionNumber.value,3)} (≤ 0.5) · cell Pe {fmt(st.cellPeclet.value,3)} · radial (implicit) {fmt(st.radialDiffusionNumber.value,3)}</small></div>
    {result.dispersion?<div className="quiet-panel"><span>Taylor–Aris dispersion</span><strong>{(result.dispersion.relativeError*100).toFixed(3)} <em>% |ΔK|/K</em></strong><small>{status(result.dispersion.pass,result.dispersion.applicable)} K = {fmt(result.dispersion.numericalM2PerS*1e12,5)} vs D(1+Pe²/48) = {fmt(result.dispersion.taylorArisM2PerS*1e12,5)} µm²/s</small></div>
     :<div className="quiet-panel"><span>Grid · time step</span><strong>{result.inputs.radialCells}×{result.inputs.axialCells}</strong><small>Δt = {fmt(d.dtS*1e3,3)} ms · {d.steps.toLocaleString()} steps · {fmt(d.elapsedS,3)} s solve</small></div>}
   </section>

   <section className="ll-charts">
    <div className="quiet-panel"><CrossSection result={result} frame={frame} probe={probe}/></div>
    <div className="quiet-panel"><VelocityChart result={result}/></div>
    <div className="quiet-panel"><figure className="ll-chart"><figcaption>Flux through the boundaries (fmol/s)</figcaption><TimeChart time={time} series={fluxSeries} timeUnit="s" unit="fmol/s" playhead={playhead}/></figure>{result.inputs.inletMode==='slug'&&result.inputs.wallPermeabilityUmPerS===0&&<p className="ll-note">Closed tube with an impermeable wall: every boundary flux is zero by construction, which is what makes this the mass-conservation test.</p>}</div>
    <div className="quiet-panel"><figure className="ll-chart"><figcaption>{result.inputs.inletMode==='slug'?'Concentration at mid-vessel and outlet':'Breakthrough at the outlet'} (mol/m³)</figcaption><TimeChart time={time} series={outletSeries} timeUnit="s" unit="mol/m³" playhead={playhead}/></figure></div>
    {varianceSeries.length>0&&<div className="quiet-panel"><figure className="ll-chart"><figcaption>Axial variance — slope is 2K (µm²)</figcaption><TimeChart time={time} series={varianceSeries} timeUnit="s" unit="µm²" playhead={playhead}/></figure></div>}
    <div className="quiet-panel"><figure className="ll-chart"><figcaption>Cross-section mean along the vessel at t = {fmt(f.t,4)} s (mol/m³)</figcaption><TimeChart time={result.frames.zUm} series={[{id:'mean',label:'c̄(z)',values:f.mean}]} timeUnit="µm" unit="mol/m³" playhead={probe}/></figure><p className="ll-note">Horizontal axis is position z (µm); the dashed line is the probe.</p></div>
   </section>

   {st.warnings.length>0&&<section className="quiet-panel bl-warnings" role="note">{st.warnings.map(w=><p key={w} className="ll-error">⚠ {w}</p>)}</section>}

   {result.particles&&<section className="quiet-panel bl-particles">
    <header><span className="ll-badge cat-B">Particle view · stochastic</span><p>{result.particles.label} {result.particles.count.toLocaleString()} particles, seed {result.particles.seed}, Δt = {fmt(result.particles.dtS*1e3,3)} ms; wall absorption probability per hit {fmt(result.particles.absorptionProbabilityPerHit,3)}.</p></header>
    {ps&&<div className="ll-tiles bl-tiles-compact">
     <div><span>Centroid difference</span><strong>{fmt(ps.centroidDifferenceM*1e6,3)} <em>µm</em></strong><small>standard error {fmt(ps.centroidStandardErrorM*1e6,3)} µm</small></div>
     <div><span>Variance difference</span><strong>{fmt(ps.varianceRelativeDifference*100,3)} <em>%</em></strong><small>standard error {fmt(ps.varianceRelativeStandardError*100,3)} %</small></div>
     <div><span>Mass in vessel</span><strong>{fmt((ps.massRelativeDifference??0)*100,3)} <em>%</em></strong><small>standard error {fmt(ps.massRelativeStandardError*100,3)} %</small></div>
     <div><span>Agreement</span><strong>{fmt(ps.maxStandardScore,3)} <em>σ max</em></strong><small>{status(ps.consistent)} within 3 standard errors of the continuum at t = {fmt(ps.atTimeS,3)} s</small></div>
    </div>}
    <details><summary>Continuum vs particle statistics</summary><div className="ll-table"><table><thead><tr><th>t (s)</th><th>mass FV (fmol)</th><th>mass particles</th><th>centroid FV (µm)</th><th>centroid particles</th><th>σ² FV (µm²)</th><th>σ² particles</th></tr></thead>
     <tbody>{particleRows.filter((_,i)=>i%Math.max(1,Math.floor(particleRows.length/24))===0).map(r=><tr key={r.t}><td>{fmt(r.t,4)}</td><td>{fmt(r.continuumMassMol*1e15,4)}</td><td>{fmt(r.particleMassMol*1e15,4)}</td><td>{fmt((r.continuumCentroidM??NaN)*1e6,4)}</td><td>{fmt((r.particleCentroidM??NaN)*1e6,4)}</td><td>{fmt((r.continuumVarianceM2??NaN)*1e12,4)}</td><td>{fmt((r.particleVarianceM2??NaN)*1e12,4)}</td></tr>)}</tbody></table></div></details>
   </section>}

   {cross&&<section className="quiet-panel bl-cross-check">
    <h3>Cross-check against the in-app Demo D solver</h3>
    {cross.applicable?<p>{status(cross.pass)} Independent co-moving solver (TypeScript, this window): K = {fmt(cross.tsK!*1e12,5)} µm²/s vs this run {fmt(cross.pyK!*1e12,5)} µm²/s — difference {fmt(cross.kRelativeDifference!*100,3)} % (≤ 1 %); mass-normalised profile L1 difference {fmt(cross.profileL1Difference!*100,3)} % (≤ 2 %).</p>
     :<p className="ll-note">{cross.reason}</p>}
   </section>}
  </>}

  <section className="quiet-panel bl-validation">
   <header><div><h3>Validation suite</h3><p>Seven automated checks with numeric tolerances, rerun live by the Python engine ({engine?.environment?`NumPy ${engine.environment.numpy}, SciPy ${engine.environment.scipy}`:'bundled runtime'}).</p></div>
    <button className="button" disabled={validating||!engine} onClick={()=>void validate()}>{validating?'Running…':report?'Run again':'Run validation suite'}</button></header>
   {report&&<div className="ll-table bl-validation-table"><table><thead><tr><th>Check</th><th>Metric</th><th>Value</th><th>Tolerance</th><th>Result</th></tr></thead>
    <tbody>{report.checks.map(c=><tr key={c.id}><td><strong>{c.name}</strong><small>{c.detail}</small></td><td>{c.metric}</td><td>{fmt(c.value,4)}</td><td>{c.higherIsBetter?'≥ ':'≤ '}{fmt(c.tolerance,3)}</td><td>{status(c.passed)}</td></tr>)}</tbody></table>
    <p className="ll-note">{report.passed?'All checks passed':'Some checks failed'} in {fmt(report.elapsedS,3)} s.</p></div>}
  </section>

  {result&&d&&st&&engine&&<section className="quiet-panel ll-meta">
   <details><summary>Solver settings and stability</summary><dl>
    <dt>Method</dt><dd>{engine.numericalMethod}</dd>
    <dt>Equations</dt><dd>{engine.equations.map(e=><div key={e}>{e}</div>)}</dd>
    <dt>Grid</dt><dd>{result.inputs.radialCells} × {result.inputs.axialCells} · Δr = {fmt(d.drM*1e6)} µm · Δz = {fmt(d.dzM*1e6)} µm</dd>
    <dt>Time</dt><dd>{d.steps.toLocaleString()} steps · Δt = {fmt(d.dtS*1e3)} ms · {fmt(d.elapsedS,3)} s</dd>
    {Object.entries(st).filter(([k])=>k!=='pass'&&k!=='warnings').map(([k,v])=>{const s=v as {value:number;limit?:number|null;meaning:string};return <Fragment key={k}><dt>{k}</dt><dd>{fmt(s.value,4)}{s.limit?` (limit ${s.limit})`:''} — {s.meaning}</dd></Fragment>;})}
    <dt>Runtime</dt><dd>Python {result.environment.python} · NumPy {result.environment.numpy} · SciPy {result.environment.scipy} · {result.environment.machine}; deterministic continuum solve{result.particles?`, particles seeded (${result.particles.seed})`:''}</dd>
   </dl></details>
   <details><summary>Assumptions and limitations</summary><ul>{[...engine.assumptions,...engine.limits].map(t=><li key={t}>{t}</li>)}</ul></details>
   <details><summary>Data table · boundary fluxes</summary><div className="ll-table"><table><thead><tr><th>t (s)</th><th>in (fmol/s)</th><th>out (fmol/s)</th><th>wall (fmol/s)</th><th>held (fmol)</th><th>budget residual (fmol)</th></tr></thead>
    <tbody>{series.filter((_,i)=>i%Math.max(1,Math.floor(series.length/40))===0).map(s=><tr key={s.t}><td>{fmt(s.t,4)}</td><td>{fmt(s.inletFluxMolPerS*1e15,4)}</td><td>{fmt(s.outletFluxMolPerS*1e15,4)}</td><td>{fmt(s.wallFluxMolPerS*1e15,4)}</td><td>{fmt(s.massMol*1e15,6)}</td><td>{fmt(s.budgetResidualMol*1e15,2)}</td></tr>)}</tbody></table></div></details>
  </section>}
 </div>;
}
