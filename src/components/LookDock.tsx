import {useEffect, useState} from 'react';
import {Palette, X} from 'lucide-react';
import {colourMode, currentLook, looks, setColourMode, setLook, type ColourMode, type LookId} from '../lib/renderLooks';
import '../cosmos/looks.css';

const families = ['Studio', 'Art', 'Microscopy'] as const;

function useLookState() {
  const [active, setActive] = useState<LookId>(() => currentLook().id), [colours, setColours] = useState<ColourMode>(colourMode);
  useEffect(() => {
    const sync = () => { setActive(currentLook().id); setColours(colourMode()); };
    window.addEventListener('fold-render-look', sync);
    return () => window.removeEventListener('fold-render-look', sync);
  }, []);
  return {active, colours};
}

function ColourSwitch({colours}: {colours: ColourMode}) {
  return <div className="cosmos-segment look-colour" role="radiogroup" aria-label="Colouring">
    <button role="radio" aria-checked={colours === 'look'} className={colours === 'look' ? 'active' : ''} onClick={() => setColourMode('look')}>Look colours</button>
    <button role="radio" aria-checked={colours === 'scientific'} className={colours === 'scientific' ? 'active' : ''} onClick={() => setColourMode('scientific')}>Scientific colours</button>
  </div>;
}

/** Floating glass dock on the left edge of the molecular viewport. */
export default function LookDock() {
  const {active, colours} = useLookState(), [open, setOpen] = useState(false);
  const current = looks.find(l => l.id === active)!;
  if (!open) return <button className="look-dock-toggle" onClick={() => setOpen(true)} title={'Render look · ' + current.name} aria-label="Choose a render look">
    <span className="look-orb" style={{background: current.swatch}}/><Palette size={13}/>
  </button>;
  return <div className="look-dock" role="dialog" aria-label="Render look" onPointerDown={e => e.stopPropagation()} onWheel={e => e.stopPropagation()}>
    <header><div><span className="eyebrow">Render look</span><strong>{current.name}</strong></div><button className="icon-button" onClick={() => setOpen(false)} aria-label="Close"><X size={15}/></button></header>
    <p className="look-dock-blurb">{current.blurb}</p>
    <ColourSwitch colours={colours}/>
    {families.map(f => <section key={f}>
      <span className="eyebrow">{f}</span>
      <div className="look-dock-grid">{looks.filter(l => l.family === f).map(l => <button key={l.id} aria-pressed={active === l.id} className={'look-chip ' + (active === l.id ? 'active' : '')} onClick={() => setLook(l.id)}>
        <span className="look-orb" style={{background: l.swatch}}/><span>{l.name}</span>
      </button>)}</div>
    </section>)}
  </div>;
}

/** Settings gallery: the same looks, larger, with their descriptions. */
export function LookGallery() {
  const {active, colours} = useLookState();
  return <div className="look-settings">
    <ColourSwitch colours={colours}/>
    {families.map(f => <section key={f}>
      <span className="eyebrow">{f}</span>
      <div className="look-gallery" role="radiogroup" aria-label={f + ' looks'}>
        {looks.filter(l => l.family === f).map(l => <button key={l.id} role="radio" aria-checked={active === l.id} className={'look-card ' + (active === l.id ? 'selected' : '')} onClick={() => setLook(l.id)}>
          <span className="look-orb" style={{background: l.swatch}}/><strong>{l.name}</strong><span>{l.blurb}</span>
        </button>)}
      </div>
    </section>)}
  </div>;
}
