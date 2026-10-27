import {useState} from 'react';
import {chooseFile,exportFile,rpc} from '../lib/api';
export interface ArchiveReview {
 schemaVersion:number;state:'integrity_reviewed';fileName:string;archiveSha256:string;
 archiveBytes:number;expandedBytes:number;entryCount:number;projectName:string;
 recordCount:number;jobCount:number;verifiedAssetCount:number;crcCheckedFiles:number;scope:string;
}
export function ArchiveReviewResult({result}:{result:ArchiveReview}){
 return <><h3>{result.projectName}</h3><p>{result.recordCount} saved records · {result.jobCount} saved job records · {result.verifiedAssetCount} assets verified</p><p className="caption">{result.fileName} · {result.crcCheckedFiles} ZIP entries checked · {(result.expandedBytes/1024**2).toFixed(2)} MiB expanded</p><p className="caption mono">Archive SHA-256: {result.archiveSha256}</p><p className="caption">{result.scope}</p></>;
}
export default function ProjectArchiveReview(){
 const [result,setResult]=useState<ArchiveReview|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState('');
 return <details className="project-edit"><summary>Check a saved project archive</summary><p className="caption">Review a local Fold Studio ZIP before moving or restoring research. This checks stored file integrity without importing records or starting jobs. Up to 128 MiB compressed / 256 MiB expanded.</p><button className="button" disabled={busy} onClick={async()=>{setBusy(true);setError('');try{const path=await chooseFile(['zip']);if(path){setResult(null);setResult(await rpc<ArchiveReview>('project_archive_inspect',{path}));}}catch(e){setError(String(e));}finally{setBusy(false);}}}>{busy?'Checking archive…':'Choose project ZIP to check'}</button>{error&&<p role="alert" className="error">{error}</p>}{result&&<><ArchiveReviewResult result={result}/><button className="button" onClick={()=>exportFile('fold-project-archive-integrity.json',{text:JSON.stringify(result,null,2)}).catch(e=>setError(String(e)))}>Export archive integrity report</button></>}</details>;
}
