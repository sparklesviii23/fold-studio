/** Export exact upstream accepted sequences; chain copies remain separate records. */
export function acceptedBinderFasta(rows:Record<string,unknown>[]):string {
 if(!rows.length)throw new Error('There are no accepted binder sequences to export.');
 return rows.flatMap(row=>{
  if(typeof row.design!=='string'||!row.design.trim()||/[\r\n]/.test(row.design)||typeof row.Binder_Sequence!=='string')throw new Error('The saved design identity or binder sequence is missing.');
  return row.Binder_Sequence.split('/').map((sequence,index)=>{
   if(!/^[ACDEFGHIKLMNPQRSTVWY]+$/.test(sequence))throw new Error('A saved binder sequence is not canonical; the original row is unchanged.');
   return `>${row.design} | binder chain ${index+1}\n${sequence.match(/.{1,80}/g)!.join('\n')}\n`;
  });
 }).join('');
}
