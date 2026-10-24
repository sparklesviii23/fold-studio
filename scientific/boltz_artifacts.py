"""Import genuine API result coordinates, with explicit transfer integrity scope."""
import datetime
import hashlib
import ipaddress
import pathlib
import socket
import urllib.parse
import urllib.request
import evolution as ev
import intelligence as mi


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args):raise ValueError('Artifact redirected; refresh the result URL instead.')


def download(artifact):
    url=artifact['url'];parts=urllib.parse.urlsplit(url)
    if parts.scheme!='https' or not parts.hostname or parts.username or parts.password or parts.port not in (None,443):raise ValueError('Invalid HTTPS result artifact endpoint.')
    addresses=socket.getaddrinfo(parts.hostname,443,type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(row[4][0]).is_global for row in addresses):raise ValueError('Artifact endpoint resolves outside the public Internet.')
    expires=datetime.datetime.fromisoformat(artifact['url_expires_at'].replace('Z','+00:00'))
    if expires.tzinfo is None or expires<=datetime.datetime.now(datetime.timezone.utc):raise ValueError('Result URL expired; refresh remote metadata.')
    request=urllib.request.Request(url,headers={'User-Agent':'FoldStudio/1.0'})
    # No API Authorization headers/cookies are forwarded to the object store.
    with urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect).open(request,timeout=30) as response:
        raw=response.read(100*1024**2+1)
        if not raw or len(raw)>100*1024**2:raise ValueError('Result coordinate size is invalid.')
    return raw,{'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw),'retrieved':ev.research.utc(),'host':parts.hostname,'hashScope':'Locally computed exact downloaded bytes; SDK does not provide an independent provider checksum.'}


def import_result(service,request,result,raw,receipt):
    if hashlib.sha256(raw).hexdigest()!=receipt['sha256']:raise ValueError('Downloaded coordinate checksum changed before import.')
    expected={}
    for entity in result['entities']:
        if entity['type']!='protein' or entity.get('modifications') or entity.get('cyclic'):raise ValueError('This result importer requires canonical linear protein chains; modified representations need separate chemistry validation.')
        seq=entity['value']
        if not seq or set(seq)-ev.AA:raise ValueError('Returned protein sequence is not canonical.')
        for chain in entity['chain_ids']:
            if chain in expected:raise ValueError('Duplicate remote chain identity.')
            expected[chain]=seq
    fmt='mmcif' if b'_atom_site.' in raw else 'pdb' if b'ATOM  ' in raw else None
    if not fmt:raise ValueError('API structure artifact is not supported PDB/mmCIF; archives are not extracted implicitly.')
    parsed=mi.parse_structure(raw.decode(),fmt);observed={c['id']:c['sequence'] for c in parsed['chains'] if c['sequence']}
    if any(observed.get(ch)!=seq for ch,seq in expected.items()):raise ValueError('API coordinate chain sequences differ from the official result metadata.')
    if observed.get('Z')!=expected.get('Z') or 'Z' not in expected:raise ValueError('Result binder chain does not match the submitted explicit Z mapping.')
    for entity in request['request']['target']['entities']:
        for chain in entity['chain_ids']:
            if observed.get(chain)!=entity['value']:raise ValueError('API result lost or changed a submitted target chain.')
    parent=None
    if request['operation']=='protein_library_screen':
        external=result.get('external_id');snapshot=next((r for r in request['candidateSnapshots'] if r['id']==external),None)
        if not snapshot:raise ValueError('Screen result external ID does not identify a submitted immutable sequence.')
        parent=ev.Evolution(service).candidate(request['projectId'],external)
        if parent['sequenceSha256']!=snapshot['sequenceSha256'] or expected['Z']!=parent['sequence']:raise ValueError('Screen result sequence changed from the submitted parent.')
    metadata={'boltzRequestId':request['id'],'boltzResultId':result['id'],'engine':'Boltz official API','rawMetrics':result['metrics'],'downloadReceipt':receipt,'experimentalValidation':False}
    existing=next((r for r in service.library({})['records'] if r['project_id']==request['projectId'] and r['data'].get('metadata',{}).get('boltzRequestId')==request['id'] and r['data'].get('metadata',{}).get('boltzResultId')==result['id']),None)
    if existing:return {'record':existing,'alreadyImported':True}
    folder=service.root/'remote-results'/'boltz'/request['id'];folder.mkdir(parents=True,exist_ok=True);path=folder/(receipt['sha256']+('.cif' if fmt=='mmcif' else '.pdb'));path.write_bytes(raw)
    record=service.import_structure({'projectId':request['projectId'],'path':str(path),'name':'Boltz API · '+result['id'],'source':'Official Boltz API computational result','metadata':metadata})
    library=ev.Evolution(service)
    if parent:
        with service.db:library.event(parent['projectId'],parent['id'],'prediction',{'structure':{'recordId':record['id'],'sha256':record['data']['sha256'],'chain':'Z'},'family':'Boltz','receipt':metadata,'metrics':result['metrics'],'experimentalValidation':False})
        candidate=parent
    else:
        candidate=library.evolution_import({'projectId':request['projectId'],'structureId':record['id'],'chain':'Z','reference':{'source':'Official Boltz API design','uncertainty':'Computational candidate; no experimental support inferred.'}})['candidates'][0]
        with service.db:library.event(request['projectId'],candidate['id'],'assessment',{'model':'BoltzProt-1 official service','family':'Boltz','role':'generation','metrics':result['metrics'],'receipt':metadata})
    return {'record':record,'candidateId':candidate['id'],'downloadReceipt':receipt,'experimentalValidation':False}
