"""Open new local-only test answers after sealing the chosen cloud predictions."""
import json
from pathlib import Path
import numpy as np
from qwen_cell_data import sha,write


def evaluate(outputs,data_folder):
    out,folder=Path(outputs),Path(data_folder)
    report=json.loads((out/'RESULTS.json').read_text());meta=json.loads((folder/'SPLIT_MANIFEST.json').read_text())
    if report['state']!='done' or not report['selectedWeightReloadPassed'] or report['testAnswersUploaded'] or report['testAnswersEvaluated']:
        raise ValueError('Only completed, selected, answer-free predictions can be evaluated.')
    if report['dataSha256']!=meta['cloudDataSha256'] or sha(folder/'cloud-inputs/data.npz')!=meta['cloudDataSha256']:raise ValueError('Evaluation data changed.')
    answers=folder/'LOCAL_SEALED_TEST_ANSWERS.npz'
    if sha(answers)!=meta['sealedAnswersSha256']:raise ValueError('Local test-answer seal changed.')
    names=['selected-hybrid.safetensors','RESULTS.json','inhibition-sealed-test-predictions.npz','drug-sealed-test-predictions.npz']
    seal={n:sha(out/n) for n in names};seal_file=out/'SELECTION_SEAL.json'
    if seal_file.exists():
        if json.loads(seal_file.read_text())!=seal:raise ValueError('Selected predictions changed after test-answer opening.')
    else:
        with seal_file.open('x') as f:json.dump(seal,f,indent=2)
    if (out/'LOCAL_TEST_EVALUATION.json').exists():return json.loads((out/'LOCAL_TEST_EVALUATION.json').read_text())
    result={'schema':'fold.qwen-cell.local-test-evaluation/1','selectionSealedBeforeAnswerLoad':True,'testAnswersUploaded':False,'legacyNormanTestEvaluated':False,
            'automaticPromotion':False,'interpretation':'New within-dataset intervention holdouts. Not independent-study or whole-cell validation. Drug conditions share held-out drug groups.'}
    with np.load(answers,allow_pickle=False) as labels,np.load(folder/'cloud-inputs/data.npz',allow_pickle=False) as inputs:
        for task in ['inhibition','drug']:
            with np.load(out/(task+'-sealed-test-predictions.npz'),allow_pickle=False) as z:
                if not np.array_equal(z['genes'],inputs['genes']):raise ValueError('Test gene order changed.')
                pred=z['prediction'].astype(float)
            y=labels[task+'TestY'].astype(float);mask=inputs[task+'TestMask']
            if pred.shape!=y.shape or not np.isfinite(pred).all() or not np.all(mask.sum(1)>0):raise ValueError('Invalid sealed predictions.')
            train_y=inputs[task+'TrainY'];train_mask=inputs[task+'TrainMask'];mean=(train_y*train_mask).sum(0)/np.maximum(train_mask.sum(0),1)
            mse=lambda p:(((p-y)**2*mask).sum(1)/mask.sum(1))
            cases=mse(pred);base=mse(mean)
            result[task]={'conditions':len(y),'interventionGroups':len(meta['groups'][task]['test']),'mse':float(cases.mean()),
                          'trainingMeanBaselineMse':float(base.mean()),'zeroResponseBaselineMse':float(mse(np.zeros_like(pred)).mean()),
                          'betterThanTrainingMeanCases':int((cases<base).sum()),'perConditionMse':cases.tolist(),
                          'unit':json.loads((folder/'cloud-inputs/manifest.json').read_text())['units'][task]}
    write(out/'LOCAL_TEST_EVALUATION.json',result);return result
