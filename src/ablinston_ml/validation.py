import logging
import pandas as pd
import numpy as np
import pdb

logger = logging.getLogger(__name__)

def k_fold_id_by_runner(n_folds, runner_series_1, runner_series_2):

	"""
	This function takes two lists of runners and returns a numeric identifier to be used to split into folder.

	It will do this in alphabetical order.

	Parameters
	----------
	n_folds : int
		The number of folds the data is to be separated into

	runner_series_1: pandas series
		A series giving the runners to be used to split the data

	runner_series_2: pandas series
		A series giving the runners to be used to split the data
	
	"""
# 	pdb.set_trace()

	if len(runner_series_1) != len(runner_series_2):
		logger.error("Runner lists must be the same length")
		return None

	# Get a unique list of all runners
	runners = sorted(set(runner_series_1.to_list() + runner_series_2.to_list()))

	# Create the fold id list
	fold_id = np.array([np.nan] * len(runner_series_1))

	# Loop through each runner and assign them to a fold
	i = 0
	for runner in runners:

		# Replace anywhere without an ID for that runner as in that group
		fold_id = np.where(
			np.isnan(fold_id) & ((runner_series_1 == runner) | (runner_series_2 == runner)),
			i,
			fold_id
		)

		# Move onto next fold
		i = (i + 1) % n_folds

	# Check the final values
	fold_id = np.where(np.isnan(fold_id), 99, fold_id)
    	
	print("Folds samples sizes:")
	print(pd.Series(fold_id).value_counts())

	return fold_id

def equals_to_dp(df1, df2, decimals, sort_by = None):

	"""
	Does the same job as pandas .equals, but numeric columns only have to agree to a given
	number of decimal places. Columns and rows are both put in order first, so the frames do
	not have to be sorted the same way. Anything that doesn't match is logged.

	The row sort means the index is ignored, unlike .equals.

	Parameters
	----------
	df1 : pandas data frame
		The first frame to compare

	df2 : pandas data frame
		The second frame to compare

	decimals : int
		The number of decimal places to round the numeric columns to before comparing

	sort_by : list, optional
		Columns that identify a row, used to line the two frames up. Without it the rows are
		sorted on every column, so a column that differs can pair the wrong rows together and
		blame columns that are actually fine.

	"""

	only_in_1 = [col for col in df1.columns if col not in df2.columns]
	only_in_2 = [col for col in df2.columns if col not in df1.columns]

	if only_in_1 or only_in_2:
		logger.info("Columns differ. Only in the first frame: %s. Only in the second frame: %s", only_in_1, only_in_2)
		return False

	if df1.shape != df2.shape:
		logger.info("Shapes differ: %s vs %s", df1.shape, df2.shape)
		return False

	# Put the columns in the same order and round before sorting, otherwise a tiny difference
	# can put the rows in a different order
	cols = sorted(df1.columns)
	to_round = {col: decimals for col in cols if pd.api.types.is_numeric_dtype(df1[col]) and pd.api.types.is_numeric_dtype(df2[col])}

	df1 = df1[cols].round(to_round).reset_index(drop = True)
	df2 = df2[cols].round(to_round).reset_index(drop = True)

	# Sorting is much the slowest part, so don't do it if the rows already line up
	if df1.equals(df2):
		return True

	# Object columns can hold a mix of types that won't sort against each other, so order on
	# their text instead. Both frames get the same treatment so they still line up
	as_text = {col: str for col in cols if df1[col].dtype == object or df2[col].dtype == object}
	sort_cols = sort_by if sort_by else cols

	df1 = df1.loc[df1.astype(as_text).sort_values(sort_cols).index].reset_index(drop = True)
	df2 = df2.loc[df2.astype(as_text).sort_values(sort_cols).index].reset_index(drop = True)

	# Go a column at a time so the log says what is actually wrong
	matched = True
	for col in cols:

		if df1[col].dtype != df2[col].dtype:
			logger.info("Column %s has different types: %s vs %s", col, df1[col].dtype, df2[col].dtype)
			matched = False

		elif not df1[col].equals(df2[col]):
			n_different = (df1[col].ne(df2[col]) & ~(df1[col].isna() & df2[col].isna())).sum()
			logger.info("Column %s differs on %s of %s rows", col, n_different, len(df1))
			matched = False

	return matched
