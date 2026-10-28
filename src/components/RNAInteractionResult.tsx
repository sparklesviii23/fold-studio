export default function RNAInteractionResult({stages}:{stages:Record<string,any>}){
 const pairs=Object.entries(stages).filter(([,stage])=>stage.operation==='rna_cofold');
 if(!pairs.length)return null;
 return <article className="ec-card"><h2>Supplied RNA interaction results</h2>{pairs.map(([id,stage])=>{
  const r=stage.result,inter=r.interstrandPairs??[];
  const available=inter.length>0&&typeof r.complexMfeKcalMol==='number'&&Number.isFinite(r.complexMfeKcalMol)&&r.complexMfeKcalMol<100000;
  const legacy=!r.intermolecularMfeState;
  return <section key={id}><h3>{id}</h3><p>ViennaRNA {r.version} · {r.temperatureC} °C · {inter.length} interstrand pairs</p>
   {available?<p>Complex MFE {r.complexMfeKcalMol} kcal/mol · difference relative to separate folds {r.deltaMfeRelativeToSeparateFoldsKcalMol} kcal/mol</p>:<p role="status">No intermolecular MFE available. A diagnostic engine return is not a physical complex energy.</p>}
   {legacy&&!available&&<p role="alert">Historical adapter receipt: its recorded complex-energy value is invalid without an interstrand structure. Original receipt preserved; this interpretation does not rerun inference.</p>}
   <pre className="ec-sequence">{r.displayDotBracket}</pre><p>RNA A: {r.sequenceA}</p><p>RNA B: {r.sequenceB}</p>
   <details><summary>Strand-specific pair coordinates and original receipt</summary><pre className="ec-output">{JSON.stringify(stage,null,2)}</pre></details><p>{r.scope}</p>
  </section>;
 })}</article>;
}
