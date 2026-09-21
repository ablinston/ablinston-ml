from ablinston_ml.validation import equals_to_dp
import logging
import numpy as np
import pandas as pd

def test_equals_to_dp(caplog):

    # 1. Setup: two frames that only differ in the last few decimal places of the elo
    left = pd.DataFrame({
        'fighter': ['alice', 'bob', 'carl'],
        'elo': [1500.0000000001, 1372.7380000002, np.nan],
        'fights': [1, 2, 3],
        'date': pd.to_datetime(['2021-01-01', '2021-02-01', '2021-03-01'])
    })

    right = left.copy()
    right['elo'] = [1500.0000000009, 1372.7379999998, np.nan]

    # 2. The two elos agree to 6 d.p. but not to 12. A NaN in the same place counts as equal
    assert equals_to_dp(left, right, 6)
    assert not equals_to_dp(left, right, 12)
    assert equals_to_dp(left, left.copy(), 12)

    # 3. Rows and columns in a different order, with an index that isn't 0, 1, 2
    shuffled = right.iloc[[2, 0, 1]][['date', 'fights', 'elo', 'fighter']]

    assert equals_to_dp(left, shuffled, 6)

    # 4. An object column holding a mix of types still sorts, including when it is the only
    # thing being sorted on, which is where pandas would otherwise refuse to compare them
    left_mixed = left.copy()
    right_mixed = shuffled.copy()
    left_mixed['scraped'] = [pd.Timestamp('2021-01-01'), '', 'n/a']
    right_mixed['scraped'] = ['n/a', pd.Timestamp('2021-01-01'), '']

    assert equals_to_dp(left_mixed, right_mixed, 6)
    assert equals_to_dp(left_mixed, right_mixed, 6, sort_by = ['scraped'])
    assert equals_to_dp(left_mixed[['scraped']], right_mixed[['scraped']], 6)

    # 5. Real differences are caught
    changed = right.copy()
    changed.loc[1, 'elo'] = 1400.0
    assert not equals_to_dp(left, changed, 6)

    extra = right.copy()
    extra['margin'] = 1
    assert not equals_to_dp(left, extra, 6)

    assert not equals_to_dp(left, right.iloc[:2], 6)

    retyped = right.copy()
    retyped['fights'] = retyped['fights'].astype('float64')
    assert not equals_to_dp(left, retyped, 6)

    # 6. Without a key the rows sort on every column, so the elo difference reorders the two
    # frames and the log blames 'name', which is actually identical. sort_by pins the pairing.
    keyed_left = pd.DataFrame({'name': ['alice', 'bob'], 'elo': [1500.0, 1400.0]})
    keyed_right = pd.DataFrame({'name': ['alice', 'bob'], 'elo': [1400.0, 1500.0]})

    with caplog.at_level(logging.INFO):

        caplog.clear()
        assert not equals_to_dp(keyed_left, keyed_right, 6)
        assert 'Column name differs' in caplog.text

        caplog.clear()
        assert not equals_to_dp(keyed_left, keyed_right, 6, sort_by = ['name'])
        assert 'Column elo differs' in caplog.text

        # 7. The log says what was wrong, not just that something was
        caplog.clear()
        assert not equals_to_dp(left, right.iloc[:2], 6)
        assert 'Shapes differ: (3, 4) vs (2, 4)' in caplog.text

        caplog.clear()
        assert not equals_to_dp(left, extra, 6)
        assert "Only in the second frame: ['margin']" in caplog.text

        caplog.clear()
        assert not equals_to_dp(left, retyped, 6)
        assert 'Column fights has different types: int64 vs float64' in caplog.text
