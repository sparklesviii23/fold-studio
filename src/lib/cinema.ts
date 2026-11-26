import type {PresentationStyle} from '../components/MolecularViewer';
export type Camera={position:number[];target:number[];up:number[];mode?:'perspective'|'orthographic';fov?:number;[key:string]:any};
export type Keyframe={time:number;camera:Camera;title:string;caption:string;offsets?:Record<string,number[]>};
export type Timeline={schemaVersion:1;mode:'presentation';duration:number;keyframes:Keyframe[];style:PresentationStyle};
export const palette=['#7652ad','#318e86','#78aaa9','#bd704e','#d8ad42','#8dabbf'];
export function interpolate(timeline:Timeline,time:number):Keyframe{
 const t=Math.max(0,Math.min(timeline.duration,time)),keys=timeline.keyframes;
 if(!keys.length)throw new Error('Add camera keyframes first.');
 let right=keys.findIndex(k=>k.time>=t);if(right<0)right=keys.length-1;
 const b=keys[right],a=keys[Math.max(0,right-1)],fraction=b.time===a.time?1:(t-a.time)/(b.time-a.time),u=fraction*fraction*(3-2*fraction);
 const vector=(name:'position'|'target'|'up')=>a.camera[name].map((v,i)=>v+(b.camera[name][i]-v)*u);
 const unit=(v:number[])=>{const n=Math.hypot(...v)||1;return v.map(x=>x/n);},dot=(x:number[],y:number[])=>x.reduce((s,v,i)=>s+v*y[i],0);
 const da=a.camera.position.map((v,i)=>v-a.camera.target[i]),db=b.camera.position.map((v,i)=>v-b.camera.target[i]),na=unit(da),nb=unit(db),cos=Math.max(-1,Math.min(1,dot(na,nb)));let direction:number[];
 if(cos<-.9999){let perpendicular=a.camera.up.map((v,i)=>v-dot(a.camera.up,na)*na[i]);perpendicular=unit(perpendicular);direction=na.map((v,i)=>v*Math.cos(Math.PI*u)+perpendicular[i]*Math.sin(Math.PI*u));}
 else if(cos>.9999)direction=unit(na.map((v,i)=>v+(nb[i]-v)*u));
 else{const angle=Math.acos(cos),sin=Math.sin(angle);direction=na.map((v,i)=>(v*Math.sin((1-u)*angle)+nb[i]*Math.sin(u*angle))/sin);}
 const distance=Math.hypot(...da)*(1-u)+Math.hypot(...db)*u,target=vector('target'),position=target.map((v,i)=>v+direction[i]*distance);
 let up=vector('up');up=up.map((v,i)=>v-dot(up,direction)*direction[i]);if(Math.hypot(...up)<1e-6){up=a.camera.up.map((v,i)=>v-dot(a.camera.up,direction)*direction[i]);if(Math.hypot(...up)<1e-6){const axis=Math.abs(direction[0])<.8?[1,0,0]:[0,1,0];up=axis.map((v,i)=>v-dot(axis,direction)*direction[i]);}}up=unit(up);
 const offsets=Object.fromEntries([...new Set([...Object.keys(a.offsets??{}),...Object.keys(b.offsets??{})])].map(chain=>[chain,[0,1,2].map(i=>(a.offsets?.[chain]?.[i]??0)*(1-u)+(b.offsets?.[chain]?.[i]??0)*u)]));
 return {...(fraction>=1?b:a),time:t,offsets,camera:{...a.camera,position,target,up}};
}
export function fitCamera(camera:Camera,points:number[][],aspect=16/9*.68,padding=1.12):Camera{
 if(!points.length)throw new Error('Open molecular coordinates before framing the film.');
 const min=[Infinity,Infinity,Infinity],max=[-Infinity,-Infinity,-Infinity];for(const p of points)for(let i=0;i<3;i++){if(!Number.isFinite(p[i]))throw new Error('Cannot frame nonfinite coordinates.');min[i]=Math.min(min[i],p[i]);max[i]=Math.max(max[i],p[i]);}const target=min.map((v,i)=>(v+max[i])/2);
 const radius=points.reduce((r,p)=>Math.max(r,Math.hypot(...p.map((v,i)=>v-target[i]))),1);
 const direction=camera.position.map((v,i)=>v-camera.target[i]),length=Math.hypot(...direction)||1;
 const half=Math.atan(Math.tan((camera.fov??Math.PI/4)/2)*Math.min(1,aspect)),distance=radius*padding/Math.sin(half);
 return {...camera,mode:'perspective',target,position:target.map((v,i)=>v+direction[i]/length*distance),radius:radius*padding,radiusMax:radius*padding};
}
export function approach(camera:Camera,style:PresentationStyle,points:{chain:string;xyz:number[]}[],distance=40,duration=30):Timeline{
 if(!style.binderChains.length)throw new Error('Mark the peptide chains before creating an approach film.');
 const binder=points.filter(p=>style.binderChains.includes(p.chain)),target=points.filter(p=>!style.binderChains.includes(p.chain));
 if(!binder.length||!target.length)throw new Error('The approach requires observed peptide and target atoms.');
 const centroid=(p:typeof points)=>[0,1,2].map(i=>p.reduce((sum,a)=>sum+a.xyz[i],0)/p.length),a=centroid(binder),b=centroid(target);
 let direction=a.map((v,i)=>v-b[i]);let length=Math.hypot(...direction);if(length<1){direction=[1,0,0];length=1;}
 const displacement=direction.map(v=>v/length*distance),far=Object.fromEntries(style.binderChains.map(c=>[c,displacement]));
 const framed=fitCamera(camera,[...points.map(p=>p.xyz),...binder.map(p=>p.xyz.map((v,i)=>v+displacement[i]))]);
 const contactPoints=style.contactAtoms?.map(a=>a.xyz)??[],close=contactPoints.length?fitCamera(framed,[...binder.map(p=>p.xyz),...contactPoints],16/9*.68,1.3):framed;
 const keyframes:Keyframe[]=[{time:0,camera:framed,offsets:far,title:'A designed peptide',caption:'Illustrative approach toward the saved predicted pose'},{time:duration*.2,camera:framed,offsets:far,title:'Target and peptide',caption:'Separate molecular partners; source conformations are preserved'},{time:duration*.55,camera:framed,offsets:{},title:'A proposed interface',caption:'Illustrative motion ends at the saved pose; this is not a simulated binding pathway'},{time:duration*.78,camera:close,offsets:{},title:'Inspect the proposed interface',caption:style.contactPairs?`${style.contactPairs} heavy-atom pairs within 4 Å in the saved pose; highlighted in gold`:'Saved coordinate geometry; experimental binding is unverified'},{time:duration,camera:orbit(close,Math.PI/6),offsets:{},title:'A candidate for further research',caption:'Predicted placement; binding and inhibition require independent validation'}];
 return {schemaVersion:1,mode:'presentation',duration,keyframes,style};
}
export function orbit(camera:Camera,angle:number,axis:'x'|'y'|'z'='y'):Camera{
 const c=Math.cos(angle),s=Math.sin(angle),point=camera.position.map((v,i)=>v-camera.target[i]);
 function rotate(v:number[]){const [x,y,z]=v;return axis==='x'?[x,y*c-z*s,y*s+z*c]:axis==='y'?[x*c+z*s,y,-x*s+z*c]:[x*c-y*s,x*s+y*c,z];}
 return {...camera,position:rotate(point).map((v,i)=>v+camera.target[i]),up:rotate(camera.up)};
}
export function overview(camera:Camera,style:PresentationStyle,duration=30):Timeline{
 const keyframes=Array.from({length:9},(_,i)=>({time:i*duration/8,camera:orbit(camera,i*Math.PI/4),title:i<3?'A proposed molecular partnership':i<6?'Inspect the interface':'A candidate for further research',caption:i<3?'Saved target coordinates and designed peptide':i<6?'Camera orbit around the predicted complex':'Prediction does not establish experimental binding or inhibition'}));
 return {schemaVersion:1,mode:'presentation',duration,keyframes,style};
}
export async function composeFrame(imageURI:string,width:number,height:number,key:Keyframe,style:PresentationStyle,sequence:string){
 const image=new Image();image.src=imageURI;await image.decode();
 const canvas=document.createElement('canvas');canvas.width=width;canvas.height=height;const ctx=canvas.getContext('2d')!;
 const paper=style.theme==='paper',panel=Math.round(width*.32);ctx.fillStyle=paper?'#f8f7f3':'#071326';ctx.fillRect(0,0,width,height);
 ctx.drawImage(image,panel,0,width-panel,height);
 const scale=height/1080;ctx.save();ctx.scale(scale,scale);const left=68,max=panel/scale-100;
 ctx.fillStyle=paper?'#827b76':'#90acc5';ctx.font='500 17px -apple-system, sans-serif';ctx.fillText('fold  /  MOLECULAR CINEMA',left,88);
 ctx.fillStyle=paper?'#25242b':'#eef3fc';ctx.font='600 52px -apple-system, sans-serif';let y=245;
 function wrap(text:string,font:string,lineHeight:number){ctx.font=font;let line='';for(const word of text.split(/\s+/)){const next=line?line+' '+word:word;if(ctx.measureText(next).width>max&&line){ctx.fillText(line,left,y);y+=lineHeight;line=word;}else line=next;}ctx.fillText(line,left,y);y+=lineHeight;}
 wrap(key.title,'600 52px -apple-system, sans-serif',62);y+=30;ctx.fillStyle=paper?'#62605e':'#a7bbd0';wrap(key.caption,'400 28px -apple-system, sans-serif',40);
 y=Math.max(y+70,650);for(const [chain,color] of Object.entries(style.palette)){ctx.fillStyle=color;ctx.fillRect(left,y-20,8,26);ctx.fillStyle=paper?'#343039':'#d6e2f1';ctx.font='500 23px -apple-system, sans-serif';ctx.fillText((style.binderChains.includes(chain)?'Designed peptide':'Target')+' · '+chain,left+22,y);y+=42;}
 ctx.fillStyle=paper?'#797473':'#97abc2';ctx.font='500 18px ui-monospace, monospace';ctx.fillText(sequence||'Original coordinates preserved',left,990);
 ctx.font='400 17px -apple-system, sans-serif';ctx.fillText(style.disclosure??'PREDICTED COMPLEX · PRESENTATION ANIMATION',left,1030);ctx.restore();
 return canvas.toDataURL('image/png');
}
