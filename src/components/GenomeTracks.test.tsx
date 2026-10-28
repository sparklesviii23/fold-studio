import {describe,it,expect} from 'vitest';
import {renderToStaticMarkup} from 'react-dom/server';
import GenomeTracks,{trackNavigation} from './GenomeTracks';
describe('genome coordinate tracks',()=>{
 it('keeps navigation within the real reference without silently wrapping',()=>{
  const w={repliconLength:1000,length:100,windowStart:950};expect(trackNavigation(w,'next')).toEqual({start:901,end:1000,strand:'+'});expect(trackNavigation({...w,windowStart:1},'previous').start).toBe(1);expect(trackNavigation(w,'in').end-trackNavigation(w,'in').start+1).toBe(50);
 });
 it('shows supplied strands and coordinates without inferring gene function',()=>{
  const window={repliconLength:100,length:10,windowStart:1,unrolledWindowEnd:10,total:1,omitted:0,features:[{feature:{index:0,type:'CDS',start:1,end:10,strand:'-',attributes:{ID:'original'}},fragments:[{startOffsetZeroBased:0,endOffsetExclusive:10}]}],scope:'Supplied spans only.'};
  const html=renderToStaticMarkup(<GenomeTracks window={window} busy={false} onFeature={()=>{throw Error('No calculation on render');}} onNavigate={()=>{}}/>);expect(html).toContain('original ←');expect(html).toContain('CDS 1–10 (-)');expect(html).toContain('Supplied spans only.');
 });
});
