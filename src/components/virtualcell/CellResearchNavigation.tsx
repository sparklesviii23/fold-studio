import {Activity, BrainCircuit, Dna, FlaskConical, Microscope, Terminal} from 'lucide-react';

export type CellResearchView = '3d' | 'painting' | 'regulatory' | 'benchmarks' | 'training' | 'runs';
const views = [
  {id: '3d', label: 'Cell workspace', detail: 'Explore and intervene', icon: Dna},
  {id: 'painting', label: 'Microscopy', detail: 'Observed cell images', icon: Microscope},
  {id: 'regulatory', label: 'Genes & regulation', detail: 'Evidence and predictions', icon: Activity},
  {id: 'benchmarks', label: 'Benchmarks', detail: 'Accuracy and limitations', icon: FlaskConical},
  {id: 'training', label: 'Cell AI training', detail: 'Evidence, learning and evaluation', icon: BrainCircuit},
  {id: 'runs', label: 'Runs & terminal', detail: 'Progress, commands and files', icon: Terminal},
] as const;

export default function CellResearchNavigation({value, onChange}: {value: CellResearchView; onChange: (value: CellResearchView) => void}) {
  return <nav className="vc-research-nav" aria-label="Virtual Cell research tools">
    {views.map(({id, label, detail, icon: Icon}) => <button key={id} className={value === id ? 'active' : ''}
      aria-current={value === id ? 'page' : undefined} onClick={() => onChange(id)}>
      <Icon size={18}/><span><strong>{label}</strong><small>{detail}</small></span>
    </button>)}
  </nav>;
}
