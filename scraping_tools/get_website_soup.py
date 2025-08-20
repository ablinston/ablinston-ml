# This function gets the response soup from a website either using selenium or a fast response

from bs4 import BeautifulSoup
import pdb
import requests
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service

from .random_user_agent import random_user_agent

def get_website_soup(
        url, 
        fast,
        playwright_context = None,
        cookies = {}, # Only needed for fast
        firefox_binary = '', # Only needed for NOT fast
        gecko_driver = '' # Only needed for NOT fast):
    ):
    
    # pdb.set_trace()

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
            print("Blocked! Try changing User-Agent, IP, or waiting.")
            print(f"Using user agent: {headers['User-Agent']}")
            
            # Change to a slow
            fast = False
        
        # Check if the response is compressed
        if response.headers.get("Content-Encoding") == 'zstd':
            dctx = zstd.ZstdDecompressor()
            stream = dctx.stream_reader(io.BytesIO(response.content))
            text = stream.read().decode("utf-8")
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
    if fast == False:
        
        ###########
        # Setup headless Firefox for getting odds information
        options = Options()
        options.headless = True
        options.accept_insecure_certs = True
        # Create a Service object with the path to Firefox driver
        options.binary_location = firefox_binary # firefox_binary
        service = Service(gecko_driver)
        # Create a WebDriver instance
        driver = webdriver.Firefox(service=service, options=options)
        ###########
    
        # Use selenium to navigate to the page
        driver.get(url)
        
        # Option 1: Check the page title
        if "429" in driver.title:
            print("Rate limited!")
            return ""
        
        else:
            # Extract the page source
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            
            driver.quit()
        
    return soup
