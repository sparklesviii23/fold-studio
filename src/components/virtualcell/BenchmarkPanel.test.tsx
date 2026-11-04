import {describe, it, expect} from 'vitest';
import {renderToStaticMarkup} from 'react-dom/server';
import {BenchmarkReport, type Benchmark} from './BenchmarkPanel';

describe('Benchmark scientific labels', () => {
  it('keeps negative results, undefined correlations and domain limitations visible', () => {
    const e = (mean: number | null) => ({mean, ci95: null, n: mean == null ? 0 : 3});
    const scores = {unchanged: {mae: e(1), mse: e(1), pearson: e(null)}, drug_dose_mean: {mae: e(2), mse: e(3), pearson: e(.1)}};
    const report = {id: 'a', protocol: 'test-fixture', created: '2026-11-05', models: {unchanged: 'Unchanged control', drug_dose_mean: 'Donor mean'},
      dataset: {unit: 'log2 fold change'}, summary: {test: scores, validation: scores}, results: {test: []}, testMseDifferenceVsTrainingMean: {},
      split: {train: ['a'], validation: ['b'], test: ['CVCL_1098'], trainPlates: [1], validationPlates: [11], testPlates: [13]},
      uncertainty: {method: 'Crossed bootstrap', predictiveCalibration: 'not established'}, promotion: {reason: 'No automatic promotion'},
      limitations: ['C3A does not validate parental HepG2']} satisfies Benchmark;
    const html = renderToStaticMarkup(<BenchmarkReport report={report}/>);
    expect(html).toContain('undefined'); expect(html).toContain('3.000'); expect(html).toContain('No automatic promotion');
    expect(html).toContain('C3A does not validate parental HepG2'); expect(html).toContain('not established');
  });
});
