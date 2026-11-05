import {useEffect,useRef,useState} from 'react';
import {Terminal as XTerm} from '@xterm/xterm';
import {FitAddon} from '@xterm/addon-fit';
import {Terminal,Unplug,Maximize2} from 'lucide-react';
import {rpc} from '../../lib/api';
import '@xterm/xterm/css/xterm.css';

type Reply={sessionId:string;data:string;offset:number;closed:boolean;ready:boolean};
const id=()=>crypto.randomUUID().replaceAll('-','');
const encode=(text:string)=>btoa(String.fromCharCode(...new TextEncoder().encode(text)));

export default function ModalTerminal({projectId,taskId,state,log,phase}:{projectId:string;taskId:string;state:string;log?:string;phase?:string}){
 const host=useRef<HTMLDivElement>(null),pre=useRef<HTMLPreElement>(null),[connected,setConnected]=useState(false),[error,setError]=useState(''),[full,setFull]=useState(false);
 const [filter,setFilter]=useState(''),[follow,setFollow]=useState(true);
 const live=state==='running'||state==='launching';
 const lines=(log||'').split('\n'),shown=lines.filter(line=>!filter||line.toLowerCase().includes(filter.toLowerCase()));
 const session=useRef(''),offset=useRef(0),pending=useRef<{eventId:string;data?:string;cols?:number;rows?:number}[]>([]),closing=useRef(false);
 useEffect(()=>{if(follow&&pre.current)pre.current.scrollTop=pre.current.scrollHeight;},[log,follow,filter]);
 useEffect(()=>{if(state!=='running')setConnected(false);},[state]);
 useEffect(()=>{
  if(!connected||!host.current||state!=='running')return;
  let alive=true,ready=false,timer:ReturnType<typeof setTimeout>;closing.current=false;session.current='';offset.current=0;pending.current=[];
  const term=new XTerm({cursorBlink:true,disableStdin:true,convertEol:false,scrollback:10000,fontSize:12,fontFamily:'Menlo, monospace',theme:{background:'#080e18',foreground:'#c9e4df',cursor:'#8dd5c4'}});
  const fit=new FitAddon();term.loadAddon(fit);term.open(host.current);fit.fit();
  const data=term.onData(text=>pending.current.push({eventId:id(),data:encode(text)}));
  const resize=()=>{fit.fit();pending.current.push({eventId:id(),cols:Math.max(20,Math.min(500,term.cols)),rows:Math.max(5,Math.min(200,term.rows))});};
  const observer=new ResizeObserver(resize);observer.observe(host.current);
  async function tick(){
   if(!alive)return;
   const first=!session.current,event=first||!ready?undefined:pending.current[0];
   try{
    const r=await rpc<Reply>('gpu_task_terminal',{projectId,taskId,start:first,approvedRemoteCommand:first,sessionId:session.current||undefined,offset:offset.current,...event});
    if(!alive)return;
    session.current=r.sessionId;offset.current=r.offset;if(event)pending.current.shift();
    if(r.data)term.write(Uint8Array.from(atob(r.data),c=>c.charCodeAt(0)));
    ready=r.ready;term.options.disableStdin=!ready;setError('');
    if(r.closed){term.writeln('\r\n[remote shell closed]');term.options.disableStdin=true;return;}
   }catch(e){if(alive){setError(String(e).replace(/^Error:\s*/,''));term.options.disableStdin=true;}}
   if(alive)timer=setTimeout(()=>void tick(),pending.current.length?80:700);
  }
  void tick();
  return()=>{alive=false;clearTimeout(timer);observer.disconnect();data.dispose();term.dispose();
   if(session.current&&!closing.current)void rpc('gpu_task_terminal',{projectId,taskId,sessionId:session.current,close:true,eventId:id()}).catch(()=>{});
  };
 },[connected,projectId,taskId,state]);
 async function close(){closing.current=true;if(session.current)try{await rpc('gpu_task_terminal',{projectId,taskId,sessionId:session.current,close:true,eventId:id()});}catch(e){setError(String(e));}setConnected(false);}
 return <section className={'bio-terminal '+(full?'expanded':'')}>
  <div className="bio-section-heading"><div><span className="eyebrow"><Terminal size={13}/> {live?'LIVE OUTPUT':'SAVED OUTPUT'}</span><p>{phase??state} · process output; interactive shell has its own scrollback</p></div><div className="button-row"><button className="button" onClick={()=>setFull(!full)}><Maximize2 size={13}/>{full?'Compact':'Expand'}</button>{connected?<button className="button" onClick={()=>void close()}><Unplug size={13}/>Close shell</button>:<button className="button" disabled={state!=='running'} onClick={()=>setConnected(true)}><Terminal size={13}/>Open interactive shell</button>}</div></div>
  <div className="bio-log-controls"><input aria-label="Search terminal output" placeholder="Search output…" value={filter} onChange={e=>setFilter(e.target.value)}/><label><input type="checkbox" checked={follow} onChange={e=>setFollow(e.target.checked)}/>Follow output</label><small>{log?shown.length:0} lines</small></div>
  <pre ref={pre} className="bio-live-log">{shown.join('\n')||(filter?'No matching output.':live?'Waiting for output from Modal…':'No process output was captured.')}</pre>
  {connected&&<><p className="bio-detail">Interactive shell in this running container. Commands can change run files. Ctrl+C, shell state and terminal resizing are supported. Idle shells close after 15 minutes.</p><div ref={host} className="bio-pty"/></>}
  {error&&<p role="alert" className="bio-message error">{error}</p>}
 </section>;
}
