import {describe,it,expect} from 'vitest';
import {renderToStaticMarkup} from 'react-dom/server';
import CrystalFractionalSites from './CrystalFractionalSites';
import {inspectUnitCell} from '../lib/crystalCell';
describe('fractional-site export controls',()=>{
 it('offers genuine translated-site exports only with reported fractional inputs',async()=>{
  const header='data_test\n_cell.length_a 2\n_cell.length_b 3\n_cell.length_c 4\n_cell.angle_alpha 90\n_cell.angle_beta 90\n_cell.angle_gamma 90\n';
  const empty=await inspectUnitCell(header);expect(renderToStaticMarkup(<CrystalFractionalSites cell={empty} onError={()=>{}}/>)).toContain('not converted implicitly');
  const cell=await inspectUnitCell(header+'loop_\n_atom_site.label\n_atom_site.type_symbol\n_atom_site.fract_x\n_atom_site.fract_y\n_atom_site.fract_z\nSite C 0 0 0\n');
  const html=renderToStaticMarkup(<CrystalFractionalSites cell={cell} onError={()=>{}}/>);
  expect(html).toContain('1');expect(html).toContain('reported atom sites');expect(html).toContain('Copies along');expect(html).toContain('coordinates · CIF');expect(html).toContain('provenance · JSON');expect(html).toContain('No space-group operations');
 });
});
