/** Enclose the complete scene even when the orbit pivot is a small selection. */
export function fullSceneClipRadius(center:ArrayLike<number>,radius:number,target:ArrayLike<number>){
 return Math.max(1,radius)+Math.hypot(center[0]-target[0],center[1]-target[1],center[2]-target[2])+Math.max(2,radius*0.02);
}
