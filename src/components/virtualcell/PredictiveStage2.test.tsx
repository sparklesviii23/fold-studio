import {describe,it,expect} from 'vitest';
import {renderToStaticMarkup} from 'react-dom/server';
import {PanelGeneTrack} from './GeneEvidencePanel';
import {BorzoiBenchmarkReport,ResponseDiagnostics} from './BenchmarkPanel';

describe('Predictive biology evidence labels',()=>{
  it('keeps model and observed scales separate and exposes unsupported metrics',()=>{
    const html=renderToStaticMarkup(<PanelGeneTrack item={{region:['chr1',0,196608],preview:[{start:0,end:512,f0:1,f1:2,ensemble:1.5,observed:null}],
      trackDescription:'RNA:HepG2',trackIdentifier:'ENCFF065PJM+',cohort:'illustrative',fold:'fold5',cellosaurus:'CVCL_0027',fullGeneCovered:false,
      observedUnit:'original signal',metrics:{f0:{spearman:null,pearson:null,n:0,status:'insufficient_reference'}}}}/>);
    for(const text of ['not an independent test','only part of this gene','Independent vertical scale','not estimable','0 / 6144','not a calibrated confidence interval'])expect(html).toContain(text);
    expect(html).not.toContain('NaN');
  });
  it('retains attempted and failed loci without a combined task score',()=>{
    const metric={mean:null,ci95:null};
    const html=renderToStaticMarkup(<BorzoiBenchmarkReport report={{testLoci:100,illustrativeLoci:4,tracks:[{index:1,cellosaurus:'CVCL_0027',metadata:{description:'DNASE:HepG2',identifier:'ENCFF136DBS'}}],
      summary:{'1':{f0:{attempted:100,scored:0,failed:100,spearman:metric,pearson:metric}}},perLocus:[],limitations:['Training-source overlap'],checkpoints:[],inferenceSeconds:1}}/>);
    for(const text of ['0 / 100','undefined','not an independent-study test','Training-source overlap','count-scale errors are not reported'])expect(html).toContain(text);
  });
  it('does not replace the negative all-gene result with a selected-gene correlation',()=>{
    const html=renderToStaticMarkup(<ResponseDiagnostics report={{sourceRun:'a',summary:{n:72,donorBeatsControlCases:7,sameLineAcrossPlateMeanPearson:.076,otherPlateSelectedMeanPearson:.565,otherPlateSelectedPairs:71,donorMeanPredictionEnergy:.08,donorMeanTwicePredictionTruthProduct:.058},conditions:[],classification:{unresolved:'Raw controls unavailable'},limitations:[]}}/>);
    expect(html).toContain('7 of 72');expect(html).toContain('do not replace the original all-gene scores');expect(html).toContain('Raw controls unavailable');
  });
});
