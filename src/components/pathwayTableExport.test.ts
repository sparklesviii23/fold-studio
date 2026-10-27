import {describe,it,expect} from 'vitest';
import {pathwayTableExport} from './pathwayTableExport';

// Parse quoted TSV as a spreadsheet reader would, including embedded newlines.
function readTable(text:string){
 const rows:string[][]=[];let row:string[]=[],value='',quoted=false;
 for(let i=0;i<text.length;i++){
  const ch=text[i];
  if(ch==='"'){if(quoted&&text[i+1]==='"'){value+='"';i++;}else quoted=!quoted;}
  else if(!quoted&&ch==='\t'){row.push(value);value='';}
  else if(!quoted&&ch==='\r'&&text[i+1]==='\n'){row.push(value);rows.push(row);row=[];value='';i++;}
  else value+=ch;
 }
 return rows.slice(1).map(values=>Object.fromEntries(rows[0].map((key,i)=>[key,values[i]])));
}
describe('pathway spreadsheet export',()=>{
 it('retains non-significant and no-testable sets, underflow logs and provenance',()=>{
  const result={rows:[{id:'strong',pValue:0,logPValue:-900,pValueUnderflow:true,adjustedPValue:0,logAdjustedPValue:-895,adjustedPValueUnderflow:true,passesDeclaredThreshold:true,overlapGenes:['G1','g2']},{id:'outside',foldEnrichment:null,pValue:1,adjustedPValue:1,passesDeclaredThreshold:false,noTestableMembers:true,overlapGenes:[],outsideBackground:['other']}],multipleTesting:'BY',inputSha256:'a'.repeat(64),collection:{name:'Original collection',source:'Line one\nLine two\t"quoted"'}};
  const before=JSON.stringify(result),rows=readTable(pathwayTableExport({operation:'pathway_enrichment',result}));
  expect(rows).toHaveLength(2);expect(rows[0].logPValue).toBe('-900');expect(rows[0].pValueUnderflow).toBe('true');expect(JSON.parse(rows[0].overlapGenes)).toEqual(['G1','g2']);
  expect(rows[1].foldEnrichment).toBe('');expect(rows[1].passesDeclaredThreshold).toBe('false');expect(rows[1].noTestableMembers).toBe('true');
  for(const row of rows){expect(row.multipleTesting).toBe('BY');expect(row.inputSha256).toBe(result.inputSha256);expect(JSON.parse(row.collection)).toEqual(result.collection);}
  expect(JSON.stringify(result)).toBe(before);
 });
 it('prevents textual formulas while keeping numeric signs and exact identifiers in JSON arrays',()=>{
  const rows=readTable(pathwayTableExport({operation:'pathway_enrichment',result:{rows:[{id:' =HYPERLINK("x")',logPValue:-12,overlapGenes:['+G1']}],scope:'@formula'}}));
  expect(rows[0].id).toBe('\' =HYPERLINK("x")');expect(rows[0].scope).toBe("'@formula");expect(rows[0].logPValue).toBe('-12');expect(JSON.parse(rows[0].overlapGenes)).toEqual(['+G1']);
  expect(()=>pathwayTableExport({operation:'other',result:{rows:[]}})).toThrow();
 });
});
