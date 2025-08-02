from flask import Flask, render_template, request, jsonify, send_file
import sqlite3
import requests
from bs4 import BeautifulSoup
import os
from datetime import datetime
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.keys import Keys
import time
import re
from urllib.parse import urljoin

app = Flask(__name__)

# logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database 
def init_db():

    """Initialize SQLite database"""

    os.makedirs('db', exist_ok=True)
    
    conn = sqlite3.connect('db/queries.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS queries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_type TEXT,
            case_number TEXT,
            case_year TEXT,
            query_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            raw_response TEXT,
            parties TEXT,
            filing_date TEXT,
            next_hearing_date TEXT,
            order_judgment_link TEXT,
            status TEXT
        )
    ''')
    
    conn.commit()
    conn.close()

class CourtDataScraper:
    def __init__(self):
        self.base_url = "https://delhihighcourt.nic.in"
        self.search_url = f"{self.base_url}/app/get-case-type-status"
        
    def setup_driver(self):
        """Setup Chrome driver with options"""

        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        try:
            # use ChromeDriverManager first
            try:
                service = Service(ChromeDriverManager().install())
                driver = webdriver.Chrome(service=service, options=chrome_options)
            except Exception:
                # Fallback to system ChromeDriver
                driver = webdriver.Chrome(options=chrome_options)
            
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            return driver
        except Exception as e:
            logger.error(f"Failed to setup Chrome driver: {e}")
            logger.info("Please ensure Chrome browser and ChromeDriver are installede")
            return None
    
    def scrape_case_data(self, case_type, case_number, case_year, captcha_token=None):
        """Scrape court case data"""

        driver = self.setup_driver()
        if not driver:
            return {"error": "Failed to initialize browser driver"}
        
        try:
            # search page
            driver.get(self.search_url)
            time.sleep(1)  
            
          
            WebDriverWait(driver, 8).until(  
                EC.presence_of_element_located((By.ID, "case_type"))
            )
            
            # Fill the form 
            try:
                
                case_type_dropdown = WebDriverWait(driver, 6).until(  
                    EC.element_to_be_clickable((By.ID, "case_type"))
                )
                case_type_select = Select(case_type_dropdown)
                case_type_select.select_by_value(case_type)
                
               
                case_number_input = WebDriverWait(driver, 6).until( 
                    EC.element_to_be_clickable((By.ID, "case_number"))
                )
                case_number_input.clear()
                case_number_input.send_keys(case_number)
                
               
                case_year_dropdown = WebDriverWait(driver, 6).until(  
                    EC.element_to_be_clickable((By.ID, "case_year"))
                )
                case_year_select = Select(case_year_dropdown)
                case_year_select.select_by_value(case_year)
                
                # Handle CAPTCHA - CRITICAL: Delhi High Court uses AJAX-based CAPTCHA validation
                try:
                    # Wait for CAPTCHA elements to load
                    WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.ID, "captchaInput"))
                    )
                    
                    # Get  CAPTCHA code 
                    captcha_code_element = driver.find_element(By.ID, "captcha-code")
                    displayed_captcha = captcha_code_element.text.strip()
                    logger.info(f"CAPTCHA code displayed on page: {displayed_captcha}")
                    
                    # Get the hidden randomid value ( the actual CAPTCHA validation key)

                    randomid_element = driver.find_element(By.ID, "randomid")
                    randomid_value = randomid_element.get_attribute("value")
                    logger.info(f"Hidden randomid value: {randomid_value}")
                    
                    captcha_input = driver.find_element(By.ID, "captchaInput")
                    captcha_input.clear()
                    
                    # CRITICAL: The court website validatess CAPTCHA via AJAX call to /app/validateCaptcha
                    # The displayed captcha-code and randomid must match for validation to succeed
                    
                    if captcha_token:
                        #  provided manual CAPTCHA
                        captcha_input.send_keys(captcha_token)
                        logger.info(f"Using provided CAPTCHA token: {captcha_token}")

                    else:
                        # Use the displayed CAPTCHA code (for text-based CAPTCHA)

                        if displayed_captcha and displayed_captcha.isdigit():
                            captcha_input.send_keys(displayed_captcha)
                            logger.info(f"Using displayed text CAPTCHA: {displayed_captcha}")
                        else:
                            logger.warning("No CAPTCHA token provided and displayed CAPTCHA is not readable")
                            return {
                                "error": "CAPTCHA is required. Please provide the CAPTCHA token manually from the court website.",
                                "status": "CAPTCHA Required",
                                "displayed_captcha": displayed_captcha,
                                "randomid": randomid_value
                            }
                        
                except Exception as captcha_error:
                    logger.warning(f"CAPTCHA handling failed: {captcha_error}")
                    return {
                        "error": f"CAPTCHA is required but could not be handled: {str(captcha_error)}",
                        "status": "CAPTCHA Required"
                    }
                
                # Submit 
                submitted = False
                
                try:
                    
                    submit_button = WebDriverWait(driver, 10).until(
                        EC.element_to_be_clickable((By.ID, "search"))
                    )
                    submit_button.click()
                    submitted = True
                    logger.info("Search button clicked - triggering CAPTCHA validation via AJAX")
                    
                   
                    time.sleep(1.5)  
                    
                    # Check for CAPTCHA error messages
                    try:
                        swal_error = driver.find_elements(By.CSS_SELECTOR, ".swal2-popup, .swal2-modal")
                        if swal_error and swal_error[0].is_displayed():
                            error_text = swal_error[0].text
                            logger.info(f"SweetAlert detected: {error_text}")
                            if "CAPTCHA is incorrect" in error_text or "incorrect" in error_text.lower():
                                return {
                                    "error": "CAPTCHA verification failed. The CAPTCHA code was incorrect.",
                                    "status": "CAPTCHA Failed",
                                    "details": error_text
                                }
                    except:
                        pass
                    
                    # Wait for DataTable to load results 
                    try:
                        WebDriverWait(driver, 8).until(  
                            lambda driver: driver.execute_script("return jQuery.active == 0")
                        )
                        logger.info("AJAX calls completed - DataTable loaded")
                    except:
                        logger.info("jQuery timeout - continuing with current page state")
                    
                    # Minimal wait for DOM updates
                    time.sleep(1)  
                    
                except Exception as e:
                    logger.error(f"Error during search button click: {e}")

                    # Fallback 
                    try:
                        case_number_input.send_keys(Keys.RETURN)
                        submitted = True
                        logger.info("Form submitted via Enter key (fallback)")
                    except:
                        pass
                
                if not submitted:
                    logger.warning("Could not submit form - but data was filled successfully")
                        
            except Exception as form_error:
                logger.error(f"Form filling error: {form_error}")
                return {"error": f"Could not fill form: {str(form_error)}", "status": "Error"}
            
            # Wait for results to load after CAPTCHA validation and DataTable refresh
            time.sleep(3)
            
            # Get page source 
            page_source = driver.page_source
            logger.info(f"Page title: {driver.title}")
            logger.info(f"Current URL: {driver.current_url}")
            
            # Parse the results
            soup = BeautifulSoup(page_source, 'html.parser')
            
           
            captcha_failed = False
            
            try:
                
                swal_elements = driver.find_elements(By.CSS_SELECTOR, ".swal2-popup, .swal2-modal")
                for swal in swal_elements:
                    if swal.is_displayed():
                        swal_text = swal.text.lower()
                        if "captcha is incorrect" in swal_text or "incorrect" in swal_text:
                            captcha_failed = True
                            logger.warning(f"Active SweetAlert CAPTCHA error detected: {swal.text}")
                            break
                        
                if not captcha_failed:
                    logger.info("No active CAPTCHA error alerts found")
                    
            except Exception as e:
                logger.info(f"Could not check SweetAlert elements: {e}")
            
            # If CAPTCHA failed, return error
            if captcha_failed:
                return {
                    "error": f"CAPTCHA verification failed. The CAPTCHA code was incorrect. Please get a fresh CAPTCHA from the court website and try again.",
                    "status": "CAPTCHA Failed",
                    "raw_response": page_source[:1500]
                }
            
            # Check for validation errors 
            if 'field is required' in page_source.lower():
                logger.warning("Form validation error detected in page source")

                # Check if this is actually an active error or just static text
                validation_errors = []
                if 'case type.*required' in page_source.lower():
                    validation_errors.append("Case Type")
                if 'case number.*required' in page_source.lower():
                    validation_errors.append("Case Number")
                if 'year.*required' in page_source.lower():
                    validation_errors.append("Year")
                
                if validation_errors:
                    return {
                        "error": f"Form validation failed. Missing fields: {', '.join(validation_errors)}",
                        "status": "Validation Error",
                        "raw_response": page_source[:1000]
                    }
                else:
                    logger.info("Validation error text found but seems to be static - continuing")
            
            #Parse case data from DataTable
            case_data = self.parse_case_data(soup)
            case_data['raw_response'] = page_source
            
            #search parameters to response for frontend display
            case_data['case_type'] = case_type
            case_data['case_number'] = case_number
            case_data['case_year'] = case_year
            
            # no data found
            if case_data['status'] == 'Not Found':
                case_data['error'] = "No case found with the provided details. This could be due to: 1) Case doesn't exist in court records, 2) CAPTCHA validation failed, 3) Case is in different category"
            
            return case_data
            
        except Exception as e:
            logger.error(f"Error scraping case data: {e}")
            return {"error": str(e)}
        finally:
            driver.quit()
    
    def parse_case_data(self, soup):
        """Parse case data from HTML - Updated for Delhi High Court structure"""

        case_data = {
            "parties": "",
            "filing_date": "",
            "next_hearing_date": "",
            "order_judgment_link": "",
            "status": "Not Found"
        }
        
        try:
            # Look for the specific case table
            case_table = soup.find('table', {'id': 'caseTable'})
            
            if case_table:
                logger.info("Found caseTable in HTML")
                tbody = case_table.find('tbody')
                
                if tbody:
                    rows = tbody.find_all('tr')
                    logger.info(f"Found {len(rows)} data rows in caseTable")
                    
                    for row in rows:
                        cells = row.find_all('td')
                        if len(cells) >= 4:
                
                            
                            case_number_cell = cells[1].get_text(strip=True)
                            parties_cell = cells[2].get_text(strip=True)
                            listing_date_cell = cells[3].get_text(strip=True)
                            
                            if case_number_cell and parties_cell:
                                case_data['parties'] = parties_cell
                                case_data['next_hearing_date'] = listing_date_cell
                                case_data['status'] = "Found"
                                logger.info(f"Found case data: {case_number_cell} - {parties_cell}")
                                
                                # Look for order/judgment 
                                for cell in cells:
                                    links = cell.find_all('a')
                                    for link in links:
                                        href = link.get('href')
                                        link_text = link.get_text(strip=True).lower()
                                        
                                        # Check for order/judgment links
                                        if href and (
                                            '.pdf' in href.lower() or 
                                            'order' in href.lower() or 
                                            'judgment' in href.lower() or
                                            'case-type-status-details' in href or
                                            'orders' in link_text or
                                            'view' in link_text
                                        ):
                                            # for full URL
                                            if href.startswith('http'):
                                                case_data['order_judgment_link'] = href
                                            else:
                                                case_data['order_judgment_link'] = urljoin(self.base_url, href)
                                            logger.info(f"Found order/judgment link: {case_data['order_judgment_link']}")
                                            break
                                
                                # Extract case status 
                                if '[' in case_number_cell and ']' in case_number_cell:
                                    status_match = case_number_cell.split('[')[-1].split(']')[0]
                                    case_data['case_status'] = status_match.upper()
                                    logger.info(f"Extracted case status: {status_match}")
                                else:
                                    case_data['case_status'] = "ACTIVE"
                                break
                else:
                    logger.info("caseTable found but tbody is empty - no results")
            else:
                logger.info("caseTable not found in HTML")
            
            # Fallback
            if case_data['status'] == "Not Found":
                tables = soup.find_all('table')
                
                for table in tables:
                    rows = table.find_all('tr')
                    for row in rows:
                        cells = row.find_all(['td', 'th'])
                        if len(cells) >= 2:
                            header = cells[0].get_text(strip=True).lower()
                            value = cells[1].get_text(strip=True)
                            
                            if 'petitioner' in header or 'respondent' in header:
                                case_data['parties'] = value
                            elif 'filing' in header or 'registration' in header:
                                case_data['filing_date'] = value
                            elif 'listing' in header or 'hearing' in header:
                                case_data['next_hearing_date'] = value
                            elif 'order' in header or 'judgment' in header:
                                #  links

                                links = cells[1].find_all('a')
                                for link in links:
                                    href = link.get('href')
                                    if href and '.pdf' in href.lower():
                                        case_data['order_judgment_link'] = urljoin(self.base_url, href)
                                        break
                
                if case_data['parties']:
                    case_data['status'] = "Found"
                    
        except Exception as e:
            logger.error(f"Error parsing case data: {e}")
            case_data['error'] = str(e)
        
        return case_data

def save_query_to_db(case_type, case_number, case_year, case_data):
    """Save query and response to database"""

    conn = sqlite3.connect('db/queries.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO queries (case_type, case_number, case_year, raw_response, 
                           parties, filing_date, next_hearing_date, order_judgment_link, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        case_type, case_number, case_year, 
        case_data.get('raw_response', ''),
        case_data.get('parties', ''),
        case_data.get('filing_date', ''),
        case_data.get('next_hearing_date', ''),
        case_data.get('order_judgment_link', ''),
        case_data.get('status', 'Error')
    ))
    
    conn.commit()
    conn.close()

@app.route('/')
def index():
    """Main page with search form"""

    return render_template('index.html')

@app.route('/search', methods=['POST'])
def search_case():

    """Handle case search request"""

    try:
        case_type = request.form.get('case_type')
        case_number = request.form.get('case_number')
        case_year = request.form.get('case_year')
        captcha_token = request.form.get('captcha_token')
        
        logger.info(f"Search request: {case_type}, {case_number}, {case_year}")
        
        # Validatinge input

        if not all([case_type, case_number, case_year]):
            logger.warning("Missing required fields")
            return jsonify({"error": "All fields are required"})
        
        # Scrape case data

        scraper = CourtDataScraper()
        case_data = scraper.scrape_case_data(case_type, case_number, case_year, captcha_token)
        
        # Save to database

        save_query_to_db(case_type, case_number, case_year, case_data)
        
        logger.info(f"Search completed with status: {case_data.get('status', 'Unknown')}")
        return jsonify(case_data)
        
    except Exception as e:
        logger.error(f"Error in search_case: {e}", exc_info=True)
        return jsonify({"error": f"Server error: {str(e)}"}), 500

@app.route('/download_pdf')

def download_pdf():
    """Download PDF from court website"""

    pdf_url = request.args.get('url')
    if not pdf_url:
        return jsonify({"error": "PDF URL not provided"})
    
    try:
        response = requests.get(pdf_url)
        if response.status_code == 200:
            return send_file(
                response.content,
                as_attachment=True,
                download_name="court_order.pdf",
                mimetype="application/pdf"
            )
        else:
            return jsonify({"error": "Failed to download PDF"})
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/history')

def query_history():
    """Get query history"""

    conn = sqlite3.connect('db/queries.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT case_type, case_number, case_year, query_timestamp, status
        FROM queries 
        ORDER BY query_timestamp DESC 
        LIMIT 50
    ''')
    
    history = cursor.fetchall()
    conn.close()
    
    return jsonify([{
        "case_type": row[0],
        "case_number": row[1],
        "case_year": row[2],
        "timestamp": row[3],
        "status": row[4]
    } for row in history])

@app.errorhandler(404)

def not_found_error(error):
    """Handle 404 errors"""

    logger.warning(f"404 error: {request.url}")
    return jsonify({"error": "Resource not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""

    logger.error(f"500 error: {error}")
    return jsonify({"error": "Internal server error"}), 500

if __name__ == '__main__':

    init_db()
    logger.info("Starting Court Data Fetcher application...")
    app.run(debug=True, host='0.0.0.0', port=5000)