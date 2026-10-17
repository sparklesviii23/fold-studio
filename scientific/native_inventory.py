"""Inspect the selected running release; availability never implies verification."""
import hashlib, importlib.metadata, json, time

def inventory(session, command_catalog, integrated=False):
    rows=[]; errors=[]
    bundles=list(session.toolshed.bundle_info(session.logger, installed=True, available=False))
    def add(kind,name,bundle='',dependencies=None,original='',access='',**extra):
        entry=dict(kind=kind,name=str(name),source=bundle,dependencies=dependencies or [],
            originalInterface=original,integrationMethod='Original installed runtime API / Qt interface',
            foldAccess=access,status='implemented_unverified' if integrated else 'upstream_available',
            automatedTest='enumerated; execution not tested',manualVerification='pending',
            limitations='External services, hardware, optional dependencies and tool-specific licenses may apply.')
        entry.update(extra);rows.append(entry)
    for bundle in bundles:
        try: dependencies=importlib.metadata.requires(bundle.name) or []
        except Exception: dependencies=[]
        add('bundle',bundle.name,bundle.name,dependencies,'Toolshed','Tools → More Tools / Toolshed',version=str(bundle.version),packages=bundle.packages,providers=bundle.providers)
        for tool in bundle.tools:
            add('tool',tool.name,bundle.name,dependencies,'Tools menu','Original Tools menu',categories=tool.categories)
    for command in command_catalog()['commands']:
        module=command.get('implementation') or ''
        owner=next((b for b in bundles if any(module=='.'.join(p) or module.startswith('.'.join(p)+'.') for p in b.packages)),None)
        try:dependencies=importlib.metadata.requires(owner.name) or [] if owner else []
        except Exception:dependencies=[]
        add('command',command['name'],owner.name if owner else module,dependencies,original='Command Line / command scripts',access='Native Command Line / FOLD Console',metadata=command)
    try:
        for fmt in session.data_formats.formats:
            owner=next((b for b in bundles if 'data formats/'+fmt.name in b.providers),None)
            try:dependencies=importlib.metadata.requires(owner.name) or [] if owner else []
            except Exception:dependencies=[]
            add('format',fmt.name,owner.name if owner else 'data_formats manager',dependencies,original='File → Open / Save',access='Original File menu',suffixes=fmt.suffixes,category=fmt.category)
    except Exception as error: errors.append('formats: '+str(error))
    # These registries have native implementations, not an emulated web theme.
    for name,source in [('cartoon','ChimeraX-StdCommands'),('ribbon','ChimeraX-Atomic'),('stick','ChimeraX-Atomic'),('sphere','ChimeraX-Atomic'),('ball','ChimeraX-Atomic'),('surface','ChimeraX-Surface'),('volume','ChimeraX-Map')]:
        add('representation',name,source,original='Native commands and tool controls',access='Native commands and original tools',limitations='Named native styles; not an exhaustive registry of every extension representation.')
    if session.ui.is_gui:
        def menus(menu,prefix=''):
            for action in menu.actions():
                if action.isSeparator(): continue
                label=prefix+action.text().replace('&','')
                add('menu',label,'ChimeraX-UI / originating native tool', ['Installed Qt and provider bundle'],original=label,access=label,enabled=action.isEnabled())
                if action.menu(): menus(action.menu(),label+' → ')
        menus(session.ui.main_window.menuBar())
        settings=getattr(session.ui,'settings',None)
        if settings:
            names=set(getattr(settings,'EXPLICIT_SAVE',{}))|set(getattr(settings,'AUTO_SAVE',{}))
            for name in sorted(names):add('preference',name,'ChimeraX-UI',original='Settings / Preferences',access='Original Settings / Preferences')
    else: errors.append('Menu actions, GUI preferences and tool interactions require a GUI session.')
    for name in ['ANGPTL3/8 chain and residue colours','Native session round trip','Molecular surface','Distance measurement','Matchmaker alignment','Contacts and hydrogen bonds','Python script','Command script','Structure export','Prediction and peptide handoff']:
        add('workflow',name,original='Native commands / tools',access='FOLD native workspace',limitations='See separate acceptance report for measured evidence; discovery is not execution.')
    fingerprint=hashlib.sha256(json.dumps(rows,sort_keys=True,default=str).encode()).hexdigest()
    return {'schemaVersion':1,'created':time.strftime('%Y-%m-%dT%H:%M:%S%z'),'integrated':integrated,
        'capabilities':rows,'count':len(rows),'fingerprint':fingerprint,'enumerationErrors':errors,
        'scope':'Actual installed bundles, registered commands, formats and current GUI menus. Dynamic menus, tool-specific settings and optional workflows require manual expansion.',
        'completeParityVerified':False}
