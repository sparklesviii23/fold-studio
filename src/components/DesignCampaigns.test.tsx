import {describe,it,expect,vi} from 'vitest';
import {renderToStaticMarkup} from 'react-dom/server';
vi.mock('../lib/api',()=>({rpc:vi.fn(),chooseDirectory:vi.fn()}));
import DesignCampaigns from './DesignCampaigns';
describe('BindCraft Architect workspace',()=>{
 it('exposes five persistent sections and separates preparing from running',()=>{const html=renderToStaticMarkup(<DesignCampaigns projectId="test" onLibraryChange={async()=>{}}/>);for(const label of ['Overview','Target &amp; Design','Scientific Settings','Compute &amp; Run','Campaign Library'])expect(html).toContain(label);expect(html).toContain('Save prepared campaign');expect(html).toContain('starts no calculation');expect(html).toContain('Original scientific options');expect(html).not.toContain('role="dialog"');expect(html).not.toContain('Construct sequence');expect(html).not.toContain('Connect chain');});
 it('makes empty selection semantics and experimental status visible',()=>{const html=renderToStaticMarkup(<DesignCampaigns projectId="test" onLibraryChange={async()=>{}}/>);expect(html).toContain('Leave empty to redesign all eligible residues');expect(html).toContain('No exclusions selected');expect(html).toContain('Clear All Exclusions');expect(html).toContain('Resource limited');expect(html).toContain('Cloud-only');expect(html).not.toContain('Full Fab protected CPU');});
});
