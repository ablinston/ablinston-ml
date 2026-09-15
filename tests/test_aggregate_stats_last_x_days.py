from ablinston_ml.features import aggregate_stats_last_x_days
import polars as pl
from datetime import date

def test_aggregate_stats_last_x_days():
    # 1. Setup: Create a messy dataset
    # Group A: Standard daily data
    # Group B: Out of order, includes a gap larger than the 'days' window, and a null value
    data = {
        "team": ["A", "A", "A", "B", "B", "B", "B", "B"],
        "date": [
            date(2023, 1, 1), date(2023, 1, 2), date(2023, 1, 3), # Group A
            date(2023, 1, 10), date(2023, 1, 1), date(2023, 1, 2), date(2023, 1, 11), date(2023, 1, 12) # Group B (Jumbled)
        ],
        "points": [10, 20, 30, 100, 40, 60, None, None]
    }
    df = pl.DataFrame(data).with_columns(pl.col("date").cast(pl.Date))

    # 2. Execution
    # We want a 2-day window. 
    # Because of the .shift(1), the result for Date T should be the mean of [T-2, T-1]
    days = 2
    stats_cols = ["points"]
    result = aggregate_stats_last_x_days(
        df, group_by="team", date_col="date", days=days, stats_cols=stats_cols
    )

    # 3. Assertions
    # Sort for predictable indexing in assertions
    res_sorted = result.sort("team", "date")

    assert df.sort("team", "date").equals(res_sorted.drop('hist_mean_points'))

    # Check values as we'd expect 
    assert result['hist_mean_points'].equals(pl.Series([None, 10.0, 15, None, 40, 50, 100, 100]))
    

