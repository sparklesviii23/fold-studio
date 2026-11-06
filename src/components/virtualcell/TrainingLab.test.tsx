import {describe,it,expect} from 'vitest';
import {renderToStaticMarkup} from 'react-dom/server';
import TrainingLab,{TrainingOverview} from './TrainingLab';
describe('Cell training workspace',()=>{
  it('shows real split counts and retains missing independent pair-test qualification',()=>{
    const textLengths=Object.fromEntries(['pair','drug','inhibition'].flatMap(task=>['train','validation',...(task==='pair'?[]:['test'])].map(part=>[task+'_'+part,{conditions:part==='train'?512:64}])));
    const html=renderToStaticMarkup(<TrainingOverview experiment={{data:{distinctTrainingCells:10000,featureWidth:518,textLengths,units:{pair:'RNA units',drug:'log2 fold change',inhibition:'RNA units'},heldoutContexts:['A','B']}}}/>);
    expect(html).toContain('10,000');expect(html).toContain('No fresh pair test');expect(html).toContain('Final answers stay');expect(html).toContain('log2 fold change');expect(html).toContain('Unavailable'.toLowerCase());
  });
  it('renders without starting computation or offering an unreviewed paid start',()=>{
    const html=renderToStaticMarkup(<TrainingLab projectId="fixture" onOpenRuns={()=>{}}/>);
    expect(html).toContain('Teach the model');expect(html).toContain('Reading saved experiments');expect(html).not.toContain('Start approved attempt');
  });
});
