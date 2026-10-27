import {describe,it,expect} from 'vitest';
import {renderToStaticMarkup} from 'react-dom/server';
import CrystalCellInspection from './CrystalCellInspection';
import type {Item} from '../lib/types';
describe('native library unit-cell inspection route',()=>{
 it('offers read-only inspection for saved mmCIF structures, with no invented initial geometry',()=>{
  const item:Item={id:'structure-1',project_id:'project-1',kind:'structure',name:'Reference',data:{format:'mmcif',asset:'saved.cif',sha256:'a'.repeat(64)}};
  const html=renderToStaticMarkup(<CrystalCellInspection item={item}/>);
  expect(html).toContain('Inspect reported cell');expect(html).toContain('Predicted structures may have no');expect(html).not.toContain('Calculated cell volume');
  expect(renderToStaticMarkup(<CrystalCellInspection item={{...item,data:{format:'pdb',asset:'saved.pdb'}}}/>)).toBe('');
 });
});
