# Timing Report Triage Web Utility

## Overview
This project is a **Python-based web utility** for loading, parsing, and analyzing up to three STA timing reports.  
It uses **Streamlit** for the UI and integrates with a custom parsing module (`custom_func.py`).

---

## Features Implemented

### 1. Multi-Report Upload
- Supports **Report A**, **Report B**, **Report C**.
- Each report is assigned a working temp directory:

where `file_name` is derived from the uploaded timing report (without extension).

### 2. Integration with Parser (`cf.cd_rpt`)
`cd_rpt` returns:
1. `path_dict` (parsed path details)
2. `field_list` (list of path fields)
3. `sp_ep_dict` (startpoint → endpoint map)
4. `pat_list` (auto-generated patterns from report)

---

### 3. Filtering Logic

#### Inputs:
- **auto_filter** (boolean)
- **patterns** (comma-separated string in UI)
- **pattern_file** (file containing patterns)
- **numFilt** (integer, default `2`, controls field to match)

#### Behavior:
```python
if auto_filter:
  cf.processMultiPatterns(path_dict, pat_list, file_name, numFilt, temp_dir)

elif patterns:
  pat_list = [p.strip() for p in patterns.split(",") if p.strip()]
  if len(pat_list) > 1:
      cf.processMultiPatterns(path_dict, pat_list, file_name, numFilt, temp_dir)
  else:
      cf.filterSummaryCsv_ver2(path_dict, pat_list[0], file_name, numFilt, temp_dir)

elif pattern_file:
  pat_list = cf.read_file(pattern_file)
  cf.processMultiPatterns(path_dict, pat_list, file_name, numFilt, temp_dir)


binv4/
│── app.py               # Streamlit UI (current)
│── custom_func.py       # Parsing & filtering functions
│── README.md            # This file
│── ...                  # Other utility scripts / assets


pip install -r requirements.txt
streamlit run app.py


Requirements
Python 3.10+
streamlit
pandas
matplotlib
Custom custom_func.py
