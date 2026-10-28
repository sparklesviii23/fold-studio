import {describe,it,expect} from 'vitest';
import {renderToStaticMarkup} from 'react-dom/server';
import AssayStatisticsView,{type AssaySummary} from './AssayStatisticsView';
describe('declared biological replicate summary',()=>{
 it('shows endpoint units, biological n separately from raw rows and missing uncertainty explicitly',()=>{
  const summary:AssaySummary={assayName:'Fixture',endpoint:'Observed endpoint',responseUnit:'RU',concentrationUnit:'nM',assaySha256:'a'.repeat(64),sourceSha256:'b'.repeat(64),groups:[{sampleGroup:'vehicle',concentration:0,biologicalUnits:1,rawReadings:20,mean:2,sampleSD:null,standardError:null,confidenceInterval95:null,intervalDegreesOfFreedom:null,intervalIsConservative:false}],method:'Technical repeats averaged within biological units',intervalMethod:'Pointwise intervals require independent approximately normal biological means',limitations:['No affinity fit or experimental validity inferred']};
  const html=renderToStaticMarkup(<AssayStatisticsView summary={summary}/>);
  expect(html).toContain('Observed endpoint');expect(html).toContain('Dose · nM');expect(html).toContain('Biological n');expect(html).toContain('Raw readings');expect(html).toContain('Not estimable');expect(html).toContain('20');expect(html).toContain(summary.assaySha256);expect(html).toContain(summary.limitations[0]);
 });
});
