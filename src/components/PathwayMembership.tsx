import {useState} from 'react';

export type MembershipRow={id:string;overlapGenes:string[]};
export function membershipGraph(rows:MembershipRow[],maximumSets=8,maximumGenes=32){
 const eligible=rows.filter(row=>Array.isArray(row.overlapGenes)&&row.overlapGenes.length);
 const sets=eligible.slice(0,maximumSets);
 const genes=[...new Set(sets.flatMap(row=>row.overlapGenes))].slice(0,maximumGenes);
 const visible=new Set(genes);
 return {sets,genes,edges:sets.flatMap(row=>row.overlapGenes.filter(gene=>visible.has(gene)).map(gene=>({set:row.id,gene}))),omittedSets:eligible.length-sets.length,omittedGenes:new Set(sets.flatMap(row=>row.overlapGenes)).size-genes.length};
}

const xml=(value:string)=>value.replace(/[&<>"']/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&apos;'}[char]!));
export function membershipSvg(rows:MembershipRow[],source:{inputSha256?:string;sourceSha256?:string;collectionSha256?:string;backgroundSha256?:string}){
 const graph=membershipGraph(rows),height=Math.max(210,Math.max(graph.sets.length,graph.genes.length)*30+50);
 const setY=(i:number)=>35+(i+.5)*(height-70)/Math.max(1,graph.sets.length);
 const geneY=(i:number)=>35+(i+.5)*(height-70)/Math.max(1,graph.genes.length);
 const bySet=new Map(graph.sets.map((row,i)=>[row.id,i])),byGene=new Map(graph.genes.map((gene,i)=>[gene,i]));
 const provenance=JSON.stringify({inputSha256:source.inputSha256??null,sourceSha256:source.sourceSha256??null,collectionSha256:source.collectionSha256??null,backgroundSha256:source.backgroundSha256??null,omittedSets:graph.omittedSets,omittedGenes:graph.omittedGenes,displayedSets:graph.sets.length,displayedGenes:graph.genes.length,displayedEdges:graph.edges.length});
 return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 720 ${height}" role="img"><title>Reported input–set membership</title><desc>Exact saved overlap identifiers only; membership is not a physical interaction, activity or causal link. Bounded display; see metadata for omitted counts.</desc><metadata>${xml(provenance)}</metadata><rect width="720" height="${height}" fill="#0c2138"/>${graph.edges.map(edge=>`<line x1="252" y1="${setY(bySet.get(edge.set)!)}" x2="468" y2="${geneY(byGene.get(edge.gene)!)}" stroke="#85b9d8"><title>${xml(edge.set)} contains ${xml(edge.gene)}</title></line>`).join('')}${graph.sets.map((row,i)=>`<text x="18" y="${setY(i)+5}" fill="#e9f3ff" font-size="12"><title>${xml(row.id)}</title>${xml(row.id.length>31?row.id.slice(0,28)+'…':row.id)}</text>`).join('')}${graph.genes.map((gene,i)=>`<text x="478" y="${geneY(i)+5}" fill="#e9f3ff" font-size="12"><title>${xml(gene)}</title>${xml(gene.length>31?gene.slice(0,28)+'…':gene)}</text>`).join('')}</svg>`;
}

export default function PathwayMembership({rows}:{rows:MembershipRow[]}){
 const [selected,setSelected]=useState<string|null>(null),graph=membershipGraph(rows);
 if(!graph.edges.length)return <p>No observed overlap connects the selected genes to these tested sets.</p>;
 const active=selected&&graph.sets.some(row=>row.id===selected)?selected:null;
 const height=Math.max(210,Math.max(graph.sets.length,graph.genes.length)*30+50);
 const setY=(i:number)=>35+(i+.5)*(height-70)/graph.sets.length;
 const geneY=(i:number)=>35+(i+.5)*(height-70)/graph.genes.length;
 const bySet=new Map(graph.sets.map((row,i)=>[row.id,i])),byGene=new Map(graph.genes.map((gene,i)=>[gene,i]));
 return <div className="ec-pathway-membership"><h3>Reported input–set membership</h3><p className="caption">Lines join exact overlapping identifiers returned by the saved calculation. They show membership, not physical interactions, pathway activity or causation. Select a gene set to inspect its links.</p><svg viewBox={`0 0 720 ${height}`} role="group" aria-label="Reported input–set membership graph" style={{width:'100%',maxHeight:560}}>
  {graph.edges.map(edge=><line key={`${edge.set}:${edge.gene}`} x1="252" y1={setY(bySet.get(edge.set)!)} x2="468" y2={geneY(byGene.get(edge.gene)!)} stroke={active===null||active===edge.set?'#85b9d8':'#38546c'} strokeWidth={active===edge.set?2:1} aria-label={`${edge.set} contains ${edge.gene}`}/>)}
  {graph.sets.map((row,i)=><g key={row.id} role="button" tabIndex={0} aria-label={`Select gene set ${row.id}`} onClick={()=>setSelected(row.id===active?null:row.id)} onKeyDown={event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();setSelected(row.id===active?null:row.id);}}}><rect x="8" y={setY(i)-12} width="244" height="24" rx="8" fill={active===row.id?'#396790':'#173650'}/><text x="18" y={setY(i)+5} fill="#e9f3ff" fontSize="12">{row.id.length>31?row.id.slice(0,28)+'…':row.id}</text><title>{row.id}</title></g>)}
  {graph.genes.map((gene,i)=><g key={gene}><rect x="468" y={geneY(i)-12} width="244" height="24" rx="8" fill={active&&graph.edges.some(edge=>edge.set===active&&edge.gene===gene)?'#3d776d':'#173650'}/><text x="478" y={geneY(i)+5} fill="#e9f3ff" fontSize="12">{gene.length>31?gene.slice(0,28)+'…':gene}</text><title>{gene}</title></g>)}
 </svg><p className="caption">Showing {graph.sets.length} sets, {graph.genes.length} genes and {graph.edges.length} exact membership links. {graph.omittedSets||graph.omittedGenes?`${graph.omittedSets} sets and ${graph.omittedGenes} genes omitted from this bounded view; the complete table and original result remain available above and below.`:''}</p>{active&&<p role="status">{active}: {graph.edges.filter(edge=>edge.set===active).map(edge=>edge.gene).join(', ')||'No displayed genes'}</p>}</div>;
}
