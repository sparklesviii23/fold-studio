import {ParamDefinition as PD} from 'molstar/lib/mol-util/param-definition';
import {SsaoParams} from 'molstar/lib/mol-canvas3d/passes/ssao';
import {OutlineParams} from 'molstar/lib/mol-canvas3d/passes/outline';
import {ShadowParams} from 'molstar/lib/mol-canvas3d/passes/shadow';
import {BloomParams} from 'molstar/lib/mol-canvas3d/passes/bloom';
import {DofParams} from 'molstar/lib/mol-canvas3d/passes/dof';
import {IlluminationParams} from 'molstar/lib/mol-canvas3d/passes/illumination';
import {Color} from 'molstar/lib/mol-util/color';
import type {EngineAtom, EngineModel} from './engineScene';

/**
 * Render looks are visual only: lighting, materials, ribbon geometry,
 * background, post-processing and, optionally, an artistic palette. They never
 * change coordinates or visibility. "Scientific colours" restores the engine's
 * own colouring under any look.
 */
export type LookId = 'nebula'|'maestro'|'studio'|'illustrative'|'cinematic'|'secondary'|'hologram'|'porcelain'|'toon'|'neon'|'cryo-em'|'negative-stain';
export type PaletteMode = 'chain'|'rainbow'|'secondary'|'goodsell'|'mono';
export type ColourMode = 'look'|'scientific';
export interface MaterialLook {material:{metalness:number;roughness:number;bumpiness:number};emissive?:number;celShaded?:boolean;ignoreLight?:boolean;xrayShaded?:boolean|'inverted'}
export interface RibbonLook {sizeFactor:number;aspectRatio:number;tubularHelices?:boolean;roundCap?:boolean;helixProfile?:'elliptical'|'rounded'|'square'}
export interface RenderLook {id:LookId;name:string;family:'Studio'|'Art'|'Microscopy';blurb:string;swatch:string;canvas:()=>any;material:MaterialLook;ribbon:RibbonLook;palette:PaletteMode;colours:string[];filter?:'cryo-em'|'negative-stain'}

// Mol* replaces mapped parameter groups; it does not deep-merge their defaults.
const on = <T extends Record<string, any>>(params: T, change: Record<string, any> = {}) => ({name: 'on' as const, params: {...PD.getDefaultValues(params as any), ...change}});
const off = {name: 'off' as const, params: {}};
const ssao = (change: Record<string, any> = {}) => on(SsaoParams, {samples: 32, radius: 5, bias: 0.8, blurKernelSize: 15, resolutionScale: 1, ...change});
const multiScale = (change: Record<string, any> = {}) => ssao({samples: 32, multiScale: {name: 'on', params: {levels: [{radius: 2, bias: 1}, {radius: 5, bias: 1}, {radius: 8, bias: 1}, {radius: 11, bias: 1}], nearThreshold: 10, farThreshold: 1500}}, ...change});
const outline = (color: number, scale = 1, threshold = 0.33) => on(OutlineParams, {scale, threshold, color: Color(color), includeTransparent: true});
const radial = (center: number, edge: number, ratio = 0.6) => ({variant: {name: 'radialGradient', params: {centerColor: Color(center), edgeColor: Color(edge), ratio, coverage: 'viewport'}}});
const vertical = (top: number, bottom: number, ratio = 0.5) => ({variant: {name: 'horizontalGradient', params: {topColor: Color(top), bottomColor: Color(bottom), ratio, coverage: 'viewport'}}});
const plain = {variant: {name: 'off', params: {}}};
const fog = (intensity: number) => ({name: 'on' as const, params: {intensity}});
const noFog = {name: 'off' as const, params: {}};
const illumination = (enabled: boolean) => enabled ? {...PD.getDefaultValues(IlluminationParams), enabled: true, maxIterations: 6, bounces: 3, shadowEnable: true, shadowSoftness: 0.15} : {enabled: false};
const light = (intensity: number, inclination = 150, azimuth = 320) => [{inclination, azimuth, color: Color(0xffffff), intensity}];
const ribbon = (change: Partial<RibbonLook> = {}): RibbonLook => ({sizeFactor: 0.24, aspectRatio: 5, helixProfile: 'elliptical', ...change});

export const looks: RenderLook[] = [
  {id:'nebula', name:'Nebula Glass', family:'Studio', blurb:'Glossy ribbons in moonlit pastels, softly shaded, floating in deep space.',
    swatch:'radial-gradient(circle at 35% 30%, #f4f8ff, #9fdcff 30%, #6f5bd6 65%, #0a0f2a)',
    // Thin loops must stay readable on a dark ground: generous ambient light, a little self-emission,
    // gentle occlusion, a mid-navy (not black) outline and only light depth fog.
    canvas:()=>({transparentBackground:false,cameraFog:fog(10),renderer:{backgroundColor:Color(0x04060f),ambientIntensity:0.66,exposure:1.12,light:light(0.9)},illumination:illumination(false),
      postprocessing:{occlusion:ssao({samples:24,radius:4,bias:1}),outline:outline(0x2a3870,1,0.5),shadow:off,dof:off,bloom:on(BloomParams,{strength:0.45,radius:0.4,mode:'emissive'}),background:radial(0x121a3c,0x02030a,0.75)}}),
    material:{material:{metalness:0,roughness:0.24,bumpiness:0},emissive:0.12}, ribbon:ribbon(), palette:'chain', colours:['#9fdcff','#c3b2ff','#f6b4dc','#7fe3d0','#ffd59a','#a7b8ff']},
  {id:'maestro', name:'Maestro Ribbons', family:'Studio', blurb:'Schrödinger-style glossy ribbons, rainbow from N- to C-terminus, with depth cueing.',
    swatch:'linear-gradient(135deg, #3b5bff, #22c4e8 25%, #3fd17a 45%, #f5d33b 65%, #ff6a3d 85%)',
    canvas:()=>({transparentBackground:false,cameraFog:fog(45),renderer:{backgroundColor:Color(0x000000),ambientIntensity:0.32,exposure:1.1,light:light(1.15,140,330)},illumination:illumination(false),
      postprocessing:{occlusion:ssao({samples:24,radius:4}),outline:off,shadow:off,dof:off,bloom:off,background:vertical(0x0b1630,0x000000,0.65)}}),
    material:{material:{metalness:0,roughness:0.16,bumpiness:0}}, ribbon:ribbon({sizeFactor:0.26}), palette:'rainbow', colours:[]},
  {id:'studio', name:'Studio Gradient', family:'Studio', blurb:'Publication-grade soft studio light on a cool gradient, with layered ambient occlusion.',
    swatch:'radial-gradient(circle at 40% 35%, #ffffff, #c9d6ea 45%, #7e8fb0 80%)',
    canvas:()=>({transparentBackground:false,cameraFog:noFog,renderer:{backgroundColor:Color(0xdfe6f1),ambientIntensity:0.62,light:light(0.85)},illumination:illumination(false),
      postprocessing:{occlusion:multiScale({samples:48}),outline:outline(0x3b4560,1,0.4),shadow:on(ShadowParams,{steps:16,maxDistance:12,tolerance:1}),dof:off,bloom:off,background:radial(0xf6f8fc,0xa9b6cc,0.85)}}),
    material:{material:{metalness:0,roughness:0.5,bumpiness:0}}, ribbon:ribbon(), palette:'chain', colours:['#6f9cf0','#f08c8c','#7cc9a6','#f2c46b','#b59af0','#6fc6d8']},
  {id:'secondary', name:'Secondary Structure', family:'Studio', blurb:'Helices, strands and loops in classic textbook colours on clean white.',
    swatch:'conic-gradient(#e2546e 0 35%, #ffc44d 0 65%, #c9d1df 0)',
    canvas:()=>({transparentBackground:false,cameraFog:noFog,renderer:{backgroundColor:Color(0xffffff),ambientIntensity:0.7,light:light(0.75)},illumination:illumination(false),
      postprocessing:{occlusion:ssao({samples:32,radius:5}),outline:outline(0x2a2f3c,1,0.33),shadow:off,dof:off,bloom:off,background:plain}}),
    material:{material:{metalness:0,roughness:0.42,bumpiness:0}}, ribbon:ribbon({sizeFactor:0.26}), palette:'secondary', colours:['#e2546e','#ffc44d','#c9d1df']},
  {id:'illustrative', name:'Illustrative', family:'Art', blurb:'Flat Goodsell-style colour, crisp ink outlines and deep crevice shading.',
    swatch:'radial-gradient(circle at 40% 40%, #ffe3c2, #f2a37b 40%, #6b8fd1 70%, #f3ead9)',
    canvas:()=>({transparentBackground:false,cameraFog:noFog,renderer:{backgroundColor:Color(0xf3ead9),ambientIntensity:1},illumination:illumination(false),
      postprocessing:{occlusion:multiScale({bias:1}),outline:outline(0x1b1420,2,0.12),shadow:off,dof:off,bloom:off,background:plain}}),
    material:{material:{metalness:0,roughness:1,bumpiness:0},ignoreLight:true}, ribbon:ribbon({sizeFactor:0.32,tubularHelices:true,roundCap:true}), palette:'goodsell', colours:['#8fb4e8','#f2a37b','#9fd39a','#e8a0c8','#f6d27a','#b9a6e8']},
  {id:'cinematic', name:'Cinematic', family:'Art', blurb:'Path-traced global illumination, soft shadows and shallow depth of field.',
    swatch:'radial-gradient(circle at 35% 30%, #fff3e2, #c9a27a 35%, #2b3352 70%, #02040a)',
    canvas:()=>({transparentBackground:false,cameraFog:fog(20),renderer:{backgroundColor:Color(0x05070f),ambientIntensity:0.35,exposure:1.15,light:light(1.1)},illumination:illumination(true),
      postprocessing:{occlusion:ssao({samples:32,radius:5}),outline:off,shadow:on(ShadowParams,{steps:16,maxDistance:16,tolerance:1}),dof:on(DofParams,{blurSize:9,blurSpread:1,center:'camera-target',mode:'sphere',PPM:30}),bloom:on(BloomParams,{strength:0.35,radius:0.4,mode:'luminosity',threshold:0.8}),background:radial(0x1c2444,0x02040a,0.75)}}),
    material:{material:{metalness:0.05,roughness:0.28,bumpiness:0.1}}, ribbon:ribbon(), palette:'chain', colours:['#f2c9a0','#9cc3e8','#e8a0a0','#b7d9b0','#d6b7f0']},
  {id:'hologram', name:'Hologram', family:'Art', blurb:'X-ray shaded edges that glow, as if the molecule were made of light.',
    swatch:'radial-gradient(circle at 50% 50%, transparent 30%, #5eead4 45%, #9fdcff 55%, #05081a 75%)',
    canvas:()=>({transparentBackground:false,cameraFog:noFog,renderer:{backgroundColor:Color(0x02040a),ambientIntensity:0.8,xrayEdgeFalloff:1.6},illumination:illumination(false),
      postprocessing:{occlusion:off,outline:off,shadow:off,dof:off,bloom:on(BloomParams,{strength:1.2,radius:0.6,mode:'emissive'}),background:radial(0x0a1830,0x01020a,0.7)}}),
    material:{material:{metalness:0,roughness:0.5,bumpiness:0},xrayShaded:true,emissive:0.5}, ribbon:ribbon(), palette:'chain', colours:['#5eead4','#9fdcff','#c3b2ff','#7fb0ff']},
  {id:'porcelain', name:'Porcelain', family:'Art', blurb:'Matte white ceramic under a soft studio light, with contact shadows.',
    swatch:'radial-gradient(circle at 38% 32%, #ffffff, #e6eaf1 40%, #aeb8c9 75%, #8a95a8)',
    canvas:()=>({transparentBackground:false,cameraFog:noFog,renderer:{backgroundColor:Color(0xdfe5ee),ambientIntensity:0.7,light:light(0.9)},illumination:illumination(false),
      postprocessing:{occlusion:multiScale({samples:48,bias:1.2}),outline:off,shadow:on(ShadowParams,{steps:24,maxDistance:20,tolerance:1}),dof:off,bloom:off,background:radial(0xf7f9fc,0xb4bfd0,0.7)}}),
    material:{material:{metalness:0,roughness:0.85,bumpiness:0.15}}, ribbon:ribbon({sizeFactor:0.3}), palette:'mono', colours:['#eef1f6']},
  {id:'toon', name:'Cel Cartoon', family:'Art', blurb:'Banded cel shading and bold contours, like a hand-inked storyboard.',
    swatch:'conic-gradient(from 200deg, #ffd27a, #ff8fa3, #9fb6ff, #7ee0c4, #ffd27a)',
    canvas:()=>({transparentBackground:false,cameraFog:noFog,renderer:{backgroundColor:Color(0x0b1226),ambientIntensity:0.5,celSteps:4,light:light(0.9)},illumination:illumination(false),
      postprocessing:{occlusion:off,outline:outline(0x05060c,3,0.08),shadow:off,dof:off,bloom:off,background:radial(0x1a2a55,0x060a18,0.7)}}),
    material:{material:{metalness:0,roughness:0.6,bumpiness:0},celShaded:true}, ribbon:ribbon({sizeFactor:0.34,roundCap:true}), palette:'chain', colours:['#ffd27a','#ff8fa3','#9fb6ff','#7ee0c4','#f0abfc']},
  {id:'neon', name:'Neon Night', family:'Art', blurb:'Self-lit colour that blooms against the dark, for talks and trailers.',
    swatch:'radial-gradient(circle at 45% 45%, #fff, #f0abfc 25%, #7c3aed 50%, #020208 75%)',
    canvas:()=>({transparentBackground:false,cameraFog:fog(30),renderer:{backgroundColor:Color(0x010104),ambientIntensity:0.3,exposure:1.2},illumination:illumination(false),
      postprocessing:{occlusion:ssao({samples:16,radius:4}),outline:off,shadow:off,dof:off,bloom:on(BloomParams,{strength:1.4,radius:0.7,mode:'emissive'}),background:radial(0x0c0a24,0x010104,0.6)}}),
    material:{material:{metalness:0,roughness:0.4,bumpiness:0},emissive:0.45}, ribbon:ribbon(), palette:'chain', colours:['#f0abfc','#7dd3fc','#a78bfa','#5eead4','#fda4af']},
  {id:'cryo-em', name:'Cryo-EM', family:'Microscopy', blurb:'Inspired by a cryo-electron micrograph: dense protein reads dark in grey, grainy ice. Illustrative, not image data.',
    swatch:'radial-gradient(circle at 50% 50%, #3a3a3a 25%, #8d8d8d 55%, #a5a5a5)',
    canvas:()=>({transparentBackground:false,cameraFog:noFog,renderer:{backgroundColor:Color(0x9a9a9a),ambientIntensity:0.9,light:light(0.35)},illumination:illumination(false),
      postprocessing:{occlusion:multiScale({samples:32,bias:1.4}),outline:off,shadow:off,dof:off,bloom:off,background:plain}}),
    material:{material:{metalness:0,roughness:1,bumpiness:0.6}}, ribbon:ribbon({sizeFactor:0.34,tubularHelices:true}), palette:'mono', colours:['#3c3c3c'], filter:'cryo-em'},
  {id:'negative-stain', name:'Negative Stain', family:'Microscopy', blurb:'Inspired by negative-stain EM: pale particles haloed in dark heavy-metal stain. Illustrative, not image data.',
    swatch:'radial-gradient(circle at 50% 50%, #e6e6e6 22%, #6b6b6b 40%, #2a2a2a 70%)',
    canvas:()=>({transparentBackground:false,cameraFog:noFog,renderer:{backgroundColor:Color(0x2b2b2b),ambientIntensity:0.95,light:light(0.4)},illumination:illumination(false),
      postprocessing:{occlusion:multiScale({samples:32,bias:1.2}),outline:outline(0x101010,2,0.2),shadow:off,dof:off,bloom:on(BloomParams,{strength:0.6,radius:0.8,mode:'luminosity',threshold:0.6}),background:plain}}),
    material:{material:{metalness:0,roughness:1,bumpiness:0.5}}, ribbon:ribbon({sizeFactor:0.36,tubularHelices:true}), palette:'mono', colours:['#e8e8e8'], filter:'negative-stain'},
];

const key = 'fold-render-look', colourKey = 'fold-render-colour';
const read = (k: string) => { try { return localStorage.getItem(k); } catch { return null; } };
export function currentLook(): RenderLook { const id = read(key); return looks.find(l => l.id === id) ?? looks[0]; }
export function colourMode(): ColourMode { return read(colourKey) === 'scientific' ? 'scientific' : 'look'; }
function announce() { window.dispatchEvent(new CustomEvent('fold-render-look', {detail: currentLook().id})); }
export function setLook(id: LookId) { try { localStorage.setItem(key, id); } catch {} announce(); }
export function setColourMode(mode: ColourMode) { try { localStorage.setItem(colourKey, mode); } catch {} announce(); }
/** Changes whenever anything that affects colour changes; feeds the theme context hash. */
export function lookRevision() { return currentLook().id + ':' + colourMode(); }

/** Representation type parameters carrying the look's material and, for ribbons, its geometry. */
export function lookTypeParams(cartoon: boolean, look: RenderLook = currentLook()) {
  const m = look.material;
  const shading = {material: m.material, emissive: m.emissive ?? 0, celShaded: m.celShaded ?? false, ignoreLight: m.ignoreLight ?? false, xrayShaded: m.xrayShaded ?? false};
  return cartoon ? {...shading, ...look.ribbon, tubularHelices: look.ribbon.tubularHelices ?? false, roundCap: look.ribbon.roundCap ?? false} : shading;
}

const hex = (h: string) => parseInt(h.slice(1), 16);
const isPolymer = (a: EngineAtom) => !!a.polymerType && a.polymerType !== 'Unclassified';
const chainOrder = new WeakMap<EngineModel, Map<string, number>>();
const chainRange = new WeakMap<EngineModel, Map<string, [number, number]>>();
function chainIndex(model: EngineModel, chain: string) {
  let map = chainOrder.get(model);
  if (!map) { map = new Map(); for (const a of model.atoms) if (!map.has(a.chain)) map.set(a.chain, map.size); chainOrder.set(model, map); }
  return map.get(chain) ?? 0;
}
function residueFraction(model: EngineModel, atom: EngineAtom) {
  let map = chainRange.get(model);
  if (!map) {
    map = new Map();
    for (const a of model.atoms) { if (!isPolymer(a)) continue; const r = map.get(a.chain); map.set(a.chain, r ? [Math.min(r[0], a.residue), Math.max(r[1], a.residue)] : [a.residue, a.residue]); }
    chainRange.set(model, map);
  }
  const [lo, hi] = map.get(atom.chain) ?? [atom.residue, atom.residue + 1];
  return hi > lo ? (atom.residue - lo) / (hi - lo) : 0;
}
// Maestro-like spectrum, blue (N-terminus) to red (C-terminus).
function spectrum(t: number) {
  const stops = [[0.23, 0.36, 1.0], [0.13, 0.77, 0.91], [0.25, 0.82, 0.48], [0.96, 0.83, 0.23], [1.0, 0.42, 0.24]];
  const x = Math.min(0.9999, Math.max(0, t)) * (stops.length - 1), i = Math.floor(x), f = x - i;
  const c = stops[i].map((v, k) => v + (stops[i + 1][k] - v) * f);
  return Color.fromNormalizedRgb(c[0], c[1], c[2]);
}
const lighten = (c: number, k: number) => { const r = (c >> 16) & 255, g = (c >> 8) & 255, b = c & 255; return Color((Math.round(r + (255 - r) * k) << 16) | (Math.round(g + (255 - g) * k) << 8) | Math.round(b + (255 - b) * k)); };

/** The look's colour for one atom, or undefined to keep the engine's colour. */
export function lookColour(atom: EngineAtom, model: EngineModel | undefined, look: RenderLook = currentLook()): Color | undefined {
  if (colourMode() === 'scientific' || !model) return undefined;
  const ligand = !isPolymer(atom);
  if (atom.residueName === 'HOH') return undefined;
  switch (look.palette) {
    case 'mono': return Color(hex(look.colours[0]));
    case 'rainbow': return ligand ? Color(0xe9edf5) : spectrum(residueFraction(model, atom));
    case 'secondary': return ligand ? Color(0x5eead4) : Color(hex(look.colours[atom.secondaryStructure === 1 ? 0 : atom.secondaryStructure === 2 ? 1 : 2]));
    case 'goodsell': {
      if (ligand) return Color(0xf6d27a);
      const base = hex(look.colours[chainIndex(model, atom.chain) % look.colours.length]);
      return atom.atom === 'CA' || atom.atom === 'N' || atom.atom === 'C' || atom.atom === 'O' ? Color(base) : lighten(base, 0.22);
    }
    default: return ligand ? Color(0xffd27a) : Color(hex(look.colours[chainIndex(model, atom.chain) % look.colours.length]));
  }
}
