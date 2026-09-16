import io
import logging
import os
import pandas as pd
import pdb
import polars as pl
import random
import requests
import time
import undetected_chromedriver as uc
import zstandard as zstd
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed

from .data import append_to_zst, read_zst_pl

logger = logging.getLogger(__name__)

# This function gets a random user agent

def random_user_agent():

    user_agents = [
        # Chrome (Windows)
        # "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        # "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        
        # # Chrome (Mac)
        # "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        # "Mozilla/5.0 (Macintosh; Intel Mac OS X 12_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",

        # Firefox (Windows)
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:115.0) Gecko/20100101 Firefox/115",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:117.0) Gecko/20100101 Firefox/117.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:118.0) Gecko/20100101 Firefox/118.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:119.0) Gecko/20100101 Firefox/119.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
        # "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
        # "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
        # "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:129.0) Gecko/20100101 Firefox/129.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:130.0) Gecko/20100101 Firefox/130.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:131.0) Gecko/20100101 Firefox/131.0",
        # "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0",
        # "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:134.0) Gecko/20100101 Firefox/134.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:135.0) Gecko/20100101 Firefox/135.0"

        # # Firefox (Mac)
        # "Mozilla/5.0 (Macintosh; Intel Mac OS X 12.6; rv:117.0) Gecko/20100101 Firefox/117.0",
        # "Mozilla/5.0 (Macintosh; Intel Mac OS X 11.7; rv:114.0) Gecko/20100101 Firefox/114.0",

        # Edge (Windows)
        # "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0",
        # "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",

        # Safari (Mac)
        # "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_3) AppleWebKit/537.36 (KHTML, like Gecko) Version/16.5 Safari/537.36",
        # "Mozilla/5.0 (Macintosh; Intel Mac OS X 12_4) AppleWebKit/537.36 (KHTML, like Gecko) Version/16.4 Safari/537.36",

        # Android Chrome
        # "Mozilla/5.0 (Linux; Android 14; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Mobile Safari/537.36",
        # "Mozilla/5.0 (Linux; Android 13; Pixel 7 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",

        # # iPhone Safari
        # "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/537.36 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/537.36",
        # "Mozilla/5.0 (iPhone; CPU iPhone OS 16_5 like Mac OS X) AppleWebKit/537.36 (KHTML, like Gecko) Version/16.5 Mobile/15E148 Safari/537.36",
    ]

    return random.choice(user_agents)


def get_website_soup(
        url, 
        fast,
        playwright_context = None,
        cookies = {}, # Only needed for fast
        firefox_binary = '', # Only needed for NOT fast
        gecko_driver = '', # Only needed for NOT fast):
        chrome_driver = '',
        chrome_binary = '',
        chrome_version_main = None, # Major Chrome version to match against when fetching a chromedriver
        driver = None, # Pass in a driver if want to use it to search the site
        time_delay = True # whether to add a time pause after the driver loads the url
    ):
    
    # pdb.set_trace()

    soup = None

    # Save whether we passed a driver
    if driver is not None:
        driver_passed = True
    else:
        driver_passed = False

    if fast == True:

        # Use random headers each time
        headers = {'Accept':'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Encoding':'gzip, deflate, br, zstd',
            'Accept-Language':'en-US,en;q=0.5',
            'Connection':'keep-alive',
        #    'Host':'www.bestfightodds.com',
            'Priority':'u=0, i',
            'Referer': 'https://www.google.com/',
        #    'Sec-Fetch-Dest':'document',
        #    'Sec-Fetch-Mode':'navigate',
        #    'Sec-Fetch-Site':'same-origin',
        #    'Upgrade-Insecure-Requests':'1',
            'User-Agent': random_user_agent()}
        
        response = requests.get(url, headers=headers, cookies=cookies)
        
        # Check if been blocked by anti bot pretection
        if response.status_code in [403, 429]:
            # print("Blocked! Try changing User-Agent, IP, or waiting.")
            # print(f"Using user agent: {headers['User-Agent']}")
            
            # Change to a slow
            fast = False
        
        else:
            # Check if the response is compressed
            if response.headers.get("Content-Encoding") == 'zstd':
                # Sometimes it says zstd compressed but isn't so try and except
                try:
                    dctx = zstd.ZstdDecompressor()
                    stream = dctx.stream_reader(io.BytesIO(response.content))
                    text = stream.read().decode("utf-8")
                except Exception:
                    text = response.text
            else:
                text = response.text
        
            soup = BeautifulSoup(text, 'html.parser')
        
    # Else, if we have a playwright context, we use that
    elif playwright_context is not None:
                
        # Get a new page
        page = playwright_context.new_page()
        page.goto(url, wait_until="domcontentloaded")
        
        soup = BeautifulSoup(page.content(), 'html.parser')
        page.close()
        
    # Otherwise, use selenium, which is the slowest
    if fast == False and playwright_context is None:
        
        # ###########
        # # Setup headless Firefox for getting odds information
        # options = Options()
        # options.headless = True
        # options.accept_insecure_certs = True
        # # Create a Service object with the path to Firefox driver
        # options.binary_location = firefox_binary # firefox_binary
        # service = Service(gecko_driver)
        # # Create a WebDriver instance
        # driver = webdriver.Firefox(service=service, options=options)
        # ###########
        # pdb.set_trace()
        options = uc.ChromeOptions()
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--start-maximized")
        
        if driver is None:
            if chrome_driver == '':

                if chrome_binary != '':
                    options.binary_location = chrome_binary
                driver = uc.Chrome(options = options, headless = False, use_subprocess = True, version_main = chrome_version_main)
            else:
                driver = uc.Chrome(options = options, headless = False, driver_executable_path = chrome_driver, version_main = chrome_version_main)
                
        # Use selenium to navigate to the page
        driver.get(url)

        # Allow 20s to solve a captcha if needed
        if time_delay:
            time.sleep(5)
        
        # Option 1: Check the page title
        if "429" in driver.title:
            logger.warning("Rate limited!")
            if not driver_passed:
                driver.quit()

            return ""
        
        else:
            # Extract the page source
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            
            if not driver_passed:
                driver.quit()
        
    return soup


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
            logger.error("Save results path must be a .zst file")
            return None
        else:
            # Check the file exists
            if not os.path.exists(save_results_path):
                logger.error("The save results path must already exist as a file with column headers")
                return None
            else:
                # Initialise the delimiter
                cctx = zstd.ZstdCompressor()
                # Open the existing file to find the columns
                existing_zst = read_zst_pl(save_results_path)

                # Force single threads
                if num_threads > 1:
                    logger.warning("Forcing num_threads to 1 because save is enabled")
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
                    logger.error("Error for url %s: %s", future_to_url[future], e, exc_info = True)

                # Increment the completed count
                completed_count += 1
                if completed_count % 10 == 0:
                    logger.info("Completed %s out of %s tasks", completed_count, total_events)
                
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
                    logger.warning("Scrape produced no results: %s", url)

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
                        logger.error("Saving scrape results failed. Column number mistmatch: %s", url)
                        pdb.set_trace()
    
                if pause_between_requests > 0:
                    time.sleep(pause_between_requests)
    
                # Increment the completed count
                completed_count += 1
                if completed_count % 10 == 0:
                    logger.info("Completed %s out of %s tasks", completed_count, len(url_list))
                
            # Otherwise, the scrape failed
            except:
                logger.error("Failed to scrape: %s", url, exc_info = True)

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
                logger.error("Error for item %s: %s", future, e, exc_info = True)

            # Increment the completed count
            completed_count += 1
            if completed_count % 100 == 0:
                logger.info("Completed %s of %s", completed_count, len(input_list))
                
    if collapse_output_to_df:
        return pl.concat(output_list)
    else:
        return output_list
