# Cleaned Indian Railways Data

This directory contains cleaned versions of the Indian Railways dataset from `data/raw/datameet_railways/`.

## Files

- **stations_cleaned.json** - Cleaned station data (8,697 records)
- **trains_cleaned.json** - Cleaned train data (5,208 records)
- **schedules_cleaned.json** - Cleaned schedule data (417,080 records)

## Data Cleaning Process

### Stations Data (`stations_cleaned.json`)

**Original:** 8,990 records  
**Cleaned:** 8,697 records  
**Removed:** 293 records (3.3%)

#### Cleaning Actions:
1. **Removed null geometry records** - Deleted 293 stations with missing coordinate data
   - These were placeholder stations with codes like XX-BECE, XX-BSPY, YY-BPLC
   - No location data available for mapping or analysis
   - Kept only stations with valid Point geometries

2. **Preserved missing property fields** - Did not remove stations with missing state/zone/address
   - 4,532 stations still missing state, zone, and address fields
   - These fields were left as-is to avoid data loss
   - Can be imputed later if needed using external sources

### Trains Data (`trains_cleaned.json`)

**Original:** 5,208 records  
**Cleaned:** 5,208 records  
**Removed:** 0 records

#### Cleaning Actions:
1. **Fixed time format inconsistencies** - Standardized all time fields to HH:MM:SS format
   - Fixed 30 records with "None" string values in arrival/departure fields
   - Converted to empty strings to indicate missing time data
   - Future-proofing added to handle HH:MM → HH:MM:00 conversion

2. **Handled missing return_train field** - Set to empty string for 599 records
   - Original: `null` → Cleaned: `""`
   - Indicates one-way trains or missing return journey data

3. **Handled missing numeric fields** - Set to 0 for 15 records
   - `duration_m`, `duration_h`, `distance` set to 0 when null
   - Allows safe arithmetic operations without errors
   - Zero values indicate missing/unknown data

4. **Handled missing classes field** - Set to empty string for 15 records
   - Original: `null` → Cleaned: `""`
   - Indicates unknown class availability

### Schedules Data (`schedules_cleaned.json`)

**Original:** 417,080 records  
**Cleaned:** 417,080 records  
**Removed:** 0 records

#### Cleaning Actions:
1. **Converted "None" strings to actual null values** - Fixed 55,662 instances
   - Original: `"None"` (string) → Cleaned: `null` (JSON null)
   - Applied to arrival, departure, day, and other fields
   - Ensures proper null handling in downstream processing

2. **Fixed invalid day values** - Set to null for 35 records
   - Days outside 1-7 range converted to `null`
   - Invalid day numbers indicate data entry errors
   - Null values clearly indicate missing/invalid data

## Data Quality Summary

| Dataset | Original | Cleaned | Removed | Key Issues Fixed |
|---------|----------|---------|---------|------------------|
| Stations | 8,990 | 8,697 | 293 | Null geometry removed |
| Trains | 5,208 | 5,208 | 0 | Missing fields defaulted, "None" strings in times |
| Schedules | 417,080 | 417,080 | 0 | "None" strings converted |

## Remaining Data Issues

The following issues were intentionally not fixed to preserve data:

### Stations
- 4,532 stations missing state, zone, and address (50% of data)
- 53 duplicate station names (different codes - may be valid)

### Trains
- 599 trains missing return_train information
- 15 trains missing duration/distance data

### Schedules
- 27,835 records missing arrival time
- 27,827 records missing departure time
- 22,561 records missing day information

## Usage

The cleaned files maintain the same structure as the original files:
- **stations_cleaned.json** - GeoJSON FeatureCollection
- **trains_cleaned.json** - GeoJSON FeatureCollection
- **schedules_cleaned.json** - JSON array

Load with standard JSON parsers in any programming language.

## Cleaning Script

The cleaning was performed using `clean_data.py` in the project root. To re-run the cleaning process:

```bash
python clean_data.py
```

## License

CC0 - Same as original dataset
