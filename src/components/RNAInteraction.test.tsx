import {describe,it,expect} from 'vitest';
import {renderToStaticMarkup} from 'react-dom/server';
import RNAInteraction from './RNAInteraction';
describe('supplied RNA pair review',()=>{
 it('requires both supplied sequences and separates review from qualified inference',()=>{
  const html=renderToStaticMarkup(<RNAInteraction onReview={()=>{throw Error('No execution on render');}}/>);
  expect(html).toContain('RNA A');expect(html).toContain('RNA B');expect(html).toContain('each up to 250');expect(html).toContain('must be updated and qualified');expect(html).toContain('does not design or optimize sequences');expect(html).toContain('disabled');
 });
});
