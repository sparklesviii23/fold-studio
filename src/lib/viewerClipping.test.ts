import {it,expect} from 'vitest';
import {readFileSync,existsSync} from 'node:fs';
import {fullSceneClipRadius} from './viewerClipping';
const fixture=new URL('../../tests/fixtures/ANGPTL3_8_pilot_target_small.pdb',import.meta.url);
const rotationTest=existsSync(fixture)?it:it.skip;
rotationTest('keeps actual ANGPTL3/8 coordinates inside the depth slab through full XYZ orbits, including an offset selection pivot',async()=>{
 const {Camera}=await import('molstar/lib/mol-canvas3d/camera');
 const {Vec3}=await import('molstar/lib/mol-math/linear-algebra');
 const pdb=readFileSync(new URL('../../tests/fixtures/ANGPTL3_8_pilot_target_small.pdb',import.meta.url),'utf8');
 const points=pdb.split('\n').filter(l=>l.startsWith('ATOM  ')).map(l=>[Number(l.slice(30,38)),Number(l.slice(38,46)),Number(l.slice(46,54))]);expect(points.length).toBe(1800);
 const center=[0,1,2].map(i=>(Math.min(...points.map(p=>p[i]))+Math.max(...points.map(p=>p[i])))/2);const radius=Math.max(...points.map(p=>Math.hypot(...p.map((v,i)=>v-center[i]))))+4;
 for(const target of [center,points[0]]){const clip=fullSceneClipRadius(center,radius,target);for(let axis=0;axis<3;axis++)for(let degree=0;degree<=360;degree++){
  const a=degree*Math.PI/180,d=clip*4;const direction=axis===0?[0,Math.sin(a),Math.cos(a)]:axis===1?[Math.sin(a),0,Math.cos(a)]:[Math.cos(a),Math.sin(a),0];
  const camera=new Camera();camera.viewport.width=1440;camera.viewport.height=960;camera.setState({position:Vec3.create(...target.map((v,i)=>v+direction[i]*d) as [number,number,number]),target:Vec3.create(...target as [number,number,number]),up:Vec3.create(...(axis===0?[1,0,0]:axis===1?[0,1,0]:[0,0,1]) as [number,number,number]),radius:clip,radiusMax:clip,clipFar:false});camera.update();
  for(const p of points){const depth=d-p.reduce((sum,v,i)=>sum+(v-target[i])*direction[i],0);if(depth<camera.near||depth>camera.far)throw new Error(`Clipped at axis ${axis}, angle ${degree}`);}
 }}
});
