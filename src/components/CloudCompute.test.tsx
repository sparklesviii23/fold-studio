import {describe,it,expect} from 'vitest';
import {renderToStaticMarkup} from 'react-dom/server';
import CloudCompute,{connectionLabel} from './CloudCompute';
const profile={id:'p',name:'Test',provider:'vast' as const,host:'example.org',port:22,username:'root',keyPath:''};
describe('Cloud Compute foundation',()=>{
 it('separates identity, SSH, worker and genuine GPU checks from scientific readiness',()=>{
  expect(connectionLabel(profile)).toBe('Disconnected');
  expect(connectionLabel({...profile,fingerprint:'SHA256:x'})).toBe('Identity saved');
  expect(connectionLabel({...profile,connection:{state:'connected'}})).toBe('SSH checked');
  expect(connectionLabel({...profile,worker:{state:'installed'}})).toBe('Worker installed');
  expect(connectionLabel({...profile,lastWorkerReading:{operation:'gpu_selftest',checkedUtc:'now',result:{cudaNumericsPassed:true,ready:false}}})).toBe('GPU checks passed · engines needed');
 });
 it('clearly identifies the actual foundation scope and keeps local compute accessible',()=>{
  const html=renderToStaticMarkup(<CloudCompute onLocal={()=>{}}/>);
  expect(html).toContain('Cloud Compute');expect(html).toContain('Connect Your GPU');
  expect(html).toContain('remote scientific campaigns are not available yet');
  expect(html).toContain('Local BindCraft Architect');
  expect(html).not.toContain('RTX 5090 · Ready');expect(html).not.toContain('Rent now');
 });
});
