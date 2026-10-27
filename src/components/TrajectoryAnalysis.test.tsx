import {describe,it,expect} from 'vitest';
import {renderToStaticMarkup} from 'react-dom/server';
import {FrameMotionTable} from './TrajectoryAnalysis';
describe('saved trajectory frame metrics',()=>{
 it('shows per-frame Cα gyration with explicit units, time and calculation scope',()=>{
  const html=renderToStaticMarkup(<FrameMotionTable result={{frameIds:[1,2],physicalTimePs:[0,.25],rmsdAngstrom:[0,3],radiusOfGyrationAngstrom:[2,2],radiusOfGyrationMethod:'Equal Cα mass weights; excludes solvent.'}}/>);
  expect(html).toContain('Cα radius of gyration · Å');expect(html).toContain('2.0000');expect(html).toContain('0.2500');expect(html).toContain('excludes solvent');
 });
 it('does not invent gyration or physical time for older saved results',()=>{
  const html=renderToStaticMarkup(<FrameMotionTable result={{frameIds:[1,2],rmsdAngstrom:[0,3]}}/>);
  expect(html).not.toContain('gyration');expect(html).not.toContain('Time · ps');expect(html).toContain('3.0000');
 });
});
