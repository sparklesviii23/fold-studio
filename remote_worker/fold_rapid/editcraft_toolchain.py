"""Pinned untrained scientific tools, kept separate from trained-model receipts.

Build/install entry points run only in the explicitly approved Linux cloud image.
The Mac only reads this manifest and validates bounded input contracts.
"""
import gzip,hashlib,io,json,os,pathlib,shutil,subprocess,tarfile,tempfile,urllib.request

MANIFEST_PATH=pathlib.Path(__file__).with_name('editcraft_toolchain.json')
MANIFEST=json.loads(MANIFEST_PATH.read_text())
TOOL_ROOT=pathlib.Path('/opt/editcraft-tools')
REFERENCE_ROOT=pathlib.Path('/research/references/editcraft')

def manifest_sha():return hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest()
def file_sha(path):
 digest=hashlib.sha256()
 with pathlib.Path(path).open('rb') as source:
  for chunk in iter(lambda:source.read(1024**2),b''):digest.update(chunk)
 return digest.hexdigest()
def download(url,maximum):
 req=urllib.request.Request(url,headers={'User-Agent':'FoldStudio-EditCraft/0.3 research'})
 with urllib.request.urlopen(req,timeout=60) as response:raw=response.read(maximum+1)
 if len(raw)>maximum:raise ValueError('Approved source exceeds its transfer bound.')
 return raw
def cloud_only():
 if os.environ.get('FOLD_ENGINE_ROLE')!='editcraft_cloud':raise RuntimeError('Scientific tool installation/execution is cloud-only.')

def build_cas_offinder():
 cloud_only();spec=MANIFEST['casOffinder'];raw=download(spec['sourceURL'],spec['sourceBytes'])
 if len(raw)!=spec['sourceBytes'] or hashlib.sha256(raw).hexdigest()!=spec['sourceSha256']:raise ValueError('Pinned Cas-OFFinder source checksum mismatch.')
 TOOL_ROOT.mkdir(parents=True,exist_ok=True)
 with tempfile.TemporaryDirectory(prefix='editcraft-cas-build-') as temporary:
  root=pathlib.Path(temporary)
  with tarfile.open(fileobj=io.BytesIO(raw),mode='r:gz') as archive:
   for entry in archive.getmembers():
    target=(root/entry.name).resolve()
    if not target.is_relative_to(root) or not (entry.isfile() or entry.isdir()):raise ValueError('Unsafe scientific source archive entry.')
   archive.extractall(root,filter='data')
  source=root/('cas-offinder-'+spec['commit']);build=root/'build'
  subprocess.run(['cmake','-S',str(source),'-B',str(build),'-DCMAKE_BUILD_TYPE=Release'],check=True)
  subprocess.run(['cmake','--build',str(build),'--parallel','2'],check=True)
  shutil.copy2(build/'cas-offinder',TOOL_ROOT/'cas-offinder')
  shutil.copy2(source/'LICENSE',TOOL_ROOT/'Cas-OFFinder-LICENSE.txt')
  shutil.copy2(source/'README.md',TOOL_ROOT/'Cas-OFFinder-README.md')
 receipt={'manifestSha256':manifest_sha(),'source':spec,'binarySha256':file_sha(TOOL_ROOT/'cas-offinder'),'licenseSha256':file_sha(TOOL_ROOT/'Cas-OFFinder-LICENSE.txt'),'cpuOnly':True}
 (TOOL_ROOT/'cas-offinder-receipt.json').write_text(json.dumps(receipt,sort_keys=True))
 return receipt

def verify_tool():
 cloud_only();file=TOOL_ROOT/'cas-offinder';receipt=json.loads((TOOL_ROOT/'cas-offinder-receipt.json').read_text())
 if receipt.get('manifestSha256')!=manifest_sha() or receipt.get('source')!=MANIFEST['casOffinder'] or file_sha(file)!=receipt.get('binarySha256'):raise ValueError('Scientific tool does not match its pinned build receipt.')
 if file_sha(TOOL_ROOT/'Cas-OFFinder-LICENSE.txt')!=receipt.get('licenseSha256'):raise ValueError('Scientific tool license receipt is absent or changed.')
 return file,receipt

def prepare_reference(identity):
 cloud_only()
 if identity not in MANIFEST['references']:raise ValueError('Reference is not in the reviewed assembly catalogue.')
 spec=MANIFEST['references'][identity];folder=REFERENCE_ROOT/identity;receipt_file=folder/'receipt.json'
 if receipt_file.is_file():return verify_reference(identity)[1]
 folder.mkdir(parents=True,exist_ok=True)
 raw=download(spec['url'],spec['maximumCompressedBytes'])
 if hashlib.md5(raw).hexdigest()!=spec['compressedMD5']:raise ValueError('NCBI reference archive differs from its published checksum.')
 with gzip.GzipFile(fileobj=io.BytesIO(raw)) as gz:sequence=gz.read(spec['maximumUncompressedBytes']+1)
 if len(sequence)>spec['maximumUncompressedBytes']:raise ValueError('Reference exceeds the approved expanded size.')
 from .editcraft_offtargets import fasta_records
 records=fasta_records(sequence.decode('ascii'),limit=spec['maximumUncompressedBytes'])
 if {key:len(value) for key,value in records.items()}!=spec['contigs']:raise ValueError('Downloaded reference does not match every contig in its reviewed NCBI assembly report.')
 pending=folder/'reference.pending';pending.write_bytes(sequence);pending.replace(folder/'reference.fa')
 receipt={'id':identity,'manifestSha256':manifest_sha(),'assembly':spec['assembly'],'organism':spec['organism'],'coverage':spec['coverage'],'topology':spec['topology'],'source':spec['url'],'assemblyReport':spec['assemblyReport'],'archiveMD5':spec['compressedMD5'],'archiveSha256':hashlib.sha256(raw).hexdigest(),'fastaSha256':hashlib.sha256(sequence).hexdigest(),'bytes':len(sequence),'contigs':{key:{'length':len(value),'sequenceSha256':hashlib.sha256(value.encode()).hexdigest()} for key,value in records.items()}}
 pending=folder/'receipt.pending';pending.write_text(json.dumps(receipt,sort_keys=True));pending.replace(receipt_file)
 return receipt

def verify_reference(identity,expected_sha=None):
 cloud_only()
 if identity not in MANIFEST['references']:raise ValueError('Unknown reviewed reference.')
 folder=REFERENCE_ROOT/identity;receipt=json.loads((folder/'receipt.json').read_text());spec=MANIFEST['references'][identity]
 if receipt.get('id')!=identity or receipt.get('manifestSha256')!=manifest_sha() or receipt.get('assembly')!=spec['assembly'] or receipt.get('coverage')!=spec['coverage'] or receipt.get('topology')!=spec['topology'] or {k:v['length'] for k,v in receipt.get('contigs',{}).items()}!=spec['contigs']:raise ValueError('Reference receipt differs from the reviewed assembly.')
 if expected_sha is not None and receipt.get('fastaSha256')!=expected_sha:raise ValueError('Reference differs from the exact approved experiment snapshot.')
 path=folder/'reference.fa'
 if file_sha(path)!=receipt.get('fastaSha256'):raise ValueError('Reference FASTA checksum mismatch.')
 return path,receipt

if __name__=='__main__':build_cas_offinder()
