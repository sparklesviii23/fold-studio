import type {EngineDescriptor,ResearchRecord} from './engineContract';
import {evidenceCategories} from './engineContract';

/**
 * Demo D: passive tracer in a straight rigid capillary with steady Poiseuille flow.
 * Axisymmetric (r,z) finite-volume solution of ∂c/∂t + u(r)∂c/∂z = D∇²c in a frame
 * moving with the mean velocity U, benchmarked against the Taylor–Aris dispersion
 * coefficient K = D(1 + Pe²/48), Pe = U·R/D (Aris 1956; exact long-time variance growth).
 */
export interface CapillaryInputs{
 radiusUm:number;meanVelocityMmPerS:number;diffusivityUm2PerS:number;durationS:number;
 initialWidthUm:number;amountFmol:number;detectorUm:number;radialCells:number;axialCells:number;
}
export type Limiter='van-leer'|'koren'|'monotonized-central'|'none';
export interface SolverSettings{limiter:Limiter;radialImplicitness:number;courant:number;axialDiffusionNumber:number;maxStepFractionOfRadialTime:number;samples:number;snapshots:number}
export const defaultSolverSettings:SolverSettings={limiter:'van-leer',radialImplicitness:.5,courant:.4,axialDiffusionNumber:.25,maxStepFractionOfRadialTime:.01,samples:200,snapshots:6};
export const capillaryPresets:{id:string;label:string;evidence:'B'|'D';note:string;inputs:CapillaryInputs}[]=[
 {id:'benchmark',label:'Benchmark · Pe = 20',evidence:'B',note:'Dimensionless verification case; parameters are chosen to make shear dispersion dominate, not to represent a tissue.',
  inputs:{radiusUm:5,meanVelocityMmPerS:4,diffusivityUm2PerS:1000,durationS:.5,initialWidthUm:20,amountFmol:1,detectorUm:1000,radialCells:24,axialCells:400}},
 {id:'small-solute',label:'Capillary-scale small solute',evidence:'D',note:'Radius ~3 µm and ~0.5 mm/s are typical literature magnitudes for capillaries; D ≈ 1000 µm²/s is a small solute in water. Blood is treated as a Newtonian fluid without cells.',
  inputs:{radiusUm:3,meanVelocityMmPerS:.5,diffusivityUm2PerS:1000,durationS:.2,initialWidthUm:15,amountFmol:1,detectorUm:50,radialCells:20,axialCells:300}},
 {id:'macromolecule',label:'Capillary-scale macromolecule',evidence:'D',note:'D ≈ 60 µm²/s is the order of a serum-albumin-sized protein in water. Same idealised Newtonian, cell-free flow.',
  inputs:{radiusUm:3,meanVelocityMmPerS:.5,diffusivityUm2PerS:60,durationS:1,initialWidthUm:20,amountFmol:1,detectorUm:250,radialCells:20,axialCells:400}}];

export const capillaryEngine:EngineDescriptor={
 id:'fold.transport.capillary-taylor-aris',name:'Capillary advection–diffusion (axisymmetric FV)',version:'1.0.0',evidence:'B',
 spatialScale:{min:{value:1,unit:'µm'},max:{value:10,unit:'mm'}},timeScale:{min:{value:1e-3,unit:'s'},max:{value:100,unit:'s'}},
 numericalMethod:'Axisymmetric finite volume in a frame moving at U; per-ring flux-limited Lax–Wendroff advection (van Leer) with explicit axial diffusion; Crank–Nicolson radial diffusion (Thomas); Strang splitting.',
 equations:['∂c/∂t + (u(r) − U)∂c/∂z = D[(1/r)∂/∂r(r∂c/∂r) + ∂²c/∂z²]','u(r) = 2U(1 − r²/R²)','no flux at r = R, at r = 0 by symmetry and at both domain ends'],
 inputs:[
  {key:'radiusUm',unit:'µm',description:'Capillary radius R',bounds:[.5,500]},
  {key:'meanVelocityMmPerS',unit:'mm/s',description:'Cross-section mean velocity U (0 = pure diffusion)',bounds:[0,100]},
  {key:'diffusivityUm2PerS',unit:'µm²/s',description:'Molecular diffusivity D',bounds:[.1,1e5]},
  {key:'durationS',unit:'s',description:'Simulated time',bounds:[1e-4,100]},
  {key:'initialWidthUm',unit:'µm',description:'Standard deviation σ₀ of the cross-sectionally uniform Gaussian slug',bounds:[.1,1e5]},
  {key:'amountFmol',unit:'fmol',description:'Injected amount',bounds:[1e-6,1e9]},
  {key:'detectorUm',unit:'µm',description:'Fixed lab-frame detector position (slug starts centred at 0)',bounds:[-1e6,1e6]},
  {key:'radialCells',unit:'1',description:'Radial finite volumes',bounds:[4,64]},
  {key:'axialCells',unit:'1',description:'Axial finite volumes',bounds:[50,2000]}],
 assumptions:['Rigid straight circular tube; fully developed steady laminar Poiseuille flow','Newtonian, incompressible, cell-free fluid','Dilute passive tracer: no binding, reaction, wall permeability, uptake or buoyancy','Constant isotropic molecular diffusivity','Initial slug uniform across the cross-section'],
 validatedDomain:['Variance growth rate within 1% of Taylor–Aris K for 0 ≤ Pe ≤ 25 once t ≳ 0.5 R²/D (automated tests)','Exact mass conservation and centroid speed U for the closed domain'],
 limits:['Not valid for red-cell single-file flow, plasma skimming, pulsatile or non-Newtonian blood, branching networks, wall exchange or tissue uptake','No physiological or pharmacokinetic accuracy is claimed','Domain ends are closed; the domain is sized to keep the plume away from them and the boundary mass fraction is reported'],
 benchmarks:[{name:'Taylor–Aris effective dispersion',reference:'Taylor 1953 Proc. R. Soc. A 219:186; Aris 1956 Proc. R. Soc. A 235:67',acceptance:'|K_num − K_TA|/K_TA ≤ 1% at default resolution'},{name:'Mass conservation',reference:'Finite-volume flux balance',acceptance:'relative drift ≤ 1e-10'}],
 uncertainty:'Discretisation error only, quantified by the benchmark residual and grid refinement; no parameter uncertainty is propagated.'};

const fmol=1e-15;
const limiters:Record<Limiter,(theta:number)=>number>={
 'van-leer':t=>(t+Math.abs(t))/(1+Math.abs(t)),
 koren:t=>Math.max(0,Math.min(2*t,(1+2*t)/3,2)),
 'monotonized-central':t=>Math.max(0,Math.min(2*t,(1+t)/2,2)),
 none:()=>1};
function check(inputs:CapillaryInputs){
 for(const spec of capillaryEngine.inputs){const v=(inputs as any)[spec.key];
  if(typeof v!=='number'||!Number.isFinite(v)||v<spec.bounds[0]||v>spec.bounds[1])throw Error(`${spec.description} must be a number from ${spec.bounds[0]} to ${spec.bounds[1]} ${spec.unit}.`);}
 if(!Number.isInteger(inputs.radialCells)||!Number.isInteger(inputs.axialCells))throw Error('Cell counts must be whole numbers.');
}

export function taylorArisCoefficient(radius:number,meanVelocity:number,diffusivity:number){
 const peclet=meanVelocity*radius/diffusivity;return {peclet,effectiveDispersion:diffusivity*(1+peclet*peclet/48)};
}

export function solveCapillary(inputs:CapillaryInputs,settings:SolverSettings=defaultSolverSettings){
 check(inputs);
 const R=inputs.radiusUm*1e-6,U=inputs.meanVelocityMmPerS*1e-3,D=inputs.diffusivityUm2PerS*1e-12,T=inputs.durationS;
 const sigma0=inputs.initialWidthUm*1e-6,amount=inputs.amountFmol*fmol,Nr=inputs.radialCells,Nz=inputs.axialCells;
 const {peclet,effectiveDispersion:K}=taylorArisCoefficient(R,U,D),radialTime=R*R/D;
 const half=Math.max(6*Math.sqrt(sigma0*sigma0+2*K*T),4*sigma0),dz=2*half/Nz,dr=R/Nr;
 // Ring geometry: faces at r_j = jΔr; exact ring-averaged moving-frame velocity has zero area-weighted mean.
 const area=new Float64Array(Nr),perimeter=new Float64Array(Nr+1),w=new Float64Array(Nr);
 for(let i=0;i<Nr;i++){const a=i*dr,b=(i+1)*dr;area[i]=Math.PI*(b*b-a*a);w[i]=U*(1-(a*a+b*b)/(R*R));}
 for(let j=1;j<Nr;j++)perimeter[j]=2*Math.PI*j*dr;
 const crossSection=Math.PI*R*R,wMax=Math.max(...Array.from(w,Math.abs));
 const limits=[settings.axialDiffusionNumber*dz*dz/D,settings.maxStepFractionOfRadialTime*radialTime];
 if(wMax>0)limits.push(settings.courant*dz/wMax);
 const steps=Math.max(1,Math.ceil(T/Math.min(...limits))),dt=T/steps;
 if(steps*Nr*Nz>3e8)throw Error(`This run needs ${steps.toLocaleString()} steps on ${Nr*Nz} cells; reduce the duration or resolution (limit 3×10⁸ cell-steps).`);
 const z=Float64Array.from({length:Nz},(_,k)=>-half+(k+.5)*dz);
 const c=new Float64Array(Nr*Nz);
 let total=0;for(let k=0;k<Nz;k++)total+=Math.exp(-z[k]*z[k]/(2*sigma0*sigma0))*crossSection*dz;
 for(let k=0;k<Nz;k++){const v=amount*Math.exp(-z[k]*z[k]/(2*sigma0*sigma0))/total;for(let i=0;i<Nr;i++)c[i*Nz+k]=v;}
 // θ-method radial operator for a half step (θ = ½ Crank–Nicolson, 1 backward Euler): constant tridiagonal matrix, factorised once.
 const theta=settings.radialImplicitness;if(!(theta>=.5&&theta<=1))throw Error('Radial implicitness must be from 0.5 (Crank–Nicolson) to 1 (backward Euler).');
 const tau=theta*dt/2,explicit=Float64Array.from(perimeter,p=>(1-theta)*dt/2*D*p/dr),lower=new Float64Array(Nr),upper=new Float64Array(Nr),cp=new Float64Array(Nr),denom=new Float64Array(Nr);
 for(let i=0;i<Nr;i++){lower[i]=-tau*D*perimeter[i]/dr;upper[i]=-tau*D*perimeter[i+1]/dr;}
 for(let i=0;i<Nr;i++){const diag=area[i]-lower[i]-upper[i];denom[i]=diag-(i?lower[i]*cp[i-1]:0);cp[i]=upper[i]/denom[i];}
 const rhs=new Float64Array(Nr);
 function radial(){
  for(let k=0;k<Nz;k++){
   for(let i=0;i<Nr;i++){
    const here=c[i*Nz+k],old=area[i]*here+(i?explicit[i]*(c[(i-1)*Nz+k]-here):0)+(i<Nr-1?explicit[i+1]*(c[(i+1)*Nz+k]-here):0);
    rhs[i]=(old-(i?lower[i]*rhs[i-1]:0))/denom[i];
   }
   for(let i=Nr-1;i>=0;i--){if(i<Nr-1)rhs[i]-=cp[i]*rhs[i+1];c[i*Nz+k]=rhs[i];}
  }
 }
 const phi=limiters[settings.limiter];if(!phi)throw Error('Unknown flux limiter.');
 const row=new Float64Array(Nz),flux=new Float64Array(Nz+1);
 function axial(){
  for(let i=0;i<Nr;i++){
   const v=w[i],nu=v*dt/dz,o=i*Nz;row.set(c.subarray(o,o+Nz));
   for(let k=0;k<Nz-1;k++){
    const jump=row[k+1]-row[k];let theta=0;
    if(jump!==0){if(v>=0&&k>0)theta=(row[k]-row[k-1])/jump;else if(v<0&&k<Nz-2)theta=(row[k+2]-row[k+1])/jump;}
    flux[k+1]=v*(v>=0?row[k]:row[k+1])+.5*Math.abs(v)*(1-Math.abs(nu))*phi(theta)*jump-D*jump/dz;
   }
   for(let k=0;k<Nz;k++)c[o+k]=row[k]-dt/dz*(flux[k+1]-flux[k]);
  }
 }
 const mean=new Float64Array(Nz);
 function crossSectionMean(){mean.fill(0);for(let i=0;i<Nr;i++){const a=area[i]/crossSection,o=i*Nz;for(let k=0;k<Nz;k++)mean[k]+=a*c[o+k];}return mean;}
 const edge=Math.max(1,Math.round(Nz*.02));
 function moments(t:number){
  const m=crossSectionMean();let m0=0,m1=0,m2=0,edgeMass=0,peak=0;
  for(let k=0;k<Nz;k++){m0+=m[k];m1+=m[k]*z[k];if(m[k]>peak)peak=m[k];if(k<edge||k>=Nz-edge)edgeMass+=m[k];}
  const centre=m1/m0;for(let k=0;k<Nz;k++)m2+=m[k]*(z[k]-centre)**2;
  const zDetector=inputs.detectorUm*1e-6-U*t;let detector:number|null=null;
  if(zDetector>=z[0]&&zDetector<=z[Nz-1]){const x=(zDetector-z[0])/dz,k=Math.min(Nz-2,Math.floor(x)),f=x-k;detector=m[k]*(1-f)+m[k+1]*f;}
  return {t,massMol:m0*crossSection*dz,centroidLabM:centre+U*t,varianceM2:m2/m0,peakMeanMolPerM3:peak,detectorMolPerM3:detector,boundaryMassFraction:edgeMass/m0};
 }
 const sampleEvery=Math.max(1,Math.floor(steps/settings.samples)),snapshotSteps=new Set(Array.from({length:Math.max(0,settings.snapshots-2)},(_,j)=>Math.round((j+1)*steps/(settings.snapshots-1))).filter(n=>n>0&&n<steps));
 const series=[moments(0)];
 const profile=(t:number)=>({t,zLabUm:Array.from(z,v=>(v+U*t)*1e6),meanMolPerM3:Array.from(crossSectionMean())});
 const snapshots=[profile(0)];
 const started=performance.now();
 for(let n=1;n<=steps;n++){
  radial();axial();radial();
  const t=n*dt;
  if(n%sampleEvery===0||n===steps)series.push(moments(t));
  if(snapshotSteps.has(n))snapshots.push(profile(t));
 }
 snapshots.push(profile(T));
 const elapsedMs=performance.now()-started;
 // Benchmark: least-squares slope of σ²(t) after the radial transient has decayed.
 const fitStart=Math.max(.5*radialTime,.25*T),window=series.filter(s=>s.t>=fitStart);
 let slope=NaN;
 if(window.length>=3){const n=window.length,tm=window.reduce((a,s)=>a+s.t,0)/n,vm=window.reduce((a,s)=>a+s.varianceM2,0)/n;
  slope=window.reduce((a,s)=>a+(s.t-tm)*(s.varianceM2-vm),0)/window.reduce((a,s)=>a+(s.t-tm)**2,0);}
 const numericalK=slope/2,relativeError=Math.abs(numericalK-K)/K;
 const massDrift=Math.max(...series.map(s=>Math.abs(s.massMol-amount)/amount));
 const last=series[series.length-1],centroidVelocity=(last.centroidLabM-series[0].centroidLabM)/T;
 const boundary=Math.max(...series.map(s=>s.boundaryMassFraction));
 const taylorRegime=T>=radialTime&&window.length>=3;
 const finalVariance=sigma0*sigma0+2*K*T,finalAnalytic=snapshots[snapshots.length-1].zLabUm.map(zu=>{const x=zu*1e-6-U*T;return amount/(crossSection*Math.sqrt(2*Math.PI*finalVariance))*Math.exp(-x*x/(2*finalVariance));});
 const field=Array.from({length:Nr},(_,i)=>Array.from(c.subarray(i*Nz,(i+1)*Nz)));
 return {
  inputs,settings,
  derived:{radiusM:R,meanVelocityMPerS:U,diffusivityM2PerS:D,peclet,taylorArisM2PerS:K,radialTimeS:radialTime,
   enhancement:K/D,domainHalfLengthM:half,dzM:dz,drM:dr,dtS:dt,steps,cells:Nr*Nz,elapsedMs},
  series,snapshots,finalAnalyticMeanMolPerM3:finalAnalytic,
  field:{rCentresUm:Array.from({length:Nr},(_,i)=>(i+.5)*dr*1e6),zLabUm:snapshots[snapshots.length-1].zLabUm,concentrationMolPerM3:field},
  benchmark:{
   effectiveDispersion:{numericalM2PerS:numericalK,taylorArisM2PerS:K,relativeError,tolerance:.01,pass:taylorRegime&&relativeError<=.01,
    fitWindowS:[fitStart,T],fitPoints:window.length,applicable:taylorRegime,
    note:taylorRegime?'Slope of the cross-sectional variance after the radial transient (t ≥ max(0.5 R²/D, 0.25 T)).':'Run for at least R²/D so the radial transient decays; the residual is not a valid benchmark yet.'},
   mass:{maxRelativeDrift:massDrift,tolerance:1e-10,pass:massDrift<=1e-10},
   centroidVelocity:{numericalMPerS:centroidVelocity,expectedMPerS:U,absoluteErrorMPerS:Math.abs(centroidVelocity-U)},
   domain:{maxBoundaryMassFraction:boundary,tolerance:1e-6,pass:boundary<=1e-6}}};
}
export type CapillaryResult=ReturnType<typeof solveCapillary>;

async function sha256(text:string){const bytes=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(text));return Array.from(new Uint8Array(bytes),b=>b.toString(16).padStart(2,'0')).join('');}
function thin<T>(values:T[],limit:number){if(values.length<=limit)return values;const step=values.length/limit;return Array.from({length:limit},(_,i)=>values[Math.floor(i*step)]);}

export async function capillaryRecord(result:CapillaryResult,presetEvidence:'B'|'D'='B',created=new Date().toISOString()){
 const e=result.derived,category=presetEvidence;
 const outputs={
  derived:{peclet:{value:e.peclet,unit:'1'},taylorArisDispersion:{value:e.taylorArisM2PerS,unit:'m²/s'},radialDiffusionTime:{value:e.radialTimeS,unit:'s'},enhancementK_over_D:{value:e.enhancement,unit:'1'}},
  timeSeries:{units:{t:'s',massMol:'mol',centroidLabM:'m',varianceM2:'m²',peakMeanMolPerM3:'mol/m³',detectorMolPerM3:'mol/m³ (null = detector outside solved domain)',boundaryMassFraction:'1'},rows:result.series},
  profiles:{units:{t:'s',zLabUm:'µm',meanMolPerM3:'mol/m³ (cross-sectional mean)'},snapshots:result.snapshots.map(s=>({...s,zLabUm:thin(s.zLabUm,200),meanMolPerM3:thin(s.meanMolPerM3,200)}))}};
 const record:ResearchRecord={
  schema:'fold.research-record',schemaVersion:1,
  engine:{id:capillaryEngine.id,name:capillaryEngine.name,version:capillaryEngine.version,numericalMethod:capillaryEngine.numericalMethod},
  evidence:{category,name:evidenceCategories[category].name,statement:category==='B'
   ?'Numerical solution of an idealised advection–diffusion model, verified against the Taylor–Aris analytical result. Not an experimental measurement.'
   :'Same verified solver, with parameters chosen to resemble a capillary. The idealised model has not been validated against in-vivo transport; treat the output as a hypothesis.'},
  created,
  inputs:Object.fromEntries(capillaryEngine.inputs.map(s=>[s.key,{value:(result.inputs as any)[s.key],unit:s.unit,description:s.description}])),
  solver:{...result.settings,equations:capillaryEngine.equations,dtS:e.dtS,steps:e.steps,drM:e.drM,dzM:e.dzM,domainHalfLengthM:e.domainHalfLengthM,
   frame:'Moving with the mean velocity U; reported positions are lab-frame (z = z′ + U·t).',boundaries:'Zero flux at r = R, symmetry at r = 0, closed axial ends',
   initialCondition:'Cross-sectionally uniform Gaussian slug centred at z = 0, normalised to the injected amount'},
  outputs,benchmark:result.benchmark,
  assumptions:capillaryEngine.assumptions,limitations:capillaryEngine.limits,
  reproducibility:{deterministic:true,seed:null,runtime:'TypeScript/IEEE-754 double precision; no random numbers are used.'}};
 record.reproducibility.contentSha256=await sha256(JSON.stringify({inputs:record.inputs,solver:record.solver,outputs:record.outputs}));
 return record;
}
