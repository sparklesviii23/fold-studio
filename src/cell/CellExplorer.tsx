import {useMemo, useState} from 'react';
import {ArrowRight, Pause, Play, Scissors, Sparkles, X} from 'lucide-react';
import CellStage, {type CellSettings} from './CellStage';
import GeneStory from './GeneStory';
import CellPhysicsLab from './physics/CellPhysicsLab';
import MicrographStage from './MicrographStage';
import {coarseGrain, demoParticle} from './micrograph';
import {cellTypes, journeys, layerNames, organelles, styles} from './organelles';
import type {AtomRecord} from '../lib/types';
import './cell.css';

const storyOrganelles = new Set([2, 3, 4, 9]);
const scaleBars = [0.5, 1, 2, 5, 10, 20, 50];
type Tab = 'cell'|'microscope'|'story'|'physics';
const titles: Record<Tab, [string, string]> = {cell: ['A living cell, ', 'sliced open.'], microscope: ['Your molecules, ', 'under the beam.'], story: ['From gene ', 'to protein.'], physics: ['Particles, ', 'actually computed.']};

/** Visualise › Cell Explorer: a sliceable 3D cell, a microscope for your own molecules, and the Gene → Protein story. */
export default function CellExplorer({structure}: {structure?: {name: string; atoms: AtomRecord[]} | null}) {
  const [tab, setTab] = useState<Tab>('cell');
  const [settings, setSettings] = useState<CellSettings>({style: 0, cut: true, slice: 0.12, glass: true, layers: layerNames.map(() => true), animate: true, quality: 'balanced', cellType: 'generic'});
  const [journey, setJourney] = useState({id: 'overview', n: 0}), [flying, setFlying] = useState(''), [selected, setSelected] = useState<number | null>(null);
  const [pxPerMicron, setPxPerMicron] = useState(20);
  const update = (change: Partial<CellSettings>) => setSettings(s => ({...s, ...change}));
  const fly = (id: string) => { const j = journeys.find(j => j.id === id)!; setJourney(v => ({id, n: v.n + 1})); setFlying(id); update({slice: j.slice, cut: true}); };
  const particle = useMemo(() => (structure && coarseGrain(structure.atoms, structure.name)) || demoParticle(), [structure]);
  const type = cellTypes.find(c => c.id === settings.cellType)!;
  const bar = scaleBars.reduce((a, b) => Math.abs(b * pxPerMicron - 110) < Math.abs(a * pxPerMicron - 110) ? b : a);

  return <div className="cell-explorer">
    <header className="cell-heading">
      <div>
        <span className="eyebrow">Visualise · Cell Explorer</span>
        <h1>{titles[tab][0]}<em>{titles[tab][1]}</em></h1>
      </div>
      <div className="cosmos-segment" role="tablist">
        {(['cell', 'microscope', 'story', 'physics'] as Tab[]).map(t => <button key={t} role="tab" aria-selected={tab === t} className={tab === t ? 'active' : ''} onClick={() => setTab(t)}>{t === 'cell' ? 'Cell · 3D' : t === 'microscope' ? 'Microscope' : t === 'story' ? 'Gene → Protein' : 'Physics · simulated'}</button>)}
      </div>
    </header>

    {tab === 'cell' && <div className="cell-layout">
      <CellStage settings={settings} journey={journey.id} journeyKey={journey.n} onJourneyDone={() => setFlying('')} onSelect={setSelected} onScale={setPxPerMicron}/>

      <aside className="cell-card cell-controls">
        <section>
          <span className="eyebrow">Cell type</span>
          <select value={settings.cellType} onChange={e => update({cellType: e.target.value})} aria-label="Cell type">{cellTypes.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</select>
          <p className="caption">{type.note}</p>
        </section>
        <section>
          <span className="eyebrow">Style</span>
          <div className="cell-styles">{styles.map((name, i) => <button key={name} className={'cell-style s' + i + (settings.style === i ? ' active' : '')} onClick={() => update({style: i})}><i/>{name}</button>)}</div>
        </section>
        <section>
          <div className="cell-row"><span className="eyebrow">Cutaway</span><button className={'cell-toggle ' + (settings.cut ? 'on' : '')} onClick={() => update({cut: !settings.cut})} aria-pressed={settings.cut}><Scissors size={13}/>{settings.cut ? 'Sliced' : 'Whole'}</button></div>
          <label className="cell-slider">Slice depth<input type="range" min={-0.6} max={0.6} step={0.005} value={settings.slice} disabled={!settings.cut} onChange={e => update({slice: Number(e.target.value)})}/></label>
        </section>
        <section>
          <span className="eyebrow">Layers</span>
          <div className="cell-layers">{layerNames.map((name, i) => <button key={name} className={settings.layers[i] ? 'on' : ''} aria-pressed={settings.layers[i]} onClick={() => update({layers: settings.layers.map((v, k) => k === i ? !v : v)})}>{name}</button>)}</div>
        </section>
        <section className="cell-row-wrap">
          <button className={'cell-toggle ' + (settings.glass ? 'on' : '')} onClick={() => update({glass: !settings.glass})} aria-pressed={settings.glass}><Sparkles size={13}/>Glass membrane</button>
          <button className={'cell-toggle ' + (settings.animate ? 'on' : '')} onClick={() => update({animate: !settings.animate})} aria-pressed={settings.animate}>{settings.animate ? <Pause size={13}/> : <Play size={13}/>}{settings.animate ? 'Alive' : 'Frozen'}</button>
          <button className={'cell-toggle ' + (settings.quality === 'high' ? 'on' : '')} onClick={() => update({quality: settings.quality === 'high' ? 'balanced' : 'high'})} aria-pressed={settings.quality === 'high'}>{settings.quality === 'high' ? 'High detail' : 'Balanced'}</button>
        </section>
      </aside>

      <nav className="cell-journeys" aria-label="Journeys">
        {journeys.map(j => <button key={j.id} className={(journey.id === j.id ? 'active ' : '') + (flying === j.id ? 'flying' : '')} onClick={() => fly(j.id)}>{j.name}</button>)}
      </nav>
      <div className="cell-scale" aria-label={'Scale bar ' + bar + ' micrometres'}><i style={{width: bar * pxPerMicron}}/><span>{bar} µm</span></div>
      <span className="evidence-badge cell-evidence" title="Category E: an illustration of known biology. Shapes, counts and motion are schematic, not simulated.">Illustrative model · not simulated</span>

      {selected && organelles[selected] && <div className="cell-card cell-info" role="dialog" aria-label={organelles[selected].name}>
        <button className="icon-button" onClick={() => setSelected(null)} aria-label="Close"><X size={15}/></button>
        <span className="eyebrow">Organelle</span>
        <h3>{organelles[selected].name}</h3>
        <p>{organelles[selected].note}</p>
        {storyOrganelles.has(selected) && <button className="button primary" onClick={() => setTab('story')}>Watch a gene become a protein<ArrowRight size={14}/></button>}
        {(selected === 3 || selected === 2) && <button className="text-button" onClick={() => setTab('microscope')}>See chromatin under the microscope<ArrowRight size={13}/></button>}
        {(selected === 5 || selected === 6) && <button className="text-button" onClick={() => fly('mitochondrion')}>Fly to a mitochondrion<ArrowRight size={13}/></button>}
        {(selected === 3 || selected === 2) && <button className="text-button" onClick={() => fly('chromatin')}>Dive into the chromatin<ArrowRight size={13}/></button>}
      </div>}
      <p className="cell-hint">Drag · scroll · click to explore</p>
    </div>}
    {tab === 'microscope' && <MicrographStage particle={particle}/>}
    {tab === 'story' && <GeneStory/>}
    {tab === 'physics' && <CellPhysicsLab/>}
    {tab !== 'physics' && <p className="cell-disclaimer">Schematic models for learning and illustration. Sizes, counts and shapes are simplified; the scale bar uses a typical diameter for the chosen cell type.</p>}
    {tab === 'physics' && <p className="cell-disclaimer">Physics tab: every drawn position and curve comes from the Brownian-dynamics engine (scientific/cell_physics.py) for an idealised model with hypothetical parameters. No physiological claim is made.</p>}
  </div>;
}
