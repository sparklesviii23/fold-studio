import {useEffect,useRef,useState} from 'react';
import {exportFile,rpc} from '../lib/api';
import {inspectUnitCell,type UnitCellInspection} from '../lib/crystalCell';
import type {Item} from '../lib/types';

export default function CrystalCellInspection({item}:{item:Item}){
 const key=item.id+':'+item.data.asset+':'+item.data.sha256,current=useRef(key);current.current=key;
 const [result,setResult]=useState<UnitCellInspection|null>(null),[error,setError]=useState(''),[busy,setBusy]=useState(false);
 useEffect(()=>{setResult(null);setError('');setBusy(false);},[key]);
 if(item.kind!=='structure'||!(item.data.format==='mmcif'||/\.(?:cif|mmcif)$/i.test(item.data.asset??'')))return null;
 const value=(v:number)=>v.toPrecision(8);
 return <details><summary>Crystallographic unit cell</summary><p className="caption">Read the cell and reported symmetry directly from this saved mmCIF. Predicted structures may have no crystallographic cell.</p><button className="button" disabled={busy} onClick={async()=>{const requested=key;setBusy(true);setError('');try{const text=await rpc<string>('asset_read',{asset:item.data.asset});const parsed=await inspectUnitCell(text,item.data.sha256);if(current.current===requested)setResult(parsed);}catch(e){if(current.current===requested){setResult(null);setError(String(e));}}finally{if(current.current===requested)setBusy(false);}}}>{busy?'Reading saved cell…':'Inspect reported cell'}</button>
 {error&&<p role="alert" className="error">{error}</p>}{result&&<><p>Data block: {result.block}</p><table><thead><tr><th>Cell parameter</th><th>Original reported value</th><th>Nominal value</th></tr></thead><tbody>{Object.entries(result.reportedCellValues).map(([field,raw],i)=><tr key={field}><td>{field} · {i<3?'Å':'degrees'}</td><td>{raw}</td><td>{value(i<3?result.lengthsAngstrom[i]:result.anglesDegrees[i-3])}</td></tr>)}</tbody></table><p>Calculated cell volume: {value(result.volumeAngstromCubed)} Å³</p><table><thead><tr><th>Lattice vector · Å</th><th>x</th><th>y</th><th>z</th></tr></thead><tbody>{result.latticeVectorsAngstrom.map((vector,i)=><tr key={i}><td>{['a','b','c'][i]}</td>{vector.map((v,j)=><td key={j}>{value(v)}</td>)}</tr>)}</tbody></table><h4>Reported symmetry labels</h4>{Object.keys(result.reportedSymmetry).length?<dl>{Object.entries(result.reportedSymmetry).map(([field,text])=><div key={field}><dt>{field}</dt><dd>{text}</dd></div>)}</dl>:<p>No symmetry labels were reported. No symmetry is inferred.</p>}<p className="caption" style={{overflowWrap:'anywhere'}}>Recorded original source SHA-256: {result.recordedSourceSha256??'Not recorded'}<br/>Parsed text SHA-256: {result.parsedTextSha256}</p><p className="caption">{result.scope}</p><button className="button" onClick={()=>exportFile(`fold-unit-cell-${item.id}.json`,{text:JSON.stringify({structureId:item.id,projectId:item.project_id,name:item.name,...result},null,2)}).catch(e=>setError(String(e)))}>Export unit-cell inspection · JSON</button></>}
 </details>;
}
