/** Sequence logic for the Gene → Protein story: a two-exon gene, splicing and translation. */
const codons: Record<string, string> = {};
const bases = 'UCAG', table = 'FFLLSSSSYY**CC*WLLLLPPPPHHQQRRRRIIIMTTTTNNKKSSRRVVVVAAAADDEEGGGG';
for (let i = 0; i < 64; i++) codons[bases[i >> 4] + bases[(i >> 2) & 3] + bases[i & 3]] = table[i];

export const aminoNames: Record<string, string> = {A:'Ala',R:'Arg',N:'Asn',D:'Asp',C:'Cys',Q:'Gln',E:'Glu',G:'Gly',H:'His',I:'Ile',L:'Leu',K:'Lys',M:'Met',F:'Phe',P:'Pro',S:'Ser',T:'Thr',W:'Trp',Y:'Tyr',V:'Val','*':'Stop'};
export function aminoClass(a: string) {
  if ('AVLIMFWC'.includes(a)) return 'hydrophobic';
  if ('KRH'.includes(a)) return 'positive';
  if ('DE'.includes(a)) return 'negative';
  if ('GP'.includes(a)) return 'special';
  return 'polar';
}

export interface Gene {name: string; exon1: string; intron: string; exon2: string; protein: string; codons: string[]}

// The opening of green fluorescent protein (MSKGEE | LFTGVVPILVELDGD), with a
// textbook intron: GU donor, UACUAAC branch point, pyrimidine tract, AG acceptor.
const demo = {name: 'GFP · first 21 residues', exon1: 'AUGAGCAAGGGCGAGGAG', intron: 'GUAAGUAUCCUUUACUAACAUUUCCAG', exon2: 'CUGUUCACCGGGGUGGUGCCCAUCCUGGUCGAGCUGGACGGCGACUAA'};

export function translate(rna: string) {
  const out: string[] = [], cs: string[] = [];
  for (let i = 0; i + 3 <= rna.length; i += 3) { const c = rna.slice(i, i + 3), a = codons[c] ?? 'X'; cs.push(c); out.push(a); if (a === '*') break; }
  return {protein: out.join(''), codons: cs};
}

/** Build the story gene from a user coding sequence (DNA or RNA, from ATG), or the demo. */
export function buildGene(input?: string): Gene {
  const clean = (input ?? '').toUpperCase().replace(/[^ACGTU]/g, '').replace(/T/g, 'U');
  let exon1 = demo.exon1, exon2 = demo.exon2, name = demo.name;
  if (clean.length >= 24) {
    if (!clean.startsWith('AUG')) throw new Error('Start the coding sequence with ATG / AUG.');
    let cds = '';
    for (let i = 0; i + 3 <= clean.length && i < 180; i += 3) { const c = clean.slice(i, i + 3); cds += c; if (codons[c] === '*') break; }
    if (codons[cds.slice(-3)] !== '*') cds += 'UAA';
    exon1 = cds.slice(0, 18); exon2 = cds.slice(18); name = 'Your sequence · ' + (cds.length / 3 - 1) + ' residues';
  }
  const {protein, codons: cs} = translate(exon1 + exon2);
  return {name, exon1, intron: demo.intron, exon2, protein, codons: cs};
}

export const chapters = [
  {title: 'Chromatin opens', body: 'Remodelling complexes slide and evict nucleosomes, so the promoter and gene body become accessible.'},
  {title: 'The machinery assembles', body: 'General transcription factors recognise the promoter and recruit RNA polymerase II.'},
  {title: 'Transcription', body: 'Polymerase opens about a turn of DNA and copies the template strand, adding tens of nucleotides each second to a growing pre-mRNA.'},
  {title: 'Capping and splicing', body: 'A 7-methylguanosine cap protects the 5′ end. The spliceosome cuts the intron at its GU…AG borders, frees it as a lariat and joins the exons.'},
  {title: 'Polyadenylation', body: 'The 3′ end is cleaved and poly(A) polymerase adds a tail of roughly two hundred adenines.'},
  {title: 'Export', body: 'The finished messenger RNA, cap first and coated in export factors, passes through a nuclear pore into the cytoplasm.'},
  {title: 'Translation', body: 'A ribosome finds the start codon and reads one codon at a time; tRNAs bring matching amino acids and the chain folds as it emerges.'},
];
