import logging
import time
import requests
import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.common.exceptions import NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
from dotenv import load_dotenv
import os
import openai
from bs4 import BeautifulSoup
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from playwright.sync_api import sync_playwright
import pytesseract
from pdf2image import convert_from_path
import random
from dotenv import load_dotenv
import os

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
load_dotenv()
openai.api_key = os.getenv('OPENAI_API_KEY')
num_iterations = int(input("Enter the number of iterations: "))

def extract_abstract(url):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        page.goto(url, timeout=60000)
        def handle_cookie_consent(page):
            cookie_keywords = [
                "accept all cookies", "accept cookies", "allow all cookies", "accept all", 
    "allow cookies", "continue", "allow", "agree", "consent", "I agree", "I consent", 
    "accept", "accept all and continue", "accept all and proceed", "I accept", "I agree to cookies",
    "allow all", "yes, accept", "yes, I accept", 
    "consent to all", "consent and continue", 
    "yes, allow",
    "allow all cookies and proceed", "allow all cookies", 
    "consent to cookies",
    "agree to all cookies", "allow cookies and continue", 
    "allow cookies and proceed", "accept cookies and continue browsing"
            ]

            for keyword in cookie_keywords:
                try:
                    button = page.locator(f"button:has-text('{keyword}')")  # This line matches only buttons with the text
                    button.wait_for(timeout=500)  # Wait for the button to appear
                    button.click()  # Click the button
                    print(f"Clicked button with text '{keyword}'")
                    return  # Exit after clicking the first button found
                except Exception as e:
                    print(f"Could not find button with text '{keyword}': {e}") 
            print("No cookie consent buttons found on the page.")


        handle_cookie_consent(page)


        screenshot_path = 'screenshot.png'
        page.screenshot(path=screenshot_path)
        print(f"Screenshot saved to {screenshot_path}")        
        pdf_path = 'output.pdf'
        page.pdf(path=pdf_path)
        print(f"PDF saved to {pdf_path}")
        content = page.content()
        browser.close()

    soup = BeautifulSoup(content, 'html.parser')
    
    abstract = soup  # Example selector
    if abstract:
        abstract_text = abstract.get_text()
    else:
        abstract_text = "Abstract not found"
    return pdf_path

def pdf_to_text(url, max_pages=3):
    pages = convert_from_path(url, 600)
    text_data = ''
    for i, page in enumerate(pages):
        if i >= max_pages:
            break
        text = pytesseract.image_to_string(page)
        text_data += text + '\n'
    return text_data

def summarize_abstract(abstract_text):
    ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY') 
    ENDPOINT_URL = "https://api.anthropic.com/v1/messages"

    headers = {
        "Content-Type": "application/json",
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
    }
    try:
        body_parameters = {
            "model": "claude-3-5-sonnet-20240620",
            "max_tokens": 1024,
            "system": "You are a helpful assistant.",
            "messages": [
                {
                    "role": "user",
                    "content": f"Extract the exact text of the abstract from the provided text along with other sections like introduction, purpose, methods, results, conclusions. Do not summarize or paraphrase; provide the text word for word. If a clear abstract is not present, look for the other parts and provide them:\n\n{abstract_text}",
                },
            ],
        }

        def get_abstract():
            retries = 3
            for attempt in range(3):
                try:
                    response = requests.post(ENDPOINT_URL, json=body_parameters, headers=headers)
                    response.raise_for_status()                  
                    return response.json()['content'][0]['text']
                except requests.exceptions.HTTPError as http_err:
                    print(f"HTTP Error: {http_err.response.status_code}")
                    print("Response Body:", http_err.response.json())
                except requests.exceptions.RequestException as req_err:
                    print("No response received:", req_err.request)
                except Exception as err:
                    print("Error:", err)
                    
                if attempt < retries - 1:
                    print(f"Retrying... ({attempt + 1}/{retries})")
                    time.sleep(random.uniform(10,30)) 
            return None

        abstract = get_abstract()
        if abstract:
            
            print("abstract_text:", abstract)
            return abstract
        else:
            print("No Abstract.")
            return None       
    except Exception as error:
        print("Error:", error)

def gmat(question):
    ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY') 
    ENDPOINT_URL = "https://api.anthropic.com/v1/messages"

    headers = {
        "Content-Type": "application/json",
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
    }
    try:
        body_parameters = {
            "model": "claude-3-5-sonnet-20240620",
            "max_tokens": 1024,
            "system": """You are an expert in evaluating research abstracts. Please read the following abstract and title very slowly, making sure not to miss any details. After reading, extract the following conclusions:

            **Conclusions**
            1. Age group of those involved in the study. Look for clearly indicated age groups in the study, not the implied age group. 
            2. If the study was done on populations residing in Long-term care. May include other variations of the term like: Nursing home residents, or elderly home residents, or aged home residents. They must be residing there. limited to residents of nursing homes or similar institutions.
            3. Ethnic group of those involved in the study and categorize it as white-skinned or not. 
            4. Identify the type of study. 

            After extracting the conclusions, categorize the abstract as "Include," or "Exclude,"  based on the following criteria:

            **Inclusion Criteria:**
            1. Age group is about Older adults (around 55+ years). 
            2. The settings of the study was done on Long-term care residents. May include other variations of the term like: Nursing home residents, or elderly home residents, or aged home residents. 
            3. The study primarily includes: non-white-skinned ethnicities. This criteria includes any non-caucasians regardless of where they live. 

            **Exclusion Criteria:**
            1. The study does not focus on older groups (around 55+ years)
            2. The study was not conducted on Long-term care residents. 
            3. The study was done on White/caucasian populations only. 
            4. The study is a Literature review. For example: scoping reviews, systematic reviews, narrative/integrative reviews, etc.

            **Instructions:**
            - Exclude if any exclusion criteria are met.
            - Include if all inclusion criteria are met.
            - Include if the study is about comparing White populations and other Minorities that are included in long-term care.
            - Include studies implying older adults populations without stating specific age. 
            - Include If the study is done in a country in South America, Africa, Asia, where the majority of residents are non-whites.
            - Important: Exclude if the study does not provide any information that you can use to imply the ethnic group of the participants.
            - The populations must be residing in Long-term facilities. It can not be home care based. 
            - Important: Exclude if the study does not explicitly state the age group. 


            /////////////////
            PLease make result as json wihtout expalining. I need only json. 
            ////here is sample json /////
            {
                "conclusions": {
                    "age_group": "Elders",
                    "long_term_care": "Not specified",
                    "ethnic_group": "Hispanic (non-white)",
                    "study_type": "Not specified (appears to be a narrative review)"
                },
                "categorization": "Exclude",
                "reasoning": "While the abstract focuses on Hispanic elders (meeting the age and ethnicity criteria), it does not specify that the study was conducted on long-term care residents. Additionally, the abstract appears to be a narrative review of health issues affecting Hispanic elders in the United States, rather than a primary research study. The lack of information about long-term care settings and the review nature of the study meet exclusion criteria."
            }
            """,
            "messages": [
                {
                    "role": "user",
                    "content": f"Abstract: {question}",
                },
            ],
        }

        def get_answer():
            retries = 3
            for attempt in range(3):
                try:
                    response = requests.post(ENDPOINT_URL, json=body_parameters, headers=headers)
                    response.raise_for_status()
                        # Output response
                    print("Response Object:", response.json()['content'][0]['text'])
                    return response.json()['content'][0]['text']
                except requests.exceptions.HTTPError as http_err:
                    print(f"HTTP Error: {http_err.response.status_code}")
                    print("Response Body:", http_err.response.json())
                except requests.exceptions.RequestException as req_err:
                    print("No response received:", req_err.request)
                except Exception as err:
                    print("Error:", err)
                    
                if attempt < retries - 1:
                    print(f"Retrying... ({attempt + 1}/{retries})")
                    time.sleep(random.uniform(10,30)) 
            return None

        answer = get_answer()
        if answer:
            parsed_data = json.loads(answer)
            categorization_value = parsed_data['categorization']
            print("Answer:", categorization_value)
            return categorization_value
        else:
            print("No valid response received.")
            return None       
    except Exception as error:
        print("Error:", error)

def human_typing(element, text, delay=0.2):
    for char in text:
        element.send_keys(char)
        time.sleep(delay)

EMAIL = os.getenv('EMAIL')
PASSWORD = os.getenv('PASSWORD')

logging.info("Initializing the Chrome driver")
driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()))

logging.info("Opening the Covidence sign-in page")
driver.get("https://app.covidence.org/sign_in")

logging.info("Locating the email and password fields and sign-in button")
email_field = driver.find_element(By.ID, "session_email")
password_field = driver.find_element(By.ID, "session_password")
sign_in_button = driver.find_element(By.NAME, "commit")

logging.info("Entering credentials")
human_typing(email_field, EMAIL)
human_typing(password_field, PASSWORD)

logging.info("Clicking the sign-in button")
sign_in_button.click()

logging.info("Waiting for the page to load")
driver.implicitly_wait(5)

try:
    logging.info("Checking for successful sign-in")
    user_profile = driver.find_element(By.ID, "react-ds-primary-nav") 
    logging.info("Sign-in successful")

    time.sleep(random.uniform(5,10))
    logging.info("Navigating to the archived reviews page")
    driver.get("https://app.covidence.org/reviews/active")

    logging.info("Waiting for the archived reviews page to load")
    driver.implicitly_wait(3)

    time.sleep(random.uniform(3,6))
    logging.info("Locating and clicking the specific link")
    specific_link = driver.find_element(By.XPATH, "//a[@title='LTC, Immigrant, Elder, NA']")
    specific_link.click()
    logging.info("Clicked the specific link")

    time.sleep(random.uniform(5,12))

    logging.info("Locating and clicking the 'Continue' link")
    continue_link = driver.find_element(By.XPATH, "//a[@data-testid='stage-action-screen']")
    continue_link.click()
    logging.info("Clicked the 'Continue' link")

    logging.info("Starting the process of locating abstracts and clicking 'No' button")
    for _ in range(num_iterations):
        try:
            review_parent_element = driver.find_element(By.XPATH, "//div[@class='reference clearfix']")
        except NoSuchElementException:
            logging.info("No more references found, clicking 'More' button")
            try:
                more_button = driver.find_element(By.XPATH, "//a[@class='button secondary more-studies']")
                more_button.click()
                logging.info("'More' button clicked")
                time.sleep(random.uniform(10,12))  
                continue  
            except NoSuchElementException:
                logging.info("'More' button not found, ending loop")
                break 
        title_element = review_parent_element.find_element(By.XPATH, "./div[@class='title']")
        title_text = title_element.text
        logging.info(f"Title found: {title_element.text}")        
        prompt_text_created = False
        try:
            abstract_div = review_parent_element.find_element(By.XPATH, "./div[@class='abstract']/p")
            logging.info(f"Abstract found: {abstract_div.text}")
            promt_text = f'title:\n {title_text}\nabstract:\n {abstract_div.text}' 
            prompt_text_created = True 
        except NoSuchElementException:
            logging.info("Abstract not found, clicking DOI link")
            try:
                doi_link_element = review_parent_element.find_element(By.XPATH, "./div[@class='source-info']/p[contains(@class, 'ref-ids')]/span/a")
                doi_link = doi_link_element.get_attribute("href")
                logging.info(f'Doi link {doi_link}')
                pdf_path = extract_abstract(doi_link)

                abstract_text = pdf_to_text(pdf_path)
                summary = summarize_abstract(abstract_text)
                
                logging.info(f'summary {summary}')
                promt_text = f'title:\n {title_text}\nabstract:\n {summary}'

                prompt_text_created = True

            except NoSuchElementException:
                logging.info("DOI link not found, skipping to next item")

        if prompt_text_created:
            answer = gmat(promt_text)
            waitingtime = random.uniform(30,70)
            time.sleep(waitingtime)
            logging.info(f"waitingtime '{waitingtime}' button")

            if answer.lower() == 'exclude':
                yes_no_button = driver.find_element(By.XPATH, "//button[@class='button vote-option primary' and @value='No']")
                yesnoinfo = 'No'
            elif answer.lower() == 'include':
                yes_no_button = driver.find_element(By.XPATH, "//button[@class='button vote-option primary' and @value='Yes']")
                yesnoinfo = 'Yes'
            else:
                yes_no_button = driver.find_element(By.XPATH, "//button[@class='button vote-option primary' and @value='Maybe']")
                yesnoinfo = 'Maybe'
            yes_no_button.click()
            logging.info(f"Clicked '{yesnoinfo}' button")
            

        else:
            logging.info("Skipping to next item as neither abstract nor DOI link was found")

            waitingtime = random.uniform(3,7)
            time.sleep(waitingtime)
            logging.info(f"waitingtime '{waitingtime}' button")
            yes_no_button = driver.find_element(By.XPATH, "//button[@class='button vote-option primary' and @value='No']")
            yesnoinfo = 'No'
            yes_no_button.click()
            logging.info(f"Clicked '{yesnoinfo}' button")


        time.sleep(random.uniform(5,10))
except NoSuchElementException:
    logging.error("Sign-in failed or element not found")

finally:
    logging.info("Closing the browser")
    driver.quit()