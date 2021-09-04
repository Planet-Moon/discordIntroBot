import json

def dump_into_file(filename,obj={}):
    with open(filename, 'w') as f:
        json.dump(obj,f,sort_keys=True,indent=4)

def read_from_file(filename):
    try:
        with open(filename, 'r') as f:
            data = json.load(f)
        return data
    except IOError:
        return dict()
