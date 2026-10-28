import type {FractionalSite,UnitCellInspection,Vector3} from './crystalCell';
type Basis=[Vector3,Vector3,Vector3];
const dot=(a:Vector3,b:Vector3)=>a.reduce((sum,value,i)=>sum+value*b[i],0);
const cross=(a:Vector3,b:Vector3):Vector3=>[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];
function validBasis(basis:Basis){
 if(basis.length!==3||basis.some(axis=>axis.length!==3||axis.some(value=>!Number.isFinite(value))))throw Error('Supply three finite XYZ lattice vectors.');
 const determinant=dot(basis[0],cross(basis[1],basis[2])),scale=basis.reduce((product,axis)=>product*Math.hypot(...axis),1);
 if(!Number.isFinite(determinant)||!Number.isFinite(scale)||scale===0||Math.abs(determinant)/scale<=1e-12)throw Error('Coordinate conversion requires a nondegenerate lattice basis.');
 return determinant;
}
export function fractionalToCartesian(fractional:Vector3,basis:Basis):Vector3 {
 validBasis(basis);if(fractional.length!==3||fractional.some(value=>!Number.isFinite(value)))throw Error('Supply three finite fractional coordinates.');
 const result=[0,1,2].map(axis=>fractional.reduce((sum,value,i)=>sum+value*basis[i][axis],0)) as Vector3;
 if(result.some(value=>!Number.isFinite(value)))throw Error('Converted coordinates exceed the numerical range.');
 return result;
}
export function cartesianToFractional(cartesian:Vector3,basis:Basis):Vector3 {
 const determinant=validBasis(basis);if(cartesian.length!==3||cartesian.some(value=>!Number.isFinite(value)))throw Error('Supply three finite Cartesian coordinates.');
 const result=[dot(cartesian,cross(basis[1],basis[2]))/determinant,dot(cartesian,cross(basis[2],basis[0]))/determinant,dot(cartesian,cross(basis[0],basis[1]))/determinant] as Vector3;
 if(result.some(value=>!Number.isFinite(value)))throw Error('Converted coordinates exceed the numerical range.');
 return result;
}
export function reciprocalLatticeBasis(basis:Basis):Basis {
 const determinant=validBasis(basis);
 const result=[cross(basis[1],basis[2]),cross(basis[2],basis[0]),cross(basis[0],basis[1])].map(axis=>axis.map(value=>value/determinant) as Vector3) as Basis;
 if(result.some(axis=>axis.some(value=>!Number.isFinite(value))))throw Error('Reciprocal coordinates exceed the numerical range.');
 return result;
}
export interface ReplicatedSite extends FractionalSite {translation:Vector3;supercellFractional:Vector3;cartesianAngstrom:Vector3;generatedLabel:string;}
export interface CrystalReplication {
 schemaVersion:1;kind:'translated_reported_fractional_sites';repeats:Vector3;sourceSiteCount:number;
 lengthsAngstrom:Vector3;anglesDegrees:Vector3;latticeVectorsAngstrom:Basis;volumeAngstromCubed:number;
 recordedSourceSha256:string|null;parsedTextSha256:string;sites:ReplicatedSite[];scope:string;
}
export function replicateFractionalSites(cell:UnitCellInspection,repeats:Vector3):CrystalReplication {
 if(repeats.length!==3||repeats.some(value=>!Number.isInteger(value)||value<1||value>3))throw Error('Choose one to three translations along each lattice axis.');
 const source=cell.fractionalSites;
 if(source?.state!=='reported'||!source.sites.length)throw Error('Reported fractional atom-site coordinates are required; Cartesian coordinates are not transformed implicitly.');
 if(source.sites.length>5000||source.sites.length*repeats.reduce((n,v)=>n*v,1)>20000)throw Error('Replication is limited to 5,000 source sites and 20,000 translated sites.');
 if(new Set(source.sites.map(site=>site.sourceRow)).size!==source.sites.length||source.sites.some(site=>!Number.isInteger(site.sourceRow)||site.sourceRow<1))throw Error('Source site row identities must be unique positive integers.');
 const sites:ReplicatedSite[]=[];
 for(let a=0;a<repeats[0];a++)for(let b=0;b<repeats[1];b++)for(let c=0;c<repeats[2];c++)for(const site of source.sites){
  const translation:Vector3=[a,b,c],translated=site.fractional.map((value,i)=>value+translation[i]) as Vector3;
  sites.push({...site,fractional:[...site.fractional],reportedFractional:[...site.reportedFractional],translation,supercellFractional:translated.map((value,i)=>value/repeats[i]) as Vector3,cartesianAngstrom:fractionalToCartesian(translated,cell.latticeVectorsAngstrom),generatedLabel:`R${site.sourceRow}_${a}_${b}_${c}`});
 }
 return {schemaVersion:1,kind:'translated_reported_fractional_sites',repeats:[...repeats],sourceSiteCount:source.sites.length,lengthsAngstrom:cell.lengthsAngstrom.map((value,i)=>value*repeats[i]) as Vector3,anglesDegrees:[...cell.anglesDegrees],latticeVectorsAngstrom:cell.latticeVectorsAngstrom.map((axis,i)=>axis.map(value=>value*repeats[i]) as Vector3) as Basis,volumeAngstromCubed:cell.volumeAngstromCubed*repeats.reduce((n,v)=>n*v,1),recordedSourceSha256:cell.recordedSourceSha256,parsedTextSha256:cell.parsedTextSha256,sites,scope:'Translations of reported fractional atom sites in a conventional lattice basis only. Supplied sites may be an asymmetric unit, not a complete crystal. No space-group operations, symmetry expansion, occupancy completion, boundary wrapping, duplicate removal or bonding were applied. Source row and translation identify every derived site; overlapping boundary or alternate sites remain distinct. Cartesian output is derived in the conventional basis, not a claim about the source Cartesian origin. No periodic simulation or stability calculation was performed.'};
}
export function replicationCif(result:CrystalReplication):string {
 const number=(value:number)=>{if(!Number.isFinite(value))throw Error('CIF export requires finite coordinates.');return value.toPrecision(15);};
 const hash=/^[a-f0-9]{64}$/i.test(result.parsedTextSha256)?result.parsedTextSha256:'not_recorded';
 const originalHash=typeof result.recordedSourceSha256==='string'&&/^[a-f0-9]{64}$/i.test(result.recordedSourceSha256)?result.recordedSourceSha256:'not_recorded';
 const lines=['data_fold_translated_sites','# Translational copies of supplied fractional sites only; no symmetry expansion.',`# Parsed source text SHA-256: ${hash}`,`# Recorded original source SHA-256: ${originalHash}`,`# Translation counts a b c: ${result.repeats.join(' ')}`,'# Source labels, uncertainties and complete provenance are retained in the companion JSON export.'];
 ['a','b','c'].forEach((axis,i)=>lines.push(`_cell.length_${axis} ${number(result.lengthsAngstrom[i])}`));
 ['alpha','beta','gamma'].forEach((axis,i)=>lines.push(`_cell.angle_${axis} ${number(result.anglesDegrees[i])}`));
 lines.push('loop_','_atom_site.label','_atom_site.type_symbol','_atom_site.fract_x','_atom_site.fract_y','_atom_site.fract_z','_atom_site.Cartn_x','_atom_site.Cartn_y','_atom_site.Cartn_z','_atom_site.occupancy','_atom_site.fold_source_row','_atom_site.fold_translation_a','_atom_site.fold_translation_b','_atom_site.fold_translation_c');
 for(const site of result.sites){
  if(!/^[A-Za-z][A-Za-z0-9_.:+-]*$|^[.?]$/.test(site.typeSymbol)||!/^[R]\d+_\d+_\d+_\d+$/.test(site.generatedLabel)||!/^[-+\d.eE()]+$|^[.?]$/.test(site.occupancy))throw Error('Use JSON export for complex atom-type or occupancy labels that cannot be exported as simple CIF tokens.');
  const typeToken=['.','?'].includes(site.typeSymbol)?site.typeSymbol:`'${site.typeSymbol}'`;
  lines.push([site.generatedLabel,typeToken,...site.supercellFractional.map(number),...site.cartesianAngstrom.map(number),site.occupancy,site.sourceRow,...site.translation].join(' '));
 }
 return lines.join('\n')+'\n';
}
