import json
import os

def check_times(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    features = data['features']
    null_count = 0
    empty_count = 0
    valid_count = 0
    
    for feature in features:
        props = feature['properties']
        for time_field in ['arrival', 'departure']:
            time_val = props.get(time_field)
            if time_val is None:
                null_count += 1
            elif time_val == '':
                empty_count += 1
            else:
                valid_count += 1
    
    return {
        'null': null_count,
        'empty': empty_count,
        'valid': valid_count
    }

if __name__ == '__main__':
    base_path = os.path.join(os.path.dirname(__file__), 'data', 'processed')
    result = check_times(os.path.join(base_path, 'trains_cleaned.json'))
    print(f"Null times: {result['null']}")
    print(f"Empty times: {result['empty']}")
    print(f"Valid times: {result['valid']}")
