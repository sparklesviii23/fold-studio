import {useState} from 'react';
import {Download, GitCompare, RotateCcw, Trash2, Upload} from 'lucide-react';
import {fmt} from '../mechanistic/MechCharts';

const STATE_LABEL: Record<string, string> = {available: 'Available', not_downloaded: 'Not downloaded', unmeasured: 'Not measured here', unsupported: 'Unsupported for this cell',
  pending: 'Computing', unvalidated: 'Model output, unvalidated'};

/** What this cell context actually has, per modality (virtual_cell_registry.coverage). */
export function Coverage({coverage}: {coverage: any}) {
  if (!coverage) return null;
  return <div className="vc-coverage">{Object.entries(coverage.coverage).map(([k, v]: any) =>
    <div key={k} className={'vc-cov ' + v.state} title={v.note ?? ''}><span>{k}</span><em>{STATE_LABEL[v.state]}</em>{(v.source || v.note) && <small>{v.source}{v.source && v.note ? ' · ' : ''}{v.note}</small>}</div>)}</div>;
}

/** Saved states of this cell (virtual_cell_state.py): save, restore, compare, export, import, delete. */
export function Snapshots({list, onSave, onRestore, onCompare, onExport, onImport, onDelete, comparison}: {list: any[]; comparison: any; onSave: (label: string) => void; onRestore: (id: string) => void;
  onCompare: (a: string, b: string) => void; onExport: (id: string) => void; onImport: (bundle: any) => void; onDelete: (id: string) => void}) {
  const [label, setLabel] = useState(''), [pick, setPick] = useState<string[]>([]);
  return <div className="vc-snaps">
    <div className="vc-row"><input value={label} placeholder="Snapshot label" onChange={e => setLabel(e.target.value)}/><button onClick={() => { onSave(label); setLabel(''); }}>Save state</button></div>
    {list.map(s => <div key={s.id} className={'vc-step ' + (pick.includes(s.id) ? 'picked' : '')}>
      <input type="checkbox" aria-label="Select for comparison" checked={pick.includes(s.id)} onChange={() => setPick(pick.includes(s.id) ? pick.filter(x => x !== s.id) : [...pick.slice(-1), s.id])}/>
      <strong title={s.id}>{s.label || s.id.slice(0, 8)}</strong>
      <small>{s.kind}{s.time != null ? ` · t ${fmt(s.time, 4)} h` : ''} · {s.steps} step{s.steps === 1 ? '' : 's'}{s.parent ? ' · branch' : ''}</small>
      <button className="vc-icon" title="Restore" onClick={() => onRestore(s.id)}><RotateCcw size={12}/></button>
      <button className="vc-icon" title="Export with provenance" onClick={() => onExport(s.id)}><Download size={12}/></button>
      <button className="vc-icon" title="Delete" onClick={() => onDelete(s.id)}><Trash2 size={12}/></button></div>)}
    <div className="vc-row">
      <button disabled={pick.length !== 2} onClick={() => onCompare(pick[0], pick[1])}><GitCompare size={13}/>Compare two</button>
      <label className="text-button"><Upload size={13}/>Import<input type="file" accept="application/json" hidden onChange={async e => { const f = e.target.files?.[0]; if (f) { try { onImport(JSON.parse(await f.text())); } catch { onImport(null); } } e.target.value = ''; }}/></label>
    </div>
    {comparison && <div className="vc-compare">
      {comparison.warning && <p className="vc-warn">{comparison.warning}</p>}
      {comparison.simulation && <p className="caption">Simulation: {comparison.simulation.sameModel ? `same model, t ${fmt(comparison.simulation.timeA, 4)} h vs ${fmt(comparison.simulation.timeB, 4)} h` : 'different models: variables not compared'}</p>}
      {comparison.simulation?.variables?.length > 0 && <table className="vc-table"><thead><tr><th>Species</th><th>A</th><th>B</th></tr></thead>
        <tbody>{comparison.simulation.variables.filter((v: any) => ['Md', 'Me', 'Ma', 'Mb', 'E2F', 'Cdc20a', 'Cdh1a', 'p27'].includes(v.id)).map((v: any) => <tr key={v.id}><td>{v.id}</td><td>{fmt(v.a, 4)}</td><td>{fmt(v.b, 4)}</td></tr>)}</tbody></table>}
      {Object.entries(comparison.blocks).map(([k, b]: any) => <p key={k} className="caption">{k}: {b.only ? `only in snapshot ${b.only.toUpperCase()}` : b.incompatible ? `not comparable (${b.incompatible})` : `${b.changed} values differ (${b.category}, ${b.unit ?? 'no unit'})`}</p>)}
      <p className="caption">History A: {comparison.history.a.join(' → ') || 'baseline'} · B: {comparison.history.b.join(' → ') || 'baseline'}</p>
    </div>}
  </div>;
}
