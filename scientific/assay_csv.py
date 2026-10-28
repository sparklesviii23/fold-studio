"""Explicit, attributed assay CSV transport; no endpoint or replicate inference."""
import base64,csv,hashlib,io,pathlib
REQUIRED=('concentration','response','biologicalReplicate','technicalReplicate','sampleGroup')
OPTIONAL=('endpoint','responseUnit','concentrationUnit')
def read(p):
 if bool(p.get('path'))==bool(p.get('csvText')):raise ValueError('Choose one assay CSV file or one supplied CSV text.')
 if p.get('path'):
  path=pathlib.Path(p['path'])
  if path.suffix.lower()!='.csv' or path.is_symlink() or not path.is_file() or path.stat().st_size>4*1024**2:raise ValueError('Choose a regular CSV file up to 4 MiB.')
  raw=path.read_bytes();name=path.name
 else:
  if not isinstance(p.get('csvText'),str):raise ValueError('CSV text must be explicit text.')
  raw=p['csvText'].encode();name='supplied-assay.csv'
 if len(raw)>4*1024**2:raise ValueError('Assay CSV exceeds 4 MiB.')
 reader=csv.DictReader(io.StringIO(raw.decode('utf-8-sig')),strict=True);fields=reader.fieldnames or []
 if len(set(fields))!=len(fields) or not set(REQUIRED)<=set(fields) or set(fields)-set(REQUIRED+OPTIONAL):raise ValueError('CSV requires concentration,response,biologicalReplicate,technicalReplicate,sampleGroup; only explicit endpoint/unit columns are optional.')
 rows=[]
 for row in reader:
  if None in row or any(not isinstance(row[key],str) or not row[key].strip() for key in REQUIRED):raise ValueError('Each CSV row requires all five declared fields.')
  for key in OPTIONAL:
   if key in row and row[key]!=p.get(key):raise ValueError('Row endpoint/units differ from the explicitly declared assay.')
  try:concentration,response=float(row['concentration']),float(row['response'])
  except ValueError:raise ValueError('Dose and response must be explicit numeric values.') from None
  rows.append({**{key:row[key] for key in REQUIRED[2:]},'concentration':concentration,'response':response})
  if len(rows)>10000:raise ValueError('At most 10,000 supplied measurement rows are supported.')
 if not rows:raise ValueError('The CSV contains no measurement rows.')
 return rows,{'fileName':name,'sha256':hashlib.sha256(raw).hexdigest(),'originalBase64':base64.b64encode(raw).decode(),'columns':fields,'scope':'Original supplied CSV bytes and explicit labels preserved. Endpoint, units and biological independence are supplied by the researcher, not inferred from column names or row counts.'}
