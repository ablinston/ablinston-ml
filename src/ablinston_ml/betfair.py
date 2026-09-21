import json
import logging
import pdb
from pathlib import Path

import pandas as pd
import polars as pl
from betfairlightweight import StreamListener

try:
    import orjson as _orjson
except ImportError:
    _orjson = None

logger = logging.getLogger(__name__)

def betfair_file_to_final_odds(file_path, odds_cutoff_hours, average_last_n, trading):
    
    """
    This function takes a path to a betfair file that has been extracted from bz2 and turns it into a dataframe
    with chosen odds given a set cutoff date
    
    """
    # pdb.set_trace()
    
    # create listener
    listener = StreamListener(max_latency=None)
    
    # Create historical stream (update file_path to your file location)
    stream = trading.streaming.create_historical_generator_stream(
        file_path = file_path,
        listener = listener,
    )

    # Convert the list of series into a data frame
    betfair_odds_df = betfair_stream_to_df(stream = stream)
    
    if len(betfair_odds_df) > 0:
        # # Get the last odds before the chosen cutoff time
        # betfair_odds_summary_df = betfair_bout_get_chosen_odds(betfair_odds_df, odds_cutoff_hours, average_last_n)
    
        return betfair_odds_summary_df
    else:
        return pl.DataFrame()
            









def betfair_get_runner_info_from_marketcatalogue(marketcatalogue):
    
    """
    This function takes a marketbook and extracts the information market name and runner ids with runner names
    
    Returns a dictionary of selection_id and runner names
    
    """
    # pdb.set_trace()
    
    # Initiate a runner dictionary
    runner_dict = {}
    
    for runner in marketcatalogue.runners:
        runner_dict.update({runner.selection_id: runner.runner_name})
    
    return runner_dict








# This function takes a Betfair stream and saves the data to a data frame

def betfair_stream_to_df(stream = None, stream_snapshot = None, inplay = False, market_catalogues = None, upcoming_min_best_offer = 0, upcoming_odds_to_use = 'last_price_traded'):
    
    # pdb.set_trace()
    
    # Initial checks
    if stream is None and stream_snapshot is None:
        logger.error("Need a valid input stream")
        return None
    
    if stream_snapshot is not None and market_catalogues is None:
        logger.error("stream_snapshot input needs a market catalogue for runner and market names")
        return None
    
    # Process the market catalogues if present
    if market_catalogues is not None:
        runners_dict = {k: v for d in map(betfair_get_runner_info_from_marketcatalogue, market_catalogues) for k, v in d.items()}
    
    if stream is not None:
        # create generator
        gen = stream.get_generator()
        all_market_books = gen()
    else:
        all_market_books = [stream_snapshot]
    
    # Create an empty odds object to be populated with the odds info
    betfair_odds_list = []
    
    # Create a file for each marketbook
    for market_books in all_market_books:
        for market_book in market_books:
                   
            try:
                # Get a list of the runners names and put them into a dictionary if we don't have the market catalogue
                if market_catalogues is None:
                    runners_dict = {}
                    for runner in market_book.market_definition.runners: # Runner names are contained in the marketbook
                        runners_dict = runners_dict | {runner.selection_id: runner.name}
                
                # Now loop through the runners and get the odds data
                for runner in market_book.runners:
                    
                    # pdb.set_trace()
                    
                    # Get the odds to use
                    if upcoming_odds_to_use == 'best_offer':
                        
                        # Use the minium to filter out offers
                        offers = [item for item in runner.ex.available_to_back if item.size > upcoming_min_best_offer]
                        
                        # Best offer is the first in the list
                        best_odds = offers[0].price
                        
                    else:
                        best_odds = runner.last_price_traded
                    
                    # Add a dictionary to the odds list for this runner
                    betfair_odds_list.append({
                        'GMT_datetime': market_book.publish_time, # is technically in UTC but that is the same as GMT in 24H clock
                        'market_id': market_book.market_id,
                        'fixture': market_book.market_definition.event_name,
                        'market_type': market_book.market_definition.market_type,
                        'status': market_book.status,
                        'inplay': market_book.inplay,
                        'runner': runners_dict[runner.selection_id],
                        'runner_handicap': runner.handicap,
                        'last_price_traded': best_odds
                    })
            except:
                # pdb.set_trace()
                pass
    
    # Get the date of the event
    output_df = pl.from_dicts(betfair_odds_list, infer_schema_length = 1000)
    
    # Get rid of NA bets
    output_df = output_df.filter(~pl.col('last_price_traded').is_null())
                                 
    
    # # Remove any bets after the cutoff time ## THE LIVE STREAMS ONLY GIVE ONE SET OF ODDS PER FIGHT
    # if cutoff_time is not None:
    #     cutoff_date = datetime.strptime(str(output_df['GMT_datetime'].dt.date.max()) + "-" + cutoff_time, "%Y-%m-%d-%H:%M")
    #     output_df = output_df[output_df['GMT_datetime'] <= cutoff_date]
        
    # pdb.set_trace()
        
    # Filter out in play
    if not inplay:
        output_df = output_df.filter((pl.col('inplay') == False) & (pl.col('status') == "OPEN"))
            
    # Convert the list of series into a data frame
    return output_df







def betfair_read_file(file_path):
    """
    Read a decompressed Betfair NDJSON stream from disk (one JSON object per line).

    Uses a single binary read, line iteration without decoding the whole buffer as text, and
    ``orjson`` when installed for faster parsing.

    Parameters
    ----------
    file_path : str or pathlib.Path
        Path to the file on disk.

    Returns
    -------
    list[dict]
        Parsed record dicts; empty lines and invalid JSON lines are skipped.
    """
    p = Path(file_path)
    raw = p.read_bytes()
    if not raw:
        return []
    out = []
    append = out.append
    if _orjson is not None:
        loads = _orjson.loads
        decode_error = _orjson.JSONDecodeError
    else:
        loads = json.loads
        decode_error = json.JSONDecodeError
    for line in raw.splitlines():
        if not line:
            continue
        try:
            obj = loads(line)
        except decode_error:
            continue
        if isinstance(obj, dict):
            append(obj)
    return out


def betfair_file_to_df_fast(file_path, inplay = False):
    """
    Build a runner-level Polars frame from Betfair-style stream messages using a flatten
    (json_normalize) step then Polars struct/list operations.

    ``inplay``: when ``False`` (default), same as ``betfair_stream_to_df``: keep only rows that are
    not in-play and market ``status`` is ``OPEN`` (pre-off), if those columns exist.

    ``file_path`` may be a ``str`` / ``Path`` to an NDJSON file on disk (read via
    :func:`betfair_read_file`) or a sequence of dict records passed straight into
    ``pd.json_normalize``.
    """
    if isinstance(file_path, (str, Path)):
        _path = Path(file_path)
        if _path.is_file():
            file_path = betfair_read_file(_path)
    if not file_path:
        return pl.DataFrame()
    # Step 1: Flatten nested dict/list structures into wide columns (pandas uses ``sep`` for
    # nested key names, e.g. parent_child). Produces one row per top-level record in ``file_path``.
    pdf = pd.json_normalize(file_path, sep="_")


    pl_df = (
        # Step 2: Move into Polars for faster columnar ops and typed datetime handling.
        pl.from_pandas(pdf)
        # Step 3: Keep only publish time and the market-changes array (``mc``) from each message.
        .select("pt", "mc")
        # Step 4: One row per element of ``mc`` (each market change object in that message).
        .explode("mc")
        # Step 5: Turn each ``mc`` struct/dict into top-level columns (``id``, ``marketDefinition``, â€¦).
        .unnest("mc")
    )

    # Check whether we have odds
    if "rc" not in pl_df.columns:
        return pl.DataFrame()
    else:

        pl_df = (
            # Step 6: Drop fields we do not need yet; keep market id, message time, and definition blob.
            pl_df.select("id", "pt", "marketDefinition", "rc")
            # Step 7: Rename Betfair's ``id`` to a clearer column name for the market.
            .rename({"id": "market_id"})
            # Step 8: Expand ``marketDefinition`` (event, market type, runner catalogue, etc.).
            .unnest("marketDefinition")

            # Step 9: Keep identifiers, event/market metadata, and the list of runner definitions.
            .select("market_id", "marketTime", "pt", "eventId", "eventName", "marketType", "inPlay", "runners", "rc")
            # Step 10: One row per runner entry inside ``runners`` (still nested fields per runner).
            .explode("runners")
            # Step 11: Turn each runner struct into columns (``id``/``name``/``hc``/â€¦ as emitted by Betfair).
            .unnest("runners")
            .rename({"id": "runner_id"})
            .select("market_id", "pt", "marketType", "eventId", "eventName", "marketTime", "inPlay", "runner_id", "name", "status", "rc")
            # Unnest the odds
            .explode("rc")
            .unnest("rc")
            # Step 12: Convert ``pt`` (Unix ms on the wire) to a timezone-aware UTC datetime column.
            .with_columns(
                pl.from_epoch(pl.col("pt"), time_unit="ms")
                .dt.replace_time_zone("UTC")
                .alias("GMT_datetime"),
            )

            # Fill the runner ID with the ID from the odds where missing
            .with_columns(pl.when(pl.col("runner_id").is_null())
                        .then(pl.col("id"))
                        .otherwise(pl.col("runner_id"))
                        .alias("runner_id")
            )

            # Now sort the data before we fill in the market info for the odds data. We want to group runners together and sort by date
            .sort(['runner_id', 'GMT_datetime'])

            # Now fill in the market information. The odds columns will have missing data for this, but it should all follow the previous market info in the file
            .with_columns(pl.col(["eventId", "eventName", "marketTime", "marketType", "inPlay", "runner_id", "name", "status"]).fill_null(strategy = "forward"))

            # Step 13: Raw millisecond timestamp and Betfair sort field are no longer needed as columns.
            .drop("pt", "id")
            # Step 14: Align names with the rest of ``betfair_tools`` / downstream code.
            .rename(
                {
                    "eventName": "event_name",
                    "marketType": "market_type",
                    "marketTime": "event_start_time",
                    "inPlay": "inplay",
                    "name": "runner_name",
                    "eventId": "event_id",
                    "ltp": "last_traded_price"
                }
            )

            # Filter out any missing information
            .filter(pl.col("last_traded_price").is_not_null())
        )

    # Rename the handicap column if it exists and fill in any missing values
    if 'hc' in pl_df.columns:
        pl_df = (
            # Fill None with 0, because in Betfair, none is no handicap
            pl_df.with_columns(pl.col('hc').fill_null(0))
            .rename({'hc': 'runner_handicap'})
        )
    else:
        # Else just create an empty column for handical
        pl_df = pl_df.with_columns(pl.lit(None).alias('runner_handicap'))

    # Match betfair_stream_to_df: when inplay flag is False, keep only pre-off (not in-play) OPEN rows
    if not inplay:
        filt = pl.col('inplay') == False
        if 'status' in pl_df.columns:
            filt = filt & (pl.col('status').is_in(['OPEN', 'ACTIVE']))
        pl_df = pl_df.filter(filt)

    # Return without duplicates (not sure why but sometimes rows are just repeats)
    return pl_df.unique()
