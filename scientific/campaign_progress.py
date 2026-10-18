"""Observe real upstream optimizer callbacks without changing their calculations."""
import json,math

def install():
 from bindcraft import trajectory
 original=getattr(trajectory.TrajectoryRecorder,'_fold_original',trajectory.TrajectoryRecorder)
 class ProgressRecorder(original):
  _fold_original=original
  def __call__(self,sequence_updates,predictions):
   super().__call__(sequence_updates,predictions)
   row=self.metric_rows[-1]
   metrics={k:(v if math.isfinite(v) else None) for k,v in row.items() if isinstance(v,float)}
   print('FOLD_PROGRESS '+json.dumps({'stage':self.design_stage,'sequenceUpdates':int(sequence_updates),'metrics':metrics},allow_nan=False,separators=(',',':')),flush=True)
 trajectory.TrajectoryRecorder=ProgressRecorder
