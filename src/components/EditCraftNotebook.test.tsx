import {describe,it,expect} from 'vitest';
import {renderToStaticMarkup} from 'react-dom/server';
import EditCraftNotebook,{notebookVersions,searchNotebook,notebookVersionExport,notebookHistoryExport,notebookMarkdown,type NotebookVersion} from './EditCraftNotebook';
const version=(projectId:string,id:string,revision:number,data:any,name='Research note'):NotebookVersion=>({projectId,id,version:revision,kind:'notebook',name,parentVersion:revision>1?revision-1:null,created:`2026-10-${20+revision}`,sha256:'a'.repeat(64),data});
const versions=[version('project-a','note',1,{markdown:'Original observation',experimentId:'exp-original',citations:[{text:'Original DOI source'}]}),version('project-a','note',2,{markdown:'Corrected interpretation',experimentId:'exp-original'}),version('project-b','note-private',1,{markdown:'Private project observation'})];
describe('project-scoped scientific notebook',()=>{
 it('searches latest notes by default and historical text only when requested',()=>{
  const before=JSON.stringify(versions);
  expect(searchNotebook(versions,'project-a','')).toHaveLength(1);
  expect(searchNotebook(versions,'project-a','original')).toHaveLength(1); // linked experiment identity remains searchable
  expect(searchNotebook(versions,'project-a','Original observation')).toHaveLength(0);
  expect(searchNotebook(versions,'project-a','Original DOI',true).map(v=>v.version)).toEqual([1]);
  expect(searchNotebook(versions,'project-a','private',true)).toEqual([]);
  expect(notebookVersions(versions,'project-a','note').map(v=>v.version)).toEqual([2,1]);
  expect(JSON.stringify(versions)).toBe(before);
 });
 it('exports the exact chosen immutable version with citations and original metadata',()=>{
  const payload=JSON.parse(notebookVersionExport(versions[0],'project-a'));
  expect(payload.version).toEqual(versions[0]);expect(payload.scope).toContain('not independently verified');
  const markdown=notebookMarkdown(versions[0],'project-a');
  expect(markdown).toContain('Original observation');expect(markdown).toContain('Original DOI source');expect(markdown).toContain('version 1');expect(markdown).toContain(versions[0].sha256);
  expect(()=>notebookVersionExport(versions[2],'project-a')).toThrow('this project');
  const archive=JSON.parse(notebookHistoryExport(versions,'project-a','note'));
  expect(archive.versions).toEqual([versions[1],versions[0]]);expect(archive.noteId).toBe('note');expect(()=>notebookHistoryExport(versions,'project-a','note-private')).toThrow('this project');
  expect(notebookMarkdown({...versions[0],data:{markdown:'Legacy note',citations:'Original free-text source'}},'project-a')).toContain('Original free-text source');
  expect(notebookMarkdown({...versions[0],data:{markdown:'Legacy note',citations:[null,{doi:'10.test/original'}]}},'project-a')).toContain('10.test/original');
 });
 it('shows native save/search/history/export controls and never exposes another project',()=>{
  const html=renderToStaticMarkup(<EditCraftNotebook projectId="project-a" versions={versions} busy={false} onSave={async()=>null}/>);
  expect(html).toContain('Search historical versions too');expect(html).toContain('Version history');expect(html).toContain('Export exact version');expect(html).toContain('Attributed citations');expect(html).toContain('Use v1 text in a new version');expect(html).not.toContain('Private project observation');
 });
});
