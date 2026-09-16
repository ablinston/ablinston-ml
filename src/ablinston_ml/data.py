import io
import logging
import pandas as pd
import pdb
import polars as pl
import os
import zstandard as zstd

logger = logging.getLogger(__name__)

def append_to_zst(
	data, # The object to be saved
	save_path, # the filepath including filename for an existing zstd file with the same schema. Use Pipe
	polars, # Boolean whether the object is a list of polars data frames
	delimiter = '|',
	force_column_schema = [], # A list of the columns to force the provided data to take
	cctx = None): # The compressor initialised with zstd.ZstdCompressor()

	"""
	This function takes a zst file, a polars or pandas data frame, and then appends the rows from the data frame onto the existing file

	"""
# 	pdb.set_trace()

	if cctx is None:
		# Initialise the compressor
		cctx = zstd.ZstdCompressor()

	# 1. Handle Polars to Pandas conversion if necessary
	if not isinstance(data, pd.DataFrame):
		# This handles Polars DataFrames automatically
		data = data.to_pandas()

	# # Ensure schema unique
	# force_column_schema = list(dict.fromkeys(force_column_schema))

	# Sort out the forced columns
	if force_column_schema != []:
		# If columns don't match, ensure in same order
		if sorted(force_column_schema) != sorted(data.columns):
			# Find columns missing
			missing_cols = [col for col in force_column_schema if col not in data.columns]
			extra_cols = [col for col in data.columns if col not in force_column_schema]

			# If there are missing cols, create blank versions
			if len(missing_cols) > 0:
				logger.info('Columns missing from data to be appended to zst %s. Creating blank placeholders: %s', save_path, missing_cols)
				# if polars:
				# 	data = data.with_columns([pl.lit(None).alias(col) for col in missing_cols])
				# else:
				data.loc[:, missing_cols] = pd.NA

			# If there are extra cols, say which are being discarded
			if len(extra_cols) > 0:
				logger.info('Extra columns are present in data to be appended to zst %s. Removed columns %s', save_path, extra_cols)
				# pdb.set_trace()

		# Force data schema
		data = data.reindex(columns = force_column_schema)

	# Do a final check that the columns are correct
	if data.columns.to_list() != force_column_schema:
		pdb.set_trace()

	# Convert to csv without header
	# if polars:

	# 	csv_bytes = data.write_csv(include_header = False, separator = delimiter).encode("utf-8")  # no header when appending

	# else:
	csv_buffer = io.BytesIO()
	data.to_csv(csv_buffer, index = False, header = False, sep = delimiter)  # important: no header when appending
	csv_bytes = csv_buffer.getvalue()
	
	# Save the file
	with open(save_path, "ab") as f:
	    with cctx.stream_writer(f) as writer:
	        writer.write(csv_bytes)


def save_zst(
	df, # The object to be saved. 
	save_path, # the filepath including filename for an existing zstd file with the same schema. Use Pipe
	force_column_schema = [], # A list of the columns to force the provided data to take
	delimiter = '|'):

	"""
	This function takes a data frame and saves it as a zst, initialising it so that the function append_to_zst can be used on it.

	"""
	# pdb.set_trace()

	# 1. Handle Polars to Pandas conversion if necessary
	if not isinstance(df, pd.DataFrame):
		# This handles Polars DataFrames automatically
		df = df.to_pandas()

	# # Ensure schema unique
	# force_column_schema = list(set(force_column_schema))

	# Sort out the forced columns
	if force_column_schema != []:
		# If columns don't match, ensure in same order
		if sorted(force_column_schema) != sorted(df.columns):
			# Find columns missing
			missing_cols = [col for col in force_column_schema if col not in df.columns]
			extra_cols = [col for col in df.columns if col not in force_column_schema]

			# If there are missing cols, create blank versions
			if len(missing_cols) > 0:
				logger.info('Columns missing from data to be saved to zst %s. Creating blank placeholders: %s', save_path, missing_cols)
				df.loc[:, missing_cols] = pd.NA

			# If there are extra cols, say which are being discarded
			if len(extra_cols) > 0:
				logger.info('Extra columns are present in data to be saved to zst %s. Removed columns %s', save_path, extra_cols)

		# Force data schema
		df = df[force_column_schema]

	# Initialise the compressor
	cctx = zstd.ZstdCompressor()

	# Convert to csv
	csv_buffer = io.BytesIO()
	df.to_csv(csv_buffer, index = False, sep = delimiter)  # important: no header when appending
	csv_bytes = csv_buffer.getvalue()
	
	# 1. Ensure the directory exists
	dir_name = os.path.dirname(save_path)
	if dir_name and not os.path.exists(dir_name):
		os.makedirs(dir_name)

	# Save the file
	with open(save_path, "wb") as f:
	    with cctx.stream_writer(f) as writer:
	        writer.write(csv_bytes)

def read_zst_pl(path, delimiter = "|"):
    
    # pdb.set_trace()
    
    dctx = zstd.ZstdDecompressor()

    with open(path, "rb") as fh:
        with dctx.stream_reader(fh, read_across_frames=True) as reader:
            decompressed = reader.read()   # reads all output

    return pl.read_csv(decompressed, separator = delimiter, ignore_errors=True)

# This function cleans a zst file, by reading in ignoring errors, then removing duplicate rows
def clean_zst_file(path, delimiter = '|'):
    return None