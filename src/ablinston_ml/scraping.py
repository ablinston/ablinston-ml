import asyncio
import logging
import os
import pandas as pd
import pdb
import polars as pl
import random
import re
import time
import zstandard as zstd
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
from curl_cffi import requests as curl_requests
from seleniumbase import sb_cdp
from seleniumbase.core import nest_asyncio

from .data import append_to_zst, read_zst_pl

logger = logging.getLogger(__name__)

# Wording used by holding pages that sit in front of the real page while it checks you are human
holding_page_text = [
    'Checking your browser',
    'Just a moment',
    'Verifying you are human',
    'Enable JavaScript and cookies to continue',
    'This site requires [Jj]ava[Ss]cript'
]

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


# This function starts a browser that sites find hard to spot as automated, and opens a page in it

def start_browser(
        url = None,
        chrome_binary = '',
        headless = True
    ):

    # Jupyter already runs an event loop in the thread, and CDP mode needs to run one of its
    # own, so let them nest. Only worth doing when there is a loop to nest inside
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        pass
    else:
        nest_asyncio.apply()

    # SeleniumBase's CDP mode drives Chrome over the devtools protocol rather than through a
    # chromedriver, so there is no driver to install and nothing to keep in step with Chrome.
    # A window on Linux needs a virtual display for the captcha click to land in the right place
    browser = sb_cdp.Chrome(
        url,
        headless = headless,
        browser_executable_path = chrome_binary if chrome_binary else None,
        sandbox = False, # Chrome refuses to start with the sandbox on when running as root
        # Some of the sites I scrape are http only, and Chrome quietly upgrades the
        # url to https, which then fails with nothing useful in the error
        browser_args = ['--disable-features=HttpsUpgrades,HttpsFirstBalancedMode'],
        xvfb = not headless and os.name != 'nt')

    return browser


# This function clears the "verify you are human" checkbox that Cloudflare and similar put up

def clear_captcha(browser, wait = 30):

    # The click is done with the mouse so it needs a screen. Where there isn't one,
    # wait instead and let it be clicked by hand
    try:
        browser.gui_click_captcha()
    except Exception:
        logger.warning("Could not click the captcha, waiting %s seconds for it to be done by hand", wait)
        time.sleep(wait)


def get_website_soup(
        url,
        fast,
        playwright_context = None,
        cookies = {}, # Only needed for fast
        impersonate = 'chrome', # Browser whose fingerprint curl_cffi copies. Only needed for fast
        referer = 'https://www.google.com/', # Page to say we arrived from. Only needed for fast
        chrome_binary = '',
        browser = None, # Pass in a browser if want to use it to search the site
        captcha = False, # Whether the page puts up a bot check. Runs the browser in a window so it can be clicked
        captcha_wait = 30, # Seconds to leave the page open for the captcha to be done by hand
        time_delay = True # whether to add a time pause after the browser loads the url
    ):

    # pdb.set_trace()

    soup = None

    # Save whether we passed a browser
    if browser is not None:
        browser_passed = True
    else:
        browser_passed = False

    if fast == True:

        # curl_cffi copies the TLS handshake and the header order of a real browser, so the only
        # header worth setting by hand is the referer. The rest have to match the browser being
        # impersonated, and curl_cffi fills those in itself
        headers = {'Referer': referer}

        response = curl_requests.get(url, headers = headers, cookies = cookies, impersonate = impersonate)

        # Check if been blocked by anti bot pretection
        if response.status_code in [403, 429]:
            # print("Blocked! Try changing the impersonate target, IP, or waiting.")

            # Change to a slow
            fast = False

        else:
            # curl_cffi decompresses gzip, brotli and zstd itself
            soup = BeautifulSoup(response.text, 'html.parser')

            # Some sites hand back a holding page with a 200 rather than an error code, so
            # look for the wording those use and fall back to the browser as well
            if soup.find(string = re.compile('|'.join(holding_page_text))) is not None:
                soup = None
                fast = False

    # Else, if we have a playwright context, we use that
    elif playwright_context is not None:
                
        # Get a new page
        page = playwright_context.new_page()
        page.goto(url, wait_until="domcontentloaded")
        
        soup = BeautifulSoup(page.content(), 'html.parser')
        page.close()
        
    # Otherwise, use a real browser, which is the slowest
    if fast == False and playwright_context is None:

        # pdb.set_trace()
        if browser is None:
            # A captcha has to be clicked, so that needs a window rather than a headless browser
            browser = start_browser(url, chrome_binary = chrome_binary, headless = not captcha)
        else:
            browser.open(url)

        # Clear the bot check if the site puts one up
        if captcha:
            clear_captcha(browser, wait = captcha_wait)

        # Give the page time to finish loading
        if time_delay:
            time.sleep(5)

        # Option 1: Check the page title
        if "429" in browser.get_title():
            logger.warning("Rate limited!")
            if not browser_passed:
                browser.stop()

            return ""

        else:
            # Extract the page source
            soup = BeautifulSoup(browser.get_page_source(), 'html.parser')

            # start_browser turns off the automatic https upgrade, so this is here to
            # catch it creeping back in, or a browser passed in that was started
            # without the flag
            final_url = browser.get_current_url()

            if not browser_passed:
                browser.stop()

            if url.startswith('http://') and final_url.startswith('https://'):
                raise ConnectionError(f"Chrome upgraded {url} to https, which the site does not serve")

            # Chrome serves its own error page when it can't reach the site. That
            # parses like any other page, so without this the failure turns up much
            # further down as missing tables
            if soup.find(id = 'main-frame-error') is not None:
                error_code = soup.find(class_ = 'error-code')
                code = error_code.get_text(strip = True) if error_code else 'no error code'
                raise ConnectionError(f"Browser could not load {url}: {code}")

    return soup


def parallel_scrape_and_process_urls( 
        url_list,
        func,
        fast,
        num_threads,
        chrome_binary = '',
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
    chrome_binary : str
        Path to the Chrome binary. Leave blank to use whichever Chrome is found.
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
    
    # Get the cookies for first page with a browser call. Run in a window rather than
    # headless so a captcha can be cleared
    browser = start_browser(url_list[0], chrome_binary = chrome_binary, headless = False)

    # Clear the checkbox, falling back to it being done by hand
    if pause_for_captcha:
        clear_captcha(browser)

    # Get cookies from the browser
    cookies = browser.get_all_cookies()
    cookies_dict = {cookie.name: cookie.value for cookie in cookies}

    # Quit the browser unless we are going through one at a time
    if num_threads > 1:
        browser.stop()

    # Check if we want to use more than 1 thread
    if num_threads > 1:

        with ThreadPoolExecutor(max_workers = num_threads) as executor:
            future_to_url = {executor.submit(get_website_soup, url, fast = fast, cookies = cookies_dict, chrome_binary = chrome_binary): url for url in url_list}

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
                soup = get_website_soup(url, fast = fast, cookies = cookies_dict, browser = browser)
                
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
                        # pdb.set_trace()
                        raise ValueError(f"Column number mismatch saving {url}. Got {len(combined.columns)} columns, expected {len(existing_zst.columns)}")
    
                if pause_between_requests > 0:
                    time.sleep(pause_between_requests)
    
                # Increment the completed count
                completed_count += 1
                if completed_count % 10 == 0:
                    logger.info("Completed %s out of %s tasks", completed_count, len(url_list))
                
            # Otherwise, the scrape failed
            except:
                logger.error("Failed to scrape: %s", url, exc_info = True)

        browser.stop()
    
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
