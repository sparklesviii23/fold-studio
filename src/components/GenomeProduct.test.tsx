import {describe,it,expect} from 'vitest';
import {renderToStaticMarkup} from 'react-dom/server';
import GenomeProduct from './GenomeProduct';
describe('annotated product controls',()=>{
 it('requires explicit translation choice and does not infer a protein from a gene interval',()=>{
  const props={projectId:'p',interval:{referenceId:'r',feature:{index:1,type:'CDS'}},onRNA:()=>{throw Error('No execution on render');}};
  const html=renderToStaticMarkup(<GenomeProduct {...props}/>);expect(html).toContain('Assemble coding DNA only');expect(html).toContain('Require a complete CDS');expect(html).toContain('Assemble annotated segments');
  expect(renderToStaticMarkup(<GenomeProduct {...props} interval={{...props.interval,feature:{index:1,type:'gene'}}}/>)).toBe('');
 });
});
