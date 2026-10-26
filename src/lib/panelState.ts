import type {PanelState} from '../components/GlassPanel';
import {tools, type ToolId} from './tools';

const openModes = ['floating', 'left', 'right', 'bottom'] as const;
export function restoredMode(mode: unknown): 'floating'|'left'|'right'|'bottom' {
  return openModes.includes(mode as any) ? mode as ReturnType<typeof restoredMode> : 'floating';
}
export function defaultPanels(): PanelState[] {
  return tools.map((tool, i) => ({id:tool.id, x:550, y:86+i*8, width:['console','python'].includes(tool.id)?760:['tools','analysis','imaging','editing','biology'].includes(tool.id)?500:400, height:tool.id==='console'?380:560, mode:'hidden', pin:false, z:2}));
}
export function restorePanels(value: unknown): PanelState[] {
  const saved = Array.isArray(value) ? value : [];
  return defaultPanels().map(fallback => {
    const panel = saved.find(p => p && p.id===fallback.id);
    if (!panel || !['floating','left','right','bottom','minimized','hidden','detached'].includes(panel.mode) || ![panel.x,panel.y,panel.width,panel.height,panel.z].every(Number.isFinite)) return fallback;
    return {...fallback,...panel, width:Math.max(['console','python'].includes(panel.id)?440:340,panel.width), pin:panel.pin===true, mode:panel.mode==='detached'?'hidden':panel.mode, lastMode:restoredMode(panel.lastMode), z:2};
  });
}
export function ensurePanel(panels: PanelState[], id: ToolId): PanelState[] {
  return panels.some(panel=>panel.id===id) ? panels : [...panels, defaultPanels().find(panel=>panel.id===id)!];
}
