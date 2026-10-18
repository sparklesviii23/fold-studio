import {useEffect,useState} from 'react';
import {rpc} from '../lib/api';

type Resources={cache:string;pin:{bytes:number;sha256:string;revision:string;repository:string};checkpoint:{state:string;bytes:number;partialBytes?:number;sha256?:string};scope:string};
const labels:Record<string,string>={missing:'Model has not been downloaded',incomplete_download:'An incomplete download is saved',placeholder:'Model download is incomplete',size_mismatch:'Model size differs from the publisher record',present_unverified:'Model is present · checksum not checked',verified:'Publisher checksum verified',checksum_mismatch:'Model checksum differs from the publisher record',changed_during_check:'Model changed during verification · check again'};

export default function PredictionResources(){
 const [resources,setResources]=useState<Resources|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState('');
 useEffect(()=>{let active=true;rpc<Resources>('prediction_resources',{}).then(value=>{if(active)setResources(value);}).catch(e=>{if(active)setError(String(e));});return()=>{active=false;};},[]);
 async function verify(){if(busy)return;setBusy(true);setError('');try{setResources(await rpc<Resources>('prediction_resources',{verify:true}));}catch(e){setError(String(e));}finally{setBusy(false);}}
 return <div><h3>Prediction model files</h3><p className="caption">The trained structure model is stored with your local research data. Missing resources download when you start a prediction.</p>
  {resources&&<><p role="status">{labels[resources.checkpoint.state]??resources.checkpoint.state}</p><dl><dt>Structure checkpoint</dt><dd>{(resources.checkpoint.bytes/1e9).toFixed(2)} / {(resources.pin.bytes/1e9).toFixed(2)} GB</dd>{resources.checkpoint.partialBytes!==undefined&&<><dt>Incomplete download</dt><dd>{(resources.checkpoint.partialBytes/1e9).toFixed(2)} GB</dd></>}</dl></>}
  <button className="button" disabled={busy||!resources?.checkpoint.bytes} onClick={verify}>{busy?'Checking model checksum…':'Verify structure-model checksum'}</button>
  {error&&<p className="error" role="alert">{error}</p>}
  <p className="caption">This verifies the saved model file against the publisher’s checksum. Scientific model quality and completed inference are separate checks. Existing cache files are preserved.</p>
  {resources&&<details><summary>Model provenance and local storage</summary><pre>{JSON.stringify(resources,null,2)}</pre></details>}
 </div>;
}
