import {describe,it,expect} from 'vitest';
import {defaultPanels,ensurePanel,restorePanels,restoredMode} from './panelState';
import {tools} from './tools';

describe('Scientific tool panel recovery',()=>{
 it('restores a usable panel for every tool from empty or missing settings',()=>{
  for(const saved of [null,[],{}]) expect(restorePanels(saved).map(p=>p.id)).toEqual(tools.map(t=>t.id));
 });
 it('adds newly introduced tools without losing an existing arrangement',()=>{
  const prior={...defaultPanels()[0],x:123,mode:'left' as const,pin:true};
  const restored=restorePanels([prior]);expect(restored).toHaveLength(tools.length);expect(restored[0]).toMatchObject({x:123,mode:'left',pin:true});
 });
 it('never restores a hidden or minimized state as the opening destination',()=>{
  for(const lastMode of ['hidden','minimized','detached','unknown',null]) expect(restoredMode(lastMode)).toBe('floating');
  expect(restoredMode('bottom')).toBe('bottom');
 });
 it('can open any tool even after an empty arrangement is applied at runtime',()=>{
  for(const tool of tools){const panels=ensurePanel([],tool.id);expect(panels).toHaveLength(1);expect(panels[0].id).toBe(tool.id);expect(ensurePanel(panels,tool.id)).toBe(panels);}
 });
 it('ignores malformed stored panels and safely reattaches detached tools',()=>{
  const panels=defaultPanels();expect(restorePanels([{...panels[0],width:NaN}])[0]).toEqual(panels[0]);
  expect(restorePanels([{...panels[0],mode:'detached'}])[0].mode).toBe('hidden');
 });
});
