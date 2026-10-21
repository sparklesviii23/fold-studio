import {describe,it,expect} from 'vitest';
import {renderToStaticMarkup} from 'react-dom/server';
import CampaignCoordinates from './CampaignCoordinates';

const entry={file:'2_Refolded/Complexes/rejected.cif',sha256:'a'.repeat(64),bytes:4000};
describe('saved stage coordinate inspection',()=>{
 it('offers the existing library route without presenting a preview as accepted',()=>{const html=renderToStaticMarkup(<CampaignCoordinates entries={[entry]} enabled busy={false} onSave={()=>{}}/>);expect(html).toContain('Save structure to library');expect(html).toContain('preserves its recorded outcome');expect(html).toContain('does not add an accepted design');expect(html).not.toContain('disabled');});
 it('does not offer nonexistent coordinates or allow a live-file snapshot',()=>{expect(renderToStaticMarkup(<CampaignCoordinates entries={[]} enabled busy={false} onSave={()=>{}}/>)).toBe('');const html=renderToStaticMarkup(<CampaignCoordinates entries={[entry]} enabled={false} busy={false} onSave={()=>{}}/>);expect(html).toContain('disabled');expect(html).toContain('after this campaign finishes or stops');});
});
