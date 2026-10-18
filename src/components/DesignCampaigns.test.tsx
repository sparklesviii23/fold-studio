import {describe,it,expect,vi} from 'vitest';
import {renderToStaticMarkup} from 'react-dom/server';
vi.mock('../lib/api',()=>({rpc:vi.fn(),chooseDirectory:vi.fn()}));
import DesignCampaigns from './DesignCampaigns';
describe('Project Metal campaign disclosure',()=>{
 it('keeps preparation and scientific execution distinct before data arrives',()=>{const html=renderToStaticMarkup(<DesignCampaigns projectId="test" onClose={()=>{}} onLibraryChange={async()=>{}}/>);expect(html).toContain('Full native design execution is still under validation');expect(html).toContain('Save prepared campaign');expect(html).toContain('observed source numbering');expect(html).not.toContain('Launch design');expect(html).not.toContain('NaN');expect(html).toContain('authentic upstream model on CPU');expect(html).toContain('Redesign selected chains');expect(html).toContain('paired heavy and light chains');});
});
