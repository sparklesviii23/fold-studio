import {describe, it, expect} from 'vitest';
import {renderToStaticMarkup} from 'react-dom/server';
import {RegulatoryTrack} from './RegulatoryPanel';

describe('Regulatory scientific labels', () => {
  it('keeps assay prediction, coverage limits and observed units separate', () => {
    const track = {supported: true, run: 'synthetic-test', status: 'one locus checked', model: 'fixture', checkpointSha256: 'a'.repeat(64), sourceRevision: 'pinned',
      reference: {assembly: 'hg38', chromosome: 'chr2'}, coordinateConvention: 'zero-based half-open', start: 100, end: 164, binSize: 32, bins: 2,
      unit: 'raw transformed coverage', track: {identifier: 'fixture+', description: 'RNA:HepG2', scale: '0.3', sum_stat: 'sum_sqrt'},
      preview: [{start: 100, end: 164, min: 0, max: 1, mean: .5}], uncertainty: {supported: false, reason: 'No calibrated predictive interval'}, note: 'Not measured RNA',
      comparison: {status: 'not genome-wide validation', region: ['chr2', 100, 164] as [string, number, number], fold: 'fold3', spearman: .4, scoredBins: 1, totalBins: 2,
        predictedUnit: 'transformed coverage', observedUnit: 'unique read signal', preview: [{start: 100, end: 132, predictedMean: 1, observedMean: 100}], limitations: ['Missing is not zero']}};
    const html = renderToStaticMarkup(<RegulatoryTrack track={track}/>);
    expect(html).toContain('1 of 2'); expect(html).toContain('Observed'); expect(html).toContain('unique read signal');
    expect(html).toContain('independent vertical scales'); expect(html).toContain('not genome-wide validation'); expect(html).toContain('No calibrated predictive interval');
  });
});
