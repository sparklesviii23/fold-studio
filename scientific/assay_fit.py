"""Descriptive 4PL point fitting of declared biological-unit dose means.

No affinity interpretation, parameter confidence intervals or efficacy inference.
"""
import json,math,pathlib,subprocess,sys
VERSION='descriptive-biological-unit-4pl-v1'

def prepare(assay,group,direction):
 import assay_statistics
 if direction not in ('increasing','decreasing'):raise ValueError('Choose the observed increasing/decreasing response direction explicitly.')
 group=assay_statistics.identifier(group,'sample group');summary=assay_statistics.summarize(assay);points=[p for p in summary['groups'] if p['sampleGroup']==group]
 if not 6<=len(points)<=100:raise ValueError('Select one sample group with 6–100 distinct concentrations.')
 units=[{u['biologicalReplicate'] for u in p['biologicalUnitSummaries']} for p in points]
 if len(units[0])<3 or any(unit!=units[0] for unit in units):raise ValueError('This descriptive fit requires the same at least three declared biological units at every dose; missing/unbalanced designs need a separate method.')
 positive=[p['concentration'] for p in points if p['concentration']>0]
 if len(positive)<5 or min(positive)<1e-30 or max(positive)>1e30:raise ValueError('Supply at least five positive doses within the bounded numerical range 1e-30–1e30 in the recorded unit.')
 values=[p['mean'] for p in points];span=max(values)-min(values)
 if not math.isfinite(span) or span<=max(1e-12,max(abs(v) for v in values)*1e-9):raise ValueError('No finite, varying dose response is available for this model.')
 return {'points':points,'sampleGroup':group,'direction':direction,'biologicalUnits':len(units[0]),'concentrationUnit':summary['concentrationUnit'],'responseUnit':summary['responseUnit'],'endpoint':summary['endpoint']}

def run(s,request):
 child=subprocess.run([s.engine_python(),'-I','-B',str(pathlib.Path(__file__).resolve())],input=json.dumps(request,allow_nan=False),text=True,capture_output=True,timeout=45)
 if child.returncode:raise ValueError('SciPy descriptive dose fit failed: '+child.stderr.strip()[-1500:])
 return json.loads(child.stdout)

def calculate(p):
 import numpy as np,scipy
 from scipy.optimize import least_squares
 from scipy.special import expit
 x=np.array([point['concentration'] for point in p['points']],dtype=float);y=np.array([point['mean'] for point in p['points']],dtype=float)
 offset=float(y.min());scale=float(y.max()-y.min());normalized=(y-offset)/scale;positive=x>0;logx=np.full(x.shape,-np.inf);logx[positive]=np.log(x[positive]);lo=float(logx[positive].min());hi=float(logx[positive].max())
 lower=np.array([-2.,math.log(.05),lo-4,math.log(.1)]);upper=np.array([2.,math.log(10),hi+4,math.log(10)])
 def predict(parameters,at=logx):
  bottom,logamplitude,logmidpoint,loghill=parameters;fraction=expit(np.exp(loghill)*(at-logmidpoint))
  return bottom+np.exp(logamplitude)*(fraction if p['direction']=='increasing' else 1-fraction)
 fits=[]
 for fraction in (.25,.5,.75):
  for hill in (.5,1.,2.):
   fits.append(least_squares(lambda v:predict(v)-normalized,[0.,0.,lo+(hi-lo)*fraction,math.log(hill)],bounds=(lower,upper),method='trf',loss='linear',x_scale='jac',max_nfev=500,ftol=1e-10,xtol=1e-10,gtol=1e-10))
 fit=min(fits,key=lambda f:float(f.cost));parameters=fit.x;predicted=predict(parameters)*scale+offset;rmse=float(np.sqrt(np.mean((predicted-y)**2)));condition=float(np.linalg.cond(fit.jac.T@fit.jac));midpoint=float(np.exp(parameters[2]));hill=float(np.exp(parameters[3]));fraction=expit(hill*(logx-parameters[2]));rank=int(np.linalg.matrix_rank(fit.jac))
 issues=[]
 if not fit.success:issues.append('optimizer_did_not_converge')
 if rank<4 or not math.isfinite(condition) or condition>1e10:issues.append('ill_conditioned_parameters')
 if np.any(np.abs(parameters-lower)<1e-4) or np.any(np.abs(parameters-upper)<1e-4):issues.append('parameter_boundary_limited')
 if not x[positive].min()<=midpoint<=x.max():issues.append('midpoint_outside_observed_positive_doses')
 if fraction.min()>.2 or fraction.max()<.8:issues.append('insufficient_low_high_response_coverage')
 if rmse/scale>.25:issues.append('large_residuals_relative_to_observed_range')
 result={**p,'algorithm':VERSION,'scipyVersion':scipy.__version__,'midpointState':'estimated_within_observed_range' if not issues else 'not_reliably_estimable','apparentHalfResponseConcentration':midpoint if not issues else None,'diagnosticIssues':issues,'diagnosticParameters':{'bottom':float(parameters[0]*scale+offset),'top':float((parameters[0]+np.exp(parameters[1]))*scale+offset),'halfResponseConcentration':midpoint,'hillMagnitude':hill},'diagnosticParameterScope':'Optimizer values are retained for reproducibility even when the usable midpoint is withheld. They are not independently validated parameters.','predictedAtObservedDoses':[float(v) for v in predicted],'residualsObservedMinusPredicted':[float(v) for v in y-predicted],'residualRMSE':rmse,'jacobianRank':rank,'jacobianNormalCondition':condition if math.isfinite(condition) else None,'initializations':9,'totalFunctionEvaluations':sum(int(f.nfev) for f in fits),'method':'Four-parameter logistic descriptive curve. Average technical readings within each declared biological unit/dose, then average the same biological units equally at each dose. Fit dose means with unweighted bounded trust-region least squares, nine recorded initializations and linear residual loss. No hypothesis test assumes doses are independent.','equation':'bottom + (top-bottom) / (1+exp(-hill*(ln(dose)-ln(midpoint)))) for increasing response; replace logistic fraction by 1-fraction for decreasing response. Dose zero uses the limiting response.','bounds':{'bottomInObservedRangeUnits':[-2,2],'amplitudeRelativeToObservedRange':[.05,10],'logMidpointBeyondObservedPositiveLogRange':4,'hillMagnitude':[.1,10]},'uncertainty':'No parameter confidence intervals or significance tests are computed. Repeated doses share biological units; validated cluster/hierarchical uncertainty and independent experiment replication remain separate requirements.','scope':'Descriptive numerical fit of supplied endpoint readings. An apparent half-response concentration is not a dissociation constant, binding affinity, independently established potency, causal effect or therapeutic recommendation. Original measurements are preserved.'}
 # Reject overflow rather than serializing misleading infinities.
 json.dumps(result,allow_nan=False)
 return result

if __name__=='__main__':print(json.dumps(calculate(json.load(sys.stdin)),allow_nan=False))
