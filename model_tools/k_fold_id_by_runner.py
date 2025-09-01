import pandas as pd
import numpy as np
import pdb

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
		print("Runner lists must be the same length")
		return None

	# Get a unique list of all runners
	runners = list(set(runner_series_1.to_list() + runner_series_1.to_list()))

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