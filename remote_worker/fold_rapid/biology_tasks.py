"""Authentic isolated scientific calls. No synthetic prediction or fallback model.

Invoked by the common RAPID supervisor and the native biology controller.
All dependencies and checkpoint paths are supplied by verified runtime receipts.
"""
import hashlib
import json
import os
import pathlib
import sys
import time
from .contracts import canonical, file_digest
from .biology_contract import AA, validate_outputs


def expected_sequences(m, mapping):
    selected=set(m['target']['chains'])|set(m['design'].get('designChains',[]))
    return {ch:m.get('biology',{}).get('sequences',{}).get(ch,value['sequence']) for ch,value in mapping['chains'].items() if ch in selected}


def normalize_prediction(raw, expected, source_mapping, chemistry):
    """Preserve author numbering without transplanting source coordinates."""
    import gemmi
    structure=gemmi.make_structure_from_block(gemmi.cif.read_string(raw).sole_block())
    if len(structure)!=1 or {c.name for c in structure[0]}!=set(expected):raise ValueError('Predictor changed chain identities or coordinate model count.')
    modifications={(r['chain'],r['position']):r['ccd'] for r in chemistry.get('modifications',[])}
    for chain in structure[0]:
        residues=list(chain)
        if len(residues)!=len(expected[chain.name]):raise ValueError('Predictor changed chain length.')
        for i,(res,aa) in enumerate(zip(residues,expected[chain.name]),1):
            if (chain.name,i) in modifications:
                if res.name!=modifications[chain.name,i]:raise ValueError('Predictor did not preserve the requested CCD modification.')
            elif gemmi.find_tabulated_residue(res.name).one_letter_code.upper()!=aa:raise ValueError('Predictor changed an input sequence.')
            if chain.name in source_mapping['chains']:
                source=source_mapping['chains'][chain.name]['residues'][i-1]
                res.seqid=gemmi.SeqId(source['authorNumber'],source['insertionCode'] or ' ')
    return structure.make_mmcif_document().as_string()


def esmfold(job,m,runtime,models,device):
    import importlib.metadata
    import numpy as np
    import torch
    if importlib.metadata.version('esm')!='3.4.1.post1':raise ValueError('ESMFold2 runtime differs from the inspected 3.4.1.post1 contract.')
    if device not in ('cuda','cpu') or device=='cuda' and not torch.cuda.is_available():raise ValueError('Requested ESMFold2 device unavailable; no fallback.')
    receipt=models['esmfold2-fast-bundle' if m['engine']=='esmfold2_fast' else 'esmfold2-bundle']
    entries=json.loads(pathlib.Path(receipt['path']).read_text())
    repository='biohub/ESMFold2-Fast' if m['engine']=='esmfold2_fast' else 'biohub/ESMFold2'
    configs=[pathlib.Path(r['path']) for r in entries if r['repository']==repository and pathlib.Path(r['path']).name=='config.json']
    ccd=[pathlib.Path(r['path']) for r in entries if pathlib.Path(r['path']).name=='ccd.pkl']
    if len(configs)!=1 or len(ccd)!=1:raise ValueError('Verified model bundle must contain the exact model config and CCD.')
    os.environ['ESMCFOLD_CCD_PATH']=str(ccd[0])
    from esm.models.esmfold2 import EsmFold2Model,ESMFold2InputBuilder,ProteinInput,StructurePredictionInput,Modification,CovalentBond
    from .molecules import inspect
    mapping=inspect((job/('target.'+m['target']['format'])).read_bytes(),m['target']['format']);sequences=expected_sequences(m,mapping)
    options=m.get('biology',{}).get('prediction',{});chemistry=m.get('biology',{}).get('chemistry',{})
    from esm.models.esmfold2.config import EsmFold2Config
    config=EsmFold2Config.from_pretrained(str(configs[0].parent))
    if config.esmc_config is None:
        esmc=[pathlib.Path(r['path']) for r in entries if r['repository']=='biohub/ESMC-6B' and pathlib.Path(r['path']).name=='config.json']
        if len(esmc)!=1:raise ValueError('Full ESMFold2 requires its verified, separately cached ESMC checkpoint.')
        config.esmc_id=str(esmc[0].parent)
    model=EsmFold2Model.from_pretrained(str(configs[0].parent),config=config,device=device,local_files_only=True).eval()
    kernel=options.get('kernel','reference')
    if kernel!='reference' and device!='cuda':raise ValueError('Optimized ESMFold2 kernels require their qualified CUDA runtime.')
    model.set_kernel_backend(None if kernel=='reference' else kernel)
    inputs=[]
    for ch,sequence in sequences.items():
        kwargs={};msa=options.get('msa',{}).get(ch)
        if msa:
            from esm.utils.msa import MSA
            path=job/('msa-'+ch+'.a3m');path.write_text(msa);kwargs['msa']=MSA.from_a3m(path=str(path))
        mods=[Modification(position=item['position']-1,ccd=item['ccd']) for item in chemistry.get('modifications',[]) if item['chain']==ch]
        inputs.append(ProteinInput(id=ch,sequence=sequence,modifications=mods or None,**kwargs))
    bonds=[CovalentBond(chain_id1=b['chain1'],res_idx1=b['position1']-1,atom_idx1=b['atomIndex1'],chain_id2=b['chain2'],res_idx2=b['position2']-1,atom_idx2=b['atomIndex2']) for b in chemistry.get('bonds',[])]
    start=time.perf_counter()
    with torch.no_grad():
        results=ESMFold2InputBuilder().fold(model,StructurePredictionInput(sequences=inputs,covalent_bonds=bonds or None),seed=m['seed'],num_loops=options.get('loops',10),num_sampling_steps=options.get('samplingSteps',100),num_diffusion_samples=options.get('samples',1),lm_dropout=options.get('lmDropout',.3))
    if not isinstance(results,list):results=[results]
    rows=[]
    def array(value):return value.detach().float().cpu().numpy() if hasattr(value,'detach') else np.asarray(value)
    for i,result in enumerate(results):
        path=job/'output'/f'prediction-{i}.cif';path.write_text(normalize_prediction(result.complex.to_mmcif(),sequences,mapping,chemistry))
        arrays={key:array(getattr(result,key)) for key in ('plddt','pae','pde','pair_chains_iptm') if getattr(result,key,None) is not None}
        if any(not np.isfinite(a).all() for a in arrays.values()):raise ValueError('Nonfinite ESMFold2 confidence output.')
        np.savez_compressed(job/'output'/f'confidence-{i}.npz',**arrays)
        metrics={key:float(getattr(result,key)) for key in ('ptm','iptm') if getattr(result,key,None) is not None}
        if 'plddt' in arrays:metrics['plddt_mean']=float(arrays['plddt'].mean())
        if any(not np.isfinite(v) for v in metrics.values()):raise ValueError('Nonfinite ESMFold2 scalar confidence.')
        rows.append({'structure':path.name,'confidenceArtifact':f'confidence-{i}.npz','metrics':metrics,'sequences':sequences,'sample':i})
    return {'engine':m['engine'],'family':'ESMFold2/ESMC','predictions':rows,'device':device,'kernel':kernel,'predictionOptions':options,'chemistry':chemistry,'inferenceSeconds':time.perf_counter()-start,'metricUnits':'Raw provider-native confidence values; PAE/PDE arrays retain provider output units. No affinity calibration.','sourceCoordinatesUsedAsTemplate':False}


def solublempnn(job,m,runtime,models,device):
    import gemmi
    import torch
    dependency=pathlib.Path(__file__).parent/'third_party/ligandmpnn'
    from .contracts import file_digest
    receipt=json.loads((dependency/'SOURCE.json').read_text())
    if any(file_digest(dependency/name)!=sha for name,sha in receipt['files'].items()):raise ValueError('Pinned SolubleMPNN source changed.')
    from .third_party.ligandmpnn import ProteinMPNN
    path=job/('target.'+m['target']['format']);structure=gemmi.read_structure(str(path))
    from .molecules import inspect
    sequences=expected_sequences(m,inspect(path.read_bytes(),m['target']['format']))
    constraints=m.get('biology',{}).get('constraints',{})
    selected=list(sequences);backbone=[];indices=[];labels=[];design=[];original=[]
    for n,ch in enumerate(selected):
        residues=[r for r in structure[0][ch] if gemmi.find_tabulated_residue(r.name).is_amino_acid()]
        for i,res in enumerate(residues):
            coords=[]
            for name in ('N','CA','C','O'):
                choices=sorted([a for a in res if a.name==name],key=lambda a:(-a.occ,a.altloc))
                if not choices:raise ValueError('SolubleMPNN requires resolved N/CA/C/O for every selected residue; no coordinate invention.')
                coords.append(list(choices[0].pos))
            backbone.append(coords);indices.append(i+1000*n);labels.append(n);design.append(i+1 in constraints.get(ch,{'mutable':[]})['mutable']);original.append(AA.index(sequences[ch][i]))
    if not any(design):raise ValueError('No mutable positions supplied to SolubleMPNN.')
    torch.manual_seed(m['seed']);checkpoint=torch.load(models['solublempnn']['path'],map_location='cpu',weights_only=True)
    model=ProteinMPNN(num_letters=21,node_features=128,edge_features=128,hidden_dim=128,num_encoder_layers=3,num_decoder_layers=3,k_neighbors=checkpoint['num_edges'],atom_context_num=1,model_type='soluble_mpnn')
    model.load_state_dict(checkpoint['model_state_dict'],strict=True);model.to(device).eval().requires_grad_(False)
    length=len(original);bias=torch.zeros((1,length,21),device=device);bias[:,:,-1]=-torch.inf
    cursor=0
    for ch,seq in sequences.items():
        for i in range(len(seq)):
            mask=constraints.get(ch,{});key=str(i+1)
            for aa in mask.get('excluded',{}).get(key,''):bias[0,cursor,AA.index(aa)]=-torch.inf
            # Preferences are a recorded logit prior, never a hard exclusion.
            for aa in mask.get('preferred',{}).get(key,''):bias[0,cursor,AA.index(aa)]+=m['design'].get('temperature',.1)
            cursor+=1
    features={'X':torch.tensor([backbone],device=device,dtype=torch.float32),'S':torch.tensor([original],device=device),'mask':torch.ones(1,length,device=device),'chain_mask':torch.tensor([design],device=device,dtype=torch.float32),'chain_labels':torch.tensor([labels],device=device),'R_idx':torch.tensor([indices],device=device),'batch_size':1,'temperature':m['design'].get('temperature',.1),'bias':bias,'symmetry_residues':[[]],'symmetry_weights':[[]]}
    if not torch.isfinite(features['X']).all():raise ValueError('Nonfinite input backbone.')
    rows=[]
    with torch.no_grad():
        for i in range(m['design']['count']):
            features['randn']=torch.randn(1,length,device=device);sample=model.sample(features)['S'][0].cpu().tolist();decoded={};offset=0
            for ch,seq in sequences.items():decoded[ch]=''.join(AA[x] if x<20 else 'X' for x in sample[offset:offset+len(seq)]);offset+=len(seq)
            validate_outputs(decoded,sequences,constraints)
            rows.append({'chains':decoded,'metrics':{},'sourceBackboneSha256':m['target']['sha256']})
            (job/'output'/f'sequence-{i}.fasta').write_text(''.join('>chain='+ch+'\n'+seq+'\n' for ch,seq in decoded.items() if ch in m['design']['designChains']))
    return {'engine':'solublempnn','family':'ProteinMPNN','candidates':rows,'device':device,'constraints':constraints,'fixedBackbone':True,'affinityOrSolubilityMeasurement':False,'preferredLogitShift':1,'backboneConformerSelection':'Highest occupancy per N/CA/C/O atom; lexicographic altloc tie break.'}


def rosetta(job,m,runtime,models,device):
    if runtime.get('licenseApproved') is not True:raise ValueError('Rosetta requires an explicitly authorized licensed installation; no redistribution.')
    import pyrosetta
    import pyrosetta.rosetta as rosetta
    import gemmi
    source=job/('target.'+m['target']['format']);structure=gemmi.read_structure(str(source));input_pdb=job/'rosetta-input.pdb';structure.write_pdb(str(input_pdb))
    # Refuse lossy conversion of multi-character or unmappable author identities.
    if any(len(c.name)!=1 for c in structure[0]):raise ValueError('Rosetta PDB adapter requires explicit single-character chain identities.')
    pyrosetta.init('-constant_seed -jran '+str(m['seed'])+' -ignore_unrecognized_res false -mute all')
    pose=pyrosetta.pose_from_pdb(str(input_pdb));score=pyrosetta.get_fa_scorefxn();before=pose.clone();energy_before=float(score(before))
    repeats=m.get('biology',{}).get('relax',{}).get('repeats',1)
    relax=rosetta.protocols.relax.FastRelax(score,repeats);relax.apply(pose);energy_after=float(score(pose))
    output=job/'output/relaxed.pdb';pose.dump_pdb(str(output))
    terms=('fa_atr','fa_rep','fa_sol','fa_elec','hbond_sr_bb','hbond_lr_bb','hbond_bb_sc','hbond_sc')
    per_residue=[]
    for i in range(1,pose.total_residue()+1):
        energies=pose.energies().residue_total_energies(i)
        per_residue.append({'poseIndex':i,'sourcePdbId':pose.pdb_info().pose2pdb(i).strip(),'totalREU':float(pose.energies().residue_total_energy(i)),'terms':{name:float(energies[getattr(rosetta.core.scoring,name)]) for name in terms}})
    analyzer=rosetta.protocols.analysis.InterfaceAnalyzerMover();analyzer.set_interface(''.join(m['design']['designChains'])+'_'+''.join(m['target']['chains']));analyzer.set_scorefunction(score);analyzer.apply(pose)
    return {'engine':'rosetta','version':pyrosetta.version(),'scoreFunction':score.get_name(),'structure':'relaxed.pdb','energyBeforeREU':energy_before,'energyAfterREU':energy_after,'interfaceDeltaGREU':float(analyzer.get_interface_dG()),'buriedSasaAngstrom2':float(analyzer.get_interface_delta_sasa()),'perResidue':per_residue,'hydrogenBonds':pose.get_hbonds().nhbonds(),'units':'Rosetta energy units, not experimental affinity. Relaxed coordinates are a separate derived artifact requiring re-evaluation.','repeats':repeats}


def main():
    engine=sys.argv[1];job=pathlib.Path(sys.argv[2]);device=os.environ.get('BGMEE_DEVICE','cuda')
    m=json.loads((job/'manifest.json').read_text());prepared=json.loads((job/'biology-runtime.json').read_text())
    started=time.perf_counter()
    result=(esmfold if engine.startswith('esmfold2') else solublempnn if engine=='solublempnn' else rosetta)(job,m,prepared['runtime'],prepared['models'],device)
    result.update(schemaVersion=1,seed=m['seed'],wallSeconds=time.perf_counter()-started,parents=m.get('biology',{}).get('parents',[]))
    (job/'output'/('mpnn.json' if engine=='solublempnn' else 'biology-result.json')).write_text(canonical(result))
    print(canonical({'engine':engine,'state':'finished','wallSeconds':result['wallSeconds']}),flush=True)


if __name__=='__main__':main()
