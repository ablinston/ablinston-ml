from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import as_completed
import datatable as dt
import pdb
import requests
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service

from .get_website_soup import get_website_soup

def parallel_scrape_and_process_urls( 
        url_list,
        func,
        fast,
        num_threads, 
        firefox_location, 
        gecko_driver,
        **kwargs):

    """
    This function takes a list of urls, scrapes them in parallel, then applies a function to the results and returns a list of the 
    results from that function.
    
    url_list : list[str]
        List of URLs to scrape.
    func : callable
        A function that takes a BeautifulSoup object (and optionally **kwargs)
        and returns a datatable dt.Frame.
    num_threads : int
        Number of parallel threads.
    firefox_location : str
        Path to Firefox binary.
    gecko_driver : str
        Path to GeckoDriver executable.
    **kwargs : dict
        Additional keyword arguments to pass to both get_website_soup and func.

    Returns
    -------
    dt.Frame
        Concatenated results from applying `func` to all scraped soups.
    
    """
    
    scrape_results = []
    
    # Keep counters to track progress
    total_events = len(url_list)
    completed_count = 0
        
    # pdb.set_trace()
    
    ###########
    # Setup headless Firefox for getting odds information
    options = Options()
    options.headless = True
    options.accept_insecure_certs = True
    # Create a Service object with the path to Firefox driver
    options.binary_location = firefox_location # firefox_binary
    service = Service(gecko_driver)
    # Create a WebDriver instance
    driver = webdriver.Firefox(service=service, options=options)
    ###########
    
    # Get the cookies for first page with a Selenium call
    driver.get(url_list[0])

    # Get cookies from Selenium
    selenium_cookies = driver.get_cookies()
    cookies_dict = {cookie['name']: cookie['value'] for cookie in selenium_cookies}
    # Quit the browser
    driver.quit()

    with ThreadPoolExecutor(max_workers = num_threads) as executor:
        future_to_url = {executor.submit(get_website_soup, url, fast = fast, cookies = cookies_dict, firefox_binary = firefox_location, gecko_driver = gecko_driver): url for url in url_list}

        # Collect results as they complete
        for future in as_completed(future_to_url):
            try:
                # pdb.set_trace()
                # Apply the function to the result
                result = func(future.result(), **kwargs)
                
                # Add the url as a source
                result[:, dt.update(source = future_to_url[future])]
                
                scrape_results.append(result)  # Collect the result (url, title)
            except Exception as e:
                print(f"Error for url {future_to_url[future]}: {e}")

            # Increment the completed count
            completed_count += 1
            print(f"Completed {completed_count} out of {total_events} tasks")
            
    # This ensures that all threads are done
    executor.shutdown(wait=True)
    
    if len(scrape_results) == 0:
        return dt.Frame()
    else:    
        # Combine the results
        return dt.rbind(scrape_results, force = True)