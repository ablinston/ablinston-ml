from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import as_completed
import pandas as pd
import pdb
import polars as pl
import os
import requests
import time
import undetected_chromedriver as uc
import zstandard as zstd

from .get_website_soup import get_website_soup
from .zst_data import append_to_zst, read_zst_pl


def parallel_scrape_and_process_urls( 
        url_list,
        func,
        fast,
        num_threads, 
        chrome_driver = '',
        concat_results = False,
        add_source_url = True,
        pause_for_captcha = False,
        pause_between_requests = 0, # How many seconds to pause between each request (only when using 1 thread)
        polars = True, # whether the output df from func is a polars data frame. If False, uses pandas
        save_results_path = '', # This sets a save path. For large scrapes, it will save data as it goes, appending to a compressed zstd file
        **kwargs):

    """
    This function takes a list of urls, scrapes them in parallel, then applies a function to the results and returns a list of the 
    results from that function.
    
    url_list : list[str]
        List of URLs to scrape.
    func : callable
        A function that takes a BeautifulSoup object (and optionally **kwargs)
        and returns a polars data frame.
    num_threads : int
        Number of parallel threads.
    chrome_driver : str
        Path to chromedriver. Leave blank to use default driver.
    **kwargs : dict
        Additional keyword arguments to pass to both get_website_soup and func.

    Returns
    -------
    pl.DataFrame
        Concatenated results from applying `func` to all scraped soups.
    
    """
    
    # Check if the save file exists and that it is a valid file
    if save_results_path != '':
        if not save_results_path.endswith('.zst'):
            print("Error: save results path must be a .zst file")
            return None
        else:
            # Check the file exists
            if not os.path.exists(save_results_path):
                print("Error: the save results path must already exist as a file with column headers")
                return None
            else:
                # Initialise the delimiter
                cctx = zstd.ZstdCompressor()
                # Open the existing file to find the columns
                existing_zst = read_zst_pl(save_results_path)

                # Force single threads
                if num_threads > 1:
                    print("Warning: forcing num_threads to 1 because save is enabled")
                    num_threads = 1

    scrape_results = []
    
    # Keep counters to track progress
    total_events = len(url_list)
    completed_count = 0
        
    # pdb.set_trace()
    
    options = uc.ChromeOptions()
    options.add_argument("--disable-blink-features=AutomationControlled")
    # options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--start-maximized")
    
    if chrome_driver == '':
        driver = uc.Chrome(options = options, headless = False)
    else:
        driver = uc.Chrome(options = options, headless = False, driver_executable_path = chrome_driver)
    
    # Get the cookies for first page with a Selenium call
    driver.get(url_list[0])

    # Give a delay to allow the checkbox to be manually done
    if pause_for_captcha:
        time.sleep(20)

    # Get cookies from driver
    cookies = driver.get_cookies()
    cookies_dict = {cookie['name']: cookie['value'] for cookie in cookies}

    # Quit the browser unless we are going through one at a time
    if num_threads > 1:
        driver.quit()

    # Check if we want to use more than 1 thread
    if num_threads > 1:

        with ThreadPoolExecutor(max_workers = num_threads) as executor:
            future_to_url = {executor.submit(get_website_soup, url, fast = fast, cookies = cookies_dict, chrome_driver = chrome_driver): url for url in url_list}

            # Collect results as they complete
            for future in as_completed(future_to_url):
                try:
                    # pdb.set_trace()
                    # Apply the function to the result
                    result = func(future.result(), **kwargs)
                    
                    # Add the url as a source
                    if add_source_url:
                        if polars:
                            result = result.with_columns(source = pl.lit(future_to_url[future]))
                        else:
                            result['source'] = future_to_url[future]
                    
                    scrape_results.append(result)  # Collect the result (url, title)

                except Exception as e:
                    print(f"Error for url {future_to_url[future]}: {e}")

                # Increment the completed count
                completed_count += 1
                if completed_count % 10 == 0:
                    print(f"Completed {completed_count} out of {total_events} tasks")
                
        # This ensures that all threads are done
        executor.shutdown(wait=True)

    # Otherwise, use a loop
    else:
        for url in url_list:

            try:
                # Get the soup
                soup = get_website_soup(url, fast = fast, cookies = cookies_dict, driver = driver)
    
                # Run it through the function
                result = func(soup, **kwargs)
                
                if len(result) == 0:
                    print(f"ERROR: Scrape produced no results: {url}")

                # Add the url as a source
                if add_source_url:
                    if polars:
                        result = result.with_columns(source = pl.lit(url))
                    else:
                        result['source'] = url
                    
                scrape_results.append(result)
    
                # Save the file if necessary
                if save_results_path != '':
                    
                    # Expand columns to match
                    if polars:
                        combined = pl.concat([existing_zst.head(0), result], how="diagonal")
                    else:
                        combined = pd.concat([existing_zst.head(0), result], how="diagonal")
                    
                    if len(combined.columns) == len(existing_zst.columns):
                        append_to_zst(
                            data = combined,
                            save_path = save_results_path,
                            polars = polars,
                            delimiter = '|',
                            cctx = cctx)
                    else:
                        pdb.set_trace()
                        print(f"ERROR: Saving scrape results failed. Column number mistmatch: {url}")
    
                if pause_between_requests > 0:
                    time.sleep(pause_between_requests)
    
                # Increment the completed count
                completed_count += 1
                if completed_count % 10 == 0:
                    print(f"Completed {completed_count} out of {len(url_list)} tasks")
                
            # Otherwise, the scrape failed
            except:
                print(f"ERROR: Failed to scrape: {url}")

        driver.quit()
    
    if concat_results:
        if len(scrape_results) == 0:
            if polars:
                return pl.DataFrame()
            else:
                return pd.DataFrame()
        else:    
            # Combine the results
            if polars:
                return pl.concat(scrape_results, how = 'diagonal') # Fills in missing columns as blank
            else:
                return pd.concat(scrape_results, axis = 0)
    else:
        return scrape_results