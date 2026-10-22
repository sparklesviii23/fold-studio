import {fullSceneClipRadius} from '../lib/viewerClipping';
import {molecularLabels,annotateMolecularImage,type AnchoredLabel} from '../lib/cinemaLabels';
import {presentationPostprocessing} from '../lib/presentationRendering';
import {forwardRef,useEffect,useImperativeHandle,useRef,useState} from 'react';
import {PluginContext} from 'molstar/lib/mol-plugin/context';
import {DefaultPluginSpec} from 'molstar/lib/mol-plugin/spec';
import {Structure,StructureElement,StructureProperties as P,Unit} from 'molstar/lib/mol-model/structure';
import {MolScriptBuilder as MS} from 'molstar/lib/mol-script/language/builder';
import {OrderedSet} from 'molstar/lib/mol-data/int';
import {IndexPairBonds} from 'molstar/lib/mol-model-formats/structure/property/bonds/index-pair';
import {nativeBondPairs} from '../lib/engineBonds';
import {Color} from 'molstar/lib/mol-util/color';
import {ParamDefinition as PD} from 'molstar/lib/mol-util/param-definition';
import {StateTransforms} from 'molstar/lib/mol-plugin-state/transforms';
import {Shape,ShapeGroup} from 'molstar/lib/mol-model/shape';
import {ShapeRepresentation} from 'molstar/lib/mol-repr/shape/representation';
import {Mesh} from 'molstar/lib/mol-geo/geometry/mesh/mesh';
import {MeshBuilder} from 'molstar/lib/mol-geo/geometry/mesh/mesh-builder';
import {addFixedCountDashedCylinder} from 'molstar/lib/mol-geo/geometry/mesh/builder/cylinder';
import {Text} from 'molstar/lib/mol-geo/geometry/text/text';
import {TextBuilder} from 'molstar/lib/mol-geo/geometry/text/text-builder';
import {Vec3,Mat4} from 'molstar/lib/mol-math/linear-algebra';
import {aminoNames,residueCorrespondence} from '../lib/sequence';
import type {Item,Residue,AtomRecord} from '../lib/types';
import {rpc,exportFile,registerScientificViewer,type VisualReceipt} from '../lib/api';
import {chartAtom,nativeCamera,nativeSelectionSpec,rgb,validateScene,type EngineScene,type EngineModel,type EngineAtom,type EngineMesh} from '../lib/engineScene';
import {LoaderCircle,Orbit,RefreshCw} from 'lucide-react';
export interface PresentationStyle {theme:"paper"|"night";mode:"mixed"|"cartoon"|"surface"|"transparent"|"sticks";binderChains:string[];palette:Record<string,string>;outline:boolean;disclosure?:string;ghost?:boolean;labels?:boolean;targetLabel?:string;showContacts?:boolean;contactAtoms?:{chain:string;residue:number;insertion:string;atom:string;xyz:number[]}[];contactPairs?:number}
export interface ViewerHandle {setPresentationOffsets(offsets:Record<string,number[]>):Promise<void>;captureFrame(width:number,height:number):Promise<string>;setCamera(camera:any):Promise<void>;setPresentation(style:PresentationStyle):Promise<void>;reset():void;selectRange(start:number,end:number):void;selectChain(chain:string):void;exportImage():Promise<void>;exportCamera():Promise<void>;atoms():AtomRecord[];selectAtoms(keys:string[]):void;focusAtoms(keys:string[]):void;setLens(keys:string[],radius:number|null,focus?:boolean):Promise<void>;snapshot():any;restoreCamera(camera:any):void}
interface Props {snapshotScene?:EngineScene;onCameraSnapshot?:(camera:any)=>void;item:Item|null;projectId:string;content:string;sequence:string;representation:string;coloring:string;environment:string;drift:boolean;visible:boolean;hiddenChains:string[];onResidues:(r:Residue[])=>void;onPick:(r:Residue)=>void;onInteract:()=>void;onError:(e:string)=>void;onAtoms?:(a:AtomRecord[])=>void;onAtomPick?:(a:AtomRecord)=>void;onLoaded?:(id:string)=>void}
interface Loaded {native:EngineModel;root:any;state:any;structure:Structure;components:any[];presentationTransforms?:{chain:string;ref:string}[];geometry:string;appearance:string}
function decode(value:string){return Uint8Array.from(atob(value),c=>c.charCodeAt(0));}
export default forwardRef<ViewerHandle,Props>(function MolecularViewer(props,ref){
 const presentation=useRef<PresentationStyle|null>(null),presentationOffsets=useRef<Record<string,number[]>>({}),labelSignature=useRef('');
 const [anchoredLabels,setAnchoredLabels]=useState<{width:number;height:number;labels:AnchoredLabel[]}>({width:1,height:1,labels:[]});
 function updateAnchoredLabels(){const c=plugin.current?.canvas3d,element=host.current,style=presentation.current;if(!c||!element||!style)return;const width=element.clientWidth,height=element.clientHeight;if(!width||!height)return;const labels=style.labels===false?[]:molecularLabels(c.camera.getSnapshot(),atoms.current,style.binderChains,style.palette,presentationOffsets.current,width,height,style.targetLabel,style.showContacts?style.contactAtoms?.filter(a=>!style.binderChains.includes(a.chain)):undefined);const value={width,height,labels},signature=JSON.stringify(value);if(signature!==labelSignature.current){labelSignature.current=signature;setAnchoredLabels(value);}}
 const statusHost=useRef<HTMLDetailsElement>(null);
 const host=useRef<HTMLDivElement>(null),canvas=useRef<HTMLCanvasElement>(null),plugin=useRef<PluginContext|null>(null),latest=useRef(props);
 const loaded=useRef(new Map<string,Loaded>()),nativeModels=useRef(new Map<any,EngineModel>()),meshes=useRef(new Map<string,{revision:string;repr:any}>()),extras=useRef<any[]>([]);
 const cameraSource=useRef(false),lastPublishedCamera=useRef('');
 const atoms=useRef<AtomRecord[]>([]),scene=useRef<EngineScene|null>(null),cameraRevision=useRef(''),cameraDirty=useRef(false),painting=useRef(false),operations=useRef(Promise.resolve());
 const [ready,setReady]=useState(false),[connected,setConnected]=useState(false),[loading,setLoading]=useState('Connecting scientific engine'),[error,setError]=useState(''),[hover,setHover]=useState<AtomRecord|null>(null),[receipt,setReceipt]=useState<VisualReceipt|null>(null);
 latest.current=props;
 function enqueue<T>(operation:()=>Promise<T>):Promise<T>{const next=operations.current.catch(()=>{}).then(operation);operations.current=next.then(()=>{});return next;}
 function nativeAt(location:StructureElement.Location):EngineAtom|undefined{return nativeModels.current.get(location.unit.model)?.atoms[P.atom.id(location)-1];}
 function recordAt(location:StructureElement.Location){const a=nativeAt(location);return a&&atoms.current.find(row=>row.key===a.key);}
 function allLoci(keys:string[]){const wanted=new Set(keys);const result:StructureElement.Loci[]=[];for(const l of loaded.current.values()){
  const elements:StructureElement.Loci['elements'][number][]=[];for(const unit of l.structure.units){if(!Unit.isAtomic(unit))continue;const indices:number[]=[];const location=StructureElement.Location.create(l.structure,unit);for(let i=0;i<unit.elements.length;i++){location.element=unit.elements[i];const a=nativeAt(location);if(a&&wanted.has(a.key))indices.push(i);}if(indices.length)elements.push({unit,indices:OrderedSet.ofSortedArray(Int32Array.from(indices)) as any});}if(elements.length)result.push(StructureElement.Loci(l.structure,elements));}return result;}
 function highlight(keys:string[]){const p=plugin.current;if(!p)return;p.managers.interactivity.lociSelects.deselectAll();for(const loci of allLoci(keys))p.managers.interactivity.lociSelects.select({loci});}
 function protectClipping(){const c=plugin.current?.canvas3d;if(!c)return;const b=c.boundingSphere; if(!b.radius)return;const radius=fullSceneClipRadius(b.center,b.radius,c.camera.state.target);if(Math.abs(c.camera.state.radius-radius)>0.01||Math.abs(c.camera.state.radiusMax-radius)>0.01)c.camera.setState({radius,radiusMax:radius,clipFar:false},0);}
 useEffect(()=>{const element=statusHost.current;if(!element)return;const observer=new ResizeObserver(()=>document.documentElement.style.setProperty('--fold-scene-status-height',element.getBoundingClientRect().height+'px'));observer.observe(element);return()=>observer.disconnect();},[receipt!==null,props.visible]);
 async function flushCamera(){if(latest.current.snapshotScene||!cameraDirty.current||!plugin.current?.canvas3d||!connected)return;const c=plugin.current.canvas3d.camera.getSnapshot();await rpc('chimerax_camera',{position:Array.from(c.position),target:Array.from(c.target),up:Array.from(c.up),fieldOfView:c.fov*180/Math.PI});cameraDirty.current=false;}
 async function command(value:string){const p=latest.current;const r=await rpc('chimerax_execute',{projectId:p.projectId,structureId:p.item?.id,command:value,confirmed:true});if(r.state!=='completed')throw new Error(r.output?.error?.message??r.error??'Scientific command failed.');return r;}
 function fire(value:string){command(value).catch(e=>latest.current.onError(String(e)));}
 function pick(loci:any):AtomRecord|null {if(!StructureElement.Loci.is(loci)||!loci.elements.length)return null;const e=loci.elements[0];const location=StructureElement.Location.create(loci.structure,e.unit,e.unit.elements[OrderedSet.getAt(e.indices,0)]);return recordAt(location)??null;}
 function colourTheme(ctx:any,params:any){const colour=(location:any)=>{if(StructureElement.Location.is(location)){const a=nativeAt(location);if(a){const hex=presentation.current?.palette[a.chain];return Color(hex?parseInt(hex.replace('#',''),16):rgb(params.target==='cartoon'?a.ribbonColor:a.color));}}if(location.kind==='bond-location'){const a=location.aUnit;const l=StructureElement.Location.create(location.aStructure,a,a.elements[location.aIndex]);const row=nativeAt(l);if(row){const hex=presentation.current?.palette[row.chain];return Color(hex?parseInt(hex.slice(1),16):rgb(row.color));}}return Color(0x8bbdf4);};return {factory:colourTheme,granularity:'group',color:colour,props:params,contextHash:params.revision,description:'Actual scientific-engine colours, with no command emulation.'};}
 function sizeTheme(ctx:any,params:any){return {factory:sizeTheme,granularity:'group',props:params,contextHash:params.revision,size:(location:any)=>{if(StructureElement.Location.is(location))return nativeAt(location)?.radius??1;if(location.kind==='bond-location'){const a=location.aUnit;return nativeAt(StructureElement.Location.create(location.aStructure,a,a.elements[location.aIndex]))?.radius??1;}return 1;}};}
 async function style(l:Loaded){
  const p=plugin.current!;const update=p.state.data.build();for(const component of l.components)update.delete(component.ref);await update.commit();l.components=[];l.presentationTransforms=[];
  if(presentation.current){
   const style=presentation.current,all=l.native.atoms.map(a=>a.index+1),target=all.filter(i=>!style.binderChains.includes(l.native.atoms[i-1].chain));
   const type=style.mode==='surface'||style.mode==='transparent'?'molecular-surface':style.mode==='sticks'?'ball-and-stick':'cartoon',alpha=style.mode==='transparent'?.5:1;
   const parts:{ids:number[];type:string;alpha:number;chain?:string;contact?:boolean}[]=style.mode==='mixed'?[{ids:target,type:'molecular-surface',alpha:.6},{ids:target,type:'cartoon',alpha:1}]:[{ids:target,type,alpha}];
   if(style.ghost)parts.push({ids:l.native.atoms.filter(a=>style.binderChains.includes(a.chain)).map(a=>a.index+1),type:'cartoon',alpha:.12});
   for(const chain of style.binderChains)parts.push({chain,ids:l.native.atoms.filter(a=>a.chain===chain).map(a=>a.index+1),type:style.mode==='mixed'?'cartoon':type,alpha});
   if(style.showContacts&&style.contactAtoms?.length){const ids=new Set(style.contactAtoms.map(a=>JSON.stringify([a.chain,a.residue,a.insertion,a.atom])));for(const chain of l.native.chains.map(c=>c.id))parts.push({chain:style.binderChains.includes(chain)?chain:undefined,contact:true,ids:l.native.atoms.filter(a=>a.chain===chain&&ids.has(JSON.stringify([a.chain,a.residue,a.insertion,a.atom]))).map(a=>a.index+1),type:'ball-and-stick',alpha:1});}
   for(const [index,part] of parts.entries()){
    if(!part.ids.length)continue;
    const expression=MS.struct.generator.atomGroups({'atom-test':MS.core.set.has([MS.set(...part.ids),MS.struct.atomProperty.macromolecular.id()])});
    const component=await p.builders.structure.tryCreateComponentFromExpression(l.state,expression,'cinema-'+index,{label:'Presentation · '+part.type});
    if(!component)continue;l.components.push(component);
    let representationSource:any=component;
    if(part.chain){const transformed=await p.state.data.build().to(component).apply(StateTransforms.Model.TransformStructureConformation,{transform:{name:'matrix',params:{data:Mat4.identity(),transpose:false}}}).commit();representationSource=transformed;l.presentationTransforms!.push({chain:part.chain,ref:transformed.ref});}
    await p.builders.structure.representation.addRepresentation(representationSource,{type:part.type as any,color:part.contact?'uniform':'fold-engine' as any,colorParams:part.contact?{value:Color(0xd8ad42)}:{target:'cartoon',revision:JSON.stringify(style)},typeParams:{alpha:part.alpha,doubleSided:true,quality:'high',sizeFactor:part.type==='ball-and-stick'?.25:.8,material:{metalness:0,roughness:1,bumpiness:0}}});
   }
   return;
  }
  if(!l.native.display)return;
  const groups=new Map<string,number[]>();for(const a of l.native.atoms){if(a.ribbonShown){const key='cartoon';if(!groups.has(key))groups.set(key,[]);groups.get(key)!.push(a.index+1);}if(a.shown){const key='atoms:'+a.style;if(!groups.has(key))groups.set(key,[]);groups.get(key)!.push(a.index+1);}}
  for(const [kind,ids] of groups){
   const expression=MS.struct.generator.atomGroups({'atom-test':MS.core.set.has([MS.set(...ids),MS.struct.atomProperty.macromolecular.id()])});
   const component=await p.builders.structure.tryCreateComponentFromExpression(l.state,expression,kind,{label:'#'+l.native.id+' · '+kind});if(!component)continue;l.components.push(component);
   const cartoon=kind==='cartoon',styleNumber=Number(kind.split(':')[1]),type=cartoon?'cartoon':styleNumber===0?'spacefill':'ball-and-stick';
   const repr=await p.builders.structure.representation.addRepresentation(component,{type,...(cartoon?{}:{size:'fold-engine-radius' as any,sizeParams:{revision:l.native.appearance}}),color:'fold-engine' as any,colorParams:{target:cartoon?'cartoon':'atoms',revision:l.native.appearance},typeParams:{doubleSided:true,flipSided:false,sizeFactor:cartoon?1:styleNumber===0?1:styleNumber===2?0.18:0.32,aspectRatio:styleNumber===2?1:0.67,material:{metalness:0.05,roughness:0.45,bumpiness:0}}});
   const alphaGroups=new Map<number,string[]>();for(const id of ids){const a=l.native.atoms[id-1],alpha=(cartoon?a.ribbonColor:a.color)[3];if(alpha<255){if(!alphaGroups.has(alpha))alphaGroups.set(alpha,[]);alphaGroups.get(alpha)!.push(a.key);}}
   const layers=[];for(const [alpha,keys] of alphaGroups){const loci=allLoci(keys).find(v=>v.structure===l.structure);if(loci)layers.push({bundle:StructureElement.Bundle.fromLoci(loci),value:1-alpha/255});}
   if(layers.length)await p.state.data.build().to(repr).apply(StateTransforms.Representation.TransparencyStructureRepresentation3DFromBundle,{layers}).commit();
  }
 }
 async function renderMesh(m:EngineMesh){
  const p=plugin.current!,old=meshes.current.get(m.id);if(old?.revision===m.revision)return;
  if(old){p.canvas3d?.remove(old.repr);old.repr.destroy();}
  const v=decode(m.vertices),t=decode(m.triangles),n=m.normals?decode(m.normals):null,colours=m.colors?decode(m.colors):null;
  const mesh=Mesh.create(new Float32Array(v.buffer),new Uint32Array(t.buffer),n?new Float32Array(n.buffer):new Float32Array(m.vertexCount*3),Float32Array.from({length:m.vertexCount},(_,i)=>i),m.vertexCount,m.triangleCount);
  if(!n)Mesh.computeNormals(mesh);
  const shape=Shape.create(m.name,m,mesh,id=>Color(colours?rgb(Array.from(colours.subarray(id*4,id*4+4))):rgb(m.color)),()=>1,()=>m.name+' · native scientific mesh');
  const repr=ShapeRepresentation(()=>shape,Mesh.Utils);await repr.createOrUpdate({alpha:colours?1:m.color[3]/255,doubleSided:true,quality:'high'},m).run();if(colours){const alpha=new Map<number,number[]>();for(let i=0;i<m.vertexCount;i++){const value=colours[i*4+3];if(value<255){if(!alpha.has(value))alpha.set(value,[]);alpha.get(value)!.push(i);}}const layers=[...alpha].map(([value,ids])=>({loci:ShapeGroup.Loci(shape,[{ids:OrderedSet.ofSortedArray(Int32Array.from(ids)) as any,instance:0}]),value:1-value/255}));if(layers.length)repr.setState({transparency:{kind:'group-loci',layers}});}
  p.canvas3d?.add(repr);meshes.current.set(m.id,{revision:m.revision,repr});
 }
 async function renderMeasurements(data:NonNullable<EngineScene['pseudobonds']>,labels:NonNullable<EngineScene['labels']>){
  const p=plugin.current!;for(const r of extras.current){p.canvas3d?.remove(r);r.destroy();}extras.current=[];if(!data.length&&!labels.length)return;
  const builder=MeshBuilder.createState();const text=TextBuilder.create({fontFamily:'sans-serif',fontQuality:2,background:true,backgroundColor:Color(0x071326)});
  data.forEach((pb,i)=>{builder.currentGroup=i;addFixedCountDashedCylinder(builder,Vec3.fromArray(Vec3(),pb.a,0),Vec3.fromArray(Vec3(),pb.b,0),1,12,true,{radiusTop:pb.radius,radiusBottom:pb.radius,radialSegments:8});if(pb.name.toLowerCase().includes('distance'))text.add(pb.length.toFixed(3)+' Å',(pb.a[0]+pb.b[0])/2,(pb.a[1]+pb.b[1])/2,(pb.a[2]+pb.b[2])/2,0,0.8,i);});
  labels.forEach((label,i)=>text.add(label.text,...label.xyz,0,label.height,data.length+i));
  const mesh=MeshBuilder.getMesh(builder),shape=Shape.create('Scientific measurements',data,mesh,i=>Color(rgb(data[i].color)),()=>1,i=>data[i].name+' · '+data[i].length.toFixed(4)+' Å');
  const repr=ShapeRepresentation(()=>shape,Mesh.Utils);await repr.createOrUpdate({},data).run();p.canvas3d?.add(repr);extras.current.push(repr);
  const textShape=Shape.create('Distance labels',data,text.getText(),i=>Color(i<data.length?0xcce6ff:rgb(labels[i-data.length].color)),()=>1,i=>i<data.length?data[i].name:labels[i-data.length].text);const labelRepr=ShapeRepresentation(()=>textShape,Text.Utils);await labelRepr.createOrUpdate({sizeFactor:1},data).run();p.canvas3d?.add(labelRepr);extras.current.push(labelRepr);
 }
 async function apply(data:EngineScene):Promise<VisualReceipt>{
  validateScene(data);const p=plugin.current!;painting.current=true;
  try{
   const first=loaded.current.size===0;const oldSession=scene.current?.sessionId;
   if(oldSession&&oldSession!==data.sessionId){await p.clear();loaded.current.clear();nativeModels.current.clear();for(const value of meshes.current.values()){p.canvas3d?.remove(value.repr);value.repr.destroy();}meshes.current.clear();}
   if(data.models){
    const wanted=new Set(data.models.map(m=>m.id));for(const [id,l] of loaded.current)if(!wanted.has(id)){await p.state.data.build().delete(l.root.ref).commit();nativeModels.current.delete(l.structure.models[0]);loaded.current.delete(id);}
    for(const m of data.models){
     let l=loaded.current.get(m.id);
     if(!l||l.geometry!==m.geometry||l.native.instance!==m.instance){
      if(l){await p.state.data.build().delete(l.root.ref).commit();nativeModels.current.delete(l.structure.models[0]);loaded.current.delete(m.id);}
      const root=await p.builders.data.rawData({data:m.cif,label:m.name+' · #'+m.id});const trajectory=await p.builders.structure.parseTrajectory(root,'mmcif');const model=await p.builders.structure.createModel(trajectory);const value=model.obj!.data;
      IndexPairBonds.Provider.set(value,nativeBondPairs(m));
      nativeModels.current.set(value,m);const state=await p.builders.structure.createStructure(model);const structure=state.obj!.data;
      let count=0;for(const unit of structure.units){if(!Unit.isAtomic(unit))continue;const location=StructureElement.Location.create(structure,unit);for(let ai=0;ai<unit.elements.length;ai++){const element=unit.elements[ai];location.element=element;const a=nativeAt(location);if(!a||a.atom!==P.atom.label_atom_id(location)||a.residue!==P.residue.auth_seq_id(location)||a.chain!==P.chain.auth_asym_id(location))throw new Error('The presentation parser changed a native atom identity.');const error=Math.hypot(P.atom.x(location)-a.xyz[0],P.atom.y(location)-a.xyz[1],P.atom.z(location)-a.xyz[2]);if(error>0.001)throw new Error('Presentation coordinates differ from the scientific engine by more than 0.001 Å.');count++;}}
      if(count!==m.atoms.length)throw new Error('The presentation atom count does not match the scientific model.');
      l={native:m,root,state,structure,components:[],geometry:m.geometry,appearance:''};loaded.current.set(m.id,l);
     }
     l.native=m;nativeModels.current.set(l.structure.models[0],m);if(l.appearance!==m.appearance){await style(l);l.appearance=m.appearance;}
    }
    const rows:AtomRecord[]=[];data.models.forEach((m,unit)=>rows.push(...m.atoms.map(a=>chartAtom(a,m,unit))));
    rows.forEach(a=>a.one=aminoNames[a.name]??'X');const rr=rows.filter(a=>a.atomName==='CA'&&aminoNames[a.name]);
    for(const key of new Set(rr.map(a=>a.unit+':'+a.chain))){const group=rr.filter(a=>a.unit+':'+a.chain===key);if(latest.current.sequence){for(const [position,index] of residueCorrespondence(latest.current.sequence,group.map(a=>a.one).join('')))group[index-1].sourcePosition=position;}}
    const residueMap=new Map(rr.map(r=>[[r.unit,r.authChain,r.auth,r.insertion].join(':'),r]));for(const a of rows)a.sourcePosition=residueMap.get([a.unit,a.authChain,a.auth,a.insertion].join(':'))?.sourcePosition;
    atoms.current=rows;latest.current.onAtoms?.(rows);latest.current.onResidues(rr);highlight(data.models.flatMap(m=>m.atoms.filter(a=>a.selected).map(a=>a.key)));
   }
   if(data.meshes){const displayMeshes=presentation.current?[]:data.meshes;const ids=new Set(displayMeshes.map(m=>m.id));for(const [id,value] of meshes.current)if(!ids.has(id)){p.canvas3d?.remove(value.repr);value.repr.destroy();meshes.current.delete(id);}for(const mesh of displayMeshes)await renderMesh(mesh);}
   if(data.pseudobonds||data.labels)await renderMeasurements(data.pseudobonds??[],data.labels??[]);
   if(first&&loaded.current.size)p.canvas3d?.requestCameraReset({durationMs:0});
   else if(cameraRevision.current&&cameraRevision.current!==data.cameraRevision&&!cameraDirty.current){const camera=nativeCamera(data);p.canvas3d?.camera.setState(camera as any,200);}
   cameraRevision.current=data.cameraRevision;
   scene.current={...scene.current,...data} as EngineScene;
   if(!presentation.current)p.canvas3d?.setProps({renderer:{ambientIntensity:Math.min(1,Math.max(0.1,data.lighting.ambient))}});
   protectClipping();p.canvas3d?.requestDraw();await new Promise<void>(resolve=>requestAnimationFrame(()=>requestAnimationFrame(()=>resolve())));
   const unsupported=data.unsupported.map(u=>u.name+': '+u.reason);const result:VisualReceipt={state:unsupported.length?'partial':'synchronized',revision:data.revision,models:loaded.current.size,atoms:atoms.current.length,meshes:meshes.current.size,unsupported,details:unsupported.length?'Some engine objects have no complete visual adapter.':'Coordinates, colours, visibility, styles and native meshes applied.'};
   setReceipt(result);if(!latest.current.snapshotScene)window.dispatchEvent(new CustomEvent('fold-scene-status',{detail:{...result,modelsData:data.models??scene.current.models,sessionId:data.sessionId}}));latest.current.onLoaded?.(latest.current.item?.id??'');return result;
  }finally{painting.current=false;}
 }
 async function refresh(){return enqueue(async()=>{try{const data=await rpc<EngineScene>('chimerax_scene',{known:scene.current?.revision});const result=await apply(data);setError('');return result;}catch(error){setReceipt({state:'failed',details:String(error),revision:scene.current?.revision});setError(String(error));throw error;}});}
 useEffect(()=>{let alive=true;const p=new PluginContext(DefaultPluginSpec());plugin.current=p;
  (async()=>{await p.init();const params={target:PD.Text('atoms'),revision:PD.Text('')};p.representation.structure.themes.colorThemeRegistry.add({name:'fold-engine',label:'Scientific engine',category:'Miscellaneous',factory:colourTheme,getParams:()=>params,defaultValues:PD.getDefaultValues(params),isApplicable:()=>true} as any);p.representation.structure.themes.sizeThemeRegistry.add({name:'fold-engine-radius',label:'Scientific atom radii',category:'',factory:sizeTheme,getParams:()=>({revision:PD.Text('')}),defaultValues:{revision:''},isApplicable:()=>true} as any);if(!alive)return;if(!await p.initViewerAsync(canvas.current!,host.current!))throw new Error('The FOLD molecular viewport could not initialize WebGL.');
   p.canvas3d?.setProps({transparentBackground:true,renderer:{backgroundColor:Color(0x071326),ambientIntensity:0.45},camera:{helper:{axes:{name:'off',params:{}}}}});
   p.canvas3d?.camera.changed.subscribe(protectClipping);
   p.behaviors.interaction.hover.subscribe(e=>setHover(pick(e.current.loci)));p.behaviors.interaction.click.subscribe(e=>{const a=pick(e.current.loci);if(a){if(latest.current.snapshotScene){highlight([a.key]);latest.current.onPick(a);return;}latest.current.onPick(a);latest.current.onAtomPick?.(a);rpc('chimerax_selection',{keys:[a.key]}).catch(error=>latest.current.onError(String(error)));}});
   setReady(true);
  })().catch(e=>{if(alive){setError(String(e));latest.current.onError(String(e));}});
  const resize=new ResizeObserver(()=>p.canvas3d?.handleResize());if(host.current)resize.observe(host.current);return()=>{alive=false;resize.disconnect();for(const m of meshes.current.values())m.repr.destroy();for(const r of extras.current)r.destroy();p.dispose();plugin.current=null;};
 },[]);
 useEffect(()=>{if(!ready)return;const subscription=plugin.current?.canvas3d?.didDraw.subscribe(()=>{updateAnchoredLabels();if(!cameraSource.current||!latest.current.onCameraSnapshot)return;const snapshot=plugin.current?.canvas3d?.camera.getSnapshot();if(!snapshot)return;const signature=JSON.stringify([snapshot.position,snapshot.target,snapshot.up]);if(signature!==lastPublishedCamera.current){lastPublishedCamera.current=signature;latest.current.onCameraSnapshot(snapshot);}});return()=>subscription?.unsubscribe();},[ready]);
 useEffect(()=>{if(!ready)return;if(props.snapshotScene){setConnected(true);setLoading('');return;}let cancelled=false;setLoading('Preparing scientific engine');(async()=>{await rpc('chimerax_start');for(let i=0;i<50;i++){const status=await rpc('chimerax_status');if(cancelled)return;if(status.connected){if(status.gui)throw new Error('A GUI ChimeraX process cannot be used as the scientific helper.');setConnected(true);setLoading('');return;}await new Promise(r=>setTimeout(r,500));}throw new Error('Scientific engine startup timed out.');})().catch(e=>{setLoading('');setError(String(e));latest.current.onError(String(e));});return()=>{cancelled=true;};},[ready]);
 useEffect(()=>{if(!ready||!connected||props.snapshotScene)return;return registerScientificViewer(refresh,flushCamera);},[ready,connected]);
 useEffect(()=>{if(props.snapshotScene||!connected||!props.item||!props.projectId)return;let cancelled=false;setLoading('Opening authoritative molecular model');rpc('chimerax_open',{projectId:props.projectId,structureId:props.item.id,replace:true}).then(r=>{if(r.state!=='completed')throw new Error(r.output?.error?.message??'The structure could not be opened.');if(!cancelled){setLoading('');setError('');}}).catch(e=>{if(!cancelled){setLoading('');setError(String(e));latest.current.onError(String(e));}});return()=>{cancelled=true;};},[connected,props.item?.id,props.projectId]);
 useEffect(()=>{if(props.snapshotScene||!connected||!props.visible)return;const interval=setInterval(()=>{if(!document.hidden)refresh().catch(e=>setError(String(e)));},2500);return()=>clearInterval(interval);},[connected,props.visible]);
 useEffect(()=>{if(ready&&props.snapshotScene)enqueue(()=>apply(props.snapshotScene!)).catch(e=>latest.current.onError(String(e)));},[ready,props.snapshotScene]);
 useEffect(()=>{if(ready&&props.visible)plugin.current?.canvas3d?.handleResize();},[props.visible,ready]);
 useEffect(()=>{plugin.current?.canvas3d?.setProps({trackball:{animate:props.drift?{name:'spin',params:{speed:0.025}}:{name:'off',params:{}}}});},[props.drift,ready]);
 async function setPresentation(style:PresentationStyle){
  if(!plugin.current?.canvas3d)throw new Error('The molecular viewport is still loading.');
  if(Object.values(style.palette).some(hex=>!/^#[0-9a-fA-F]{6}$/.test(hex)))throw new Error('Use six-digit chain colours.');
  presentation.current=style;const c=plugin.current.canvas3d;
  c.setProps({transparentBackground:false,renderer:{backgroundColor:Color(style.theme==='paper'?0xf8f7f3:0x071326),ambientIntensity:.75},postprocessing:presentationPostprocessing(style.outline,style.theme==='paper')});
  await enqueue(async()=>{for(const l of loaded.current.values())await stylePresentation(l);for(const value of meshes.current.values()){c.remove(value.repr);value.repr.destroy();}meshes.current.clear();c.requestDraw();});
  await setPresentationOffsets(presentationOffsets.current);updateAnchoredLabels();
 }
 async function stylePresentation(l:Loaded){await style(l);}
 async function setPresentationOffsets(offsets:Record<string,number[]>){
  if(!plugin.current?.canvas3d||!presentation.current)throw new Error('Open a presentation scene first.');
  for(const [chain,v] of Object.entries(offsets))if(!presentation.current.binderChains.includes(chain)||v.length!==3||v.some(n=>!Number.isFinite(n)||Math.abs(n)>500))throw new Error('Presentation translations require an assigned peptide chain and finite offsets up to 500 Å.');
  presentationOffsets.current=Object.fromEntries(Object.entries(offsets).map(([chain,v])=>[chain,[...v]]));
  await enqueue(async()=>{const p=plugin.current!,update=p.state.data.build();for(const l of loaded.current.values())for(const node of l.presentationTransforms??[]){const matrix=Mat4.identity();Mat4.setTranslation(matrix,Vec3.create(...(offsets[node.chain]??[0,0,0]) as [number,number,number]));update.to(node.ref).update({transform:{name:'matrix',params:{data:matrix,transpose:false}}});}await update.commit();p.canvas3d?.requestDraw();});updateAnchoredLabels();
 }
 async function setCamera(camera:any){const c=plugin.current?.canvas3d;if(!c)throw new Error('The viewport is not ready.');cameraSource.current=false;c.camera.setState(camera,0);protectClipping();c.requestDraw();await new Promise<void>(resolve=>requestAnimationFrame(()=>requestAnimationFrame(()=>resolve())));}
 async function captureFrame(width:number,height:number){
  const helper=plugin.current?.helpers.viewportScreenshot;if(!helper)throw new Error('Image export is not ready.');
  helper.behaviors.values.next({...helper.values,resolution:{name:'custom',params:{width,height}},format:{name:'png',params:{}},transparent:false});
  helper.behaviors.cropParams.next({auto:false,relativePadding:0});helper.behaviors.relativeCrop.next({x:0,y:0,width:1,height:1});
  const uri=await helper.getImageDataUri(),style=presentation.current,camera=plugin.current?.canvas3d?.camera.getSnapshot();
  return style&&style.labels!==false&&camera?annotateMolecularImage(uri,width,height,molecularLabels(camera,atoms.current,style.binderChains,style.palette,presentationOffsets.current,width,height,style.targetLabel,style.showContacts?style.contactAtoms?.filter(a=>!style.binderChains.includes(a.chain)):undefined)):uri;
 }
 useImperativeHandle(ref,()=>({captureFrame,setCamera,setPresentation,setPresentationOffsets,atoms:()=>atoms.current,snapshot:()=>plugin.current?.canvas3d?.camera.getSnapshot(),restoreCamera(c){cameraSource.current=false;if(c&&!c.engine){plugin.current?.canvas3d?.camera.setState(c,200);cameraDirty.current=true;}},reset(){plugin.current?.canvas3d?.requestCameraReset({durationMs:200});cameraDirty.current=true;},selectAtoms(keys){rpc('chimerax_selection',{keys}).catch(e=>latest.current.onError(String(e)));},selectChain(chain){const keys=atoms.current.filter(a=>a.chain===chain).map(a=>a.key);rpc('chimerax_selection',{keys}).catch(e=>latest.current.onError(String(e)));},selectRange(a,b){const keys=atoms.current.filter(r=>r.sourcePosition!==undefined&&r.sourcePosition>=a&&r.sourcePosition<=b).map(a=>a.key);rpc('chimerax_selection',{keys}).catch(e=>latest.current.onError(String(e)));},focusAtoms(keys){const loci=allLoci(keys)[0];if(loci)plugin.current?.managers.camera.focusLoci(loci,{durationMs:250});cameraDirty.current=true;},async setLens(keys,radius,focus=true){const spec=nativeSelectionSpec(atoms.current,keys);if(radius===null){await command('hide atoms');return;}if(!spec)return;await command('select zone '+spec+' '+radius+' residues true\nshow sel atoms\nstyle sel ball');if(focus){const loci=allLoci(keys)[0];if(loci)plugin.current?.managers.camera.focusLoci(loci,{durationMs:250});cameraDirty.current=true;}},async exportImage(){const p=plugin.current,helper=p?.helpers.viewportScreenshot;if(!helper)throw new Error('Image export is not ready.');helper.behaviors.values.next({...helper.values,resolution:{name:'custom',params:{width:2400,height:1800}}});const uri=await helper.getImageDataUri();await exportFile('fold-molecular-laboratory.png',{base64:uri.split(',')[1]});await exportFile('fold-figure-provenance.json',{text:JSON.stringify({engine:'ChimeraX 1.12',renderer:'Mol*',sceneRevision:scene.current?.revision,camera:p?.canvas3d?.camera.getSnapshot(),source:latest.current.item,unsupported:scene.current?.unsupported,exported:new Date().toISOString()},null,2)});},async exportCamera(){await exportFile('fold-camera.json',{text:JSON.stringify({camera:plugin.current?.canvas3d?.camera.getSnapshot(),engineCamera:scene.current?.camera},null,2)});}}));
 return <div ref={host} className="molecular-canvas engine-viewport" onPointerDown={()=>{props.onInteract();cameraSource.current=true;latest.current.onCameraSnapshot?.(plugin.current?.canvas3d?.camera.getSnapshot());cameraDirty.current=true;}} onPointerMove={e=>{if(e.buttons&&latest.current.onCameraSnapshot)requestAnimationFrame(()=>latest.current.onCameraSnapshot?.(plugin.current?.canvas3d?.camera.getSnapshot()));}} onPointerUp={()=>{cameraDirty.current=true;requestAnimationFrame(()=>latest.current.onCameraSnapshot?.(plugin.current?.canvas3d?.camera.getSnapshot()));}} onWheel={()=>{props.onInteract();cameraSource.current=true;latest.current.onCameraSnapshot?.(plugin.current?.canvas3d?.camera.getSnapshot());cameraDirty.current=true;requestAnimationFrame(()=>latest.current.onCameraSnapshot?.(plugin.current?.canvas3d?.camera.getSnapshot()));}}><canvas ref={canvas}/>{presentation.current&&<svg className="cinema-anchored-labels" viewBox={`0 0 ${anchoredLabels.width} ${anchoredLabels.height}`} aria-hidden="true">{anchoredLabels.labels.map((label,i)=>{const scale=Math.max(.55,anchoredLabels.height/720),h=30*scale;return <g key={i}><line x1={label.anchor[0]} y1={label.anchor[1]} x2={label.box[0]+label.width/2} y2={label.box[1]+h/2} stroke={label.color} strokeWidth={1.3*scale}/><rect x={label.box[0]} y={label.box[1]} width={label.width} height={h} rx={5*scale} fill={label.color}/><text x={label.box[0]+10*scale} y={label.box[1]+h/2} dominantBaseline="middle" fill="white" fontSize={15*scale} fontWeight={600}>{label.text}</text></g>;})}</svg>}{loading&&<div className="viewer-loading"><LoaderCircle className="spin" size={20}/>{loading}…</div>}{error&&<div className="viewer-loading error"><span>{error}</span><button className="text-button" onClick={()=>refresh().then(()=>setError('')).catch(e=>setError(String(e)))}><RefreshCw size={15}/>Refresh scene</button></div>}{!props.item&&!loading&&<div className="viewer-empty"><Orbit size={50}/><h3>Molecular Laboratory</h3><p>Import a structure to begin.</p></div>}{hover&&<div className="residue-tooltip">#{hover.nativeModelId} · {hover.name} · {hover.authChain} {hover.auth}{hover.insertion} · {hover.atomName}</div>}{props.visible&&!props.snapshotScene&&receipt&&<details ref={statusHost} className={'scene-integrity '+receipt.state}><summary><span className="status-dot"/>{receipt.state==='synchronized'?'Scientific scene synchronized':receipt.state==='failed'?'Scene synchronization failed':'Partial visual coverage'} · {receipt.models} models</summary><p>{receipt.atoms?.toLocaleString()} native atoms · {receipt.meshes} native meshes</p><p>Revision <code>{receipt.revision?.slice(0,12)}</code></p><p>{receipt.details}</p>{receipt.unsupported?.map(u=><p key={u}>{u}</p>)}</details>}</div>;
});
