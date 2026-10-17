#!/usr/bin/env python3
"""Refresh the pinned 20-component CCD subset from RCSB; review diffs before release."""
import concurrent.futures, hashlib, json, pathlib, re, urllib.request
ROOT = pathlib.Path(__file__).resolve().parents[1]
CODES = 'ALA ARG ASN ASP CYS GLN GLU GLY HIS ILE LEU LYS MET PHE PRO SER THR TRP TYR VAL'.split()
def tokens(text):
    out=[]; block=None
    for line in text.splitlines():
        if line.startswith(';'):
            if block is None: block=[line[1:]]
            else: out.append('\n'.join(block)); block=None
        elif block is not None: block.append(line)
        elif not line.lstrip().startswith('#'):
            out.extend(m.group(1) or m.group(2) or m.group(3) for m in re.finditer(r'"([^\"]*)"|\'([^\']*)\'|([^\s]+)',line))
    if block is not None: raise ValueError('Unterminated CIF text field')
    return out
def parse(text):
    tt=tokens(text); values={}; loops={}; i=0
    while i<len(tt):
        t=tt[i];i+=1
        if t=='loop_':
            fields=[]
            while i<len(tt) and tt[i].startswith('_'): fields.append(tt[i]);i+=1
            rows=[]
            while i<len(tt) and not tt[i].startswith(('_','data_','loop_')):
                row=tt[i:i+len(fields)]
                if len(row)!=len(fields): raise ValueError('Incomplete CIF row')
                rows.append(dict(zip(fields,row)));i+=len(fields)
            loops[fields[0].split('.')[0]]=rows
        elif t.startswith('_'): values[t]=tt[i];i+=1
    return values,loops
def get(code):
    url=f'https://files.rcsb.org/ligands/download/{code}.cif'
    raw=urllib.request.urlopen(url,timeout=30).read()
    (ROOT/'scientific/components'/f'{code}.cif').write_bytes(raw)
    v,l=parse(raw.decode()); atoms=[]; bonds=[]
    for row in l['_chem_comp_atom']:
        def a(key): return row['_chem_comp_atom.'+key]
        atoms.append(dict(id=a('atom_id'),element=a('type_symbol'),charge=int(a('charge')),stereo=a('pdbx_stereo_config'),leaving=a('pdbx_leaving_atom_flag')=='Y',backbone=a('pdbx_backbone_atom_flag')=='Y',xyz=[float(a('pdbx_model_Cartn_'+axis+'_ideal')) for axis in 'xyz']))
    for row in l['_chem_comp_bond']:
        def b(key): return row['_chem_comp_bond.'+key]
        bonds.append(dict(a=b('atom_id_1'),b=b('atom_id_2'),order={'SING':1,'DOUB':2,'TRIP':3}[b('value_order')],aromatic=b('pdbx_aromatic_flag')=='Y'))
    return dict(code=code,one=v['_chem_comp.one_letter_code'],name=v['_chem_comp.name'].title(),formula=v['_chem_comp.formula'],mass=float(v['_chem_comp.formula_weight']),type=v['_chem_comp.type'],modified=v['_chem_comp.pdbx_modified_date'],atoms=atoms,bonds=bonds,source=url,sha256=hashlib.sha256(raw).hexdigest(),coordinateMethod='wwPDB CCD ideal coordinates',protonation='CCD neutral reference; no pH-specific protonation model')
if __name__=='__main__':
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool: components=list(pool.map(get,CODES))
    result=dict(schemaVersion=1,source='wwPDB Chemical Component Dictionary via RCSB PDB',retrieved='2026-10-10',components=components)
    (ROOT/'scientific/amino-acids.json').write_text(json.dumps(result,indent=2)+'\n')
    print('Pinned',len(components),'components;',sum(len(c['atoms']) for c in components),'atoms')
