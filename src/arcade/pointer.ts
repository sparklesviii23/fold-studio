import type {GraphAtom} from './graph';
export interface Camera {x:number;y:number;zoom:number}
export interface Rect {left:number;top:number;width:number;height:number}
export function toBoard(x:number,y:number,rect:Rect,camera:Camera):[number,number]{return [(x-rect.left-camera.x)/camera.zoom,(y-rect.top-camera.y)/camera.zoom];}
export function toScreen(point:number[],rect:Rect,camera:Camera):[number,number]{return [rect.left+camera.x+point[0]*camera.zoom,rect.top+camera.y+point[1]*camera.zoom];}
export function attraction(x:number,y:number,targets:GraphAtom[],placed:Set<string>,element:string,rect:Rect,camera:Camera,previous?:string|null,radius=22):{atom:GraphAtom|null;reason:string} {
 const ranked=targets.map(atom=>({atom,d:Math.hypot(...toScreen(atom.board,rect,camera).map((v,i)=>v-[x,y][i]))})).sort((a,b)=>a.d-b.d||a.atom.id.localeCompare(b.atom.id));
 const prior=ranked.find(v=>v.atom.id===previous&&v.d<=radius+6&&v.atom.element===element&&!placed.has(v.atom.id));
 const candidate=prior??ranked.find(v=>v.d<=radius&&v.atom.element===element&&!placed.has(v.atom.id));
 if(candidate)return {atom:candidate.atom,reason:'Release to snap '+element+' · '+candidate.atom.templateAtom};
 const nearest=ranked[0];return {atom:null,reason:nearest?.d<=radius?placed.has(nearest.atom.id)?'That atom is already placed.':'This site needs '+nearest.atom.element+'.':'Bring the piece to a matching ghost site.'};
}
/** One active pointer, primary button only, 5 CSS px drag threshold.
 * UI paints at rAF cadence; graph mutations happen only on finish. */
export class PiecePointer<T>{
 active:{id:number;startX:number;startY:number;x:number;y:number;piece:T;moved:boolean}|null=null;
 begin(id:number,button:number,primary:boolean,x:number,y:number,piece:T){if(this.active||button!==0||!primary)return false;this.active={id,startX:x,startY:y,x,y,piece,moved:false};return true;}
 move(id:number,x:number,y:number){if(!this.active||id!==this.active.id)return null;this.active.x=x;this.active.y=y;this.active.moved ||=Math.hypot(x-this.active.startX,y-this.active.startY)>=5;return this.active;}
 finish(id:number){if(!this.active||id!==this.active.id)return null;const result=this.active;this.active=null;return result;}
 cancel(){this.active=null;}
}
