"""Score fresh final answers locally after sealing every candidate prediction."""
import json
from pathlib import Path
import numpy as np
from qwen_cell_data import sha,write
from cell_training_metrics import metrics,paired_group_interval


def evaluate(outputs,experiment):
    out,experiment=map(Path,[outputs,experiment]);result=json.loads((out/'RESULTS.json').read_text());split=json.loads((experiment/'SPLIT_MANIFEST.json').read_text())
    if result['state']!='done' or result['testAnswersUploaded'] or result['freshFinalAnswersEvaluated']:raise ValueError('Completed answer-free selected predictions required.')
    if result['dataSha256']!=split['dataSha256'] or sha(experiment/'cloud-inputs/data.npz')!=split['dataSha256'] or sha(experiment/'LOCAL_FINAL_ANSWERS.npz')!=split['answerSha256']:raise ValueError('Final dataset seal changed.')
    names=['RESULTS.json','SELECTION.json','final-predictions.npz',*(task+'-selected.safetensors' for task in result['selectedPerTask'])]
    seals={n:sha(out/n) for n in names};path=out/'SELECTION_SEAL.json'
    if path.exists():
        if json.loads(path.read_text())!=seals:raise ValueError('Predictions or chosen weights changed after opening final answers.')
    else:
        with path.open('x') as f:json.dump(seals,f,indent=2)
    if (out/'FINAL_EVALUATION.json').exists():return json.loads((out/'FINAL_EVALUATION.json').read_text())
    report={'schema':'fold.cell-training-final/2','state':'done','selectionSealedBeforeAnswers':True,'dataSha256':result['dataSha256'],
            'validationWinnersIncludingBaselines':result['validationWinnersIncludingBaselines'],'evaluations':{},'automaticPromotion':False,
            'predictionUncertaintyCalibration':'Not established. Group-bootstrap confidence intervals describe score differences, not individual-cell certainty.',
            'limitations':['Within-dataset intervention/context holdouts, not independent-study validation.','One training seed; multiple candidate comparisons reported in full.','Primary pair task still has only reused development validation.']}
    with np.load(experiment/'LOCAL_FINAL_ANSWERS.npz',allow_pickle=False) as answers,np.load(experiment/'cloud-inputs/data.npz',allow_pickle=False) as data,np.load(out/'final-predictions.npz',allow_pickle=False) as predictions:
        for key in predictions.files:
            prefix,arm=key.split('__');task=prefix.split('_')[0];y=answers[prefix+'_Y'];mask=data[prefix+'_Mask'];groups=data[prefix+'_Group']
            scores=metrics(predictions[key],y,mask,groups);report['evaluations'].setdefault(prefix,{})[arm]=scores
        for prefix,arms in report['evaluations'].items():
            winner=result['validationWinnersIncludingBaselines'][prefix.split('_')[0]]
            for arm,scores in arms.items():
                errors=[r['mse'] for r in scores['perCondition']];scores['comparisons']={}
                for reference in ['training_mean','ridge']:
                    scores['comparisons'][reference]=paired_group_interval(errors,[r['mse'] for r in arms[reference]['perCondition']],data[prefix+'_Group'])
                scores['selectedOnValidation']=arm==winner
    lines=['# Grounded cell training results','','All final answers were opened locally after model selection and prediction sealing.','',
           '| Task / split | Candidate | MSE | Top-effect direction | Selected on validation |','| --- | --- | ---: | ---: | --- |']
    for prefix,arms in report['evaluations'].items():
        for arm,row in arms.items():
            direction=row['mean']['topEffectDirectionAccuracy'];lines.append(f"| {prefix} | {arm} | {row['mean']['mse']:.7f} | {direction:.3f} | {'yes' if row['selectedOnValidation'] else ''} |" if direction is not None else f"| {prefix} | {arm} | {row['mean']['mse']:.7f} | unavailable | |")
    lines+=['','A selected baseline remains a valid result. No app predictor was replaced.','',report['predictionUncertaintyCalibration'],'',*report['limitations']]
    (out/'RESULTS_EXPLAINED.md').write_text('\n'.join(lines)+'\n');write(out/'FINAL_EVALUATION.json',report);return report
