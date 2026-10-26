import {describe,it,expect,vi} from 'vitest';
import {renderToStaticMarkup} from 'react-dom/server';
import FabCampaignControls from './FabCampaignControls';
import {resumeEligibility} from '../lib/architect';
describe('cloud-only Fab controls',()=>{
 it('retains saved data and offers cloud configuration without any local launch',()=>{
  const job:any={state:'prepared',data:{preparation:{modality:'Fab'}}};const html=renderToStaticMarkup(<FabCampaignControls job={job} busy={false} onCloud={vi.fn()}/>);
  expect(html).toContain('Full Fab is cloud-only');expect(html).toContain('Configure Fab in Cloud Compute');expect(html).not.toContain('Start full Fab');
 });
 it('never offers local recovery for cancelled Fab but preserves smaller protein recovery',()=>{
  const job:any={state:'cancelled',data:{profile:'experimental-cpu-fab-amme',preparation:{modality:'Fab',config:{max_trajectories:2}},executionProgress:{trajectory:1}}};expect(resumeEligibility(job)).toBe(false);job.data.profile='experimental-cpu-float32-ensemble';job.data.preparation.modality='binder';expect(resumeEligibility(job)).toBe(true);
 });
});
