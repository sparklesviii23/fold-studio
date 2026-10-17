import type {AtomRecord} from './types';
export interface EngineAtom {key:string;spec:string;index:number;chain:string;labelChain:string;residue:number;label:number|null;insertion:string;residueName:string;atom:string;element:string;serial:number;altLoc:string;xyz:[number,number,number];bFactor:number;occupancy:number;radius:number;color:number[];ribbonColor:number[];shown:boolean;ribbonShown:boolean;style:number;selected:boolean;secondaryStructure:number}
export interface EngineModel {id:string;instance:string;name:string;geometry:string;appearance:string;display:boolean;atoms:EngineAtom[];bonds:{a:number;b:number;shown:boolean;radius:number}[];cif:string;chains:{id:string;spec:string;residues:number}[];coordsets:number[];activeCoordset:number}
export interface EngineMesh {id:string;name:string;revision:string;vertices:string;triangles:string;normals:string|null;color:number[];colors:string|null;vertexCount:number;triangleCount:number}
export interface EngineScene {schemaVersion:1;sessionId:string;revision:string;cameraRevision:string;camera:{name:string;position:number[];target:number[];direction:number[];matrix:number[][];fieldOfView:number;fieldWidth:number|null};models?:EngineModel[];meshes?:EngineMesh[];pseudobonds?:{id:string;name:string;a:number[];b:number[];length:number;color:number[];radius:number}[];labels?:{id:string;text:string;xyz:[number,number,number];color:number[];height:number}[];unsupported:{id:string;name:string;reason:string}[];engineGui:boolean;lighting:{ambient:number;key:number;fill:number};rendering:string}
export function rgb(rgba:number[]):number{return (rgba[0]<<16)|(rgba[1]<<8)|rgba[2];}
export function validateScene(scene:EngineScene){
 if(scene.schemaVersion!==1||scene.engineGui)throw new Error('FOLD requires the GUI-free scientific engine and a supported scene schema.');
 const keys=new Set<string>(),models=new Set<string>();
 for(const m of scene.models??[]){if(models.has(m.id))throw new Error('Duplicate scientific model identity.');models.add(m.id);
  m.atoms.forEach((a,index)=>{if(a.index!==index||keys.has(a.key)||a.xyz.length!==3||a.xyz.some(v=>!Number.isFinite(v)))throw new Error('Invalid authoritative atom identity or coordinates.');keys.add(a.key);for(const value of [...a.color,...a.ribbonColor])if(!Number.isInteger(value)||value<0||value>255)throw new Error('Invalid engine colour.');});
  for(const bond of m.bonds)if(bond.a<0||bond.b<0||bond.a>=m.atoms.length||bond.b>=m.atoms.length||bond.a===bond.b)throw new Error('Invalid authoritative bond.');
 }
}
export function chartAtom(a:EngineAtom,model:EngineModel,unit:number):AtomRecord{
 return {key:a.key,chain:a.chain,authChain:a.chain,label:a.label??0,auth:a.residue,insertion:a.insertion,name:a.residueName,one:'X',xyz:a.xyz,bFactor:a.bFactor,unit,index:a.index,atomName:a.atom,element:a.element,occupancy:a.occupancy,altLoc:a.altLoc,serial:a.serial,operatorName:'Engine #'+model.id,modelIndex:unit,nativeModelId:model.id,nativeSpec:a.spec};
}
export function nativeSelectionSpec(atoms:AtomRecord[],keys:string[]){const wanted=new Set(keys);return atoms.filter(a=>wanted.has(a.key)).map(a=>a.nativeSpec).filter(Boolean).join('|');}
export function nativeCamera(scene:EngineScene){
 const c=scene.camera,up=[c.matrix[0][1],c.matrix[1][1],c.matrix[2][1]];
 return {position:c.position,target:c.target,up,fov:c.fieldOfView*Math.PI/180,mode:c.name.includes('ortho')?'orthographic':'perspective'};
}
