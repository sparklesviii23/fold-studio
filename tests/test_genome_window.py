import pathlib,sys,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scientific'))
from genome_workspace import window_annotations
def feature(start,end,index=0,replicon='chr',strand='+'):
 return {'index':index,'replicon':replicon,'start':start,'end':end,'strand':strand,'type':'gene','attributes':{'ID':str(index)}}
class WindowTests(unittest.TestCase):
 def test_linear_overlap_clipping_and_no_inferred_neighbors(self):
  fs=[feature(1,3),feature(4,10,1,strand='-'),feature(12,14,2),feature(4,6,3,'other')]
  r=window_annotations(fs,'chr',3,5,20,False);self.assertEqual(r['total'],2)
  self.assertEqual(r['features'][0]['fragments'][0],{'startOffsetZeroBased':0,'endOffsetExclusive':1,'continuesBeforeWindow':True,'continuesAfterWindow':False})
  self.assertEqual(r['features'][1]['fragments'][0],{'startOffsetZeroBased':1,'endOffsetExclusive':5,'continuesBeforeWindow':False,'continuesAfterWindow':True})
  self.assertEqual(r['features'][1]['feature']['strand'],'-')
 def test_circular_origin_and_original_unrolled_feature(self):
  r=window_annotations([feature(7,10),feature(1,2,1)],'chr',7,4,8,True)
  self.assertEqual(r['features'][0]['fragments'][0]['endOffsetExclusive'],4);self.assertEqual(r['features'][1]['fragments'][0]['startOffsetZeroBased'],2)
  r=window_annotations([feature(7,10)],'chr',1,4,8,True);self.assertEqual(r['features'][0]['fragments'][0]['endOffsetExclusive'],2)
 def test_full_traversal_wrap_fragments_are_explicit_and_display_bounded(self):
  r=window_annotations([feature(2,6)],'chr',4,8,8,True);self.assertEqual(len(r['features'][0]['fragments']),2)
  r=window_annotations([feature(1,2,i) for i in range(201)],'chr',1,2,8,False);self.assertEqual((len(r['features']),r['total'],r['omitted']),(200,201,1))
