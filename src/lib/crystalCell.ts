export type Vector3=[number,number,number];
export interface FractionalSite {
 sourceRow:number;label:string;typeSymbol:string;fractional:Vector3;
 reportedFractional:[string,string,string];occupancy:string;
}
export interface FractionalSiteInspection {state:'reported'|'unavailable';sites:FractionalSite[];scope:string;}
export interface UnitCellInspection {
 schemaVersion:1;
 block:string;
 lengthsAngstrom:Vector3;
 anglesDegrees:Vector3;
 latticeVectorsAngstrom:[Vector3,Vector3,Vector3];
 volumeAngstromCubed:number;
 reportedCellValues:Record<string,string>;
 reportedSymmetry:Record<string,string>;
 recordedSourceSha256:string|null;
 parsedTextSha256:string;
 fractionalSites?:FractionalSiteInspection;
 scope:string;
}
const fields=['length_a','length_b','length_c','angle_alpha','angle_beta','angle_gamma'] as const;
export function cifMeasuredNumber(text:string):number {
 // Keep parenthetical standard uncertainties as original text; use the nominal value.
 const match=text.trim().match(/^([+-]?(?:\d+(?:\.\d*)?|\.\d+))(?:\((\d+)\))?([eE][+-]?\d+)?(?:\((\d+)\))?$/);
 if(!match||(match[2]&&match[4]))throw Error('A reported CIF value is missing or is not a supported number.');
 const value=Number(match[1]+(match[3]??''));
 if(!Number.isFinite(value))throw Error('Unit-cell values must be finite.');
 return value;
}
export function cellGeometry(lengths:Vector3,angles:Vector3){
 if(lengths.some(v=>!Number.isFinite(v)||v<=0)||angles.some(v=>!Number.isFinite(v)||v<=0||v>=180))throw Error('Unit-cell lengths must be positive and angles strictly between 0 and 180 degrees.');
 const [a,b,c]=lengths,[alpha,beta,gamma]=angles.map(v=>v*Math.PI/180),ca=Math.cos(alpha),cb=Math.cos(beta),cg=Math.cos(gamma),sg=Math.sin(gamma);
 const gram=1+2*ca*cb*cg-ca*ca-cb*cb-cg*cg;
 if(!Number.isFinite(gram)||gram<=1e-12||sg<=1e-12)throw Error('Reported unit-cell geometry is degenerate, inconsistent or too ill-conditioned for this inspection.');
 const vectors:[Vector3,Vector3,Vector3]=[[a,0,0],[b*cg,b*sg,0],[c*cb,c*(ca-cb*cg)/sg,c*Math.sqrt(gram)/sg]];
 const volume=a*b*c*Math.sqrt(gram);
 if(!Number.isFinite(volume)||volume<=0||vectors.some(v=>v.some(x=>!Number.isFinite(x))))throw Error('Unit-cell geometry exceeds the numerical inspection range.');
 return {latticeVectorsAngstrom:vectors,volumeAngstromCubed:volume};
}
export async function inspectUnitCell(text:string,recordedSourceSha256?:string):Promise<UnitCellInspection>{
 const limit=20*1024**2;
 if(typeof text!=='string'||!text.trim()||text.length>limit)throw Error('Inspect a nonempty mmCIF text asset of at most 20 MiB.');
 const encoded=new TextEncoder().encode(text);
 if(encoded.byteLength>limit)throw Error('Unit-cell text inspection is limited to 20 MiB.');
 const {CIF}=await import('molstar/lib/mol-io/reader/cif');
 const parsed=await CIF.parse(text).run();
 if(parsed.isError)throw Error('The saved mmCIF could not be parsed: '+parsed.message);
 const blocks=parsed.result.blocks.filter(block=>block.categories.cell);
 if(blocks.length!==1)throw Error(blocks.length?'Multiple unit-cell blocks are present; a single cell cannot be chosen implicitly.':'This mmCIF has no reported unit cell. No cell is inferred from the coordinates.');
 const block=blocks[0],cell=block.categories.cell;
 if(cell.rowCount!==1)throw Error('Unit-cell inspection requires one explicit cell row.');
 const raw=Object.fromEntries(fields.map(name=>[name,cell.getField(name)?.str(0)??'']));
 const values=fields.map(name=>cifMeasuredNumber(raw[name]));
 const lengths=values.slice(0,3) as Vector3,angles=values.slice(3) as Vector3;
 const reportedSymmetry:Record<string,string>={};
 for(const [categoryName,names] of [['symmetry',['space_group_name_H-M','Int_Tables_number']],['space_group',['name_H-M_alt','name_Hall','IT_number']]] as const){
  const category=block.categories[categoryName];
  if(category?.rowCount===1)for(const name of names){const value=category.getField(name)?.str(0);if(value&&value!=='.'&&value!=='?')reportedSymmetry[`_${categoryName}.${name}`]=value;}
 }
 const textHash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',encoded))).map(v=>v.toString(16).padStart(2,'0')).join('');
 const atomSite=block.categories.atom_site,coordinateFields=['fract_x','fract_y','fract_z'].map(name=>atomSite?.getField(name));
 let fractionalSites:FractionalSiteInspection={state:'unavailable',sites:[],scope:'No reported fractional atom-site coordinates are available. Cartesian coordinates are not converted implicitly because their crystallographic origin/transform is not established here.'};
 if(coordinateFields.some(Boolean)){
  if(coordinateFields.some(field=>!field))throw Error('Reported fractional atom-site coordinates require all three axes.');
  if(!atomSite||atomSite.rowCount<1||atomSite.rowCount>5000)throw Error('Fractional-site inspection supports 1–5,000 reported sites.');
  const sites:FractionalSite[]=[];
  for(let i=0;i<atomSite.rowCount;i++){
   const reported=coordinateFields.map(field=>field!.str(i)) as [string,string,string];
   // Mol* returns an empty str() for CIF '.' and '?'; retain their distinct meanings.
   const fieldText=(name:string)=>{const field=atomSite.getField(name),kind=field?.valueKind(i);return !field||kind===2?'?':kind===1?'.':field.str(i);};
   const occupancy=fieldText('occupancy');
   if(!['.','?'].includes(occupancy)){const value=cifMeasuredNumber(occupancy);if(value<0||value>1)throw Error('Reported site occupancies must be between zero and one, or explicitly unknown.');}
   sites.push({sourceRow:i+1,label:fieldText(atomSite.getField('label')?'label':'label_atom_id'),typeSymbol:fieldText('type_symbol'),fractional:reported.map(cifMeasuredNumber) as Vector3,reportedFractional:reported,occupancy});
  }
  fractionalSites={state:'reported',sites,scope:'Reported fractional sites only. These may be an asymmetric unit or a supplied site subset. No symmetry expansion, occupancy completion, missing-site inference, boundary wrapping or duplicate removal has been performed. Standard uncertainties remain original text and are not propagated.'};
 }
 return {schemaVersion:1,block:block.header,lengthsAngstrom:lengths,anglesDegrees:angles,...cellGeometry(lengths,angles),reportedCellValues:raw,reportedSymmetry,recordedSourceSha256:typeof recordedSourceSha256==='string'&&/^[a-f\d]{64}$/i.test(recordedSourceSha256)?recordedSourceSha256:null,parsedTextSha256:textHash,fractionalSites,scope:'Read-only nominal unit-cell geometry from the reported mmCIF cell. Lattice axes use a along x and b in the xy plane; coordinates are unchanged. Parenthetical standard uncertainties are retained as text, not propagated into derived geometry. Reported symmetry labels are not independently determined. The recorded source checksum identifies original stored bytes; the parsed-text checksum identifies the text returned by the file reader, which may normalize line endings. This inspection does not establish periodic simulation, crystal stability or a qualified materials engine.'};
}
