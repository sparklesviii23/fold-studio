"""Actual Scanpy pipeline; input checks require only the standard library locally.

Scientific libraries and H5AD loading execute only in the approved cloud runtime.
Native output is a bounded real processed view; complete artifacts stay on Modal.
"""
import base64,hashlib,json,math,numbers,os,pathlib,re,urllib.request,uuid
MANIFEST_PATH=pathlib.Path(__file__).with_name('editcraft_cell_assets.json')
MANIFEST=json.loads(MANIFEST_PATH.read_text());DATA_ROOT=pathlib.Path('/research/datasets/editcraft');MAX_BYTES=8*1024**2
HDF_HEADER=b'\x89HDF\r\n\x1a\n'
def manifest_sha():return hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest()
def cloud_only():
 if os.environ.get('FOLD_ENGINE_ROLE')!='editcraft_cloud':raise RuntimeError('Single-cell scientific execution and dataset preparation are cloud-only.')
def file_sha(path):
 h=hashlib.sha256()
 with pathlib.Path(path).open('rb') as stream:
  for chunk in iter(lambda:stream.read(1024**2),b''):h.update(chunk)
 return h.hexdigest()
def artifact_info(artifact,key,root=pathlib.Path('/research')):
 if not re.fullmatch('[a-f0-9]{32}',str(key)):raise ValueError('Invalid scientific experiment identity.')
 root=pathlib.Path(root).resolve();job=root/key;path=pathlib.Path(artifact['path']).resolve()
 # Modal can expose a mounted volume through a symlink. Resolve both sides;
 # resolving only the file incorrectly rejects a legitimate owned artifact.
 if not path.is_relative_to(job):raise ValueError('Processed artifact is outside its original experiment.')
 if not path.is_file():raise ValueError('Original processed artifact is unavailable in the research volume.')
 if not 0<path.stat().st_size<=128*1024**2 or path.stat().st_size!=artifact['bytes']:raise ValueError('Processed artifact size differs from its original receipt.')
 if file_sha(path)!=artifact['sha256']:raise ValueError('Processed artifact checksum differs from its original receipt.')
 return {**artifact,'volumePath':str(path.relative_to(root))}
def integer(value,low,high,name):
 if type(value)is not int or not low<=value<=high:raise ValueError(name+' is outside its explicit scientific input bounds.')
def validate_input(p):
 if not isinstance(p,dict) or not re.fullmatch('[a-f0-9]{64}',str(p.get('datasetSha256',''))):raise ValueError('Select an installed H5AD dataset by exact source SHA-256.')
 for key,low,high in [('seed',0,2**31-1),('minGenes',1,10000),('maxGenes',2,40000),('minCells',1,10000),('nTopGenes',50,3000),('nPCs',2,50),('nNeighbors',2,100),('maxDisplayCells',100,10000)]:integer(p.get(key),low,high,key)
 if p['maxGenes']<=p['minGenes']:raise ValueError('The exclusive maximum-gene threshold must exceed the minimum.')
 for key,low,high in [('maxMitoPct',0.01,100),('resolution',.01,5),('minDist',0,1)]:
  if type(p.get(key))not in(int,float) or not math.isfinite(p[key]) or not low<=p[key]<=high:raise ValueError('Invalid '+key+' scientific parameter.')
 if not isinstance(p.get('mitoPrefix'),str) or not re.fullmatch('[A-Za-z0-9_.-]{1,30}',p['mitoPrefix']):raise ValueError('Declare the mitochondrial gene-name prefix explicitly.')
 genes=p.get('displayGenes')
 if not isinstance(genes,list) or not 1<=len(genes)<=16 or any(not isinstance(g,str) or not re.fullmatch('[A-Za-z0-9_.-]{1,80}',g) for g in genes) or len(set(genes))!=len(genes):raise ValueError('Choose 1–16 unique gene names for the real expression display.')
 columns=p.get('metadataColumns',[])
 if not isinstance(columns,list) or len(columns)>8 or any(not isinstance(c,str) or not 1<=len(c)<=80 or not c.strip() or any(ord(char)<32 for char in c) for c in columns) or len(set(columns))!=len(columns):raise ValueError('Choose at most eight explicit observation-metadata columns.')
 return p
def validate_shape(shape,nnz=None,dense=False):
 if len(shape)!=2 or any(type(n)is not int for n in shape) or not 5<=shape[0]<=10000 or not 50<=shape[1]<=40000:raise ValueError('This CPU worker accepts 5–10,000 cells and 50–40,000 genes.')
 if dense and shape[0]*shape[1]>50000000 or nnz is not None and not 0<nnz<=15000000:raise ValueError('H5AD matrix exceeds the reviewed memory profile.')

def display_view(result,maximum,seed):
 # Sampling affects presentation only. Complete matrices, metadata and QC remain
 # in H5AD; global cluster counts and means are never recomputed on this view.
 cells=result['cells'];expression=result['expression'];ordered=sorted(range(len(cells)),key=lambda i:hashlib.sha256((str(seed)+'\0'+cells[i]['barcode']).encode()).digest());limit=min(maximum,len(cells));initial=limit
 while True:
  indices=sorted(ordered[:limit]);result['cells']=[cells[i] for i in indices];result['expression']=[{**g,'values':[g['values'][i] for i in indices]} for g in expression]
  result['display']={'cells':len(indices),'retainedCells':len(cells),'allRetainedCellsDisplayed':len(indices)==len(cells),'requestedMaximum':maximum,'selectionMethod':'all retained cells' if len(indices)==len(cells) else 'deterministic SHA-256 barcode/seed display sample; scientific analysis uses every retained cell','reducedForNativePayloadBound':limit<initial,'fullAnalysisPreservedInH5AD':True}
  if len(json.dumps(result,allow_nan=False).encode())<=3*1024**2:return result
  if limit<=1:raise ValueError('Even a minimal display exceeds the native payload limit; full processed artifacts remain saved remotely.')
  limit=max(1,limit//2)

def prepare_dataset(payload):
 cloud_only();kind=payload.get('kind')
 if kind=='public':
  identity=payload.get('id');spec=MANIFEST['datasets'].get(identity)
  if not spec:raise ValueError('Dataset is not in the reviewed public catalogue.')
  expected=spec['sha256'];source={'kind':'public','id':identity,**spec}
  cached=DATA_ROOT/expected/'receipt.json'
  if cached.is_file():return verify_dataset(expected)[1]
  with urllib.request.urlopen(urllib.request.Request(spec['url'],headers={'User-Agent':'FoldStudio-EditCraft/0.4 research'}),timeout=60) as response:raw=response.read(spec['bytes']+1)
  if len(raw)!=spec['bytes']:raise ValueError('Public H5AD size differs from the reviewed reference.')
 elif kind=='upload':
  expected=payload.get('sha256');name=payload.get('name')
  if not isinstance(name,str) or not 1<=len(name)<=200 or not isinstance(payload.get('base64'),str) or len(payload['base64'])>12*1024**2:raise ValueError('Invalid bounded H5AD upload.')
  raw=base64.b64decode(payload['base64'],validate=True);source={'kind':'user_upload','name':name,'evidence':'user_supplied_observations','metadataStatus':'Scientific metadata is read and validated only during the approved analysis.'}
 else:raise ValueError('Choose a reviewed public dataset or an explicitly approved H5AD upload.')
 if not re.fullmatch('[a-f0-9]{64}',str(expected)) or not 8<len(raw)<=MAX_BYTES or raw[:8]!=HDF_HEADER or hashlib.sha256(raw).hexdigest()!=expected:raise ValueError('H5AD header, size or original source checksum is invalid.')
 folder=DATA_ROOT/expected;folder.mkdir(parents=True,exist_ok=True);pending=folder/('dataset-'+uuid.uuid4().hex+'.pending');pending.write_bytes(raw);pending.replace(folder/'source.h5ad')
 receipt={'sha256':expected,'manifestSha256':manifest_sha(),'bytes':len(raw),'source':source,'analysisPerformed':False}
 pending=folder/'receipt.pending';pending.write_text(json.dumps(receipt,sort_keys=True));pending.replace(folder/'receipt.json');return receipt
def verify_dataset(identity):
 cloud_only()
 if not re.fullmatch('[a-f0-9]{64}',str(identity)):raise ValueError('Invalid dataset identity.')
 folder=DATA_ROOT/identity;receipt=json.loads((folder/'receipt.json').read_text());path=folder/'source.h5ad'
 if receipt.get('sha256')!=identity or path.stat().st_size>MAX_BYTES or file_sha(path)!=identity:raise ValueError('Saved H5AD source/receipt changed after review.')
 provenance=receipt.get('source',{})
 if provenance.get('kind')=='public':
  spec=MANIFEST['datasets'].get(provenance.get('id'))
  if not spec or spec['sha256']!=identity or any(provenance.get(k)!=v for k,v in spec.items()):raise ValueError('Public dataset no longer matches its exact reviewed source manifest.')
 elif provenance.get('kind')!='user_upload':raise ValueError('Dataset has no explicit observed-data source.')
 return path,receipt

def sparse_layout(attributes):
 def text(value):return value.decode('ascii') if isinstance(value,bytes) else str(value)
 modern=attributes.get('encoding-type');legacy=attributes.get('h5sparse_format')
 if modern is not None:
  kind={'csr_matrix':'csr','csc_matrix':'csc'}.get(text(modern));shape=attributes.get('shape')
  if legacy is not None and (text(legacy)!=kind or list(attributes.get('h5sparse_shape',[]))!=list(shape if shape is not None else [])):raise ValueError('Conflicting modern and legacy H5AD sparse metadata.')
 else:kind=text(legacy) if legacy is not None else None;shape=attributes.get('h5sparse_shape')
 if kind not in ('csr','csc') or shape is None or len(shape)!=2 or any(isinstance(n,bool) or not isinstance(n,numbers.Integral) for n in shape):raise ValueError('H5AD must declare a valid modern or legacy CSR/CSC shape; no matrix coordinates are inferred.')
 shape=[int(n) for n in shape];validate_shape(shape);return kind,shape

def validate_h5ad(path):
 import h5py
 # Refuse cross-file references, plugin filters and allocation bombs before AnnData
 # materializes any expression matrix. Dataset import itself never loads H5AD.
 with h5py.File(path,'r') as file:
  seen=set();total=0
  def inspect(group):
   nonlocal total
   for key in group:
    if not isinstance(group.get(key,getlink=True),h5py.HardLink):raise ValueError('H5AD external and symbolic links are not accepted.')
    item=group[key];address=h5py.h5o.get_info(item.id).addr
    if address in seen:continue
    seen.add(address)
    if isinstance(item,h5py.Group):inspect(item)
    else:
     size=math.prod(item.shape)*item.dtype.itemsize;total+=size
     if size>512*1024**2 or total>1024**3 or item.compression not in (None,'gzip','lzf'):raise ValueError('H5AD metadata/matrix exceeds its safe format or allocation bound.')
  inspect(file)
  if 'X' not in file:raise ValueError('H5AD has no explicit X count matrix.')
  matrix=file['X']
  if isinstance(matrix,h5py.Dataset):validate_shape([int(n) for n in matrix.shape],dense=True)
  else:
   kind,shape=sparse_layout(matrix.attrs)
   if any(name not in matrix for name in ('data','indices','indptr')):raise ValueError('Sparse H5AD arrays are incomplete.')
   data,indices,pointer=matrix['data'],matrix['indices'],matrix['indptr'];nnz=int(data.size);validate_shape(shape,nnz=nnz)
   if any(len(a.shape)!=1 for a in (data,indices,pointer)) or indices.size!=nnz or pointer.size!=(shape[0] if kind=='csr' else shape[1])+1 or indices.dtype.kind not in 'iu' or pointer.dtype.kind not in 'iu':raise ValueError('Sparse H5AD array dimensions/types do not match its declared shape.')
   ptr=pointer[:]
   if int(ptr[0])!=0 or int(ptr[-1])!=nnz or any(int(a)>int(b) for a,b in zip(ptr,ptr[1:])):raise ValueError('Sparse H5AD row/column pointers are invalid.')
   maximum=shape[1] if kind=='csr' else shape[0]
   for offset in range(0,nnz,65536):
    values=indices[offset:offset+65536]
    if int(values.min())<0 or int(values.max())>=maximum:raise ValueError('Sparse H5AD indices exceed the original declared matrix shape.')

def execute(p):
 cloud_only();validate_input(p);source,receipt=verify_dataset(p['datasetSha256']);validate_h5ad(source)
 import importlib.metadata,platform,time
 import anndata as ad,numpy as np,scanpy as sc
 from scipy import sparse
 started=time.monotonic();packages={name:importlib.metadata.version(name) for name in MANIFEST['runtime']}
 if packages!=MANIFEST['runtime']:raise ValueError('Single-cell runtime versions differ from the reviewed pinned environment.')
 adata=ad.read_h5ad(source);validate_shape([int(n) for n in adata.shape],nnz=int(adata.X.nnz) if sparse.issparse(adata.X) else None,dense=not sparse.issparse(adata.X))
 if sparse.issparse(adata.X) and not adata.X.has_canonical_format:raise ValueError('Raw sparse counts must use canonical indices without duplicate coordinates; original bytes are preserved.')
 if not adata.obs_names.is_unique or not adata.var_names.is_unique:raise ValueError('H5AD cell and feature identifiers must be unique; do not silently rename scientific identifiers.')
 if any(len(str(v))>200 for v in list(adata.obs_names)+list(adata.var_names)) or len(adata.obs.columns)>64 or len(adata.var.columns)>128:raise ValueError('Dataset identifier/metadata dimensions exceed this reviewed native display profile; original bytes are preserved.')
 values=adata.X.data if sparse.issparse(adata.X) else adata.X
 if not np.all(np.isfinite(values)) or np.any(values<0) or not np.all(values==np.floor(values)):raise ValueError('This workflow requires raw nonnegative integer UMI counts in X; normalized/logged values are not reinterpreted as counts.')
 missing_columns=[c for c in p.get('metadataColumns',[]) if c not in adata.obs]
 if missing_columns:raise ValueError('An explicitly requested observation-metadata column is absent.')
 archive_keys=['fold_editcraft_original_obs','fold_editcraft_original_var','fold_editcraft_provenance_json']
 if any(key in adata.uns for key in archive_keys):raise ValueError('Reserved EditCraft output metadata already exists. Choose the original raw-count source rather than overwriting prior scientific metadata.')
 original_obs_metadata=adata.obs.copy(deep=True);original_var_metadata=adata.var.copy(deep=True)
 adata.uns[archive_keys[0]]=original_obs_metadata;adata.uns[archive_keys[1]]=original_var_metadata
 sc.settings.n_jobs=2;initial_shape=list(map(int,adata.shape));original_barcodes=list(map(str,adata.obs_names));original_obs_columns=list(map(str,adata.obs.columns));original_var_columns=list(map(str,adata.var.columns))
 folder=pathlib.Path(os.environ['FOLD_EDITCRAFT_JOB_DIR'])/('scanpy-'+uuid.uuid4().hex);folder.mkdir()
 def phase(name):
  job=os.environ.get('FOLD_EDITCRAFT_STAGE_ID')
  if job:
   event={'stageId':job,'operation':'scanpy_analysis','state':'running','phase':name}
   with (folder.parent/'events.jsonl').open('a') as stream:stream.write(json.dumps(event)+'\n')
 phase('Quality control')
 sc.pp.filter_cells(adata,min_genes=p['minGenes']);after_min_cells=int(adata.n_obs)
 sc.pp.filter_genes(adata,min_cells=p['minCells']);after_gene_filter=list(map(int,adata.shape))
 if adata.n_obs<5 or adata.n_vars<50:raise ValueError('Too few observed cells/features remain after the declared count filters.')
 adata.var['fold_mito']=adata.var_names.str.startswith(p['mitoPrefix'])
 if not int(adata.var['fold_mito'].sum()):raise ValueError('No mitochondrial features match the declared prefix; choose a valid feature annotation rather than reporting invented zero mitochondrial content.')
 sc.pp.calculate_qc_metrics(adata,qc_vars=['fold_mito'],percent_top=None,log1p=False,inplace=True)
 qc_before=adata.obs[['total_counts','n_genes_by_counts','pct_counts_fold_mito']].copy()
 adata.uns['fold_editcraft_qc_before_quality_thresholds']=qc_before
 keep=(adata.obs['n_genes_by_counts']<p['maxGenes'])&(adata.obs['pct_counts_fold_mito']<p['maxMitoPct'])&(adata.obs['total_counts']>0)
 adata=adata[keep].copy()
 if adata.n_obs<5:raise ValueError('Too few cells remain after the explicitly declared quality thresholds.')
 adata.layers['fold_original_counts']=adata.X.copy();phase('Normalization and variable genes')
 sc.pp.normalize_total(adata,target_sum=10000);sc.pp.log1p(adata)
 sc.pp.highly_variable_genes(adata,n_top_genes=min(p['nTopGenes'],adata.n_vars),flavor='seurat',inplace=True)
 work=adata[:,adata.var['highly_variable']].copy();n_pcs=min(p['nPCs'],work.n_obs-1,work.n_vars-1)
 if n_pcs<2:raise ValueError('Insufficient variable features for the declared PCA workflow.')
 phase('PCA and neighbor graph');sc.pp.scale(work,max_value=10);sc.tl.pca(work,n_comps=n_pcs,svd_solver='arpack',random_state=p['seed'])
 n_neighbors=min(p['nNeighbors'],work.n_obs-1);sc.pp.neighbors(work,n_neighbors=n_neighbors,n_pcs=n_pcs,random_state=p['seed'])
 phase('UMAP and Leiden clustering');sc.tl.umap(work,min_dist=p['minDist'],random_state=p['seed']);sc.tl.leiden(work,resolution=p['resolution'],random_state=p['seed'],flavor='igraph',n_iterations=2,directed=False)
 if work.obsm['X_umap'].shape!=(adata.n_obs,2) or not np.all(np.isfinite(work.obsm['X_umap'])):raise ValueError('Upstream UMAP coordinates are not a valid finite two-dimensional embedding.')
 adata.obs['fold_leiden']=work.obs['leiden'];adata.obsm['X_umap']=work.obsm['X_umap'];adata.obsm['X_pca']=work.obsm['X_pca'];adata.obsp['connectivities']=work.obsp['connectivities'];adata.obsp['distances']=work.obsp['distances'];adata.uns['neighbors']=work.uns['neighbors']
 clusters=list(map(str,adata.obs['fold_leiden'].cat.categories));markers=[]
 if len(clusters)>1 and min(int((adata.obs['fold_leiden']==c).sum()) for c in clusters)>1:
  phase('Exploratory cluster markers');sc.tl.rank_genes_groups(adata,'fold_leiden',method='wilcoxon',use_raw=False,n_genes=5,tie_correct=True,key_added='fold_cluster_markers')
  for cluster in clusters:
   table=sc.get.rank_genes_groups_df(adata,group=cluster,key='fold_cluster_markers')
   for row in table.to_dict('records'):
    markers.append({'cluster':cluster,'gene':str(row['names']),'score':float(row['scores']),'logFoldChange':float(row['logfoldchanges']),'pValue':float(row['pvals']),'adjustedPValue':float(row['pvals_adj'])})
 genes=[];missing_genes=[];cluster_expression=[]
 for gene in p['displayGenes']:
  if gene not in adata.var_names:missing_genes.append(gene);continue
  column=adata[:,[gene]].X;expression=np.asarray(column.toarray() if sparse.issparse(column) else column).reshape(-1)
  genes.append({'name':gene,'values':list(map(float,expression)),'units':'log1p(total-count-normalized UMI; target sum 10,000)'})
  for cluster in clusters:
   observed=expression[np.asarray(adata.obs['fold_leiden']==cluster)]
   cluster_expression.append({'cluster':cluster,'gene':gene,'meanLogNormalizedExpression':float(observed.mean()),'percentDetected':float(100*np.count_nonzero(observed)/len(observed))})
 def scalar(value):
  if value is None or isinstance(value,(float,np.floating)) and not np.isfinite(value):return None
  if isinstance(value,(np.integer,int)):return int(value)
  if isinstance(value,(np.floating,float)):return float(value)
  return str(value)
 cells=[{'barcode':str(barcode),'umap':list(map(float,adata.obsm['X_umap'][i])),'cluster':str(row['fold_leiden']),'totalCounts':int(row['total_counts']),'genesDetected':int(row['n_genes_by_counts']),'mitoPercent':float(row['pct_counts_fold_mito']),'metadata':{c:scalar(original_obs_metadata.loc[barcode,c]) for c in p.get('metadataColumns',[])}} for i,(barcode,row) in enumerate(adata.obs.iterrows())]
 provenance={'method':'Scanpy '+packages['scanpy'],'manifestSha256':manifest_sha(),'packages':packages,'environmentFreeze':sorted(d.metadata['Name']+'=='+d.version for d in importlib.metadata.distributions() if d.metadata.get('Name')),'sourceDatasetSha256':p['datasetSha256'],'pipelineSourceSha256':file_sha(__file__),'parameters':p,'effectivePCs':n_pcs,'effectiveNeighbors':n_neighbors,'normalizationTargetSum':10000,'python':platform.python_version(),'elapsedSeconds':time.monotonic()-started}
 adata.uns['fold_editcraft_provenance_json']=json.dumps(provenance,sort_keys=True);phase('Saving complete processed H5AD');artifact=folder/'analysis.h5ad';adata.write_h5ad(artifact,compression='gzip',convert_strings_to_categoricals=False)
 if artifact.stat().st_size>128*1024**2 or file_sha(source)!=p['datasetSha256']:raise ValueError('Processed artifact exceeded its bound or original source changed; no result accepted.')
 check=ad.read_h5ad(artifact)
 a,b=adata.layers['fold_original_counts'],check.layers.get('fold_original_counts')
 same_counts=b is not None and ((a!=b).nnz==0 if sparse.issparse(a) and sparse.issparse(b) else np.array_equal(a,b))
 roundtrip={'shape':check.shape==adata.shape,'cellIds':list(check.obs_names)==list(adata.obs_names),'featureIds':list(check.var_names)==list(adata.var_names),'umapExact':np.array_equal(check.obsm['X_umap'],adata.obsm['X_umap']),'rawCountsExact':same_counts,'originalObservationMetadata':check.uns[archive_keys[0]].equals(original_obs_metadata),'originalFeatureMetadata':check.uns[archive_keys[1]].equals(original_var_metadata)}
 if not all(roundtrip.values()):raise ValueError('Written H5AD failed its scientific data/metadata round-trip checks.')
 retained=set(adata.obs_names)
 result={'method':'Scanpy '+packages['scanpy'],'source':receipt,'inputShape':initial_shape,'filteredShape':list(map(int,adata.shape)),'qualityControl':{'minGenesInclusive':p['minGenes'],'afterMinGenesCells':after_min_cells,'afterMinCellsGeneFilterShape':after_gene_filter,'maxGenesExclusive':p['maxGenes'],'maxMitoPercentExclusive':p['maxMitoPct'],'mitochondrialPrefix':p['mitoPrefix'],'retainedCells':len(cells),'excludedBarcodes':[b for b in original_barcodes if b not in retained],'metricsBeforeQualityThresholds':[{'barcode':str(b),'totalCounts':int(r['total_counts']),'genesDetected':int(r['n_genes_by_counts']),'mitoPercent':float(r['pct_counts_fold_mito'])} for b,r in qc_before.iterrows()]},'cells':cells,'clusters':[{'id':c,'cells':int((adata.obs['fold_leiden']==c).sum())} for c in clusters],'expression':genes,'clusterExpression':cluster_expression,'missingDisplayGenes':missing_genes,'clusterMarkers':markers,'markerTestScope':'Exploratory cell-level Wilcoxon comparison of computational clusters, with original Scanpy adjusted p-values. Not donor-replicate or perturbation differential expression, a confirmatory test or cell-type annotation.','originalMetadata':{'observationColumns':original_obs_columns,'featureColumns':original_var_columns,'originalSourceRetained':True,'processedMetadataRetainedInH5AD':True},'artifact':{'path':str(artifact),'sha256':file_sha(artifact),'bytes':artifact.stat().st_size,'format':'H5AD','rawCountsLayer':'fold_original_counts'},'provenance':provenance,'scope':'Real count QC, normalization, PCA, neighbor graph, UMAP and computational Leiden clusters. All retained display cells use actual upstream coordinates; no cell types, donor replication, batch correction, biological perturbation, scvi-tools or Pertpy execution is inferred. Raw source and complete processed metadata remain in cloud storage.'}
 # Fail rather than fabricate/clamp unsupported nonfinite scientific output.
 result['originalMetadata']['archiveKeys']=archive_keys[:2]+['fold_editcraft_qc_before_quality_thresholds'];result['artifact']['roundTripChecks']=roundtrip
 qc=result['qualityControl'];qc['excludedCellCount']=len(qc['excludedBarcodes']);qc['metricsBeforeQualityThresholdsCount']=len(qc['metricsBeforeQualityThresholds']);qc['detailRowsInJSONLimitedTo']=500;qc['excludedBarcodes']=qc['excludedBarcodes'][:500];qc['metricsBeforeQualityThresholds']=qc['metricsBeforeQualityThresholds'][:500];qc['fullQCAndOriginalIdentifiersRetainedInH5AD']=True
 return display_view(result,p['maxDisplayCells'],p['seed'])
