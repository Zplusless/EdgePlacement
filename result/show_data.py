import pickle
from pprint import pprint

file = "final_result_k"

with open(file, 'rb') as f:
    data = pickle.load(f)

pprint(data)