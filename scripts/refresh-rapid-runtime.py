"""Overlay a reviewed worker release without reinstalling scientific runtimes.

Used during RC packaging after protocol fixes; never mutates a running container.
The original Dockerfile remains the clean build route for each runtime image.
"""
import argparse,json,pathlib,shutil,subprocess,sys,tempfile
ROOT=pathlib.Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--base',required=True);p.add_argument('--tag',required=True);p.add_argument('--release',type=pathlib.Path,required=True);p.add_argument('--metadata',type=pathlib.Path,required=True);a=p.parse_args()
docker='/opt/homebrew/bin/docker' if sys.platform=='darwin' else 'docker'
buildx=['/opt/homebrew/lib/docker/cli-plugins/docker-buildx'] if sys.platform=='darwin' else [docker,'buildx']
with tempfile.TemporaryDirectory(prefix='rapid-refresh-') as temporary:
 root=pathlib.Path(temporary);shutil.copytree(a.release/'release',root/'release');shutil.copy2(ROOT/'remote_worker/containers/startup.sh',root/'startup.sh');(root/'startup.sh').chmod(0o755)
 (root/'Dockerfile').write_text('ARG BASE\nFROM ${BASE}\nCOPY release /opt/fold-rapid-release\nCOPY startup.sh /usr/local/bin/rapid-start\nRUN /opt/fold-rapid/bin/pip install --no-index --no-deps --no-build-isolation /opt/fold-rapid-release/worker\nLABEL org.opencontainers.image.title="Fold Studio RAPID Compute Worker" org.opencontainers.image.version="0.2.0" io.fold.cuda-qualified="false"\n')
 a.metadata.parent.mkdir(parents=True,exist_ok=True)
 subprocess.run([*buildx,'build','--platform','linux/amd64','--build-arg','BASE='+a.base,'--tag',a.tag,'--load','--metadata-file',str(a.metadata),str(root)],check=True)
 inspect=json.loads(subprocess.check_output([docker,'image','inspect',a.tag],text=True))[0]
 a.metadata.with_suffix('.image.json').write_text(json.dumps(inspect,indent=2)+'\n')
 print(json.dumps({'tag':a.tag,'id':inspect['Id'],'architecture':inspect['Architecture'],'scientificRuntimesReinstalled':False}))
