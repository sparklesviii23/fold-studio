"""Fetch one genuine AF2 parameter member via bounded HTTP ranges, not a 5.6 GB archive.
The provider ETag pins all ranges. A local SHA-256 records acquired member integrity;
it is not represented as an independently published provider checksum.
"""
import argparse,hashlib,json,pathlib,shutil,urllib.request
URL='https://storage.googleapis.com/alphafold/alphafold_params_2022-12-06.tar'
p=argparse.ArgumentParser();p.add_argument('--model',default='model_1_ptm');p.add_argument('--directory',required=True);a=p.parse_args()
if a.model not in tuple(f'model_{n}_{suffix}' for suffix in ('ptm','multimer_v3') for n in range(1,6)):raise SystemExit('Model not enabled in this acquisition tool.')
out=pathlib.Path(a.directory).expanduser().resolve();out.mkdir(parents=True,exist_ok=True);name='params_'+a.model+'.npz';dest=out/name
if dest.exists():raise SystemExit('Parameter file already exists; refusing to overwrite a recorded checkpoint.')
head=urllib.request.urlopen(urllib.request.Request(URL,method='HEAD'),timeout=30);etag=head.headers['ETag'];total=int(head.headers['Content-Length'])
pins=json.loads((pathlib.Path(__file__).resolve().parents[1]/'scientific/af2-parameters.json').read_text())
if pins['source']!=URL or pins['archiveETag']!=etag:raise RuntimeError('Official archive identity changed; acquisition requires a separately reviewed pin update.')
def fetch(start,end):
 request=urllib.request.Request(URL,headers={'Range':f'bytes={start}-{end}','If-Match':etag})
 response=urllib.request.urlopen(request,timeout=60)
 if response.status!=206 or response.headers.get('Content-Range')!=f'bytes {start}-{end}/{total}':response.close();raise RuntimeError('Provider did not honor exact byte range.')
 return response
position=0
while position+512<=total:
 with fetch(position,position+511) as response:header=response.read(512)
 if not any(header):raise RuntimeError('Model not present in official archive.')
 stored=int(header[148:156].strip(b'\0 ') or b'0',8);check=sum(header[:148])+8*32+sum(header[156:])
 if stored!=check:raise RuntimeError('Invalid TAR header checksum.')
 member=header[:100].split(b'\0')[0].decode();size=int(header[124:136].strip(b'\0 ') or b'0',8)
 print(member,size,flush=True)
 if pathlib.PurePosixPath(member).name==name:
  if shutil.disk_usage(out).free<size+3*1024**3:raise RuntimeError('Insufficient disk space including 3 GiB reserve.')
  partial=dest.with_suffix('.partial');digest=hashlib.sha256();remaining=size
  with fetch(position+512,position+511+size) as response,open(partial,'wb') as target:
   while remaining:
    block=response.read(min(4*1024**2,remaining))
    if not block:raise RuntimeError('Truncated parameter download.')
    target.write(block);digest.update(block);remaining-=len(block)
  partial.replace(dest);manifest={'source':URL,'archiveETag':etag,'archiveBytes':total,'member':member,'memberBytes':size,'sha256':digest.hexdigest(),'checksumAuthority':'Locally computed; no independently published member checksum asserted','model':a.model}
  dest.with_suffix('.provenance.json').write_text(json.dumps(manifest,indent=2)+'\n');print(json.dumps(manifest));break
 position+=512+((size+511)//512)*512
else:raise RuntimeError('Model not found.')
