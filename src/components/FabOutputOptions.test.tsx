import {describe,it,expect} from 'vitest';
import {renderToStaticMarkup} from 'react-dom/server';
import FabOutputOptions,{fabOutputOptions} from './FabOutputOptions';

describe('Fab trajectory output choices',()=>{
 it('records final-pose retention in a new Fab recipe without modifying input options',()=>{
  const original={design_recycles:1,save_failed_trajectories:false};
  expect(fabOutputOptions('Fab',original)).toEqual({save_design_trajectory:true,save_failed_trajectories:false,design_recycles:1});
  expect(original).toEqual({design_recycles:1,save_failed_trajectories:false});
  expect(fabOutputOptions('Fab',{save_design_trajectory:false})).toEqual({save_design_trajectory:false,save_failed_trajectories:true});
  expect(fabOutputOptions('binder',original)).toBe(original);
 });
 it('shows the effective saved output choice and preserves the existing-campaign distinction',()=>{
  const html=renderToStaticMarkup(<FabOutputOptions options={fabOutputOptions('Fab',{})} disabled={false} onChange={()=>{}}/>);
  expect(html).toContain('checked');expect(html).toContain('including rejected attempts');expect(html).toContain('Existing campaigns keep their saved choices.');
  const off=renderToStaticMarkup(<FabOutputOptions options={fabOutputOptions('Fab',{save_design_trajectory:false})} disabled onChange={()=>{}}/>);
  expect(off).not.toContain('checked');expect(off).toContain('disabled');
 });
});
