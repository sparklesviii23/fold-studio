import {describe,it,expect} from 'vitest';
import {renderToStaticMarkup} from 'react-dom/server';
import PathwayMembership,{membershipGraph,membershipSvg} from './PathwayMembership';

describe('saved pathway membership graph',()=>{
 it('draws only exact reported overlaps and reports bounded omissions',()=>{
  const rows=[{id:'set_A',overlapGenes:['G1','G2']},{id:'set_B',overlapGenes:['G2','G3']},{id:'no_overlap',overlapGenes:[]}];
  expect(membershipGraph(rows).edges).toEqual([{set:'set_A',gene:'G1'},{set:'set_A',gene:'G2'},{set:'set_B',gene:'G2'},{set:'set_B',gene:'G3'}]);
  expect(membershipGraph(rows,1,1)).toMatchObject({omittedSets:1,omittedGenes:1,edges:[{set:'set_A',gene:'G1'}]});
  const html=renderToStaticMarkup(<PathwayMembership rows={rows}/>);
  expect(html).toContain('set_A contains G1');expect(html).toContain('set_B contains G3');expect(html).not.toContain('no_overlap contains');
  expect(html).toContain('not physical interactions, pathway activity or causation');
 });
 it('exports a standalone bounded SVG with exact links, escaped labels and source hashes',()=>{
  const svg=membershipSvg([{id:'A<&',overlapGenes:['G"1','G2']},{id:'B',overlapGenes:['G2']}],{inputSha256:'a'.repeat(64),backgroundSha256:'b'.repeat(64)});
  expect(svg).toContain('<svg xmlns="http://www.w3.org/2000/svg"');
  expect(svg).toContain('A&lt;&amp; contains G&quot;1');
  expect(svg).not.toContain('A<&');
  expect(svg).toContain('a'.repeat(64));expect(svg).toContain('b'.repeat(64));
  expect(svg).toContain('&quot;displayedEdges&quot;:3');
  expect(svg).toContain('membership is not a physical interaction');
 });
});
