// The JSON export remains the exact archival receipt; this table is for spreadsheets.
function cell(value: unknown): string {
 const text=value===undefined||value===null?'':typeof value==='object'?JSON.stringify(value):String(value);
 // Quoting alone does not prevent spreadsheet formula evaluation.
 const safe=typeof value==='string'&&/^\s*[=+\-@]/.test(text)?`'${text}`:text;
 return /[\t\r\n"]/.test(safe)?`"${safe.replace(/"/g,'""')}"`:safe;
}
const rowFields=['id','originalMembers','testableMembers','overlapCount','expectedOverlap','foldEnrichment','pValue','logPValue','minusLog10P','pValueUnderflow','adjustedPValue','logAdjustedPValue','minusLog10AdjustedP','adjustedPValueUnderflow','passesDeclaredThreshold','noTestableMembers','overlapGenes','outsideBackground'] as const;
const resultFields=['multipleTesting','alpha','testedFamilySize','selectedCount','backgroundCount','inputSha256','sourceSha256','collectionSha256','backgroundSha256','collection','collectionVerification','scope'] as const;
export function pathwayTableExport(output:any):string {
 if(output?.operation!=='pathway_enrichment'||!output.result||!Array.isArray(output.result.rows))throw Error('Choose a completed pathway result.');
 const result=output.result;
 const header=[...rowFields,...resultFields,'spreadsheetTextPolicy'];
 const policy='Formula-like text receives a leading apostrophe for spreadsheet safety. JSON export preserves the exact original receipt. Empty numeric cells represent unavailable values, not zero.';
 const rows=result.rows.map((row:any)=>[...rowFields.map(key=>row[key]),...resultFields.map(key=>result[key]),policy].map(cell).join('\t'));
 return [header.join('\t'),...rows].join('\r\n')+'\r\n';
}
