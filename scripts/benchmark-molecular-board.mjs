// CPU-only graph timing. This cannot measure WebKit frames or input-to-display latency.
// node scripts/benchmark-molecular-board.mjs /absolute/report.json
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import ts from 'typescript';
const folder=await fs.mkdtemp(path.join(os.tmpdir(),'fold-graph-timing-'));
try {
 const source=await fs.readFile(new URL('../src/arcade/graph.ts',import.meta.url),'utf8');
 await fs.writeFile(path.join(folder,'graph.mjs'),ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ES2022}}).outputText);
 const {sequenceGraph,validateGraph}=await import(pathToFileURL(path.join(folder,'graph.mjs')));
 const data=JSON.parse(await fs.readFile(new URL('../scientific/amino-acids.json',import.meta.url),'utf8'));
 const templates=new Map(data.components.map(c=>[c.one,c]));
 const cases=[];
 for(const [name,sequence] of [['single Glycine','G'],['20 diverse residues','ACDEFGHIKLMNPQRSTVWY'],['maximum 128 Tryptophans','W'.repeat(128)]]) {
  let start=performance.now();const graph=sequenceGraph(sequence,templates);const firstBuildMs=performance.now()-start;
  validateGraph(graph,templates);const times=[];
  for(let i=0;i<50;i++){start=performance.now();const result=validateGraph(graph,templates);if(!result.valid)throw Error('Invalid benchmark graph');times.push(performance.now()-start);}
  times.sort((a,b)=>a-b);cases.push({name,residues:sequence.length,atoms:graph.atoms.length,bonds:graph.bonds.length,serializedBytes:Buffer.byteLength(JSON.stringify(graph)),firstBuildMs,p50ValidationMs:times[24],p95ValidationMs:times[47],samples:times.length});
 }
 const report={date:new Date().toISOString(),hardware:os.cpus()[0].model,architecture:process.arch,platform:os.platform(),runtime:process.version,method:'One cold sequenceGraph construction, one warm validation, then 50 direct local validateGraph calls per case; sorted p50/p95. Educational layout cache shared across cases.',cases,nativeFrameRate:'unverified',nativeInputToFeedbackP95:'unverified',memoryAndThermals:'unverified'};
 await fs.writeFile(process.argv[2],JSON.stringify(report,null,2));console.log(JSON.stringify(cases));
}finally{await fs.rm(folder,{recursive:true,force:true});}
