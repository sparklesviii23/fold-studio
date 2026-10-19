"""Explicit original scientific overrides; native lifecycle and memory policies stay owned."""
import re
import fold_engine as fe
RESERVED={'core','modality','target','targets','project_folder','binder_lengths','number_of_final_designs','max_trajectories','campaign_seed','resume','design_models','validation_models','validation_model','design_workers','auto_multi_gpu','gpu_ids','workers_per_gpu','max_workers_per_gpu','worker_launch_stagger','compile_next_length','attention_backend','use_cueq','binder_scaffold','copies','cyclize_peptide','binder_shapes','idr_crop_count','parameter_sweep','autotune_loss_weights','weights_induced_fit_interface','weights_induced_fit_global','weights_fold_switching'}

def validate(options,source):
 from campaign_profile import property_catalog
 if not isinstance(options,dict) or any(not isinstance(key,str) for key in options) or len(options)>100:raise ValueError('Original scientific options must be a JSON object with at most 100 named settings.')
 if len(fe.canonical(options).encode())>32768:raise ValueError('Original scientific options exceed 32 KiB.')
 blocked=set(options)&(RESERVED|{entry['name'] for entry in property_catalog(source)})
 if blocked:raise ValueError('Use native campaign, format, property and execution controls for: '+', '.join(sorted(blocked)))
 if 'binder_name' in options and (not isinstance(options['binder_name'],str) or not re.fullmatch('[A-Za-z0-9_-]{1,80}',options['binder_name'])):raise ValueError('Binder name must be a safe 1–80 character filename prefix using letters, numbers, underscores or hyphens.')
 for key in ('design_recycles','validation_recycles','betasheet_reopt_recycles'):
  if key in options and (type(options[key]) is not int or not 0<=options[key]<=3):raise ValueError('Experimental native profiles support 0–3 recycles: '+key)
 for key in ('screen_steps','refine_steps','anneal_steps','harden_steps','mutate_steps','betasheet_reopt_extra_refine_steps','betasheet_reopt_extra_anneal_steps'):
  if key in options and (type(options[key]) is not int or not 0<=options[key]<=200):raise ValueError('Experimental native profiles support 0–200 optimizer steps per stage: '+key)
 if 'subbatch_size' in options and not (options['subbatch_size']=='auto' or type(options['subbatch_size']) is int and 1<=options['subbatch_size']<=4):raise ValueError('Choose auto or a measured subbatch size from 1 to 4.')
 if 'mpnn_model' in options and options['mpnn_model']!='v_48_020':raise ValueError('The packaged ProteinMPNN model is v_48_020.')
 if 'mpnn_variant' in options and options['mpnn_variant'] not in ('neutral','negative','positive'):raise ValueError('Choose a packaged ProteinMPNN variant: neutral, negative or positive.')
 # Arbitrary prediction-state graphs require output/state adapters of their own.
 for section in ('losses','filters'):
  if section in options and not isinstance(options[section],dict):raise ValueError('Supply self-contained JSON objects for losses and filters; external files and implicit filter disabling are unavailable.')
  for entry in options.get(section,{}).values() if isinstance(options.get(section),dict) else ():
   params=entry.get('params',{}) if isinstance(entry,dict) else {}
   if isinstance(params,dict) and set(params)&{'prediction_state','reference_state','binder_shapes'}:raise ValueError('Custom prediction-state references require a validated native state adapter.')
 if 'crop_fasta_sequence' in options:
  crop=options['crop_fasta_sequence'];bounds=crop if isinstance(crop,list) else [crop,crop]
  if crop is not None and crop is not False and (len(bounds)!=2 or any(type(v) is not int or not 1<=v<=4000 for v in bounds) or bounds!=sorted(bounds)):raise ValueError('FASTA crop bounds must be 1–4000 ordered residues, or false for the full sequence.')
 return options

def verify_preparation(preparation):
 receipt=preparation.get('scientificOptions')
 if not receipt:return
 values=receipt.get('values')
 def contained(expected,actual):
  if isinstance(expected,dict):return isinstance(actual,dict) and all(key in actual and contained(value,actual[key]) for key,value in expected.items())
  return expected==actual
 if not isinstance(values,dict) or fe.checksum(fe.canonical(values).encode())!=receipt.get('sha256') or not contained(values,preparation['config']):raise ValueError('Scientific option receipt differs from the saved campaign configuration.')
