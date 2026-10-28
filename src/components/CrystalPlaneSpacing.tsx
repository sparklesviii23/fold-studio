import {useMemo,useState} from 'react';
import type {UnitCellInspection,Vector3} from '../lib/crystalCell';
import {interplanarSpacing} from '../lib/crystalPlanes';
import {exportFile} from '../lib/api';
export default function CrystalPlaneSpacing({cell,onError}:{cell:UnitCellInspection;onError:(message:string)=>void}){
 const [indices,setIndices]=useState(['1','0','0']);
 const calculation=useMemo(()=>{try{if(indices.some(value=>!/^[-+]?\d+$/.test(value.trim())))throw Error('Enter three explicit integer Miller indices.');return {result:interplanarSpacing(cell,indices.map(Number) as Vector3),error:''};}catch(e){return {result:null,error:String(e)};}},[cell,indices]);
 const result=calculation.result;
 return <details><summary>Interplanar spacing · Miller indices</summary><p className="caption">Calculate d(hkl) from the reported lattice. This does not predict diffraction intensity or allowed reflections.</p><div className="button-row">{indices.map((value,i)=><label key={i}>Miller index {['h','k','l'][i]}<input type="number" step="1" min="-1000" max="1000" value={value} onChange={event=>setIndices(indices.map((v,j)=>i===j?event.target.value:v))}/></label>)}</div>{calculation.error&&<p role="alert">{calculation.error}</p>}{result&&<><p>Calculated d({result.millerIndices.join(' ')}) = {result.spacingAngstrom.toPrecision(10)} Å</p><p className="caption">{result.reciprocalConvention}</p><p className="caption">{result.scope}</p><button className="button" onClick={async()=>{try{await exportFile('fold-interplanar-spacing.json',{text:JSON.stringify(result,null,2)});}catch(e){onError(String(e));}}}>Export lattice-plane calculation · JSON</button></>}</details>;
}
