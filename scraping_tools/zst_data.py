import io
import pandas as pd
import pdb
import polars as pl
import zstandard as zstd

def append_to_zst(
	data, # The object to be saved
	save_path, # the filepath including filename for an existing zstd file with the same schema. Use Pipe
	polars, # Boolean whether the object is a list of polars data frames
	delimiter = '|',
	cctx = None): # The compressor initialised with zstd.ZstdCompressor()

	"""
	This function takes a zst file, a polars or pandas data frame, and then appends the rows from the data frame onto the existing file

	"""
# 	pdb.set_trace()

	if cctx is None:
		# Initialise the compressor
		cctx = zstd.ZstdCompressor()

	# Convert to csv without header
	if polars:

		csv_bytes = data.write_csv(include_header = False, separator = delimiter).encode("utf-8")  # no header when appending

	else:
		csv_buffer = io.BytesIO()
		data.to_csv(csv_buffer, index = False, header = False, sep = delimiter)  # important: no header when appending
		csv_bytes = csv_buffer.getvalue()
	
	# Save the file
	with open(save_path, "ab") as f:
	    with cctx.stream_writer(f) as writer:
	        writer.write(csv_bytes)


def save_zst(
	pandas_df, # The object to be saved. 
	save_path, # the filepath including filename for an existing zstd file with the same schema. Use Pipe
	delimiter = '|'):

	"""
	This function takes a data frame and saves it as a zst, initialising it so that the function append_to_zst can be used on it.

	"""
# 	pdb.set_trace()

	# Initialise the compressor
	cctx = zstd.ZstdCompressor()

	# Convert to csv
	csv_buffer = io.BytesIO()
	pandas_df.to_csv(csv_buffer, index = False, sep = delimiter)  # important: no header when appending
	csv_bytes = csv_buffer.getvalue()
	
	# Save the file
	with open(save_path, "wb") as f:
	    with cctx.stream_writer(f) as writer:
	        writer.write(csv_bytes)

def read_zst_pl(path, delimiter = "|"):
    
    # pdb.set_trace()
    
    dctx = zstd.ZstdDecompressor()

    with open(path, "rb") as fh:
        with dctx.stream_reader(fh) as reader:
            decompressed = reader.read()   # reads all output

    return pl.read_csv(decompressed, separator = delimiter, ignore_errors=True)

# This function cleans a zst file, by reading in ignoring errors, then removing duplicate rows
def clean_zst_file(path, delimiter = '|'):
    return None