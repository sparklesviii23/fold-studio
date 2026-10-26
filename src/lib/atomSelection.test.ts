import {describe,it,expect} from 'vitest';
import {atomPickSelection} from './atomSelection';
describe('native atom picking for measurements',()=>{
 it('retains multiple live atom picks on Shift and replaces on an ordinary click',()=>{const live=new Set(['atom:a','atom:b','atom:c']);const first=atomPickSelection([], 'atom:a',false,live);const second=atomPickSelection(first,'atom:b',true,live);expect(second).toEqual(['atom:a','atom:b']);expect(atomPickSelection(second,'atom:c',true,live)).toEqual(['atom:a','atom:b','atom:c']);expect(atomPickSelection(second,'atom:c',false,live)).toEqual(['atom:c']);});
 it('drops keys from replaced models, avoids duplicate picks and refuses stale atoms',()=>{const live=new Set(['new:1','new:2']);expect(atomPickSelection(['old:1','new:1'],'new:1',true,live)).toEqual(['new:1']);expect(()=>atomPickSelection([],'old:1',false,live)).toThrow('no longer');});
});
