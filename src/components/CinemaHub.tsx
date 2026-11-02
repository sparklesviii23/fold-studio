import {useMemo, useState, type ReactNode} from 'react';
import BindingStory from './BindingStory';
import type {AtomRecord} from '../lib/types';
import '../cell/cell.css';

/** Molecular Cinema: the illustrated 2D binding story beside the existing 3D film tools. */
export default function CinemaHub({atoms, name, film}: {atoms: AtomRecord[]; name: string; film: ReactNode}) {
  const [tab, setTab] = useState<'story'|'film'>('story');
  const trace = useMemo(() => atoms.map(a => ({xyz: a.xyz, chain: a.authChain || a.chain, atomName: a.atomName})), [atoms]);
  return <div className="cinema-hub">
    <header className="cell-heading">
      <div><span className="eyebrow">Visualise · Molecular Cinema</span><h1>{tab === 'story' ? <>Watch it <em>find its partner.</em></> : <>Films of <em>your molecules.</em></>}</h1></div>
      <div className="cosmos-segment" role="tablist">
        <button role="tab" aria-selected={tab === 'story'} className={tab === 'story' ? 'active' : ''} onClick={() => setTab('story')}>Illustrated binding</button>
        <button role="tab" aria-selected={tab === 'film'} className={tab === 'film' ? 'active' : ''} onClick={() => setTab('film')}>3D film</button>
      </div>
    </header>
    {tab === 'story' ? <BindingStory atoms={trace} name={name}/> : film}
  </div>;
}
