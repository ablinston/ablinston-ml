from data_tools.feature_engineering import calculate_decayed_mean
import polars as pl

def test_calculate_decayed_mean():

    # Read in the data
    input_df = pl.read_parquet('X:/Repos/custom_tools/tests/data/test_calculate_decayed_mean_input.parquet')
    correct = pl.read_parquet('X:/Repos/custom_tools/tests/data/test_calculate_decayed_mean_output.parquet')
    
    result = calculate_decayed_mean(
        input_df, 
        group_by = 'team',
        date = 'date',
        window = 364,
        half_life = 180,
        stats_cols = 'points',
        new_col_prefix = 'test_',
        shift = 1)
    
    assert correct.equals(result)



# fp.write('X:/Repos/custom_tools/tests/data/test_calculate_decayed_mean_input.parquet', input_df.to_pandas(), compression = 'ZSTD')
# fp.write('X:/Repos/custom_tools/tests/data/test_calculate_decayed_mean_output.parquet', result.to_pandas(), compression = 'ZSTD')