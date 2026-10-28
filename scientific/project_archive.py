"""Bounded read-only review of Fold project archives. Never extracts or executes."""
import hashlib
import json
import pathlib
import re
import stat
import zipfile

MAX_ARCHIVE = 128 * 1024**2
MAX_EXPANDED = 256 * 1024**2
MAX_MEMBER = 100 * 1024**2
MAX_MANIFEST = 10 * 1024**2


def inspect_archive(parameters):
    if set(parameters) != {'path'} or not isinstance(parameters['path'], str):
        raise ValueError('Choose one local Fold Studio project ZIP.')
    path = pathlib.Path(parameters['path'])
    if path.suffix.lower() != '.zip' or path.is_symlink() or not path.is_file():
        raise ValueError('Choose a regular project ZIP file.')
    with path.open('rb') as stream:
        before = path.stat()
        if before.st_size > MAX_ARCHIVE:
            raise ValueError('Archive review supports ZIP files up to 128 MiB.')
        archive_hash = hashlib.file_digest(stream, 'sha256').hexdigest()
        stream.seek(0)
        with zipfile.ZipFile(stream) as archive:
            entries = archive.infolist()
            names = [entry.filename for entry in entries]
            if len(entries) > 10000 or len({name.casefold() for name in names}) != len(names):
                raise ValueError('Archive has duplicate entries or exceeds 10,000 entries.')
            if sum(entry.file_size for entry in entries) > MAX_EXPANDED:
                raise ValueError('Expanded archive exceeds the 256 MiB review limit.')
            for entry in entries:
                member = pathlib.PurePosixPath(entry.filename)
                mode = entry.external_attr >> 16
                if (member.is_absolute() or '..' in member.parts or '\\' in entry.filename
                        or str(member) != entry.filename.rstrip('/') or not member.parts
                        or stat.S_ISLNK(mode) or entry.flag_bits & 1
                        or entry.file_size > (MAX_ARCHIVE if entry.filename.startswith('snapshots/') else MAX_MEMBER)):
                    raise ValueError('Archive has unsafe, encrypted or oversized entries.')
            if 'project.json' not in names or archive.getinfo('project.json').file_size > MAX_MANIFEST:
                raise ValueError('A bounded project.json manifest is required.')
            data = json.loads(archive.read('project.json'))
            if not isinstance(data, dict) or data.get('format') != 'fold-studio-project-v1':
                raise ValueError('Unsupported Fold Studio project archive format.')
            project, records, jobs, manifest = (data.get(key) for key in ('project', 'records', 'jobs', 'assetManifest'))
            if (not isinstance(project, dict) or not isinstance(project.get('name'), str)
                    or not isinstance(records, list) or not isinstance(jobs, list)
                    or not isinstance(manifest, list)):
                raise ValueError('The archive is missing its project, records, jobs or asset-integrity manifest.')
            declared = {}
            for asset in manifest:
                if not isinstance(asset, dict):
                    raise ValueError('Invalid asset integrity entry.')
                name, sha, size = (asset.get(key) for key in ('file', 'sha256', 'bytes'))
                if (not isinstance(name, str) or not name.startswith('assets/')
                        or len(pathlib.PurePosixPath(name).parts) != 2 or name in declared
                        or not re.fullmatch('[a-f0-9]{64}', str(sha))
                        or type(size) is not int or size < 0 or name not in names
                        or archive.getinfo(name).file_size != size):
                    raise ValueError('Asset integrity receipt is invalid or its file is missing.')
                declared[name] = sha
            snapshots=data.get('importedArchives',[])
            if not isinstance(snapshots,list):raise ValueError('Invalid retained archive manifest.')
            for snapshot in snapshots:
                if not isinstance(snapshot,dict):raise ValueError('Invalid retained archive receipt.')
                name,sha,size=(snapshot.get(key) for key in ('file','sha256','bytes'))
                if (not isinstance(name,str) or not re.fullmatch(r'snapshots/[a-f0-9-]{36}\.zip',name)
                        or name in declared or name not in names or type(size) is not int or size<0
                        or archive.getinfo(name).file_size!=size or not re.fullmatch('[a-f0-9]{64}',str(sha))):
                    raise ValueError('Retained archive checksum receipt is invalid or missing.')
                declared[name]=sha
            genomes=data.get('genomeReferences',[])
            if not isinstance(genomes,list):raise ValueError('Invalid genome reference manifest.')
            genome_count=0
            for reference in genomes:
                if not isinstance(reference,dict) or not isinstance(reference.get('sources'),list):raise ValueError('Invalid genome source receipt.')
                for source in reference['sources']:
                    if not isinstance(source,dict):raise ValueError('Invalid genome source receipt.')
                    name,sha,size=(source.get(key) for key in ('file','sha256','bytes'))
                    if (not isinstance(name,str) or not re.fullmatch(r'genomes/[a-f0-9-]{36}\.(fasta|gff3)',name) or name in declared or name not in names or not re.fullmatch('[a-f0-9]{64}',str(sha)) or type(size) is not int or not 0<=size<=32*1024**2 or archive.getinfo(name).file_size!=size):raise ValueError('Genome source integrity receipt is invalid or missing.')
                    declared[name]=sha;genome_count+=1
            def check_reference(name, sha):
                if (not isinstance(name, str) or pathlib.PurePath(name).name != name
                        or not re.fullmatch('[a-f0-9]{64}', str(sha))
                        or 'assets/' + name not in declared or declared['assets/' + name] != sha):
                    raise ValueError('A saved structure or scene reference differs from the asset manifest.')
            for record in records:
                if not isinstance(record, dict) or not isinstance(record.get('data'), dict):
                    raise ValueError('Invalid saved record.')
                if record.get('kind') == 'structure':
                    info = record['data']
                    references = [(info.get('asset'), info.get('sha256'))]
                    metadata = info.get('metadata', {})
                    if not isinstance(metadata, dict) or not isinstance(metadata.get('ligand', {}), dict):
                        raise ValueError('Invalid structure metadata.')
                    ligand = metadata.get('ligand', {})
                    if ligand.get('sdfAsset'):
                        references.append((ligand['sdfAsset'], ligand.get('sdfSha256')))
                    for name, sha in references:
                        check_reference(name, sha)
            views = data.get('researchViews', [])
            if not isinstance(views, list):
                raise ValueError('Invalid research-view collection.')
            for view in views:
                if not isinstance(view, dict) or not isinstance(view.get('data'), dict):
                    raise ValueError('Invalid saved research view.')
                if view.get('kind') == 'scene' and view['data'].get('engine') == 'chimerax':
                    check_reference(view['data'].get('asset'), view['data'].get('sha256'))
            # Read every file to enforce ZIP CRC integrity without writing anything.
            for entry in entries:
                digest = hashlib.sha256()
                with archive.open(entry) as saved:
                    count = 0
                    while block := saved.read(1024**2):
                        count += len(block)
                        limit=MAX_ARCHIVE if entry.filename.startswith('snapshots/') else MAX_MEMBER
                        if count > min(entry.file_size, limit):
                            raise ValueError('Archive member exceeded its declared size.')
                        digest.update(block)
                if count != entry.file_size:
                    raise ValueError('Archive member size differs from its directory entry.')
                if entry.filename in declared and digest.hexdigest() != declared[entry.filename]:
                    raise ValueError('Asset checksum mismatch: ' + entry.filename)
            after = path.stat()
            if (before.st_ino, before.st_size, before.st_mtime_ns) != (after.st_ino, after.st_size, after.st_mtime_ns):
                raise ValueError('Archive changed during review; choose it again.')
            return {'schemaVersion': 1, 'state': 'integrity_reviewed', 'fileName': path.name,
                    'archiveSha256': archive_hash, 'archiveBytes': before.st_size,
                    'expandedBytes': sum(entry.file_size for entry in entries), 'entryCount': len(entries),
                    'projectName': project['name'], 'recordCount': len(records), 'jobCount': len(jobs),
                    'verifiedAssetCount': sum(name.startswith('assets/') for name in declared), 'verifiedSnapshotCount':len(snapshots), 'verifiedGenomeSourceCount':genome_count, 'crcCheckedFiles': len(entries),
                    'scope': 'Read-only ZIP CRC and declared asset SHA-256 checks. No files extracted, records imported, jobs resumed or code executed. Saved scientific results and undeclared job artifacts are not independently scientifically validated.'}
