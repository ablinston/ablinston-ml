import numpy as np
import polars as pl
import pdb

def calculate_decayed_mean(df, group_by, date, window, half_life, stats_cols, new_col_prefix = 'decayed_', shift = 1):
    """
    This function calculates the decayed statistics for a game, using the date differences to decay the stats

    Parameters
    ----------
    df : polars data frame
        the dataset to be used
    group_by : character
        The column to be grouped by
    date : date
        The name of the date column
    window : integer
        How many days history to include in the decayed stats
    half_life: integer
        How many days half life for the decayed stats
    shift: integer
        How many fixtures to shift the stat by (if stats data is current row)
    stats_cols: list
        A list of the stats cols to calculate decayed stats for
    new_col_prefix: character
        A prefix to add to the new stats cols

    Returns
    -------
    data frame with the decayed stats added (other columns left alone)

    """
    
    # pdb.set_trace()
    
    # Sort of list of stats cols
    if type(stats_cols) != 'list':
        stats_cols = [stats_cols]
    
    decay_constant = np.log(2) / half_life
    
    decayed_df = (
        df.sort(group_by, date)
        # Start by establishing a rolling window with a hard boundary
        .rolling(
            index_column = date,
            period = f"{window}d",
            by = group_by
        )
        # Now aggregate across the window and calculate decayed stats
        .agg([
            (
                # 1. Calculate the weight for every game in the window
                # weight = exp(-lambda * days_ago)
                # 2. Multiply points by weight and divide by sum of weights
                (
                    pl.col(col) * (-decay_constant * (pl.col(date).max() - pl.col(date)).dt.total_days()).exp()
                ).sum() / 
                (-decay_constant * (pl.col(date).max() - pl.col(date)).dt.total_days()).exp().sum()
            )
            for col in stats_cols
        ])
        # Shift the results to the next fixture
        .with_columns(
            pl.col(stats_cols)
            .shift(shift)
            .over(group_by)
            .name.prefix(new_col_prefix))
        .drop(stats_cols)
    )
    
    return decayed_df