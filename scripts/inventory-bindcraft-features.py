"""Inventory the pinned engine's dynamic options without running neural models."""
import argparse,ast,hashlib,inspect,json,math,pathlib,sys
sys.dont_write_bytecode=True
ROOT=pathlib.Path(__file__).resolve().parents[1];SOURCE=ROOT/'vendor/bindcraft2'
sys.path.insert(0,str(SOURCE));sys.path.insert(0,str(ROOT/'scientific'))
from bindcraft import command_modules
from bindcraft import cli
from bindcraft.settings import known_campaign_settings,metric_parameter_names
from bindcraft.loss import REGISTERED_LOSSES
from bindcraft.filters import REGISTERED_FILTER_METRICS
from fold_engine import PIN,verify_source
from campaign_options import RESERVED,CONFORMATION_WEIGHTS
from campaign_profile import property_catalog

def serialize_default(value):
 if value is None or isinstance(value,(str,bool,int)):return value
 if isinstance(value,float):return value if math.isfinite(value) else {'specialFloat':repr(value)}
 if isinstance(value,(tuple,list)):return [serialize_default(v) for v in value]
 if isinstance(value,dict):return {str(k):serialize_default(v) for k,v in value.items()}
 if callable(value):return {'pythonCallable':value.__module__+'.'+value.__qualname__}
 return {'pythonType':type(value).__module__+'.'+type(value).__qualname__,'representation':repr(value)}

def metric_rows(registry):
 rows=[]
 for name,function in sorted(registry.items()):
  signature=inspect.signature(function);parameters=[]
  for key in sorted(metric_parameter_names(function)):
   default=signature.parameters[key].default
   parameters.append({'name':key,'required':default is inspect.Parameter.empty,'default':None if default is inspect.Parameter.empty else serialize_default(default)})
  rows.append({'name':name,'status':'INTEGRATED','scope':'Original registered implementation available to configured native modes. No claim that every metric/objective has an individually validated full trajectory.','parameterExposure':'original_defaults_and_selected_presets; unrestricted nested parameters not exposed by native form','parameters':parameters})
 return rows

def argument_flags(path):
 tree=ast.parse(path.read_text());flags=set()
 for node in ast.walk(tree):
  if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and node.func.attr=='add_argument':
   flags.update(arg.value for arg in node.args if isinstance(arg,ast.Constant) and isinstance(arg.value,str) and arg.value.startswith('-'))
 return sorted(flags)

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--output',default=str(ROOT/'docs/BINDCRAFT_FEATURE_PARITY.json'));args=parser.parse_args();path=pathlib.Path(args.output);report=json.loads(path.read_text());source=verify_source()
 prior={item['name']:item for item in report['campaignSettings']};native={'binder_lengths','campaign_seed','max_trajectories','number_of_final_designs','targets','resume','core','modality'};guarded={'project_folder','design_workers','auto_multi_gpu','attention_backend','use_cueq','design_models','validation_models','validation_model'};properties={entry['name'] for entry in property_catalog(SOURCE)};unsupported=RESERVED|properties
 format_controls={'binder_scaffold','copies','cyclize_peptide'};gpu_controls={'gpu_ids','max_workers_per_gpu','worker_launch_stagger','workers_per_gpu'}
 settings=[]
 for name in sorted(known_campaign_settings()):
  item=prior.get(name,{'name':name})
  if name in native:item.update(status='INTEGRATED',exposure='native_control',limitation='Observed structures or one canonical FASTA target and one selected modality; source modality combinations/mixed FASTA states remain unavailable.' if name in ('targets','modality') else None)
  elif name in properties:item.update(status='INTEGRATED',exposure='native_property_preset_selection',limitation='Already selected through the native property-preset control and original resolver. Duplicate JSON boolean override is intentionally blocked; property-specific scientific validation remains scoped separately.')
  elif name in format_controls:item.update(status='INTEGRATED',exposure='native_format_selection',limitation='Original supplied scaffolds, two-copy homodimer and cyclic-peptide switch are owned by the native format selector. Arbitrary scaffold files/copy counts or format combinations are unavailable; Fab remains a separately tracked resource blocker.')
  elif name in gpu_controls:item.update(status='UNAVAILABLE',exposure='not_applicable_single_device_macos',limitation='Original multi-GPU scheduling control is retained in source. The native Apple Silicon engine owns one scientific worker; this is not a missing Fab algorithm.')
  elif name in guarded:item.update(status='INTEGRATED',exposure='explicit_native_policy',limitation='Execution profiles own this value; arbitrary override is unavailable.')
  elif name in CONFORMATION_WEIGHTS:item.update(status='INTEGRATED',exposure='conformational_scientific_options',limitation='Explicit numeric overrides only in induced-fit/fold-switch modes. Original unbound-state and192aggregate-residue execution checks still apply; full custom-weight trajectory validation is not claimed.')
  elif name=='idr_crop_count':item.update(status='INTEGRATED',exposure='sequence_crop_states',limitation='One immutable FASTA input with up to three original distinct crop states and192aggregate-padded-residue CPU guard. Native two-crop original-model CPU campaign completed359.914s with original anneal rejection,1/0/0 outputs. Three-crop preparation and scalar/fixed-range equivalence checked; accepted multi-crop refolding/import remains unexercised.',evidence='reports/native-bindcraft-two-crop-outcome.json')
  elif name in unsupported:item.update(status='UNAVAILABLE',exposure='source_preserved_native_override_unavailable',limitation='Custom input/execution option is not exposed; applicable shipped preset/default behavior may still run.')
  else:item.update(status='INTEGRATED',exposure='native_advanced_scientific_options',limitation='Strict original settings validation plus native measured resource bounds. External filter files and arbitrary state graphs are unavailable; individual option-specific model campaigns are not all validated.')
  settings.append(item)
 report['campaignSettings']=settings;report['losses']=metric_rows(REGISTERED_LOSSES);report['filterMetrics']=metric_rows(REGISTERED_FILTER_METRICS)
 commands=[]
 for name in sorted(set(command_modules())|set(cli.COMMANDS)|set(cli.COMMAND_MODULES)):
  module=cli.COMMAND_MODULES.get(name,name);file=SOURCE/'bindcraft'/f'{module}.py';flags=argument_flags(file) if file.is_file() else []
  if name=='design':
   flags=sorted(set(cli.design_property_flags())|{'--core','--modality','--metadata','--set','--list-targets','--list-modalities','--list-properties','--list-core','--list-settings','-h','--help'})
  scope={'design':'Native campaign lifecycle, observed/FASTA targets and explicit scientific options with original settings validation. Native lifecycle/models/memory fields remain owned; no combined modalities or unrestricted CLI parity.','rank':'Native original table reranking with up to three tie-breaking metrics, original/highest/lowest direction, saved stages and source metric listing. Arbitrary folder rescoring and every CLI flag are not all exposed.','filter':'Native original saved/custom-threshold filtering, saved-stage selection, source metric listing and rejected CSV export. External filter-file paths are unavailable.','score':'Original score_design recomputes coordinate metrics on 1–4 saved accepted complex CIF files, max384 residues and explicit chain roles. Site/unbound/confidence omissions explicit; not arbitrary structure/flag parity.','campaign_output':'Native original summarize_campaign over all recorded saved stages and trajectory metrics on a private snapshot, with exact original statistics and separate review CSV. Arbitrary CLI paths/flags remain unavailable.','fetch-weights':'Seven pinned official AF2 checkpoints and original ProteinMPNN models bundled; native acquisition differs from upstream fetch-weights command.','archive':'Native original per-trajectory compression with logical byte-checksum verification, atomic macOS directory exchange, persistence-failure rollback and recorded receipts. Bounded saved campaign scope.','unarchive':'Native original per-trajectory restoration with ZIP path/type/size validation, exact logical checksums, atomic exchange and receipts. Bounded saved campaign scope.'}.get(name,'Same original filtering module as the filter alias: native saved/custom-threshold reviews, metric listing and rejected CSV export.' if name=='campaign_filter' else 'Original source retained; no matching native application action is currently connected.')
  status='INTEGRATED' if name in ('design','rank','filter','campaign_filter','score','campaign_output','fetch-weights','archive','unarchive') else 'UNAVAILABLE'
  commands.append({'name':name,'status':status,'scope':scope,'source':str(file.relative_to(ROOT)) if file.is_file() else 'vendor/bindcraft2/bindcraft/cli.py','flags':[{'name':flag,'status':'UNAVAILABLE','scope':'CLI spelling is inventoried; native equivalents/limits are described at command level, not full CLI flag parity.'} for flag in flags]})
 report['scientificOptions']={'status':'INTEGRATED','scope':'Explicit original setting overrides through a native JSON field and original loader. Native input/lifecycle/model/preset controls remain separate; bounded recycles/steps/subbatch/checkpoint choices. Default preparation unchanged; custom recipes and hashes are clearly retained.','evidence':'reports/bindcraft-scientific-options.json'}
 report['remainingNativeOptionGaps']={'implementation':['binder_shapes','parameter_sweep','target','weights_fold_switching'],'notApplicableToSingleDeviceMacOS':sorted(gpu_controls),'accountingCorrection':'Nine property aliases and three format-controlled settings were previously labeled unavailable because raw JSON overrides were blocked. They already have bounded native controls; this reclassification is not twelve newly implemented features and does not certify full scientific parity.'}
 report['commands']=commands;report['inventorySource']={'revision':PIN,'manifestSha256':source['manifestSha256'],'knownCampaignSettings':len(settings),'registeredLosses':len(report['losses']),'registeredFilterMetrics':len(report['filterMetrics']),'commands':len(commands),'files':{str(file.relative_to(ROOT)):hashlib.sha256(file.read_bytes()).hexdigest() for file in (SOURCE/'bindcraft/settings.py',SOURCE/'bindcraft/loss.py',SOURCE/'bindcraft/filters.py',SOURCE/'bindcraft/cli.py')}}
 report['note']='Inventory covers every original known_campaign_settings name, dynamically registered loss/filter metric and its parameters, shipped modality/property presets, discovered source commands and their literal argparse flags. Source presence and default wiring are distinct from native option exposure and scientific validation. Full parity remains incomplete; command internals/public Python helpers are not individually certified.'
 report['fullPortComplete']=False;path.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n');print(json.dumps(report['inventorySource'],indent=2))
if __name__=='__main__':main()
