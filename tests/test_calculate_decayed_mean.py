from ablinston_ml.features import calculate_decayed_mean
import polars as pl

def test_calculate_decayed_mean(data_path):

    # Read in the data
    input_df = pl.read_parquet(data_path / 'test_calculate_decayed_mean_input.parquet')
    correct = pl.read_parquet(data_path / 'test_calculate_decayed_mean_output.parquet')
    
    result = calculate_decayed_mean(
        input_df, 
        group_by = 'team',
        date = 'date',
        window = 364,
        half_life = 180,
        stats_cols = 'points',
        new_col_prefix = 'test_',
        shift = 1).drop('points')
    
    assert correct.equals(result)
