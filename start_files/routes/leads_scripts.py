from selenium.common.exceptions import WebDriverException, TimeoutException, StaleElementReferenceException
from start_files.models.leads_db_section import leads_sessionLocal, init_db, Mls_leads, init_tables 
from start_files.routes.export_leads_scripts import export_leads
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dotenv import load_dotenv
from datetime import datetime
import requests
import logging
import asyncio
import time
import csv
import re
import os

# Load environment variables
load_dotenv()
BRIGHTMLS_USERNAME = os.getenv("BRIGHTMLS")
BRIGHTMLS_PASSWORD = os.getenv("BRIGHTPW")

# Set up logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

def purge_cloudflare_cache():
    logger.info("Starting purge")
    response = requests.post(
        f'https://api.cloudflare.com/client/v4/zones/{os.getenv("CLOUDFLARE_ZONE")}/purge_cache',
        headers={
            'Authorization': f'Bearer {os.getenv("CLOUDFLARE_API_TOKEN")}',
            'Content-Type': 'application/json',
        },
        json={'purge_everything': True}
    )
    return response.json()


def get_end_time_and_elapsed(start_time):
    end_time = time.time()
    elapsed = end_time - start_time
    formatted_end_time = datetime.fromtimestamp(end_time).strftime('%Y-%m-%d %H:%M:%S')
    formatted_elapsed_time = f"{int(elapsed // 60)}m {int(elapsed % 60)}s"
    return formatted_end_time, formatted_elapsed_time


def clean():
    csv_path1 = "brightscrape/Export_exchange.csv"
    csv_path2 = "brightscrape/Export_public_record.csv"

    if os.path.exists(csv_path1):
        os.remove(csv_path1)
        logger.info("Removed CSV.")

    if os.path.exists(csv_path2):
        os.remove(csv_path2)
        logger.info("Removed CSV.")


def preprocess_price(price_str: str) -> float:
    """Cleans and converts price strings to float."""
    match = re.search(r'\d+', price_str.replace(',', ''))
    return float(match.group()) if match else float('inf')


def public() -> list:
    csv_path = "brightscrape/Export_public_record.csv"
    all_data = []

    max_retries = 3
    delay = 2

    def preprocess_price(price_str: str) -> float:
        match = re.search(r'\d+', price_str.replace(',', ''))
        if match:
            return float(match.group())
        return float('inf')

    logger.info('Opening csv for rentals')
    
    for attempt in range(max_retries):
        try:
            with open(csv_path, mode='r') as data:
                data_content = csv.reader(data, delimiter=',')
                next(data_content, None)
                for row in data_content:
                    processed_row = (
                        row[0], row[7], row[8], row[9], row[10],
                        row[17], row[18], row[19],
                        row[23].strip().lower() == 'yes',
                        preprocess_price(row[44]), row[46]
                    )
                    all_data.append(processed_row)
            logger.info('Finished reading csv for rentals')
            return all_data
        
        except Exception as e:
            logger.error(f"Attempt {attempt + 1} failed: {e}")
            time.sleep(delay)
    raise Exception(f"Failed to read CSV after {max_retries} attempts")


def exchange() -> list:
    csv_path = "brightscrape/Export_exchange.csv"
    all_data = []

    max_retries = 3
    delay = 2

    def preprocess_price(price_str: str) -> float:
        match = re.search(r'\d+', price_str.replace(',', ''))
        if match:
            return float(match.group())
        return float('inf')

    logger.info('Opening csv for rentals')
    
    for attempt in range(max_retries):
        try:
            with open(csv_path, mode='r') as data:
                data_content = csv.reader(data, delimiter=',')
                next(data_content, None)
                for row in data_content:
                    processed_row = (
                        row[0], row[1], preprocess_price(row[3]), 
                        row[4], row[17], row[18], row[19], 
                        row[56], row[57], row[61], row[68]
                    )
                    all_data.append(processed_row)
            logger.info('Finished reading csv for rentals')
            return all_data
        
        except Exception as e:
            logger.error(f"Attempt {attempt + 1} failed: {e}")
            time.sleep(delay)
    raise Exception(f"Failed to read CSV after {max_retries} attempts")


@contextmanager
def get_db_session_pending():
    db = leads_sessionLocal()
    yield db 
    if db:
        db.close()


def add_listing_to_db1(db, item):
    listing = Mls_leads(
        mls=item[0],
        listing_agreement_type=item[1],
        list_price=item[2],
        status=item[3],
        ownership = item[4],
        owner_name=item[5],
        owner_phone=item[6],
        list_agent_first_name=item[7],
        list_agent_last_name=item[8],
        list_office_name=item[9],
        remarks_private=item[10],
        )
    db.add(listing)
    db.commit()

def update_listing_in_db1(listing_item, item):
    listing_item.mls = item[0]
    listing_item.listing_agreement_type = item[1]
    listing_item.list_price = item[2]
    listing_item.status = item[3]
    listing_item.ownership = item[4]
    listing_item.owner = item[5]
    listing_item.owner_phone = item[6]
    listing_item.list_agent_first_name = item[7]
    listing_item.list_agent_last_name = item[8]
    listing_item.list_office_name = item[9]
    listing_item.remarks_private = item[10]

def update_listing_in_db2(listing_item, item):
    listing_item.mls = item[0]
    listing_item.sale_amt = item[9]
    listing_item.owner_names = item[1]
    listing_item.owner_last_name = item[2]
    listing_item.owner_first_name = item[3]
    listing_item.owner2_last_name = item[4]
    listing_item.owner_address = item[5]
    listing_item.owner_city_state = item[6]
    listing_item.owner_zip_code = item[7]
    listing_item.owner_occupied = item[8]
    listing_item.property_class = item[10]


def clean_up_temp_listings(sorted_results):
    with get_db_session_pending() as db:
        results = {item[1] for item in sorted_results}
        temp_listings = db.query(Mls_leads).all()
        for listing_item in temp_listings:
            if listing_item.mls not in results:
                logger.info(f"{listing_item.mls} not in sorted results. Removing from database.")
                db.delete(listing_item)
                db.commit()
                logger.info(f"Removed {listing_item.mls} from database.")



def load_leads1(item, max_retries, delay):
    logger.info("Gathering leads..")
    mls = item[0]
    attempt = 0
    while attempt < max_retries:
#        try:            
            with get_db_session_pending() as db:
                listing_item = db.query(Mls_leads).filter_by(mls=mls).first()
                if listing_item is None:
                    logger.info(f"{mls} not found in database, adding data.")
                    try:
                        add_listing_to_db1(db, item)
                        logger.info(f"{mls} added to database!")
                    except Exception as e:
                        logger.info(f"{mls} something failed adding to database: {e}")
                else:
                    logger.info(f"{mls} found in the database, updating item.")
                    update_listing_in_db1(listing_item, item)
            logger.info(f'Completed {mls} run')
            return True 
                      
#        except (WebDriverException, TimeoutException, StaleElementReferenceException) as e:
#            logger.error(f"Attempt {attempt + 1} for MLS {mls} failed with error: {str(e)}")
#            attempt += 1
#            if attempt < max_retries:
#                time.sleep(delay)
#        except Exception as e:
#            logger.error(f"Unexpected error for MLS {mls}: {str(e)}")
#            return False 

    logger.error(f"MLS {mls} failed after {max_retries} attempts.")
    return False  

def load_leads2(item, max_retries, delay):
    logger.info("Gathering leads..")
    mls = item[0]
    attempt = 0
    while attempt < max_retries:
#        try:            
            with get_db_session_pending() as db:
                listing_item = db.query(Mls_leads).filter_by(mls=mls).first()
                try:
                    update_listing_in_db2(listing_item, item)
                    db.commit()  # Commit changes to the database
                    logger.info(f"{mls} added to database!")
                except Exception as e:
                    logger.info(f"{mls} failed adding to database: {e}")
            logger.info(f'Completed 2nd run')
            return True 
                      
#        except (WebDriverException, TimeoutException, StaleElementReferenceException) as e:
#            logger.error(f"Attempt {attempt + 1} for MLS {mls} -failed with error: {str(e)}")
#            attempt += 1
#            if attempt < max_retries:
#                time.sleep(delay)
#        except Exception as e:
#            logger.error(f"Unexpected error for MLS {mls}: {str(e)}")
#            return False 

    logger.error(f"MLS {mls} failed after {max_retries} attempts.")
    return False  


async def start_concurrency1(max_retries, delay, concurrency_limit, sorted_results: list) -> list:
    semaphore = asyncio.Semaphore(concurrency_limit)
    results = []

    async def download_leads_with_semaphore(item):
        async with semaphore:
            for attempt in range(max_retries):
                try:
                    return await asyncio.get_event_loop().run_in_executor(
                        executor, 
                        load_leads1,
                        item, 
                        max_retries, 
                        delay
                    )
                except (WebDriverException, TimeoutException, StaleElementReferenceException):
                    logger.error(f"Error processing item {item}. Attempt {attempt + 1}/{max_retries}")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(delay)  
                    else:
                        logger.error(f"Failed to process item {item} after {max_retries} attempts.")
                        raise 

    logger.info("Starting concurrent tasks")
    with ThreadPoolExecutor() as executor:
        tasks = [download_leads_with_semaphore(item) for item in sorted_results]
        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
        except Exception:
            logger.error("An error occurred during concurrent tasks")
    logger.info("Concurrent tasks completed")
    return results


async def start_concurrency2(max_retries, delay, concurrency_limit, sorted_public: list) -> list:
    semaphore = asyncio.Semaphore(concurrency_limit)
    results = []

    async def download_leads_with_semaphore(item):
        async with semaphore:
            for attempt in range(max_retries):
                try:
                    return await asyncio.get_event_loop().run_in_executor(
                        executor, 
                        load_leads2,
                        item, 
                        max_retries, 
                        delay
                    )
                except (WebDriverException, TimeoutException, StaleElementReferenceException):
                    logger.error(f"Error processing item {item}. Attempt {attempt + 1}/{max_retries}")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(delay)  
                    else:
                        logger.error(f"Failed to process item {item} after {max_retries} attempts.")
                        raise 


    logger.info("Starting concurrent tasks")
    with ThreadPoolExecutor() as executor:
        tasks = [download_leads_with_semaphore(item) for item in sorted_public]
        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
        except Exception:
            logger.error("An error occurred during concurrent tasks")
    logger.info("Concurrent tasks completed")
    return results


async def start_task_in_loop(concurrency_limit, max_retries, delay) -> None:
    await export_leads()
    csv_path1 = "brightscrape/Export_public_record.csv"
    csv_path2 = "brightscrape/Export_exchange.csv"

    while not (os.path.exists(csv_path1) and os.path.exists(csv_path2)):
        logger.info("Waiting for CSV files to appear...")
        await asyncio.sleep(5) 
    sorted_exchange = exchange()  
    sorted_public = public() 
    logger.info(f"cvs count {len(sorted_public[0]) + len(sorted_exchange[0])}")
    try:
        init_db()
        init_tables()
        logger.info("Initialized tables passed")
    except Exception:
        logger.info("Initialized tables failed.")
        
    await start_concurrency1(max_retries, delay, concurrency_limit, sorted_exchange)
    await start_concurrency2(max_retries, delay, concurrency_limit, sorted_public)
    logger.info("Loop task completed successfully")

def start_leads(concurrency_limit, max_retries, delay):
    start_time = time.time()
    logger.info(f"Start Time: {datetime.fromtimestamp(start_time).strftime('%Y-%m-%d %H:%M:%S')}")
    success = False
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(
        start_task_in_loop(concurrency_limit, max_retries, delay)
    )
    loop.close()
    success = True
    if success:
        clean()
        purge_cloudflare_cache()
        elapsed_time = time.time() - start_time
        minutes = int(elapsed_time // 60)
        seconds = elapsed_time % 60
        logger.info(f"Elapsed Time: {minutes} minutes {seconds:.2f} seconds")
