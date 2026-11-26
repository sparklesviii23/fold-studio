import {useEffect,useRef,useState} from 'react';
import {isTauri} from '@tauri-apps/api/core';
import {emitTo,listen} from '@tauri-apps/api/event';
import {getCurrentWindow} from '@tauri-apps/api/window';
import {rpc} from '../lib/api';
import type {Library} from '../lib/types';
import {restoreBounds,trackBounds} from './nativeState';
import WindowChrome from '../components/WindowChrome';
import MolecularGame,{type GameHandle} from './MolecularGame';
export default function ArcadeWindow(){
 const requested=new URLSearchParams(location.search).get('project')??'';
 const [projectId,setProjectId]=useState(requested),[projects,setProjects]=useState<Library['projects']>([]),[error,setError]=useState(''),[ready,setReady]=useState(false),[listening,setListening]=useState(false);
 const current=useRef(projectId),game=useRef<GameHandle>(null);current.current=projectId;
 async function change(next:string){if(next===current.current)return;await game.current?.flush();if(next&&!projects.some(p=>p.id===next))throw new Error('That project is unavailable. Arcade kept its current context.');setProjectId(next);current.current=next;const url=new URL(location.href);url.searchParams.set('project',next);history.replaceState(null,'',url);}
 const changeRef=useRef(change);changeRef.current=change;
 useEffect(()=>{let disposed=false;rpc<Library>('library').then(l=>{if(disposed)return;setProjects(l.projects);if(requested&&!l.projects.some(p=>p.id===requested)){setProjectId('');setError('Requested project is unavailable. Opened clearly labeled local practice.');}setReady(true);}).catch(e=>setError(String(e)));return()=>{disposed=true;};},[]);
 useEffect(()=>{let disposed=false;const stops:(()=>void)[]=[];const add=(stop:()=>void)=>disposed?stop():stops.push(stop);let closing=false;
 const receive=async(payload:any)=>{let error:string|undefined;try{await changeRef.current(payload.projectId??'');}catch(e){error=String(e);setError(error);}const result={requestId:payload.requestId,error};if(isTauri())await emitTo('main','fold-arcade-context-result',result);else localStorage.setItem('fold-arcade-context-result',JSON.stringify(result));};
 const storage=(e:StorageEvent)=>{if(e.key==='fold-arcade-context')try{receive(JSON.parse(e.newValue??'null'));}catch{}};
 if(isTauri()){
  restoreBounds().then(()=>trackBounds()).then(add).catch(e=>setError('Window bounds could not be restored: '+String(e)));
  listen<any>('fold-arcade-context',e=>receive(e.payload)).then(stop=>{add(stop);if(!disposed)setListening(true);}).catch(e=>setError(String(e)));
  getCurrentWindow().onCloseRequested(async event=>{if(closing)return;event.preventDefault();try{await game.current?.flush();closing=true;await getCurrentWindow().close();}catch(e){const recovered=game.current?.hasRecovery();setError('Saving failed: '+String(e)+(recovered?'. Local recovery retained; close again to use that snapshot.':'. No local recovery snapshot; keep this window open and retry saving.'));closing=!!recovered;}}).then(add).catch(e=>setError(String(e)));
 }else window.addEventListener('storage',storage);
 return()=>{disposed=true;stops.forEach(stop=>stop());window.removeEventListener('storage',storage);};
 },[]);
 useEffect(()=>{if(ready&&listening&&isTauri())emitTo('main','fold-arcade-ready',{projectId:current.current}).catch(e=>setError(String(e)));},[ready,listening]);
 const projectName=projects.find(p=>p.id===projectId)?.name??'Local practice';
 useEffect(()=>{document.title='Molecular Arcade · '+projectName;},[projectName]);
 return <div className="arcade-native-shell"><WindowChrome title="Molecular Arcade" subtitle="fold"><select aria-label="Arcade project context" value={projectId} onChange={e=>change(e.target.value).catch(e=>setError(String(e)))}><option value="">Local practice</option>{projects.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</select></WindowChrome>{error&&<div className="arcade-window-error" role="alert">{error}<button onClick={()=>setError('')}>Dismiss</button></div>}{ready?<MolecularGame ref={game} key={projectId||'local-practice'} projectId={projectId} projectName={projectName}/>:<div className="game-loading"><h1>Molecular Arcade</h1><p>{error||'Opening local practice…'}</p></div>}</div>;
}
