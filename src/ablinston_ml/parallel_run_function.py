from concurrent.futures import ThreadPoolExecutor, as_completed

import polars as pl


def parallel_run_function(
        func,
        input_list: list,
        max_workers: int,
        collapse_output_to_df: bool = False,
        **kwargs):
    """Run ``func`` over each element of ``input_list`` in parallel using threads.

    Work is distributed with :class:`~concurrent.futures.ThreadPoolExecutor`.
    Results are collected as futures complete, so **the order of items in the
    returned list matches completion order, not the original order of**
    ``input_list``.

    Parameters
    ----------
    func : callable
        Function to call for each item. Invoked as ``func(item, **kwargs)``.
    input_list : list
        Values to pass as the first argument to ``func``, one per task.
    max_workers : int
        Maximum number of worker threads (passed to ``ThreadPoolExecutor``).
    collapse_output_to_df : bool, default False
        If True, concatenate successful results with :func:`polars.concat`.
        Each result must be a :class:`polars.DataFrame`; use this when every
        ``func`` return value is a small frame you want stacked into one.
    **kwargs
        Extra keyword arguments forwarded to every ``func`` call.

    Returns
    -------
    list or polars.DataFrame
        If ``collapse_output_to_df`` is False, a list of return values from
        ``func`` (completion order). If True, a single concatenated
        :class:`polars.DataFrame`.

    Notes
    -----
    On exception inside ``func``, the error is printed and that item is
    skipped (nothing is appended for that task). For CPU-bound work, threads
    may not help due to the GIL; consider ``multiprocessing`` for heavy compute.
    """

    # Set up a list to contain all the results
    output_list = []
    completed_count = 0
    
    # Run the function in parallel
    with ThreadPoolExecutor(max_workers = max_workers) as executor:
        future_to_url = {executor.submit(func, item, **kwargs): item for item in input_list}

        # Collect results as they complete
        for future in as_completed(future_to_url):
            try:
                result = future.result()
                # Add the result to the list
                output_list.append(result)
                
            except Exception as e:
                print(f"Error for item {future}: {e}")

            # Increment the completed count
            completed_count += 1
            if completed_count % 100 == 0:
                print('Completed ' + str(completed_count) + ' of ' + str(len(input_list)))
                
    if collapse_output_to_df:
        return pl.concat(output_list)
    else:
        return output_list
