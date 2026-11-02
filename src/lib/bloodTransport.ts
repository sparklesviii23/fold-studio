import {rpc} from './api';
import {solveCapillary,type CapillaryResult} from './taylorAris';

/**
 * Blood & Circulation Laboratory, Demo 6: client for the Python plasma-transport engine
 * (scientific/blood_transport.py) and the cross-check against the in-app Demo D solver (taylorAris.ts).
 */
export type InletMode='step'|'pulse'|'slug';
export interface BloodInputs{
 radiusUm:number;lengthUm:number;meanVelocityMmPerS:number;diffusivityUm2PerS:number;wallPermeabilityUmPerS:number;durationS:number;
 inletMode:InletMode;inletAmplitude:number;pulseCentreS:number;pulseWidthS:number;slugCentreUm:number;slugWidthUm:number;
 plasmaViscosityMPaS:number;radialCells:number;axialCells:number;particles:number;seed:number;
}
export interface BloodPreset{id:string;label:string;evidence:'B'|'D';note:string;inputs:BloodInputs}
export interface BloodDescriptor{
 id:string;name:string;version:string;evidence:'B';numericalMethod:string;equations:string[];assumptions:string[];limits:string[];
 benchmarks:{name:string;reference:string;acceptance:string}[];inputs:{key:string;unit:string;description:string;bounds:[number,number]}[];
 presets:BloodPreset[];validatedDomain:string[];uncertainty:string;environment:Record<string,string>;
}
export interface SeriesRow{
 t:number;massMol:number;centroidM:number|null;varianceM2:number|null;inletFluxMolPerS:number;outletFluxMolPerS:number;wallFluxMolPerS:number;
 cumulativeInMol:number;cumulativeOutMol:number;cumulativeWallMol:number;budgetResidualMol:number;outletMeanMolPerM3:number;outletCupMolPerM3:number;midMeanMolPerM3:number;
}
export interface StabilityNumber{value:number;limit?:number|null;requested?:number;meaning:string}
export interface ParticleTrackFrame{t:number;zUm:number[];rUm:number[];state:number[]}
export interface BloodResult{
 inputs:BloodInputs;settings:Record<string,unknown>;environment:Record<string,string>;
 derived:{radiusM:number;lengthM:number;meanVelocityMPerS:number;diffusivityM2PerS:number;permeabilityMPerS:number;drM:number;dzM:number;dtS:number;steps:number;cells:number;elapsedS:number;radialTimeS:number;transitTimeS:number|null;taylorArisM2PerS:number;peclet:number};
 stability:Record<'courant'|'axialDiffusionNumber'|'radialDiffusionNumber'|'cellPeclet'|'peclet'|'axialPeclet'|'wallBiot',StabilityNumber>&{pass:boolean;warnings:string[]};
 flow:{rUm:number[];ringVelocityMmPerS:number[];pointVelocityMmPerS:number[];fvPointVelocityMmPerS:number[];pressureGradientPaPerM:number;wallShearStressPa:number;fvRelativeError:number;fvPressureGradientRelativeError:number;flowRateRelativeError:number};
 series:SeriesRow[];
 frames:{rUm:number[];zUm:number[];peakMolPerM3:number;levels:number;note:string;items:{t:number;field:number[][];mean:number[]}[]};
 final:{zUm:number[];meanMolPerM3:number[];minMolPerM3:number};
 budget:{initialMol:number;finalMol:number;inMol:number;outMol:number;wallMol:number;maxRelativeResidual:number;tolerance:number;pass:boolean;closedMassDrift?:number};
 dispersion?:{numericalM2PerS:number;taylorArisM2PerS:number;relativeError:number;tolerance:number;applicable:boolean;pass:boolean;fitWindowS:[number,number];fitPoints:number;centroidVelocityMPerS:number};
 particles?:{count:number;seed:number;dtS:number;steps:number;absorptionProbabilityPerHit:number;molPerParticle:number;method:string;label:string;
  stats:{t:number;continuumMassMol:number;particleMassMol:number;continuumCentroidM:number|null;particleCentroidM:number|null;continuumVarianceM2:number|null;particleVarianceM2:number|null;continuumWallMol:number;particleWallMol:number}[];
  summary:{atTimeS:number;particlesInVessel:number;centroidDifferenceM:number;centroidStandardErrorM:number;varianceRelativeDifference:number;varianceRelativeStandardError:number;massRelativeDifference:number|null;massRelativeStandardError:number;maxStandardScore:number;consistent:boolean}|Record<string,never>;
  tracks:ParticleTrackFrame[]};
 record:Record<string,unknown>&{reproducibility:{contentSha256:string}};
}
export interface ValidationCheck{id:string;name:string;metric:string;value:number;tolerance:number;passed:boolean;detail:string;higherIsBetter?:boolean}
export interface ValidationReport{checks:ValidationCheck[];passed:boolean;elapsedS:number;environment:Record<string,string>}

export const describeBloodEngine=()=>rpc<BloodDescriptor>('blood_transport_describe',{});
export const runBloodTransport=(inputs:BloodInputs,evidence:'B'|'D',particles:boolean)=>rpc<BloodResult>('blood_transport_run',{inputs,evidence,particles:particles?inputs.particles:null});
export const validateBloodEngine=()=>rpc<ValidationReport>('blood_transport_validate',{});

/** Linear interpolation that returns 0 outside the sampled range (both profiles vanish there). */
function sampleAt(xs:number[],ys:number[],x:number){if(x<=xs[0]||x>=xs[xs.length-1])return 0;let lo=0,hi=xs.length-1;while(hi-lo>1){const m=(lo+hi)>>1;if(xs[m]<=x)lo=m;else hi=m;}const f=(x-xs[lo])/(xs[hi]-xs[lo]);return ys[lo]*(1-f)+ys[hi]*f;}

export interface CrossCheck{applicable:boolean;reason?:string;tsK?:number;pyK?:number;kRelativeDifference?:number;profileL1Difference?:number;pass?:boolean;ts?:CapillaryResult}

/**
 * Re-solve a closed-tube slug run with the independent co-moving Demo D solver and compare the dispersion
 * coefficient and the mass-normalised cross-sectional profile at the final time. Acceptance: K within 1 %, profile L1 ≤ 2 %.
 */
export function crossCheckWithDemoD(inputs:BloodInputs,pythonK:number,final:{zUm:number[];meanMolPerM3:number[]},axialCells=400):CrossCheck{
 if(inputs.inletMode!=='slug')return {applicable:false,reason:'The Demo D solver only models a slug in a closed tube; switch the inlet to “slug” for the cross-check.'};
 if(inputs.wallPermeabilityUmPerS>0)return {applicable:false,reason:'The Demo D solver has an impermeable wall only.'};
 if(inputs.meanVelocityMmPerS<=0)return {applicable:false,reason:'Cross-check needs flow (U > 0).'};
 const ts=solveCapillary({radiusUm:inputs.radiusUm,meanVelocityMmPerS:inputs.meanVelocityMmPerS,diffusivityUm2PerS:inputs.diffusivityUm2PerS,durationS:inputs.durationS,
  initialWidthUm:inputs.slugWidthUm,amountFmol:1,detectorUm:0,radialCells:Math.min(64,inputs.radialCells),axialCells});
 const last=ts.snapshots[ts.snapshots.length-1],z=final.zUm,py=final.meanMolPerM3;
 const tsOn=z.map(x=>sampleAt(last.zLabUm,last.meanMolPerM3,x-inputs.slugCentreUm));
 const area=(v:number[])=>v.reduce((a,b)=>a+b,0);
 const a=area(py),b=area(tsOn);
 const l1=z.reduce((s,_,k)=>s+Math.abs(py[k]/a-tsOn[k]/b),0);
 const tsK=ts.benchmark.effectiveDispersion.numericalM2PerS,kd=Math.abs(tsK-pythonK)/pythonK;
 return {applicable:true,tsK,pyK:pythonK,kRelativeDifference:kd,profileL1Difference:l1,pass:kd<=.01&&l1<=.02,ts};
}

/** Decode a display frame (16-bit levels of the run's peak) into mol/m³. */
export const frameValue=(level:number,peak:number,levels:number)=>level/levels*peak;
