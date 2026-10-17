import {useEffect,useRef,type ReactNode} from 'react';

export default function Dialog({children,onClose,label,className=''}:{children:ReactNode;onClose:()=>void;label:string;className?:string}) {
  const ref=useRef<HTMLDivElement>(null),close=useRef(onClose);close.current=onClose;
  useEffect(()=>{
    const previous=document.activeElement as HTMLElement|null;
    const panel=ref.current!;
    const focusable=()=>Array.from(panel.querySelectorAll<HTMLElement>('button:not(:disabled),input:not(:disabled),select:not(:disabled),textarea:not(:disabled),[tabindex="0"]')).filter(el=>el.getClientRects().length);
    (panel.querySelector<HTMLElement>('[autofocus]')??focusable()[0]??panel).focus();
    const key=(e:KeyboardEvent)=>{if(e.key==='Escape'){e.preventDefault();e.stopPropagation();close.current();}if(e.key==='Tab'){const all=focusable(),first=all[0],last=all.at(-1);if(!first){e.preventDefault();panel.focus();}else if(e.shiftKey&&(document.activeElement===first||document.activeElement===panel)){e.preventDefault();last?.focus();}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first.focus();}}};
    panel.addEventListener('keydown',key);return()=>{panel.removeEventListener('keydown',key);previous?.focus();};
  },[]);
  return <div className="modal-backdrop"><div ref={ref} role="dialog" aria-modal="true" aria-label={label} tabIndex={-1} className={'modal '+className}>{children}</div></div>;
}
