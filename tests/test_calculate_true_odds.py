from ablinston_ml.features import calculate_true_odds
import polars as pl

def test_calculate_true_odds():

    # 1. Setup: a two way market. Worked out by hand, probs are 1/odds:
    # 2.00 / 2.00   0.5  + 0.5   = 1.000   already true, odds come back unchanged
    # 1.50 / 1.50   2/3  + 2/3   = 1.333   true probs 0.5 each, so 2.0 / 2.0
    # 1.25 / 4.00   0.8  + 0.25  = 1.050   true probs 0.7619 / 0.2381, so 1.3125 / 4.2
    # null / 1.25   null + 0.8            home price missing
    two_way = pl.DataFrame({
        'home_odds': [2.0, 1.5, 1.25, None],
        'away_odds': [2.0, 1.5, 4.00, 1.25]
    })

    # 2. Execution
    result = calculate_true_odds(two_way, ['home_odds', 'away_odds']).select(pl.all().round(6))

    # 3. Assertions
    assert result['true_home_odds'].to_list() == [2.0, 2.0, 1.3125, None]
    assert result['true_away_odds'].to_list() == [2.0, 2.0, 4.2, None]

    # With imputation the missing price is filled so the book sums to 1, giving 0.2 for home.
    # The other rows have nothing missing so they are unaffected.
    imputed = calculate_true_odds(two_way, ['home_odds', 'away_odds'], impute_nulls = True).select(pl.all().round(6))

    assert imputed['true_home_odds'].to_list() == [2.0, 2.0, 1.3125, 5.0]
    assert imputed['true_away_odds'].to_list() == [2.0, 2.0, 4.2, 1.25]

    # 4. Setup: the same idea for a three way market
    # 3.00 / 3.00 / 3.00   1/3 + 1/3 + 1/3     = 1.000   already true, unchanged
    # 2.50 / 2.50 / 2.50   0.4 + 0.4 + 0.4     = 1.200   true probs 1/3 each, so 3.0 / 3.0 / 3.0
    # 1.60 / 4.00 / 4.00   0.625 + 0.25 + 0.25 = 1.125   true probs 0.5556 / 0.2222 / 0.2222, so 1.8 / 4.5 / 4.5
    # 2.00 / null / 4.00   0.5 + null + 0.25            draw price missing, imputes to 0.25
    three_way = pl.DataFrame({
        'win_odds':  [3.0, 2.5, 1.6, 2.0],
        'draw_odds': [3.0, 2.5, 4.0, None],
        'loss_odds': [3.0, 2.5, 4.0, 4.0]
    })

    odds_cols = ['win_odds', 'draw_odds', 'loss_odds']

    result = calculate_true_odds(three_way, odds_cols).select(pl.all().round(6))

    assert result['true_win_odds'].to_list() == [3.0, 3.0, 1.8, None]
    assert result['true_draw_odds'].to_list() == [3.0, 3.0, 4.5, None]
    assert result['true_loss_odds'].to_list() == [3.0, 3.0, 4.5, None]

    imputed = calculate_true_odds(three_way, odds_cols, impute_nulls = True).select(pl.all().round(6))

    assert imputed['true_win_odds'].to_list() == [3.0, 3.0, 1.8, 2.0]
    assert imputed['true_draw_odds'].to_list() == [3.0, 3.0, 4.5, 4.0]
    assert imputed['true_loss_odds'].to_list() == [3.0, 3.0, 4.5, 4.0]


def test_calculate_true_odds_imputation_assumes_no_margin():

    # 1. Setup: the same away price of 1.25 in two books, one complete and one missing the home price
    # 4.00 / 1.25   0.25 + 0.8 = 1.050   5% margin to take off, so 4.2 / 1.3125
    # null / 1.25   0.2  + 0.8 = 1.000   home imputed with the leftover 0.2, nothing to take off
    df = pl.DataFrame({
        'home_odds': [4.0, None],
        'away_odds': [1.25, 1.25]
    })

    # 2. Execution
    result = calculate_true_odds(df, ['home_odds', 'away_odds'], impute_nulls = True).select(pl.all().round(6))

    # 3. Assertions
    assert result['true_home_odds'].to_list() == [4.2, 5.0]
    assert result['true_away_odds'].to_list() == [1.3125, 1.25]

    # This is the bit worth pinning down. Imputing assumes no margin, so the away price we
    # already had comes back untouched instead of drifting out to 1.3125 like it does in the
    # complete book above.
    assert result['true_away_odds'][1] == df['away_odds'][1]


def test_calculate_true_odds_too_many_missing():

    # 1. Setup: a three way market where a row is missing more than one price
    # 2.00 / 4.00 / 4.00   complete, sums to 1 already
    # 2.00 / null / null   two missing, no way to split the leftover
    # null / null / null   nothing to go on at all
    df = pl.DataFrame({
        'win_odds':  [2.0, 2.0, None],
        'draw_odds': [4.0, None, None],
        'loss_odds': [4.0, None, None]
    })

    # 2. Execution
    result = calculate_true_odds(df, ['win_odds', 'draw_odds', 'loss_odds'], impute_nulls = True).select(pl.all().round(6))

    # 3. Assertions: only the complete row gets true odds, the rest stay null
    assert result['true_win_odds'].to_list() == [2.0, None, None]
    assert result['true_draw_odds'].to_list() == [4.0, None, None]
    assert result['true_loss_odds'].to_list() == [4.0, None, None]


def test_calculate_true_odds_keeps_other_columns():

    # 1. Setup: odds sat in a frame with other columns around them, which is the normal case
    df = pl.DataFrame({
        'match_id': [1, 2],
        'league': ['prem', 'champ'],
        'home_odds': [2.0, 1.5],
        'away_odds': [2.0, 1.5]
    })

    # 2. Execution
    result = calculate_true_odds(df, ['home_odds', 'away_odds'])

    # 3. Assertions: everything that went in comes back, with the true odds on the end
    assert result.columns == ['match_id', 'league', 'home_odds', 'away_odds', 'true_home_odds', 'true_away_odds']
    assert result.drop('true_home_odds', 'true_away_odds').equals(df)
    assert result['true_home_odds'].to_list() == [2.0, 2.0]
    assert result['true_away_odds'].to_list() == [2.0, 2.0]
