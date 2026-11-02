/** Minimal WebGL2 helpers shared by the backdrop and the Cell Explorer. */
export interface Quad {gl:WebGL2RenderingContext;program:WebGLProgram;uniform(name:string):WebGLUniformLocation|null;draw():void;dispose():void}

function compile(gl:WebGL2RenderingContext,type:number,source:string){
  const shader=gl.createShader(type)!;gl.shaderSource(shader,source);gl.compileShader(shader);
  if(!gl.getShaderParameter(shader,gl.COMPILE_STATUS))throw new Error(gl.getShaderInfoLog(shader)??'Shader compilation failed.');
  return shader;
}

export function fullscreenQuad(canvas:HTMLCanvasElement,vertex:string,fragment:string,options:WebGLContextAttributes={}):Quad{
  const gl=canvas.getContext('webgl2',{antialias:false,alpha:false,premultipliedAlpha:false,powerPreference:'high-performance',...options});
  if(!gl)throw new Error('WebGL2 is unavailable.');
  const program=gl.createProgram()!;
  const vs=compile(gl,gl.VERTEX_SHADER,vertex),fs=compile(gl,gl.FRAGMENT_SHADER,fragment);
  gl.attachShader(program,vs);gl.attachShader(program,fs);gl.linkProgram(program);
  if(!gl.getProgramParameter(program,gl.LINK_STATUS))throw new Error(gl.getProgramInfoLog(program)??'Shader link failed.');
  const buffer=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,buffer);
  gl.bufferData(gl.ARRAY_BUFFER,new Float32Array([-1,-1,3,-1,-1,3]),gl.STATIC_DRAW);
  const vao=gl.createVertexArray();gl.bindVertexArray(vao);
  const location=gl.getAttribLocation(program,'aPosition');gl.enableVertexAttribArray(location);gl.vertexAttribPointer(location,2,gl.FLOAT,false,0,0);
  gl.useProgram(program);
  const cache=new Map<string,WebGLUniformLocation|null>();
  return {gl,program,
    uniform(name){if(!cache.has(name))cache.set(name,gl.getUniformLocation(program,name));return cache.get(name)!;},
    draw(){gl.bindVertexArray(vao);gl.drawArrays(gl.TRIANGLES,0,3);},
    dispose(){gl.deleteBuffer(buffer);gl.deleteVertexArray(vao);gl.deleteProgram(program);gl.deleteShader(vs);gl.deleteShader(fs);gl.getExtension('WEBGL_lose_context')?.loseContext();}};
}

/** Resize a canvas backing store to its CSS box times a scale; returns true when it changed. */
export function fitCanvas(canvas:HTMLCanvasElement,scale:number){
  const w=Math.max(1,Math.round(canvas.clientWidth*scale)),h=Math.max(1,Math.round(canvas.clientHeight*scale));
  if(canvas.width===w&&canvas.height===h)return false;
  canvas.width=w;canvas.height=h;return true;
}
