import logging
import yaml
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
import time
import pickle
import os


# Load the configuration from the YAML file
def load_config():
    with open("../utilities/config.properties.yaml", "r") as file:
        properties = yaml.safe_load(file)
    env = properties["env"]
    config_file = properties["config_file"][env]

    with open(config_file, "r") as file:
        config = yaml.safe_load(file)
    return config, env

# Set up logging configuration for production from config
def setup_logging(config):
    log_level = getattr(logging, config["logging"]["level"].upper(), logging.DEBUG)
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(config["logging"]["log_file"]),  # Log to file
            logging.StreamHandler()  # Log to console
        ]
    )


# Login to LinkedIn using credentials from config file
def login(driver, username, password, login_url, config):

    # Set cookies_file path
    cookies_file = config["cookies_file"]

    if os.path.exists(cookies_file):
        driver.get("https://www.linkedin.com")
        with open(cookies_file, "rb") as f:
            cookies = pickle.load(f)

        # Check if any cookie is expired
        cookies_expired = False
        for cookie in cookies:
            if 'expiry' in cookie:
                if cookie['expiry'] < int(time.time()):  # If current time is past the expiry time
                    cookies_expired = True
                    break

        if not cookies_expired:
            for cookie in cookies:
                driver.add_cookie(cookie)
            logging.info("Valid cookies loaded, skipping login")
            driver.get(login_url)  # Go to the intended page after loading cookies
            return  # Skip the login process if cookies are valid

        logging.info("Cookies expired, logging in as usual...")

    logging.info("Cookies not found or expired, logging in...")
    wait = WebDriverWait(driver, 10)
    driver.get(login_url)

    try:
        username_field = wait.until(EC.presence_of_element_located((By.ID, "username")))
        username_field.send_keys(username)  # Use username from config
        password_field = wait.until(EC.presence_of_element_located((By.ID, "password")))
        password_field.send_keys(password)  # Use password from config
        wait.until(EC.element_to_be_clickable((By.CLASS_NAME, "login__form_action_container"))).click()
        logging.debug("Login successful")

        # Save cookies after successful login
        cookies = driver.get_cookies()
        with open(cookies_file, "wb") as f:
            pickle.dump(cookies, f)
        logging.info("Cookies saved for future sessions")

    except Exception as e:
        logging.debug(f"Error: Login failed: {e}")




# Search LinkedIn using search URL from config
def search(driver, search_url):
    time.sleep(5)
    try:
        driver.get(search_url)
        logging.debug("Search initiated on LinkedIn")
    except Exception as e:
        logging.debug(f"Error: Error during search: {e}")

def get_jobs(driver):
    try:
        job_list_container = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, 'scaffold-layout__list-container'))
        )
        logging.debug("Job list container found")
        return job_list_container
    except TimeoutException:
        logging.debug("Error: Timeout while waiting for job list container")
        return None

def load_next_page(driver):
    try:
        curr = driver.find_element(By.XPATH, '//*[@aria-current="true"]').text
        next_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, f'//*[@aria-label="Page {int(curr)+1}"]'))
        )
        next_button.click()
        logging.debug(f"Loaded next page: {int(curr)+1}")
    except Exception as e:
        logging.debug(f"Error: Failed to load next page: {e}")

def get_n_results(driver):
    try:
        wait = WebDriverWait(driver, 10)
        results_div = wait.until(
            EC.presence_of_element_located((By.CLASS_NAME, "jobs-search-results-list__subtitle"))
        )
        n_string = results_div.text
        n = int(n_string.split()[0].replace(',', ""))
        logging.info(f"Found {n} job results")
        return n
    except Exception as e:
        # Log to inspect its error
        logging.debug(f"Error fetching number of results: {e}")
        return None

def filter_jobs(jobs):
    cleaned_jobs = {}

    for job in jobs:
        if job['title'] != 'N/A':
            job_title_cleaned = job['title'].split('\n')[0].strip()
            job['title'] = job_title_cleaned
        if job['link'] != 'N/A':
            cleaned_jobs[job['link']] = {
                'title': job['title'],
                'location': job['location']
            }

    filtered_jobs = {link: job for link, job in cleaned_jobs.items() if not (job['title'] == 'N/A' and job['location'] == 'N/A')}
    logging.debug(f"Filtered {len(filtered_jobs)} jobs")
    return filtered_jobs

def extract_all_job_titles_links_and_locations(driver, job_list_container):
    try:
        job_cards = job_list_container.find_elements(By.TAG_NAME, 'li')
        jobs = []

        for job_card in job_cards:
            try:
                job_element = job_card.find_element(By.CLASS_NAME, 'job-card-list__title')
                job_title = job_element.text.strip()
                job_link = job_element.get_attribute('href')
            except NoSuchElementException:
                job_title = 'N/A'
                job_link = 'N/A'

            try:
                location_element = job_card.find_element(By.CLASS_NAME, 'job-card-container__metadata-item')
                location = location_element.text.strip()
            except NoSuchElementException:
                location = 'N/A'

            jobs.append({
                'title': job_title,
                'link': job_link,
                'location': location
            })

        filtered_jobs = filter_jobs(jobs)
        logging.debug(f"Extracted and filtered {len(filtered_jobs)} jobs")
        return filtered_jobs

    except TimeoutException as e:
        logging.debug(f"Error: Timeout waiting for job list container: {e}")
        return []
    except Exception as e:
        logging.debug(f"Error: Error extracting job titles, links, and locations: {e}")
        return []


def get_description(driver, job_dict, max_retries=3, retry_wait=3, wait_time=10):
    good = []
    fail = []

    for link in list(job_dict.keys()):
        if link not in good:
            logging.info(f"Extracting {job_dict[link]['title']}")
            retries = 0
            while retries < max_retries:
                try:
                    driver.get(link)

                    # Wait for the job description element to appear before scrolling
                    WebDriverWait(driver, wait_time).until(
                        EC.presence_of_element_located((By.ID, 'job-details'))
                    )

                    # Scroll the page after waiting for the page to load
                    click_see_more_button(driver)

                    if driver.current_url != link:
                        logging.debug(f"Error: Failed to load job details for {link}")
                        job_dict.pop(link)
                        break  # Move on to the next link if page doesn't load correctly

                    # Scrape the job description within the retry loop
                    job_description_element = driver.find_element(By.ID, 'job-details')
                    job_description = job_description_element.text.strip()  # Remove leading/trailing spaces

                    # Check if description is empty
                    if not job_description:
                        logging.debug(f"Job description is empty for {link}. Retrying... {retries + 1}/{max_retries}")
                        retries += 1
                        time.sleep(retry_wait)  # Wait before retrying
                        continue  # Retry scraping the description

                    # Initialize default values for other fields
                    applicants = ''
                    days_ago = ''

                    # Try to scrape "applicants", if it fails, leave as empty string
                    try:
                        parent_div = driver.find_element(By.XPATH,
                                                         "//div[contains(@class, 'job-details-jobs-unified-top-card__primary-description-container')]")
                        applicants_element = parent_div.find_element(By.XPATH, ".//span[contains(text(), 'applicants')]")
                        applicants = applicants_element.text
                    except Exception as e:
                        logging.debug(f"Error: Could not extract applicants for {link}: {e}")

                    # Try to scrape "days ago", if it fails, leave as empty string
                    try:
                        days_ago_element = parent_div.find_element(By.XPATH, ".//span[contains(text(), 'ago')]")
                        days_ago = days_ago_element.text
                    except Exception as e:
                        logging.debug(f"Error: Could not extract days ago for {link}: {e}")

                    # Update the job dictionary with the scraped information
                    job_dict[link].update({
                        "description": job_description,
                        "applicants": applicants,
                        "posted_time": days_ago
                    })

                    good.append(link)
                    logging.debug(f"Successfully scraped job details for {link}")
                    break  # Exit the retry loop since scraping was successful

                except Exception as e:
                    logging.debug(f"Error: Failed to scrape {link} on attempt {retries + 1}: {e}")
                    retries += 1
                    time.sleep(retry_wait)  # Wait before retrying

            # If max retries are exhausted, log the failure and move on
            if retries == max_retries:
                logging.debug(f"Error: Max retries reached for {link}. Skipping...")
                fail.append(link)
    logging.info(f"Scraping Summary: Good_Links {len(good)} & Fail_Links {len(fail)}")
    return job_dict


def save(final_file, new_data, save_dir):
    file_path = os.path.join(save_dir, final_file)

    # Load existing data if file exists, otherwise create an empty dict
    try:
        with open(file_path, 'rb') as fp:
            existing_data = pickle.load(fp)
        logging.debug(f"Existing data loaded from {file_path}")
    except FileNotFoundError:
        logging.debug(f"{file_path} does not exist. Starting fresh.")
        existing_data = {}  # Start with an empty dict if no file exists
    except Exception as e:
        logging.debug(f"Error loading existing data: {e}")
        existing_data = {}

    # Filter out the keys from new_data that already exist in existing_data
    unique_new_data = {k: v for k, v in new_data.items() if k not in existing_data}

    if not unique_new_data:
        logging.info("No unique keys found. Nothing to save.")
        return

    logging.info(f"Saving {len(unique_new_data)} new links")

    # Merge the unique new data with the existing data
    updated_data = {**existing_data, **unique_new_data}

    # Saving the updated data back to the file
    try:
        with open(file_path, 'wb') as fp:
            pickle.dump(updated_data, fp, protocol=pickle.HIGHEST_PROTOCOL)
        logging.info(f"Data successfully saved to {file_path}")
    except Exception as e:
        logging.debug(f"Error saving file: {e}")

def load(file_name, save_dir):
    file_path = os.path.join(save_dir, file_name)

    try:
        with open(file_path, 'rb') as fp:
            job_dict = pickle.load(fp)
        logging.info(f"Data successfully loaded from {file_path}")
        return job_dict
    except FileNotFoundError:
        logging.debug(f"{file_path} does not exist. Starting fresh.")
        return {}
    except Exception as e:
        logging.debug(f"Error: Error loading file: {e}")
        return {}

def scroll_through_jobs(driver):
    try:
        jobs_block = WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.XPATH, "//ul[@class='scaffold-layout__list-container']/li"))
        )
        for index, job in enumerate(jobs_block):
            driver.execute_script("arguments[0].scrollIntoView({block: 'center', inline: 'nearest'});", job)
            time.sleep(1)
        logging.debug("Finished scrolling through all jobs.")
    except Exception as e:
        logging.debug(f"Error: Error scrolling through jobs: {e}")


def scroll_until_see_more_button(driver):
    """Scroll the page until the 'See more' button becomes visible."""
    try:
        while True:
            # Try to find the "See more" button
            see_more_button = driver.find_element(By.XPATH, "//button[@aria-label='Click to see more description']")

            # Check if the button is displayed and clickable
            if see_more_button.is_displayed() and see_more_button.is_enabled():
                logging.debug("See more button is visible and clickable.")
                break  # Exit the loop once the button is found and visible

            # Scroll the page by 1000 pixels vertically if the button is not visible yet
            driver.execute_script("window.scrollBy(0, 1000);")
            logging.debug("Page scrolled by 1000 pixels.")

            # Optionally add a small delay between scrolls
            time.sleep(1)

    except NoSuchElementException:
        logging.debug("Error: 'See more' button not found while scrolling.")
    except Exception as e:
        logging.debug(f"Error: Error while scrolling the page: {e}")

def click_see_more_button(driver):
    try:
        # Scroll the page until the button is visible
        scroll_until_see_more_button(driver)

        # Once the button is visible, click it
        see_more_button = driver.find_element(By.XPATH, "//button[@aria-label='Click to see more description']")
        see_more_button.click()
        logging.debug("Clicked 'See more' button to expand the job description")
    except Exception as e:
        logging.debug(f"Error: Failed to click 'See more' button: {e}")


def start_scraping_with_job_dict(driver, config, password):

    login(driver, config["username"], password, config["urls"]["login_url"], config)
    all_job_details =load(config["paths"]["job_data_file"], config["paths"]["save_directory"])
    job_dict_full = get_description(driver, all_job_details)
    save(config["paths"]["full_job_data_file"], job_dict_full, config["paths"]["save_directory"])


def start_scraping(driver, config, password, env):
    login(driver, config["username"], password, config["urls"]["login_url"], config)
    search(driver, config["urls"]["search_url"])
    total_job = get_n_results(driver)
    logging.info(f"Total jobs found: {total_job}")

    if total_job is None:
        return

    all_job_details = {}

    for i in range(config["scraping"]["no_of_pages"]):  # Scraping multiple pages
        logging.info(f"Getting Links from page: {i+1}")
        scroll_through_jobs(driver)
        time.sleep(2)
        job_list_container = get_jobs(driver)
        if job_list_container:
            job_details = extract_all_job_titles_links_and_locations(driver, job_list_container)
            all_job_details.update(job_details)
            load_next_page(driver)

    save(config["paths"]["job_data_file"], all_job_details, config["paths"]["save_directory"])

    job_dict_full = get_description(driver, all_job_details)
    save(config["paths"]["full_job_data_file"], job_dict_full, config["paths"]["save_directory"])


def configure_driver(config, env):

    if env == "DOCKER":
        chrome_options = Options()

        # Set headless mode for production, useful in Docker environments
        if config["browser"]["headless"]:
            chrome_options.add_argument("--headless")

        # Disable GPU in Docker
        chrome_options.add_argument("--disable-gpu")

        # Disable dev-shm-usage for Docker to avoid shared memory issues
        chrome_options.add_argument("--disable-dev-shm-usage")

        # No sandbox, useful for running in restricted environments like Docker
        chrome_options.add_argument("--no-sandbox")

        # Disable extensions for performance and security
        chrome_options.add_argument("--disable-extensions")

        # Set window size to prevent issues with element visibility
        chrome_options.add_argument(f"--window-size={config['browser']['window_size']}")

        # Return the configured driver
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    elif env == "LOCAL":
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))

    return driver

def main():
    config, env = load_config()  # Load config.properties.yaml file
    setup_logging(config)  # Set up logging

    # Configure the WebDriver with options for production
    driver = configure_driver(config, env)

    # Load password from file
    password = open(config["paths"]["password_file"], "r").read().strip()

    # Start the scraping process
    start_scraping(driver, config, password, env)

    # Start the scraping with existing links
    # start_scraping_with_job_dict(driver, config, password)

    driver.quit()


if __name__ == "__main__":
    main()
