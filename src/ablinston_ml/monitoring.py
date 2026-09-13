import glob
import numpy as np
import os
import pandas as pd
import pdb
import whylogs as why
from datetime import datetime
from evidently.metric_preset import DataQualityPreset
from evidently.report import Report
from evidently.ui.workspace import Workspace


def log_data_evidently(pl_df, ev_project_name, ev_workspace):
    """
    This function takes a polars data frame and logs it in a EvidentlyAI report

    Parameters
    ----------
    pl_df : polars data frame
    ev_project: an evidently project
    ev_workspace: an evidently workspace
    Returns
    -------
    None.

    """
    # pdb.set_trace()
    
    if len(pl_df) == 0:
        print("Data frame empty.")
        return None

    # 1. Create the report
    report = Report(metrics = [DataQualityPreset()])
    project = ev_workspace.search_project(ev_project_name)
    

    # 2. Run it (Evidently math happens here)
    # Convert your Polars df to pandas first
    report.run(reference_data = None, current_data = pl_df.to_pandas())

    # 3. Save the snapshot to your workspace
    ev_workspace.add_report(project[0].id, report, timestamp = datetime.now())

    return None


def save_project_snapshot(df_pl, project_name):
    """
    This function saves a snapshot of a polars data frame with a ./logs/ folder

    Parameters
    ----------
    df_pl : polars data frame
    project_name : str
        the name of the dataset being logged

    Returns
    -------
    None.

    """
    # pdb.set_trace()
    # 1. Define the path: logs/project_name/
    base_dir = os.path.join("logs", project_name)
    
    # 2. Create the folders if they aren't there
    if not os.path.exists(base_dir):
        os.makedirs(base_dir)
        print(f"Created new log folder for: {project_name}")

    # 3. Create a UNIQUE filename with a timestamp
    # This ensures you never try to "overwrite" the folder itself
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"profile_{timestamp}.bin"
    
    # 4. FULL path to the actual file
    full_file_path = os.path.join(base_dir, filename)

    # 5. Log and Write
    results = why.log(df_pl.to_pandas())
    
    # Use 'dest' for the FULL file path
    results.writer("local").write(dest=full_file_path)
    
    print(f"✅ Saved stats to: {full_file_path}")
    
def get_project_history(project_name):
    """
    This function gets the project history of a whylogs project and converts the stats into a data frame

    Parameters
    ----------
    project_name : str
        The name of the project/datasets.

    Returns
    -------
    df : pandas df

    """
    
    
    # 1. Find all .bin files in that project's folder
    path = os.path.join("logs", project_name, "*.bin")
    files = sorted(glob.glob(path)) # Sorted by filename (timestamp)

    history_records = []

    for f in files:
        # Load the profile view
        view = why.read(path=f).view()
        stats_df = view.to_pandas()
        
        # Get the timestamp from the filename (e.g., profile_20260202_120000.bin)
        filename = os.path.basename(f)
        timestamp = filename.replace("profile_", "").replace(".bin", "")

        # 2. Extract specific stats you care about for EVERY column
        for col_name, row in stats_df.iterrows():
            history_records.append({
                'snapshot': timestamp,
                'column': col_name,
                'missing_proportion': row.get('counts/null', np.nan) / row.get('counts/n', np.nan),
                'mean': row.get('distribution/mean', None),
                'std_dev': row.get('distribution/stddev', None),
                'max': row.get('distribution/max', None),
                'min': row.get('distribution/min', None)
            })
  
    df = pd.DataFrame(history_records)
    
    # Assuming 'snapshot' is the column name in your history DataFrame
    df['snapshot'] = pd.to_datetime(df['snapshot'], format='%Y%m%d_%H%M%S')

    return df
