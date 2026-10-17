import { describe, expect, it } from 'vitest';
import { angle, contacts, dihedral, distance } from './geometry';
import { constrainPanel } from '../components/GlassPanel';
import type { AtomRecord } from './types';
describe('coordinate geometry',()=>{
 it('measures a 3–4–5 triangle in source coordinate units',()=>expect(distance([0,0,0],[3,4,0])).toBe(5));
 it('calculates right and straight angles',()=>{expect(angle([1,0,0],[0,0,0],[0,1,0])).toBe(90);expect(angle([1,0,0],[0,0,0],[-1,0,0])).toBe(180);});
 it('preserves the sign of a known dihedral',()=>{expect(dihedral([1,0,0],[0,0,0],[0,1,0],[0,1,1])).toBe(-90);expect(dihedral([1,0,0],[0,0,0],[0,1,0],[0,1,-1])).toBe(90);});
 it('rejects undefined angles and dihedrals',()=>{expect(()=>angle([0,0,0],[0,0,0],[1,0,0])).toThrow();expect(()=>dihedral([0,0,0],[1,0,0],[2,0,0],[3,0,0])).toThrow();});
 it('finds actual neighbors and excludes the selected atom',()=>{const atoms=[{key:'a',xyz:[0,0,0]},{key:'b',xyz:[3,4,0]},{key:'c',xyz:[6,0,0]}] as AtomRecord[];expect(contacts(atoms,[atoms[0]],5).map(x=>[x.atom.key,x.distance])).toEqual([['b',5]]);expect(contacts(atoms,[],5)).toEqual([]);});
 it('keeps a panel reachable after a display resolution changes',()=>{const panel=constrainPanel({id:'atoms',x:2000,y:1400,width:900,height:900,mode:'floating',pin:false,z:1},1024,720);expect(panel.x+panel.width).toBeLessThanOrEqual(1024);expect(panel.y+panel.height).toBeLessThanOrEqual(720);expect(panel.x).toBeGreaterThanOrEqual(12);expect(panel.y).toBeGreaterThanOrEqual(74);});
});
