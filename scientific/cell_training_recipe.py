"""Prepared-only grounded cell training protocol; no scientific imports."""
from qwen_cell_cloud_recipe import RECIPE as OLD
import copy
PROTOCOL={'maximumSeconds':5400,'seed':20261106,'batchSize':16,'maximumEpochs':12,'patience':4,'minimumDelta':1e-6,'gradientCheckpointing':True,
          'foundationPasses':1,'learningRate':2e-5,'numericLearningRate':1e-3,'adapterLayers':4,'adapterRank':16,
          'arms':['numeric','biology_numeric','qwen','qwen_frozen','qwen_biology']}
RECIPE_ID='cell_response_training_v2';RECIPE=copy.deepcopy(OLD)
RECIPE.update(title='Cell AI · grounded training laboratory',purpose='Measured starting cells, molecular structures and pathway evidence; separate task validation; numerical, Qwen and Cell2Sentence comparisons.',timeout=5400,
              source='Fold Studio grounded response study; Qwen2.5-Coder-3B plus official Cell2Sentence Pythia-410M',
              license='Qwen Apache-2.0; Cell2Sentence weights CC BY 4.0 with attribution; public input source evidence retained.')
RECIPE['script']=RECIPE['script'].replace('code/qwen_cell_cloud_entry.py','code/cell_training_entry.py').replace('from qwen_cell_cloud_entry import main','from cell_training_entry import main')
