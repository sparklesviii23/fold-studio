import type {UnitCellInspection,Vector3} from './crystalCell';
import {fractionalToCartesian,reciprocalLatticeBasis} from './crystalReplication';

/** Enumerate image bounds in the dual metric, valid for oblique cells too. */
export function periodicReportedNeighbours(cell:UnitCellInspection,cutoffAngstrom:number){
 const source=cell.fractionalSites;
 if(source?.state!=='reported'||!source.sites.length||source.sites.length>200)throw Error('Use one to 200 explicit fractional sites. This tool does not generate crystallographic symmetry mates.');
 if(!Number.isFinite(cutoffAngstrom)||cutoffAngstrom<.1||cutoffAngstrom>10)throw Error('Choose a distance cutoff from 0.1 to 10 Å.');
 const basis=cell.latticeVectorsAngstrom,dual=reciprocalLatticeBasis(basis),radii=dual.map(axis=>Math.hypot(...axis)*cutoffAngstrom);
 if(radii.some(r=>r>32))throw Error('The cutoff/cell geometry needs too many periodic images; choose a smaller cutoff or a less ill-conditioned cell.');
 const sites=source.sites.map(site=>({...site,wrapped:site.fractional.map(value=>((value%1)+1)%1) as Vector3}));
 if(new Set(sites.map(s=>s.sourceRow)).size!==sites.length||sites.some(s=>s.wrapped.some(v=>!Number.isFinite(v))))throw Error('Source rows must be unique with finite fractional coordinates.');
 const neighbours:{centralRow:number;neighbourRow:number;imageTranslation:Vector3;distanceAngstrom:number;displacementAngstrom:Vector3;coincidentReportedSite:boolean}[]=[];
 let candidates=0;
 for(const a of sites)for(const b of sites){
  const delta=b.wrapped.map((v,i)=>v-a.wrapped[i]);
  const low=delta.map((v,i)=>Math.ceil(-radii[i]-v-1e-10)),high=delta.map((v,i)=>Math.floor(radii[i]-v+1e-10));
  const count=low.reduce((n,v,i)=>n*Math.max(0,high[i]-v+1),1);candidates+=count;
  if(candidates>1000000)throw Error('Periodic image search exceeds one million candidates; reduce the sites or cutoff. No incomplete neighbour table is returned.');
  for(let i=low[0];i<=high[0];i++)for(let j=low[1];j<=high[1];j++)for(let k=low[2];k<=high[2];k++){
   if(a.sourceRow===b.sourceRow&&i===0&&j===0&&k===0)continue;
   const imageTranslation:Vector3=[i||0,j||0,k||0],displacementAngstrom=fractionalToCartesian(delta.map((v,n)=>v+imageTranslation[n]) as Vector3,basis),distanceAngstrom=Math.hypot(...displacementAngstrom);
   if(distanceAngstrom>cutoffAngstrom+1e-10)continue;
   neighbours.push({centralRow:a.sourceRow,neighbourRow:b.sourceRow,imageTranslation,distanceAngstrom,displacementAngstrom,coincidentReportedSite:distanceAngstrom<1e-8});
   if(neighbours.length>20000)throw Error('Periodic neighbour table exceeds 20,000 rows; reduce the cutoff. No partial table is returned.');
  }
 }
 neighbours.sort((a,b)=>a.centralRow-b.centralRow||a.distanceAngstrom-b.distanceAngstrom||a.neighbourRow-b.neighbourRow);
 return {schemaVersion:1,kind:'periodic_reported_site_neighbours',cutoffAngstrom,sourceSiteCount:sites.length,centralImages:'Each supplied row wrapped into [0,1); image translations refer to those wrapped sites.',sourceSites:sites.map(({wrapped,...site})=>({...site,wrappedFractional:wrapped})),latticeVectorsAngstrom:basis.map(axis=>[...axis]),recordedSourceSha256:cell.recordedSourceSha256,parsedTextSha256:cell.parsedTextSha256,neighbours,scope:'Directed geometric distances to translational images of the reported site subset only. No space-group expansion or crystal completeness is inferred. Partial occupancies, alternate and coincident sites remain distinct; counts are not physical coordination numbers. No bonding, forces, stability or periodic dynamics were calculated. Source coordinates are unchanged.'};
}
