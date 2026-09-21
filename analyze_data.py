import json
from collections import defaultdict, Counter
import sys
import os

def analyze_stations(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    features = data['features']
    total = len(features)
    
    issues = {
        'null_geometry': 0,
        'null_properties': defaultdict(int),
        'duplicate_codes': 0,
        'duplicate_names': 0,
        'invalid_coordinates': 0
    }
    
    codes = []
    names = []
    
    for feature in features:
        # Check null geometry
        if feature['geometry'] is None:
            issues['null_geometry'] += 1
        
        # Check null properties
        for key, value in feature['properties'].items():
            if value is None:
                issues['null_properties'][key] += 1
        
        # Check for duplicates
        code = feature['properties']['code']
        name = feature['properties']['name']
        codes.append(code)
        names.append(name)
        
        # Check invalid coordinates
        if feature['geometry'] and feature['geometry']['coordinates']:
            coords = feature['geometry']['coordinates']
            if not isinstance(coords, list) or len(coords) != 2:
                issues['invalid_coordinates'] += 1
    
    code_counts = Counter(codes)
    issues['duplicate_codes'] = sum(count - 1 for count in code_counts.values() if count > 1)
    
    name_counts = Counter(names)
    issues['duplicate_names'] = sum(count - 1 for count in name_counts.values() if count > 1)
    
    return {
        'total_records': total,
        'issues': issues,
        'sample_null_geometry': [f['properties']['code'] for f in features if f['geometry'] is None][:5]
    }

def analyze_trains(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    features = data['features']
    total = len(features)
    
    issues = {
        'null_geometry': 0,
        'null_properties': defaultdict(int),
        'duplicate_numbers': 0,
        'empty_coordinates': 0,
        'invalid_time_format': 0
    }
    
    numbers = []
    
    for feature in features:
        # Check null geometry
        if feature['geometry'] is None:
            issues['null_geometry'] += 1
        elif not feature['geometry']['coordinates']:
            issues['empty_coordinates'] += 1
        
        # Check null properties
        for key, value in feature['properties'].items():
            if value is None:
                issues['null_properties'][key] += 1
        
        # Check for duplicates
        number = feature['properties']['number']
        numbers.append(number)
        
        # Check time format
        for time_field in ['arrival', 'departure']:
            time_val = feature['properties'].get(time_field)
            if time_val and time_val != '':
                try:
                    parts = time_val.split(':')
                    if len(parts) != 3:
                        issues['invalid_time_format'] += 1
                except:
                    issues['invalid_time_format'] += 1
    
    number_counts = Counter(numbers)
    issues['duplicate_numbers'] = sum(count - 1 for count in number_counts.values() if count > 1)
    
    return {
        'total_records': total,
        'issues': issues
    }

def analyze_schedules(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    total = len(data)
    
    issues = {
        'null_values': defaultdict(int),
        'invalid_time_format': 0,
        'invalid_day': 0,
        'duplicate_ids': 0
    }
    
    ids = []
    
    for record in data:
        # Check null values
        for key, value in record.items():
            if value is None or value == 'None':
                issues['null_values'][key] += 1
        
        # Check time format
        for time_field in ['arrival', 'departure']:
            time_val = record.get(time_field)
            if time_val and time_val != 'None':
                try:
                    parts = time_val.split(':')
                    if len(parts) != 3:
                        issues['invalid_time_format'] += 1
                except:
                    issues['invalid_time_format'] += 1
        
        # Check day validity
        day = record.get('day')
        if day is not None and (not isinstance(day, int) or day < 1 or day > 7):
            issues['invalid_day'] += 1
        
        ids.append(record.get('id'))
    
    id_counts = Counter(ids)
    issues['duplicate_ids'] = sum(count - 1 for count in id_counts.values() if count > 1)
    
    return {
        'total_records': total,
        'issues': issues
    }

if __name__ == '__main__':
    base_path = os.path.join(os.path.dirname(__file__), 'data', 'raw', 'datameet_railways')
    
    print("=" * 60)
    print("STATIONS ANALYSIS")
    print("=" * 60)
    stations_result = analyze_stations(f'{base_path}/stations.json')
    print(f"Total records: {stations_result['total_records']}")
    print(f"Null geometry: {stations_result['issues']['null_geometry']}")
    print(f"Duplicate codes: {stations_result['issues']['duplicate_codes']}")
    print(f"Duplicate names: {stations_result['issues']['duplicate_names']}")
    print(f"Invalid coordinates: {stations_result['issues']['invalid_coordinates']}")
    print(f"Null properties: {dict(stations_result['issues']['null_properties'])}")
    print(f"Sample null geometry codes: {stations_result['sample_null_geometry']}")
    
    print("\n" + "=" * 60)
    print("TRAINS ANALYSIS")
    print("=" * 60)
    trains_result = analyze_trains(f'{base_path}/trains.json')
    print(f"Total records: {trains_result['total_records']}")
    print(f"Null geometry: {trains_result['issues']['null_geometry']}")
    print(f"Empty coordinates: {trains_result['issues']['empty_coordinates']}")
    print(f"Duplicate numbers: {trains_result['issues']['duplicate_numbers']}")
    print(f"Invalid time format: {trains_result['issues']['invalid_time_format']}")
    print(f"Null properties: {dict(trains_result['issues']['null_properties'])}")
    
    print("\n" + "=" * 60)
    print("SCHEDULES ANALYSIS")
    print("=" * 60)
    schedules_result = analyze_schedules(f'{base_path}/schedules.json')
    print(f"Total records: {schedules_result['total_records']}")
    print(f"Null values: {dict(schedules_result['issues']['null_values'])}")
    print(f"Invalid time format: {schedules_result['issues']['invalid_time_format']}")
    print(f"Invalid day: {schedules_result['issues']['invalid_day']}")
    print(f"Duplicate IDs: {schedules_result['issues']['duplicate_ids']}")
