import {useState} from 'react';
import {exportFile} from '../lib/api';

export interface NotebookVersion {
 id:string;projectId:string;kind:string;name:string;version:number;parentVersion:number|null;
 created:string;sha256:string;data:Record<string,any>;
}
export function notebookVersions(versions:NotebookVersion[],projectId:string,id?:string){
 return versions.filter(v=>v.projectId===projectId&&v.kind==='notebook'&&(!id||v.id===id)).slice().sort((a,b)=>b.version-a.version||b.created.localeCompare(a.created));
}
export function searchNotebook(versions:NotebookVersion[],projectId:string,query:string,includeHistory=false){
 const ordered=notebookVersions(versions,projectId),latest=new Map<string,NotebookVersion>();
 for(const version of ordered)if(!latest.has(version.id))latest.set(version.id,version);
 const q=query.trim().toLocaleLowerCase();
 return (includeHistory?ordered:[...latest.values()]).filter(v=>!q||[v.name,v.id,JSON.stringify(v.data)].join(' ').toLocaleLowerCase().includes(q));
}
export function notebookVersionExport(version:NotebookVersion,projectId:string){
 if(version.projectId!==projectId||version.kind!=='notebook')throw Error('Choose a notebook version from this project.');
 return JSON.stringify({schemaVersion:1,kind:'saved_notebook_version',version,scope:'Original saved notebook version and recorded data checksum. Researcher notes and attributed citations are not independently verified scientific evidence.'},null,2);
}
export function notebookHistoryExport(versions:NotebookVersion[],projectId:string,id:string){
 const saved=notebookVersions(versions,projectId,id);
 if(!saved.length)throw Error('Choose an existing notebook identity in this project.');
 return JSON.stringify({schemaVersion:1,kind:'saved_notebook_history',projectId,noteId:id,versions:saved,scope:'All locally returned saved versions of this notebook identity. Original data and recorded checksums are retained; this is not independent verification of note contents or citations.'},null,2);
}
export function notebookMarkdown(version:NotebookVersion,projectId:string){
 notebookVersionExport(version,projectId);
 const citations=Array.isArray(version.data.citations)?version.data.citations:version.data.citations===undefined?[]:[version.data.citations];
 return `# ${version.name}\n\nProject: ${version.projectId}\nNote: ${version.id} · version ${version.version}\nCreated: ${version.created}\nRecorded data SHA-256: ${version.sha256}\n\n${typeof version.data.markdown==='string'?version.data.markdown:'```json\n'+JSON.stringify(version.data,null,2)+'\n```'}\n\n`+(citations.length?'## Attributed citations\n\n'+citations.map((c:any)=>'- '+referenceText(c)).join('\n')+'\n\n':'')+'Research notes and citations retain their original attribution; external sources were not fetched or independently verified.\n';
}
const referenceText=(value:any):string=>typeof value==='string'?value:value&&typeof value==='object'?(typeof value.text==='string'?value.text:JSON.stringify(value)):JSON.stringify(value)??'';
const citationText=(data:Record<string,any>)=>Array.isArray(data.citations)?data.citations.map(referenceText).join('\n'):data.citations===undefined?'':referenceText(data.citations);
export default function EditCraftNotebook({projectId,versions,busy,onSave}:{projectId:string;versions:NotebookVersion[];busy:boolean;onSave:(payload:any)=>Promise<NotebookVersion|null|undefined>}){
 const [query,setQuery]=useState(''),[history,setHistory]=useState(false),[page,setPage]=useState(0),[note,setNote]=useState<NotebookVersion|null>(null),[title,setTitle]=useState('Research observation'),[body,setBody]=useState(''),[citations,setCitations]=useState(''),[error,setError]=useState('');
 const notes=searchNotebook(versions,projectId,query,history);
 const pageSize=25,currentPage=Math.min(page,Math.max(0,Math.ceil(notes.length/pageSize)-1)),visible=notes.slice(currentPage*pageSize,(currentPage+1)*pageSize);
 function edit(source:NotebookVersion){const latest=notebookVersions(versions,projectId,source.id)[0];setNote(latest);setTitle(source.name);setBody(typeof source.data.markdown==='string'?source.data.markdown:'');setCitations(citationText(source.data));setError('');}
 function clean(){setNote(null);setTitle('Research observation');setBody('');setCitations('');setError('');}
 async function save(){try{
  const data:Record<string,any>={...(note?.data??{}),markdown:body,evidence:'researcher_annotation'};
  if(!note||citations!==citationText(note.data))data.citations=citations.split(/\r?\n/).map(text=>text.trim()).filter(Boolean).map(text=>({text}));
  const result=await onSave({id:note?.id,parentVersion:note?.version,name:title.trim(),data});
  if(result)setNote(result);
 }catch(e){setError(String(e));}}
 function exports(version:NotebookVersion){const filename=`fold-notebook-${version.id.replace(/[^a-z\d_-]/gi,'_')}-v${version.version}`;return <><button className="button" onClick={()=>exportFile(filename+'.json',{text:notebookVersionExport(version,projectId)}).catch(e=>setError(String(e)))}>Export exact version · JSON</button><button className="button" onClick={()=>exportFile(filename+'.md',{text:notebookMarkdown(version,projectId)}).catch(e=>setError(String(e)))}>Export note · Markdown</button></>;}
 return <article className="ec-card"><h2>Scientific notebook</h2><p>Append a research note or save a new version. Original versions and linked experiment metadata are retained.</p>
 <label>Title<input maxLength={200} value={title} onChange={e=>setTitle(e.target.value)}/></label><label>Research notes · Markdown<textarea rows={14} value={body} onChange={e=>setBody(e.target.value)} placeholder="Objective, hypothesis, observations, sources, interpretation and next questions"/></label><label>Attributed citations · one per line<textarea rows={3} value={citations} onChange={e=>setCitations(e.target.value)} placeholder="Citation text, DOI or URL; sources are not automatically verified"/></label>
 <div className="button-row"><button className="button primary" disabled={busy||!body.trim()||!title.trim()} onClick={()=>void save()}>Save {note?'new version':'note'}</button><button className="button" disabled={busy} onClick={clean}>New note</button></div>{note&&<p className="caption">Editing {note.id} from latest version {note.version}. Saving appends a new version; conflicting newer edits are rejected.</p>}{error&&<p className="error" role="alert">{error}</p>}
 <label>Find a notebook record<input value={query} onChange={e=>{setQuery(e.target.value);setPage(0);}} placeholder="Title, content, citation or note identity"/></label><label className="checkbox-label"><input type="checkbox" checked={history} onChange={e=>{setHistory(e.target.checked);setPage(0);}}/>Search historical versions too</label><p className="caption">Search is local to this project's saved notebook records. {notes.length} matching {history?'versions':'latest notes'}. Up to 25 records are displayed per page.</p>
 <div className="button-row"><button className="button" disabled={currentPage===0} onClick={()=>setPage(currentPage-1)}>Previous notebook page</button><span>Page {currentPage+1} of {Math.max(1,Math.ceil(notes.length/pageSize))}</span><button className="button" disabled={(currentPage+1)*pageSize>=notes.length} onClick={()=>setPage(currentPage+1)}>Next notebook page</button></div>
 {visible.map(version=><details className="ec-record" key={version.id+':'+version.version}><summary>{version.name} · v{version.version}</summary><p className="caption">{version.created} · recorded data SHA-256 {version.sha256}</p><pre className="ec-output">{typeof version.data.markdown==='string'?version.data.markdown:JSON.stringify(version.data,null,2)}</pre>{version.data.citations&&<pre className="ec-output">{JSON.stringify(version.data.citations,null,2)}</pre>}<button className="button" disabled={busy} onClick={()=>edit(version)}>Use this text in a new version</button>{exports(version)}<details><summary>Version history · {notebookVersions(versions,projectId,version.id).length} saved versions</summary><p className="caption">Showing the 50 most recent versions here. Search historical versions or export the full saved history to inspect earlier entries.</p><button className="button" onClick={()=>exportFile(`fold-notebook-history-${version.id.replace(/[^a-z\d_-]/gi,'_')}.json`,{text:notebookHistoryExport(versions,projectId,version.id)}).catch(e=>setError(String(e)))}>Export complete saved history · JSON</button>{notebookVersions(versions,projectId,version.id).slice(0,50).map(old=><div key={old.version}><p>{old.name} · v{old.version} · {old.created}</p><pre className="ec-output">{typeof old.data.markdown==='string'?old.data.markdown:JSON.stringify(old.data,null,2)}</pre><button className="button" disabled={busy} onClick={()=>edit(old)}>Use v{old.version} text in a new version</button>{exports(old)}</div>)}</details></details>)}{!notes.length&&<p>No matching notebook records in this project.</p>}
 </article>;
}
