import {describe,it,expect} from 'vitest';
import {renderToStaticMarkup} from 'react-dom/server';
import EditCraftSingleCell,{SingleCellResult,singleCellExtent,singleCellHistogram} from './EditCraftSingleCell';
describe('single-cell result integrity',()=>{
 it('includes zero counts, bin boundaries and the maximum exactly once',()=>{
  const cells=[0,0,1,1,1].map(cluster=>({cluster:String(cluster)}));
  expect(singleCellHistogram(cells,[0,0,.5,.75,1],null,4)).toEqual({counts:[2,0,1,2],width:.25,maximum:1,observations:5,zeroCount:2});
  expect(singleCellHistogram(cells,[0,0,.5,.75,1],'0',4)?.counts).toEqual([2,0,0,0]);
  expect(singleCellHistogram(cells,[0,0,.5,.75,1],'1',4)?.observations).toBe(3);
 });
 it('refuses a histogram when expression does not match the real displayed cells',()=>{
  expect(singleCellHistogram([{cluster:'0'}],[])).toBeNull();expect(singleCellHistogram([{cluster:'0'}],[NaN])).toBeNull();expect(singleCellHistogram([{cluster:'0'}],[-1])).toBeNull();expect(singleCellHistogram([{cluster:'0'}],[1],'missing')).toBeNull();
 });
 it('never substitutes made-up positions for invalid upstream coordinates',()=>{
  expect(singleCellExtent([{umap:[1,2]},{umap:[3,4]}])).toEqual({minX:1,maxX:3,minY:2,maxY:4});expect(singleCellExtent([{umap:[0,NaN]}])).toBeNull();expect(singleCellExtent([])).toBeNull();
 });
 it('does not plot illustrative clusters before a real result is selected',()=>{
  const html=renderToStaticMarkup(<EditCraftSingleCell datasets={[]} outputs={[]} onDraft={()=>{throw Error('No calculation during rendering');}} onImport={()=>{}} onPrepare={()=>{throw Error('No transfer during rendering');}}/>);
  expect(html).toContain('No illustrative clusters');expect(html).not.toContain('Actual Scanpy UMAP embedding');expect(html).toMatch(/disabled="">Prepare Scanpy analysis/);
 });
 it('keeps exploratory markers, source metadata and missing expression distinct',()=>{
  const r={method:'Scanpy test fixture',source:{source:{name:'Synthetic UI fixture'},sha256:'a'.repeat(64)},inputShape:[2,100],filteredShape:[2,90],cells:[{barcode:'fixture1',umap:[1,2],cluster:'0',totalCounts:100,genesDetected:30,mitoPercent:2,metadata:{}},{barcode:'fixture2',umap:[3,4],cluster:'1',totalCounts:200,genesDetected:40,mitoPercent:3,metadata:{}}],clusters:[{id:'0',cells:1},{id:'1',cells:1}],expression:[{name:'GENE',values:[0,2]}],clusterExpression:[{cluster:'0',gene:'GENE',meanLogNormalizedExpression:0,percentDetected:0},{cluster:'1',gene:'GENE',meanLogNormalizedExpression:2,percentDetected:100}],missingDisplayGenes:['MISSING'],clusterMarkers:[],markerTestScope:'Exploratory cell-level comparisons, not donor-replicate inference.',artifact:{sha256:'b'.repeat(64)},provenance:{parameters:{metadataColumns:[]}},scope:'No inferred cell types.'};
  const html=renderToStaticMarkup(<SingleCellResult result={r}/>);expect(html).toContain('Actual Scanpy UMAP embedding');expect(html).toContain('fixture1');expect(html).toContain('MISSING');expect(html).toContain('not filled with zeros');expect(html).toContain('not donor-replicate inference');expect(html).not.toContain('Download complete processed H5AD');
 });
});
