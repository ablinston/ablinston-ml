from datetime import datetime
from evidently.report import Report
from evidently.metric_preset import DataQualityPreset
from evidently.ui.workspace import Workspace
import pdb

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