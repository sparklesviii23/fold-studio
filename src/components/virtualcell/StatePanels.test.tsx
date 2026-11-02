import {describe, it, expect} from 'vitest';
import {renderToStaticMarkup} from 'react-dom/server';
import {Coverage, Snapshots} from './StatePanels';
import TranscriptInspector from './TranscriptInspector';
import CellCycleTimeline from './CellCycleTimeline';

const t = Array.from({length: 11}, (_, i) => i * 10);
const RUN = {key: 'k', gf: 1, hours: 100, time: t, shown: ['Me', 'Mb'], series: {Me: t.map(x => Math.sin(x)), Mb: t.map(x => Math.cos(x))}, evidence: 'Mechanistic simulation output',
  model: {id: 'BIOMD0000000730', name: 'Gerard2009', calibration: 'Not calibrated to Hep G2 or any cell line.', notModelled: ['cell size and volume'], species: 44, parameters: 187, sbml: 'Level 2 Version 4', sha256: 'abcdef0123456789', licence: 'CC0'},
  solver: {library: 'SciPy', method: 'LSODA', rtol: 1e-8, points: 11}, diagnostics: {reliable: true, toleranceSensitivity: 1e-6, negativeValues: false},
  analysis: {quiescent: false, regime: 'sustained oscillation (limit cycle)', labels: [null, null, 0, 1, 2, 3, 0, 1, 2, 3, 0], phases: ['G1', 'G1/S', 'S–G2', 'G2/M'], segments: [{phase: 'G1', start: 20, end: 20}],
             period: 25.6, periodSd: 0.1, cyclesAnalysed: 3, mitoticExit: [64.2], transientExcluded: 48, rule: 'Forward-only half-maximum crossings.'},
  interpretation: 'Convergence says nothing about whether it describes Hep G2.'};

describe('Virtual Cell state panels', () => {
  it('shows every coverage state in words, including what is missing', () => {
    const html = renderToStaticMarkup(<Coverage coverage={{coverage: {'protein abundance': {state: 'unsupported', note: 'No verified proteomics dataset'}, 'transcript isoforms': {state: 'not_downloaded', source: 'ENCODE'},
      'cell-cycle dynamics': {state: 'unvalidated'}}}}/>);
    expect(html).toContain('Unsupported for this cell'); expect(html).toContain('Not downloaded'); expect(html).toContain('Model output, unvalidated'); expect(html).toContain('No verified proteomics dataset');
  });
  it('lists snapshots and flags incomparable comparisons', () => {
    const html = renderToStaticMarkup(<Snapshots list={[{id: 'a'.repeat(32), label: 't = 70 h', kind: 'simulation', time: 70, steps: 1, parent: 'b'}]} onSave={() => {}} onRestore={() => {}} onCompare={() => {}} onExport={() => {}} onImport={() => {}} onDelete={() => {}}
      comparison={{warning: 'Different cell contexts', history: {a: [], b: ['gene_knockout:CDK1']}, blocks: {e: {incompatible: 'measured [u] vs prediction [u]'}, f: {only: 'b'}}, simulation: {sameModel: false, variables: []}}}/>);
    expect(html).toContain('t = 70 h'); expect(html).toContain('simulation · t 70 h'); expect(html).toContain('Different cell contexts');
    expect(html).toContain('not comparable'); expect(html).toContain('only in snapshot B'); expect(html).toContain('different models: variables not compared');
  });
  it('reports unsupported transcripts instead of values', () => {
    expect(renderToStaticMarkup(<TranscriptInspector data={{supported: false, reason: 'No transcript-level dataset is integrated for K-562.'}}/>)).toContain('No transcript-level dataset');
  });
  it('labels the cell-cycle model as generic and the phases as a rule', () => {
    const html = renderToStaticMarkup(<CellCycleTimeline run={RUN} time={30} onTime={() => {}} onSnapshot={() => {}} onClose={() => {}}/>);
    expect(html).toContain('Not calibrated to Hep G2'); expect(html).toContain('The 3D cell is not driven by this model');
    expect(html).toContain('>G1/S</span>'); expect(html).toContain('Forward-only half-maximum crossings'); expect(html).toContain('reliable');
  });
});
