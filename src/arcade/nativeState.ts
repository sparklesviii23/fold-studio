import {isTauri} from '@tauri-apps/api/core';
import {availableMonitors,currentMonitor,getCurrentWindow,PhysicalPosition,LogicalSize,type Monitor} from '@tauri-apps/api/window';
export interface ArcadeBounds {schemaVersion:2; width:number; height:number; position?:{x:number;y:number}; monitor?:string|null; scale?:number}
const key='fold-arcade-window-v2';
export function savedBounds():ArcadeBounds {
  try {const b=JSON.parse(localStorage.getItem(key)??'null');if(b?.schemaVersion===2&&[b.width,b.height].every(Number.isFinite))return {...b,width:Math.max(980,Math.min(3200,b.width)),height:Math.max(690,Math.min(2200,b.height)),position:b.position&&[b.position.x,b.position.y].every(Number.isFinite)?b.position:undefined};}catch{}
  // v1 divided desktop positions by the window scale: those mixed-space positions are unsafe.
  return {schemaVersion:2,width:1360,height:900};
}
export function visibleBounds(b:ArcadeBounds,monitors:Pick<Monitor,'name'|'workArea'|'scaleFactor'>[]):ArcadeBounds {
  if(!monitors.length)return {...b,position:undefined};
  const overlaps=(m:typeof monitors[number])=>b.position&&b.position.x>=m.workArea.position.x-32&&b.position.y>=m.workArea.position.y&&b.position.x+120*m.scaleFactor<=m.workArea.position.x+m.workArea.size.width&&b.position.y+60*m.scaleFactor<=m.workArea.position.y+m.workArea.size.height;
  const monitor=monitors.find(overlaps)??monitors.find(m=>m.name===b.monitor)??monitors[0];
  const w=monitor.workArea;
  const width=Math.max(980,Math.min(b.width,w.size.width/monitor.scaleFactor));
  const height=Math.max(690,Math.min(b.height,w.size.height/monitor.scaleFactor));
  const x=overlaps(monitor)?Math.max(w.position.x,Math.min(b.position!.x,w.position.x+w.size.width-width*monitor.scaleFactor)):w.position.x+24*monitor.scaleFactor;
  const y=overlaps(monitor)?Math.max(w.position.y,Math.min(b.position!.y,w.position.y+w.size.height-height*monitor.scaleFactor)):w.position.y+24*monitor.scaleFactor;
  return {schemaVersion:2,width,height,position:{x,y},monitor:monitor.name,scale:monitor.scaleFactor};
}
export async function restoreBounds(){if(!isTauri())return;const w=getCurrentWindow(),b=visibleBounds(savedBounds(),await availableMonitors());await w.setSize(new LogicalSize(b.width,b.height));if(b.position)await w.setPosition(new PhysicalPosition(b.position.x,b.position.y));}
export async function trackBounds(){
  if(!isTauri())return()=>{};
  const w=getCurrentWindow();let disposed=false,timer:ReturnType<typeof setTimeout>|undefined;const stops:(()=>void)[]=[];
  async function save(){if(disposed||await w.isFullscreen()||await w.isMaximized()||await w.isMinimized())return;const [size,position,scale,monitor]=await Promise.all([w.innerSize(),w.outerPosition(),w.scaleFactor(),currentMonitor()]);if(!disposed)localStorage.setItem(key,JSON.stringify({schemaVersion:2,width:size.width/scale,height:size.height/scale,position:{x:position.x,y:position.y},monitor:monitor?.name,scale}));}
  const schedule=()=>{clearTimeout(timer);timer=setTimeout(()=>save().catch(console.error),150);};
  try{stops.push(await w.onResized(schedule));stops.push(await w.onMoved(schedule));stops.push(await w.onScaleChanged(schedule));}catch(e){stops.forEach(stop=>stop());throw e;}
  return()=>{disposed=true;clearTimeout(timer);stops.forEach(stop=>stop());};
}
