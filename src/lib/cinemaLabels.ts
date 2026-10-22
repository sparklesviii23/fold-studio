import type {Camera} from './cinema';
export type AnchoredLabel={text:string;color:string;anchor:number[];box:number[];width:number};
const dot=(a:number[],b:number[])=>a.reduce((s,n,i)=>s+n*b[i],0);
const cross=(a:number[],b:number[])=>[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];
const unit=(a:number[])=>{const d=Math.hypot(...a);return a.map(v=>v/(d||1));};
export function projectPoint(camera:Camera,point:number[],width:number,height:number){
 const forward=unit(camera.target.map((v,i)=>v-camera.position[i])),right=unit(cross(forward,camera.up)),up=cross(right,forward),delta=point.map((v,i)=>v-camera.position[i]),depth=dot(delta,forward);
 if(depth<=0)return null;
 const vertical=Math.tan((camera.fov??Math.PI/4)/2)*(camera.mode==='orthographic'?Math.hypot(...camera.position.map((v,i)=>v-camera.target[i])):depth);
 return [(1+dot(delta,right)/(vertical*width/height))*width/2,(1-dot(delta,up)/vertical)*height/2];
}
export function molecularLabels(camera:Camera,atoms:{chain:string;xyz:number[]}[],binders:string[],palette:Record<string,string>,offsets:Record<string,number[]>,width:number,height:number,targetLabel='Target construct',targetAtoms?:{chain:string;xyz:number[]}[]){
 const groups=[{text:targetLabel,atoms:targetAtoms?.length?targetAtoms:atoms.filter(a=>!binders.includes(a.chain)),chain:atoms.find(a=>!binders.includes(a.chain))?.chain,side:-1},...binders.map(chain=>({text:'Designed peptide · '+chain,atoms:atoms.filter(a=>a.chain===chain),chain,side:1}))];
 const labels:AnchoredLabel[]=[],scale=Math.max(.55,height/720),boxHeight=30*scale;
 for(const group of groups){if(!group.atoms.length)continue;const center=[0,1,2].map(i=>group.atoms.reduce((sum,a)=>sum+a.xyz[i]+(offsets[a.chain]?.[i]??0),0)/group.atoms.length),anchor=projectPoint(camera,center,width,height);if(!anchor||anchor.some((v,i)=>v<0||v>(i?height:width)))continue;
  const boxWidth=Math.min(width-16,Math.max(100,group.text.length*8+20)*scale),x=Math.max(8,Math.min(width-boxWidth-8,anchor[0]+group.side*80*scale-(group.side<0?boxWidth:0)));let y=Math.max(8,Math.min(height-boxHeight-8,anchor[1]-75*scale));
  for(const other of labels)if(x<other.box[0]+other.width&&x+boxWidth>other.box[0]&&Math.abs(y-other.box[1])<boxHeight+6)y=Math.min(height-boxHeight-8,other.box[1]+boxHeight+10);
  labels.push({text:group.text,color:palette[group.chain??'']??'#7652ad',anchor,box:[x,y],width:boxWidth});
 }return labels;
}
export async function annotateMolecularImage(uri:string,width:number,height:number,labels:AnchoredLabel[]){
 const img=new Image();img.src=uri;await img.decode();const canvas=document.createElement('canvas');canvas.width=width;canvas.height=height;const ctx=canvas.getContext('2d')!;ctx.drawImage(img,0,0,width,height);
 const scale=Math.max(.55,height/720),h=30*scale;ctx.font=`600 ${15*scale}px -apple-system, sans-serif`;ctx.textBaseline='middle';
 for(const label of labels){const [x,y]=label.box;ctx.strokeStyle=label.color;ctx.lineWidth=1.3*scale;ctx.beginPath();ctx.moveTo(...label.anchor as [number,number]);ctx.lineTo(x+label.width/2,y+h/2);ctx.stroke();ctx.fillStyle=label.color;ctx.beginPath();ctx.roundRect(x,y,label.width,h,5*scale);ctx.fill();ctx.fillStyle='#ffffff';ctx.fillText(label.text,x+10*scale,y+h/2,label.width-20*scale);}
 return canvas.toDataURL('image/png');
}
