import sys,unittest
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scientific'))
from virtual_cell_response_research import transfer_fit

class TransferTests(unittest.TestCase):
 def test_linear_kernel_agrees_with_primal_ridge(self):
  rng=np.random.default_rng(5);x=rng.normal(size=(12,8));y=rng.normal(size=(12,20));q=rng.normal(size=(3,8));alpha=.1
  actual=transfer_fit(x,y,q,{'family':'ridge_context','dimensions':8,'alpha':alpha})
  xc=x-x.mean(0);yc=y-y.mean(0);expected=y.mean(0)+(q-x.mean(0))@np.linalg.solve(xc.T@xc+alpha*8*np.eye(8),xc.T@yc)
  np.testing.assert_allclose(actual,expected,rtol=1e-11,atol=1e-11)
 def test_missing_training_values_are_fit_on_observed_subsets(self):
  rng=np.random.default_rng(7);x=rng.normal(size=(8,8));q=rng.normal(size=(2,8));y=rng.normal(size=(8,3));y[:3,0]=np.nan;y[1:,1]=np.nan;y[:,2]=np.nan
  spec={'family':'ridge_context','dimensions':8,'alpha':1.}
  actual=transfer_fit(x,y,q,spec);expected=transfer_fit(x[3:],y[3:,:1],q,spec)
  np.testing.assert_allclose(actual[:,0],expected[:,0]);np.testing.assert_array_equal(actual[:,1],np.repeat(y[0,1],2));self.assertTrue(np.isnan(actual[:,2]).all())
 def test_nonlinear_and_low_rank_are_finite_and_do_not_modify_inputs(self):
  rng=np.random.default_rng(8);x=rng.normal(size=(10,8));y=rng.normal(size=(10,16));saved=y.copy();q=rng.normal(size=(3,8))
  for family in ('low_rank','rbf_context'):
   p=transfer_fit(x,y,q,{'family':family,'dimensions':8,'alpha':1.,'bandwidth':1.})
   self.assertTrue(np.isfinite(p).all());self.assertEqual(p.shape,(3,16))
  np.testing.assert_array_equal(saved,y)
if __name__=='__main__':unittest.main()
