export const alphabet='ACDEFGHIKLMNPQRSTVWY';
const mass:Record<string,number>={A:89.094,R:174.203,N:132.119,D:133.104,C:121.154,E:147.131,Q:146.146,G:75.067,H:155.156,I:131.175,L:131.175,K:146.189,M:149.208,F:165.192,P:115.132,S:105.093,T:119.119,W:204.228,Y:181.191,V:117.148};
export function properties(sequence:string) {const s=sequence.replace(/\s/g,'').toUpperCase();const composition=Object.fromEntries([...alphabet].map(a=>[a,[...s].filter(c=>c===a).length]));return {length:s.length,valid:s.length>0&&[...s].every(c=>alphabet.includes(c)),mass:s.length?[...s].reduce((v,c)=>v+(mass[c]??0),0)-(s.length-1)*18.015:0,composition};}
export function fasta(name:string,sequence:string) {return '>'+name.replace(/[\r\n]/g,' ')+'\n'+(sequence.match(/.{1,80}/g)?.join('\n')??'')+'\n';}
export interface Alignment {a:string;b:string;identity:number;matches:number;pairs:[number,number][];score:number}
/** Needleman–Wunsch, +2 match, -1 mismatch, -2 linear gap. 1-based pairs. */
export function align(a:string,b:string):Alignment {
 if(a.length>2500||b.length>2500) throw new Error('Alignment is limited to 2,500 residues per sequence.');
 const cols=b.length+1;const score=new Int32Array((a.length+1)*cols);const trace=new Uint8Array(score.length);
 for(let i=1;i<=a.length;i++){score[i*cols]=-2*i;trace[i*cols]=1;}for(let j=1;j<=b.length;j++){score[j]=-2*j;trace[j]=2;}
 for(let i=1;i<=a.length;i++)for(let j=1;j<=b.length;j++){const k=i*cols+j;const d=score[k-cols-1]+(a[i-1]===b[j-1]?2:-1),u=score[k-cols]-2,l=score[k-1]-2;score[k]=Math.max(d,u,l);trace[k]=score[k]===d?0:score[k]===u?1:2;}
 let i=a.length,j=b.length,aa='',bb='',matches=0,aligned=0;const pairs:[number,number][]=[];
 while(i||j){const t=trace[i*cols+j];if(i&&j&&t===0){aa=a[i-1]+aa;bb=b[j-1]+bb;aligned++;if(a[i-1]===b[j-1]){matches++;pairs.push([i,j]);}i--;j--;}else if(i&&(t===1||!j)){aa=a[i-1]+aa;bb='-'+bb;i--;}else{aa='-'+aa;bb=b[j-1]+bb;j--;}}
 return {a:aa,b:bb,matches,identity:aligned?matches/aligned:0,pairs:pairs.reverse(),score:score[a.length*cols+b.length]};
}
export const aminoNames:Record<string,string>={ALA:'A',ARG:'R',ASN:'N',ASP:'D',CYS:'C',GLN:'Q',GLU:'E',GLY:'G',HIS:'H',ILE:'I',LEU:'L',LYS:'K',MET:'M',PHE:'F',PRO:'P',SER:'S',THR:'T',TRP:'W',TYR:'Y',VAL:'V',MSE:'M'};

/** Conservative sequence-derived correspondence; short fragments require one exact occurrence. */
export function residueCorrespondence(source:string,observed:string):[number,number][] {
 if(!source||!observed)return [];
 const exact=source.indexOf(observed);
 if(exact>=0){if(source.indexOf(observed,exact+1)>=0)return [];return [...observed].map((_,i)=>[exact+i+1,i+1]);}
 if(observed.length<source.length*0.5)return [];
 const alignment=align(source,observed);return alignment.identity>=0.9&&alignment.matches>=Math.min(10,observed.length)?alignment.pairs:[];
}
