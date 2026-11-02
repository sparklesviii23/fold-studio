import {useEffect, useState} from 'react';
import {Check, Cloud, Cpu, Server} from 'lucide-react';
import {rpc} from '../lib/api';
import ModalAccounts from './ModalAccounts';
import {selectExecutionBackend} from './ExecutionBackendSelector';

/** Settings › Compute servers: sign in and out of server accounts and pick the server the whole app uses. */
export default function ComputeServers({projectId, onOpenTasks}: {projectId: string; onOpenTasks: () => void}) {
  const [data, setData] = useState<any>(null), [error, setError] = useState(''), [busy, setBusy] = useState(false), [profiles, setProfiles] = useState<any[]>([]);
  async function read() { try { setData(await rpc<any>('compute_servers', {projectId})); } catch (e) { setError(String(e).replace(/^Error:\s*/, '')); } }
  useEffect(() => { if (projectId) void read(); rpc<any>('gpu_profiles').then(v => setProfiles(v.profiles ?? [])).catch(() => {}); }, [projectId]);
  async function choose(mode: 'local' | 'modal' | 'vast', profileId?: string) {
    setBusy(true); setError('');
    try { await selectExecutionBackend({mode, ...(profileId ? {profileId} : {})}); await read(); } catch (e) { setError(String(e).replace(/^Error:\s*/, '')); } finally { setBusy(false); }
  }
  const mode = data?.backend?.mode ?? 'local';
  const active = data?.modal.profiles.find((p: any) => p.id === data.modal.activeId);
  return <section className="quiet-panel compute-servers">
    <div className="cs-servers">
      <button className={'cs-server ' + (mode === 'local' ? 'selected' : '')} disabled={busy} onClick={() => choose('local')}>
        <Cpu size={20}/><strong>This Mac</strong><span>Apple silicon engines run locally. GPU-only models still go to your server through Cloud GPU Tasks.</span>{mode === 'local' && <Check size={14}/>}</button>
      <button className={'cs-server ' + (mode === 'modal' ? 'selected' : '')} disabled={busy || !data?.modal.activeId} onClick={() => choose('modal')}>
        <Cloud size={20}/><strong>Modal{active ? ' · ' + active.name : ''}</strong><span>{data?.modal.activeId ? 'Scientific runs across the app use your Modal account.' : 'Sign in below to use Modal.'}</span>{mode === 'modal' && <Check size={14}/>}</button>
      {profiles.map(p => <button key={p.id} className={'cs-server ' + (mode === 'vast' && data?.backend?.profileId === p.id ? 'selected' : '')} disabled={busy} onClick={() => choose('vast', p.id)}>
        <Server size={20}/><strong>{p.name}</strong><span>Saved SSH GPU host.</span>{mode === 'vast' && data?.backend?.profileId === p.id && <Check size={14}/>}</button>)}
    </div>
    {error && <p className="caption cs-error">{error}</p>}
    <ModalAccounts projectId={projectId} onChanged={() => void read()}/>
    <div className="setting-row"><div><h3>Cloud GPU Tasks</h3><p>RNA 3D prediction, HemoCell blood flow and any other GPU model run on the active Modal account; results come back into the app. A terminal reaches the running container.</p></div>
      <button className="button" onClick={onOpenTasks}>Open Cloud GPU Tasks</button></div>
    <div className="cs-providers">
      {(data?.providers ?? []).map((p: any) => <div key={p.id} className={'cs-provider ' + p.state}><strong>{p.name}</strong><span>{p.state === 'available' ? 'Available' : 'Coming later'}</span><small>{p.note}</small></div>)}
    </div>
    <p className="caption">Signing out removes a saved account from the Keychain (accounts that own saved campaigns are kept so their results stay recoverable). Switching applies to new runs; running jobs keep the account they started with. Nothing is billed until you approve a run.</p>
  </section>;
}
