#!/usr/bin/env python3
"""Read-only verification of original saved structure records and source bytes.

Uses the pre-observatory receipt's original identities, so adding public references
does not change the baseline. Never opens the live research store as a fixture.
"""
import argparse,hashlib,json,pathlib,sqlite3,datetime
REPO=pathlib.Path(__file__).resolve().parents[1]
def verify(root,baseline):
 expected=baseline['previousMetadataSha256'];ids=[r['id'] for r in baseline['originalAssets']]
 connection=sqlite3.connect('file:'+str(root/'library.sqlite3')+'?mode=ro',uri=True);connection.row_factory=sqlite3.Row
 try:
  rows=connection.execute('SELECT id,kind,data FROM records WHERE id IN ('+','.join('?' for _ in ids)+') ORDER BY id',ids).fetchall()
  values=[dict(r) for r in rows];metadata=hashlib.sha256(json.dumps(values,sort_keys=True,separators=(',',':')).encode()).hexdigest();assets=[]
  for row in rows:
   data=json.loads(row['data']);path=root/'assets'/data['asset'];digest=hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None;assets.append({'id':row['id'],'sha256':data['sha256'],'actualSha256':digest,'intact':digest==data['sha256']})
  result={'observed':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scope':'Original saved structure-record metadata and exact original coordinate assets; not a scientific model accuracy test.','originalRecords':len(ids),'presentOriginalRecords':len(rows),'expectedMetadataSha256':expected,'actualMetadataSha256':metadata,'metadataUnchanged':metadata==expected,'assets':assets,'allOriginalAssetHashesValid':all(r['intact'] for r in assets),'readOnlyDatabase':True}
  if len(rows)!=len(ids) or metadata!=expected or not result['allOriginalAssetHashesValid']:raise ValueError('Original research metadata or coordinate assets changed; inspect before continuing.')
  return result
 finally:connection.close()
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--root',required=True,type=pathlib.Path);args=parser.parse_args();baseline=json.loads((REPO/'reports/editcraft/nucleic-data-integrity.json').read_text());result=verify(args.root,baseline)
 path=REPO/'reports/editcraft/preservation-current.json';path.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='assets'},indent=2))
if __name__=='__main__':main()
