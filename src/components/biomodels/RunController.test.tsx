import {describe,it,expect,vi} from 'vitest';
import {renderToStaticMarkup} from 'react-dom/server';
import RunController,{RunTimeline,runOutput,liveRun,type RunRecord} from './RunController';
import ModalTerminal from './ModalTerminal';
vi.mock('@xterm/xterm',()=>({Terminal:class {}}));
vi.mock('@xterm/addon-fit',()=>({FitAddon:class {}}));
const task:RunRecord={id:'a'.repeat(32),title:'Borzoi evaluation',recipe:'bio_borzoi_panel',state:'failed',created:'2026-11-05T01:26:01Z',launched:1793841961,finished:'2026-11-05T02:00:00Z',timeout:2700,returncode:1,stdout:'[fold] fresh inference reproduction passed\nHTTP Error 400',outputs:[{path:'reproduction.json',bytes:100,sha256:'b'.repeat(64)}]};
describe('Run controller',()=>{
 it('retains a failed run, its terminal output and the full lifecycle',()=>{
  const html=renderToStaticMarkup(<RunController task={task} projectId="project" busy={false} autoRefresh={true} onAutoRefresh={()=>{}} onRefresh={async()=>{}} onRead={async()=>{}} onStop={async()=>{}} onRetryDownload={async()=>{}}/>);
  for(const text of ['Failed','Submitted','Container launched','Files returned','45 min runtime limit','Exit code:','SAVED OUTPUT','HTTP Error 400','Commands','Activity','Export log'])expect(html).toContain(text);
  expect(html).not.toContain('Stop run');expect(html).not.toContain('Waiting for output');
 });
 it('does not invent a launch time for a rejected request',()=>{
  const html=renderToStaticMarkup(<RunTimeline task={{...task,launched:undefined,finished:undefined,outputs:[]}}/>);
  expect(html).toContain('Pending');expect(html).toContain('Time not recorded');expect(html).toContain('0 saved files');
 });
 it('keeps completed output searchable and identifies live states',()=>{
  const html=renderToStaticMarkup(<ModalTerminal projectId="p" taskId={task.id} state="done" log="Saved result"/>);
  expect(html).toContain('Search terminal output');expect(html).toContain('Follow output');expect(html).toContain('SAVED OUTPUT');
  expect(liveRun('running')).toBe(true);expect(liveRun('done')).toBe(false);
 });
 it('redacts familiar credential patterns before display/export',()=>{
  expect(runOutput({...task,stdout:'api_key=private-value',stderr:''})).not.toContain('private-value');
 });
});
