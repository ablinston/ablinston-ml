from bs4 import BeautifulSoup
import pdb
import requests
import time
import undetected_chromedriver as uc
import zstandard as zstd

from .random_user_agent import random_user_agent

def get_website_soup(
        url, 
        fast,
        playwright_context = None,
        cookies = {}, # Only needed for fast
        firefox_binary = '', # Only needed for NOT fast
        gecko_driver = '', # Only needed for NOT fast):
        chrome_driver = '',
        driver = None, # Pass in a driver if want to use it to search the site
        time_delay = True # whether to add a time pause after the driver loads the url
    ):
    
    # pdb.set_trace()

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
                except:
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
    if fast == False:
        
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
                driver = uc.Chrome(options = options, headless = False)
            else:
                driver = uc.Chrome(options = options, headless = False, driver_executable_path = chrome_driver)
                
        # Use selenium to navigate to the page
        driver.get(url)

        # Allow 20s to solve a captcha if needed
        if time_delay:
            time.sleep(2)
        
        # Option 1: Check the page title
        if "429" in driver.title:
            print("Rate limited!")
            if not driver_passed:
                driver.quit()

            return ""
        
        else:
            # Extract the page source
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            
            if not driver_passed:
                driver.quit()
        
    return soup
