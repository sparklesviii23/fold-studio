import {describe, it, expect} from 'vitest';
import {renderToStaticMarkup} from 'react-dom/server';
import SimulationResult from './SimulationResult';
import RnaProtein from './RnaProtein';
import ProteinWorkspace from './ProteinWorkspace';

const RESULT = {lab: 'Living Cell Physics', kind: 'diffusion', created: '2026-10-31', scale: 'single idealised cell (µm, s)', model: {name: 'Living Cell Brownian dynamics', version: '1.0.0', numericalMethod: 'Euler–Maruyama'},
  evidence: {category: 'B', name: 'Physics simulation', statement: 'Not a model of any specific molecule or cell.'}, context: 'Describes the idealised system in its own inputs, not the selected Virtual Cell context.',
  time: {values: [0, 1, 2], unit: 's'}, lengthUnit: 'µm', series: [{id: 'free.msd', values: [0, 6, 12]}], profiles: [], scalars: [{id: 'rate', value: 0.5}],
  inputs: {diffusion: {value: 10, unit: 'µm²/s', provenance: {kind: 'hypothetical'}}}, solver: {dt: 0.1}, convergence: {checks: [{name: 'Free: fitted D', passed: true, detail: 'D = 9.83 vs 10'}]},
  validation: 'benchmark checks passed', assumptions: ['Point particles.'], limitations: ['No crowding.'], integrity: {match: true, recipe: ['inputs', 'solver', 'outputs']}, reproducibility: {runtime: 'Python 3.12', seed: 1}};

describe('Virtual Cell modality panels', () => {
  it('shows a saved lab result with units, checks, integrity and its own scope', () => {
    const html = renderToStaticMarkup(<SimulationResult r={RESULT} onClose={() => {}}/>);
    expect(html).toContain('10 µm²/s'); expect(html).toContain('hypothetical'); expect(html).toContain('✓ Free: fitted D');
    expect(html).toContain('content SHA-256 re-computed and matches'); expect(html).toContain('not the selected Virtual Cell context');
    expect(renderToStaticMarkup(<SimulationResult r={{...RESULT, integrity: {match: false, recipe: ['inputs']}}} onClose={() => {}}/>)).toContain('MISMATCH');
  });
  it('reports RNA–protein agreement as rank correlation with its caveats, or unsupported', () => {
    const html = renderToStaticMarkup(<RnaProtein r={{context: 'Hep G2', rna: 'ENCODE TPM', comparisons: [{dataset: 'geiger2012_ibaq', method: 'iBAQ', unit: 'ppm', spearman: 0.487, n: 6737, p: 1e-300,
      sample: [[1, 2, 'A'], [10, 30, 'B']], note: 'RNA does not determine protein abundance'}]}} onClose={() => {}}/>);
    expect(html).toContain('Spearman ρ 0.487'); expect(html).toContain('6,737'); expect(html).toContain('RNA does not determine protein abundance');
    expect(renderToStaticMarkup(<RnaProtein r={{supported: false, reason: 'No proteomics dataset is integrated for K-562.'}} onClose={() => {}}/>)).toContain('No proteomics dataset');
  });
  it('shows measured abundance and explicit non-reporting in the protein panel', () => {
    const protein = {resolution: {status: 'resolved', matchedBy: 'symbol'}, symbol: 'APOA1', context: 'Hep G2', identifiers: {uniprot: ['P02647'], ensembl: [], hgnc: null, synonyms: [], length: 267},
      expression: {inPanel: false, unit: 'u', evidenceBaseline: 'A · Experimental'}, fitness: null, pathways: [], pathwayEvidence: '', structures: {pdb: [], count: 0, source: ''}, mechanisticTarget: null, manifest: {},
      localization: {hpa: null, uniprot: [], goComponent: [], humanGem: [], layers: [], note: ''},
      abundance: {evidence: 'A · Experimental', note: 'Separate experiment', datasets: [{dataset: 'ibaq', reported: true, value: 209, rank: 1266, of: 6740, percentile: 81.2, method: 'iBAQ', uniprot: 'P02647', citation: 'Geiger 2012', replicates: 'none published'},
        {dataset: 'sc', reported: false, method: 'Spectral counting', note: 'not reported = below detection or not identified (not zero)'}]}};
    const html = renderToStaticMarkup(<ProteinWorkspace protein={protein} cellId="c" onClose={() => {}} onError={() => {}}/>);
    expect(html).toContain('209 ppm'); expect(html).toContain('rank 1,266 of 6,740'); expect(html).toContain('Not reported · Spectral counting'); expect(html).toContain('(not zero)');
  });
});
