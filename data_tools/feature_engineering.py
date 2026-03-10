import numpy as np
import polars as pl
import pdb

def aggregate_stats_last_x_days(df, group_by, date_col, days, stats_cols, agg_func = 'mean', new_prefix = 'hist_mean_'):
    """
    Aggregates data for the last X number of days and provides the mean historic data for the team at the fixture date
    i.e. does not include the current data point
    
    :param df: polars data frame
    :param group_by: 
    :param days: the number of days history to include in the mean
    """
    # pdb.set_trace()
    
    # Change group to list if it isn't already
    if not isinstance(group_by, list):
        group_by = [group_by]

    # Sort the data frame
    df = df.sort(group_by + [date_col])

    # Only roll the columns we actually need to aggregate
    # This keeps the temporary 'rolling object' as small as possible
    cols_to_roll = group_by + [date_col] + stats_cols

    # 2. Define the aggregation expression dynamically
    if agg_func == 'mean':
        aggs = [pl.col(stats_cols).mean()]
    elif agg_func == 'sum':
        aggs = [pl.col(stats_cols).sum()]
    else:
        pdb.set_trace()

    # Now compute the new column
    new_df = (
        # Establish the rolling window
        df.select(cols_to_roll)
        # Convert stats to float 32. This is to 6-9 d.p. but reduces memory load and speed
        .with_columns(pl.col(stats_cols).cast(pl.Float32))
        .rolling(
            index_column = date_col,
            period = f'{days}d',
            group_by = group_by)
        .agg(aggs)
        )
    
    # Now shift them within the groups and relabel
    new_df = new_df.with_columns(
                pl.col(stats_cols)
                .shift(1)
                .over(group_by)
                .name.prefix(new_prefix)
                )

    # Data frames should be in the same order but check before merging
    if df.select(group_by + [date_col]).equals(new_df.select(group_by + [date_col])):
        return pl.concat([df, new_df.select([col for col in new_df.columns if col not in df.columns])], how = 'horizontal')
    else:
        pdb.set_trace()
        return df.join(
            new_df.select(group_by + [date_col] + [col for col in new_df.columns if 'hist' in col]), 
            on = group_by + [date_col], 
            how = 'left')

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
    if not isinstance(stats_cols, list):
        stats_cols = [stats_cols]
        
    if not isinstance(group_by, list):
        group_by = [group_by]
        
    
    decay_constant = np.log(2) / half_life
            
    # Sort the data
    df = df.sort(group_by + [date])
    
    # Only roll the columns we actually need to aggregate
    # This keeps the temporary 'rolling object' as small as possible
    cols_to_roll = group_by + [date] + stats_cols

    decayed_df = (
        df.select(cols_to_roll)
        # Start by establishing a rolling window with a hard boundary
        .rolling(
            index_column = date,
            period = f"{window}d",
            group_by = group_by
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
    
    # Return a data frame concatenated with the columns not used
    return pl.concat([decayed_df, df.select([col for col in df.columns if col not in decayed_df.columns])], how = 'horizontal')