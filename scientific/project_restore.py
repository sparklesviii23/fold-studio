"""Restore a new library copy; preserve complete domain/job history as inert snapshots."""
import datetime
import hashlib
import json
import os
import pathlib
import re
import tempfile
import uuid
import zipfile
from project_archive import inspect_archive, MAX_ARCHIVE

TABLE = 'imported_project_archives'
SCOPE = ('A new project contains the restored Library records with remapped identities and unchanged asset bytes. '
         'All original domain data, job receipts and archived files are retained in the checksummed source ZIP. '
         'Archived jobs are historical snapshots, never live or resumable jobs; domain-specific operational state is not activated.')


def rows(s, project_id=None):
    if not s.db.execute("SELECT 1 FROM sqlite_master WHERE name=?", (TABLE,)).fetchone():
        return []
    query='SELECT * FROM '+TABLE
    return s.rows(query+(' WHERE project_id=?' if project_id else ''), (project_id,) if project_id else ())


def summary(row):
    data=json.loads(row['data'])
    return {key:row[key] for key in ('id','project_id','source_sha256','file_name','created')} | {
        'sourceProjectName':data['sourceProjectName'],'recordCount':data['recordCount'],
        'archivedJobCount':data['archivedJobCount'],'retainedSections':data['retainedSections'],'scope':SCOPE}


def list_snapshots(s,p):
    if set(p)!={'projectId'}:raise ValueError('Choose one project for archive history.')
    s.project(p['projectId'])
    return [summary(row) for row in rows(s,p['projectId'])]


def snapshot_source(s,p):
    if set(p)-{'projectId','id','path'}:raise ValueError('Unsupported archive history field.')
    s.project(p['projectId'])
    row=next((row for row in rows(s,p['projectId']) if row['id']==p.get('id')),None)
    if not row:raise ValueError('Choose an imported archive in this project.')
    name=row['asset']
    if pathlib.Path(name).name!=name:raise ValueError('Invalid retained archive identity.')
    path=s.root/'archive-imports'/name
    if path.is_symlink() or not path.is_file() or path.stat().st_size>MAX_ARCHIVE:raise ValueError('The original retained archive is missing or exceeds its limit.')
    with path.open('rb') as stream:
        if hashlib.file_digest(stream,'sha256').hexdigest()!=row['source_sha256']:raise ValueError('The original retained archive checksum changed.')
    return row,path


def read_snapshot(s,p):
    row,path=snapshot_source(s,p)
    with zipfile.ZipFile(path) as archive:data=json.loads(archive.read('project.json'))
    return {'archive':summary(row),'originalManifest':data,'identityMap':json.loads(row['data'])['identityMap'],
            'scope':'Original manifest and receipts, not an operational or resumable campaign. Original IDs are preserved here; identityMap resolves restored Library records.'}


def copy_checked(source,destination,expected):
    digest=hashlib.sha256();count=0
    with source.open('rb') as original,destination.open('xb') as saved:
        while block:=original.read(1024**2):
            count+=len(block)
            if count>MAX_ARCHIVE:raise ValueError('Archive source grew beyond its limit.')
            digest.update(block);saved.write(block)
    if digest.hexdigest()!=expected:raise ValueError('Archive changed after its reviewed snapshot; review it again.')


def export_original(s,p):
    row,source=snapshot_source(s,p);target=pathlib.Path(p['path'])
    if target.suffix.lower()!='.zip':raise ValueError('The retained original uses ZIP format.')
    temporary=target.with_name('.'+target.name+'.'+str(uuid.uuid4())+'.tmp')
    try:
        copy_checked(source,temporary,row['source_sha256']);os.replace(temporary,target)
    finally:temporary.unlink(missing_ok=True)
    return {'path':str(target),'sha256':row['source_sha256'],'scope':'Exact original imported ZIP, unchanged; no jobs executed.'}


def import_archive(s,p):
    if set(p)-{'path','expectedSha256','name'} or not re.fullmatch('[a-f0-9]{64}',str(p.get('expectedSha256',''))):
        raise ValueError('Review the archive and supply its exact SHA-256 before restoring a copy.')
    review=inspect_archive({'path':p['path']})
    if review['archiveSha256']!=p['expectedSha256']:raise ValueError('Archive differs from the reviewed snapshot; review it again.')
    existing=next((row for row in rows(s) if row['source_sha256']==review['archiveSha256']),None)
    if existing:return {'state':'already_imported','projectId':existing['project_id'],'archive':summary(existing),'scope':'This exact archive already has a restored copy; no records were overwritten or duplicated.'}
    name=p.get('name',review['projectName']+' · imported')
    if not isinstance(name,str) or not name.strip() or len(name)>160 or any(ord(c)<32 for c in name):raise ValueError('Use an imported project name of 1–160 characters without control characters.')
    project_id,snapshot_id=str(uuid.uuid4()),str(uuid.uuid4());created=datetime.datetime.now(datetime.timezone.utc).isoformat()
    folder=s.root/'archive-imports';folder.mkdir(exist_ok=True)
    if folder.is_symlink():raise ValueError('Archive storage must be a real local directory.')
    published=[]
    with tempfile.TemporaryDirectory(prefix='project-import-',dir=s.root/'cache') as temporary:
        staging=pathlib.Path(temporary);source=staging/'source.zip';copy_checked(pathlib.Path(p['path']),source,review['archiveSha256'])
        # A snapshot, not the mutable chooser path, is used for all subsequent reads.
        with zipfile.ZipFile(source) as archive:
            data=json.loads(archive.read('project.json'));project=data['project'];records=data['records']
            old_project=project.get('id')
            def canonical_id(value):
                try:return isinstance(value,str) and str(uuid.UUID(value))==value
                except (ValueError,AttributeError):return False
            if not canonical_id(old_project):raise ValueError('The saved project has no supported canonical identity.')
            record_ids=[row.get('id') for row in records]
            if any(not canonical_id(value) for value in record_ids) or len(set(record_ids))!=len(record_ids):raise ValueError('Record identities must be canonical and unique.')
            if any(row.get('project_id')!=old_project for row in records):raise ValueError('An archived record belongs to a different project.')
            mapping={old_project:project_id,**{old:str(uuid.uuid4()) for old in record_ids}}
            if old_project in record_ids:raise ValueError('Project and record identities conflict.')
            asset_mapping={}
            for asset in data['assetManifest']:
                original=asset['file'].split('/')[1];suffix=pathlib.Path(original).suffix
                if not re.fullmatch(r'\.[A-Za-z0-9]{1,12}',suffix):raise ValueError('An archived asset has an unsupported extension.')
                renamed=str(uuid.uuid4())+suffix.lower();asset_mapping[original]=renamed
                raw=archive.read(asset['file'])
                if hashlib.sha256(raw).hexdigest()!=asset['sha256']:raise ValueError('Asset checksum changed after review.')
                (staging/renamed).write_bytes(raw)
            id_fields={'id','projectId','project_id','recordId','record_id','structureId','structure_id','parentRecordId','parentId','sourceRecordId','sourceStructureId','targetStructureId','derivedFrom','outputs','recordIds','structureIds','sourceRecordIds'}
            asset_fields={'asset','sdfAsset','coordinateAsset','inputAsset'}
            def remap(value,field=None):
                if isinstance(value,str):
                    return mapping.get(value,value) if field in id_fields else asset_mapping.get(value,value) if field in asset_fields else value
                if isinstance(value,list):return [remap(v,field) for v in value]
                if isinstance(value,dict):return {key:remap(v,key) for key,v in value.items()}
                return value
            restored=[]
            for record in records:
                if record.get('kind') not in ('protein','sequence','variant','structure','analysis','figure','complex') or not isinstance(record.get('name'),str) or len(record['name'])>200:raise ValueError('Unsupported Library record schema.')
                if record['kind']=='structure' and record['data'].get('format') not in ('pdb','mmcif'):raise ValueError('Unsupported archived molecular coordinate format.')
                info=remap(record['data'])
                info['archiveOrigin']={'snapshotId':snapshot_id,'sourceArchiveSha256':review['archiveSha256'],'originalProjectId':old_project,'originalRecordId':record['id'],
                    'originalDataSha256':hashlib.sha256(json.dumps(record['data'],sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest(),
                    'scope':'Library identities remapped; original scientific receipt and identifiers retained in the source archive snapshot.'}
                restored.append((mapping[record['id']],project_id,record['kind'],record['name'],json.dumps(info,allow_nan=False),record.get('created') or created))
        meta={'sourceProjectName':project['name'],'recordCount':len(restored),'archivedJobCount':len(data['jobs']),
              'retainedSections':sorted(key for key in data if key not in ('format','exported','project','records','assetManifest')),'identityMap':mapping,'assetMap':asset_mapping}
        s.db.execute('BEGIN IMMEDIATE')
        try:
            s.db.execute('CREATE TABLE IF NOT EXISTS '+TABLE+'(id TEXT PRIMARY KEY,project_id TEXT NOT NULL,source_sha256 TEXT NOT NULL UNIQUE,file_name TEXT NOT NULL,asset TEXT NOT NULL,data TEXT NOT NULL,created TEXT NOT NULL)')
            if s.db.execute('SELECT 1 FROM '+TABLE+' WHERE source_sha256=?',(review['archiveSha256'],)).fetchone():raise ValueError('This archive was imported concurrently; refresh its history.')
            notes=project.get('notes','')
            if not isinstance(notes,str):raise ValueError('Invalid project notes.')
            s.db.execute('INSERT INTO projects VALUES(?,?,?,?,?)',(project_id,name.strip(),notes,created,created))
            s.db.executemany('INSERT INTO records VALUES(?,?,?,?,?,?)',restored)
            original_asset=snapshot_id+'.zip'
            s.db.execute('INSERT INTO '+TABLE+' VALUES(?,?,?,?,?,?,?)',(snapshot_id,project_id,review['archiveSha256'],review['fileName'],original_asset,json.dumps(meta),created))
            for renamed in asset_mapping.values():
                target=s.root/'assets'/renamed;os.link(staging/renamed,target);published.append(target)
            target=folder/original_asset;os.link(source,target);published.append(target)
            s.db.commit()
        except Exception:
            s.db.rollback()
            for path in published:path.unlink(missing_ok=True)
            raise
    return {'state':'imported_library_copy','projectId':project_id,'projectName':name.strip(),'recordCount':len(restored),'archivedJobCount':len(data['jobs']),
            'snapshotId':snapshot_id,'archiveSha256':review['archiveSha256'],'identityMap':mapping,'scope':SCOPE}


def export_snapshots(s,project_id,archive):
    result=[]
    for row in rows(s,project_id):
        _,source=snapshot_source(s,{'projectId':project_id,'id':row['id']})
        member='snapshots/'+row['id']+'.zip';digest=hashlib.sha256();size=0
        with source.open('rb') as original,archive.open(member,'w') as saved:
            while block:=original.read(1024**2):
                size+=len(block)
                if size>MAX_ARCHIVE:raise ValueError('Retained archive grew beyond its limit.')
                digest.update(block);saved.write(block)
        if digest.hexdigest()!=row['source_sha256']:raise ValueError('Retained archive changed during project export.')
        result.append({**summary(row),'file':member,'sha256':row['source_sha256'],'bytes':size})
    return result
