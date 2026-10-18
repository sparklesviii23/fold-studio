"""Local integrity receipts for the actual protein-prediction model inputs.
The confidence checkpoint is checked against the publisher Git LFS SHA-256;
chemical dictionary hashes are locally computed. Acquisition is atomic and
never replaces an existing usable cache that differs from the reviewed pin.
"""
import hashlib,json,pathlib,shutil,urllib.request
AMINO={'A':'ALA','R':'ARG','N':'ASN','D':'ASP','C':'CYS','E':'GLU','Q':'GLN','G':'GLY','H':'HIS','I':'ILE','L':'LEU','K':'LYS','M':'MET','F':'PHE','P':'PRO','S':'SER','T':'THR','W':'TRP','Y':'TYR','V':'VAL'}

def file_digest(path):
 digest=hashlib.sha256()
 with pathlib.Path(path).open('rb') as stream:
  while block:=stream.read(4*1024**2):digest.update(block)
 return digest.hexdigest()

def model_pin():return json.loads(pathlib.Path(__file__).with_name('boltz-parameters.json').read_text())

def ensure_checkpoint(cache):
 """Acquire the pinned official checkpoint before any model deserialization."""
 cache=pathlib.Path(cache);cache.mkdir(parents=True,exist_ok=True);pin=model_pin();path=cache/pin['file']
 if path.is_file():
  with path.open('rb') as stream:header=stream.read(128)
  placeholder=not path.stat().st_size or header.startswith(b'version https://git-lfs.github.com/spec/v1')
  if not placeholder:
   if path.stat().st_size!=pin['bytes'] or file_digest(path)!=pin['sha256']:raise ValueError('Boltz confidence checkpoint differs from the reviewed publisher SHA-256. Existing cache is preserved.')
   return pin
 if shutil.disk_usage(cache).free<pin['bytes']+1024**3:raise ValueError('Insufficient space for the 2.29 GB trained Boltz checkpoint and a 1 GiB reserve.')
 print('Downloading pinned Boltz confidence checkpoint from the publisher repository.',flush=True)
 partial=path.with_suffix('.partial');digest=hashlib.sha256();received=0
 with urllib.request.urlopen(pin['source'],timeout=120) as response,partial.open('wb') as target:
  while block:=response.read(4*1024**2):
   received+=len(block)
   if received>pin['bytes']:raise ValueError('Checkpoint download exceeds the published size.')
   target.write(block);digest.update(block)
 if received!=pin['bytes'] or digest.hexdigest()!=pin['sha256']:raise ValueError('Checkpoint download failed publisher size/SHA-256 verification; no model loaded.')
 partial.replace(path);path.with_suffix('.provenance.json').write_text(json.dumps(pin,indent=2)+'\n');return pin

def fingerprints(cache,chains):
 cache=pathlib.Path(cache);files=['boltz2_conf.ckpt']+['mols/'+AMINO[aa]+'.pkl' for aa in sorted(set(''.join(chain['sequence'] for chain in chains)))]
 out={}
 for name in files:
  path=cache/name
  if not path.is_file():continue
  out[name]={'bytes':path.stat().st_size,'sha256':file_digest(path)}
  if name=='boltz2_conf.ckpt':
   with path.open('rb') as stream:header=stream.read(128)
   out[name]['repairablePlaceholder']=not path.stat().st_size or header.startswith(b'version https://git-lfs.github.com/spec/v1')
 return out

def receipt(before,after,pin=None):
 if 'boltz2_conf.ckpt' not in after or after['boltz2_conf.ckpt'].get('repairablePlaceholder'):raise ValueError('Completed prediction has no usable model checkpoint integrity receipt.')
 changed=[name for name,value in before.items() if after.get(name)!=value and not (name=='boltz2_conf.ckpt' and value.get('repairablePlaceholder'))]
 if changed:raise ValueError('Model resources changed during prediction: '+', '.join(changed))
 if pin and after[pin['file']]['sha256']!=pin['sha256']:raise ValueError('Model checkpoint differs from the reviewed publisher SHA-256.')
 return {'files':after,'checkpointPin':pin,'repairedPlaceholders':[name for name,value in before.items() if value.get('repairablePlaceholder') and after.get(name)!=value],'checksumAuthority':'Checkpoint matched the publisher Git LFS SHA-256' if pin else 'Locally computed; no independent provider checksum asserted','scope':'Boltz-2 confidence checkpoint and canonical amino-acid CCD files present for the supplied protein sequences. Unused affinity weights and the full chemical dictionary are not asserted as validated.'}
