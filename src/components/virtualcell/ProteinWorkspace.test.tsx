import {describe, it, expect} from 'vitest';
import {renderToStaticMarkup} from 'react-dom/server';
import ProteinWorkspace, {Enrichment} from './ProteinWorkspace';
import {fmt} from '../mechanistic/MechCharts';

const PROTEIN = {
  resolution: {status: 'resolved', symbol: 'ALB', matchedBy: 'UniProt accession'}, symbol: 'ALB', context: 'Hep G2',
  identifiers: {uniprot: ['P02768'], ensembl: ['ENSG00000163631'], hgnc: 'HGNC:399', synonyms: ['GIG42'], length: 609},
  expression: {inPanel: true, unit: 'log2(TPM+1), DepMap 24Q4 bulk RNA-seq (protein-coding genes)', baseline: 13.96, baselineSource: 'Baseline = DepMap 24Q4 bulk RNA-seq of Hep G2 (CVCL_0027)', change: 0, changeEvidence: null, evidenceBaseline: 'A · Experimental'},
  fitness: {chronos: 0.07, evidence: 'A · Experimental', source: 'DepMap 24Q4 CRISPR knockout in Hep G2'},
  localization: {hpa: {reliability: 'Enhanced', drawn: true, cellCycleDependency: null, scope: 'General human annotation; not specific to this cell context.',
                       terms: [{term: 'Endoplasmic reticulum', main: true, layer: 'er'}, {term: 'Cytosol', main: false, layer: null}]},
                 uniprot: [{location: 'Secreted', isoform: null, evidence: 'experimental'}], goComponent: [], humanGem: [], layers: ['er'],
                 note: 'Compartment-level annotations only: positions inside a compartment are not known and are not drawn.'},
  pathways: [{id: 'R-HSA-2', name: 'Child A', topLevel: 'Top', evidence: 'TAS', url: 'https://reactome.org/content/detail/R-HSA-2'}],
  pathwayEvidence: 'Reactome lowest-level pathways for the UniProt accession.',
  structures: {pdb: ['1AO6'], count: 1, source: 'PDB entries cross-referenced by UniProt.'},
  mechanisticTarget: {accession: 'P02768', genes: ['ALB'], name: 'ALB'},
  abundance: 'Protein abundance is not available for this context (no installed proteomics dataset); RNA is not used as a substitute.',
  manifest: {reactomeRelease: '98', built: '2026-11-02T03:46:00Z'},
};

describe('Virtual Cell protein workspace', () => {
  it('separates measured expression, general localization and pathway membership, each with its source', () => {
    const html = renderToStaticMarkup(<ProteinWorkspace protein={PROTEIN} cellId="c" onClose={() => {}} onError={() => {}}/>);
    expect(html).toContain('A · Experimental'); expect(html).toContain(`<b>${fmt(13.96, 3)}</b>`);
    expect(html).toContain('not specific to this cell context'); expect(html).toContain('positions inside a compartment are not known');
    expect(html).toContain('Secreted (experimental (ECO:0000269))');
    expect(html).toContain('Protein abundance is not available'); expect(html).toContain('A structure is not evidence of a cellular function');
    expect(html).toContain('release 98'); expect(html).toContain('Child A'); expect(html).toContain('rcsb.org/structure/1AO6');
    expect(html).toContain('Drawn in the ER layer'); expect(html).toContain('No layer in the cell view');
  });
  it('states ambiguity and misses instead of guessing a protein', () => {
    const amb = renderToStaticMarkup(<ProteinWorkspace protein={{resolution: {status: 'ambiguous', candidates: ['GENEA', 'GENEB'], matchedBy: 'alias shared by several genes'}}} cellId="c" onClose={() => {}} onError={() => {}}/>);
    expect(amb).toContain('Ambiguous identifier: it names GENEA, GENEB');
    const miss = renderToStaticMarkup(<ProteinWorkspace protein={{resolution: {status: 'unknown', query: 'NOPE'}}} cellId="c" onClose={() => {}} onError={() => {}}/>);
    expect(miss).toContain('is not a reviewed human UniProt entry');
  });
  it('labels enrichment as a description of model output', () => {
    const html = renderToStaticMarkup(<Enrichment r={{query: '100 genes with the largest modelled change', queryInUniverse: 98, universe: 2085, tested: 900, evidence: 'C · AI prediction',
      method: 'one-sided hypergeometric test', note: 'enrichment describes them and is not an independent measurement', rows: [{id: 'R-HSA-2', name: 'Child A', size: 10, hits: ['ALB'], p: 0.001, fdr: 0.02}]}} onClose={() => {}}/>);
    expect(html).toContain('C · AI prediction'); expect(html).toContain('not an independent measurement'); expect(html).toContain('1 / 10');
    expect(renderToStaticMarkup(<Enrichment r={{empty: 'This cell is the unperturbed baseline'}} onClose={() => {}}/>)).toContain('unperturbed baseline');
  });
});
