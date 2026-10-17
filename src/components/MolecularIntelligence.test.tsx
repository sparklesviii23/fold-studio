import {describe,it,expect,vi} from 'vitest';
import {renderToStaticMarkup} from 'react-dom/server';
vi.mock('./MolecularViewer',()=>({default:()=>null}));
import MolecularIntelligence from './MolecularIntelligence';
const props={projectId:'project',item:null,library:{projects:[],records:[],jobs:[],settings:{}},atoms:[],loadedId:'',viewer:{current:null},onOpen:async()=>{},onImport:()=>{},onRefresh:async()=>{},onError:()=>{}};
describe('Molecular Intelligence startup',()=>{
 it('allows the rest of the app to start before a structure or analysis exists',()=>{expect(renderToStaticMarkup(<MolecularIntelligence {...props} visible={false}/>)).toBe('');});
 it('shows an actionable empty inspector without inventing measurements',()=>{const html=renderToStaticMarkup(<MolecularIntelligence {...props} visible/>);expect(html).toContain('Import or select a structure');expect(html).toContain('Confidence unavailable');expect(html).toContain('Analyze prediction');expect(html).not.toContain('NaN');expect(html).toContain('Research Reports');});
});
