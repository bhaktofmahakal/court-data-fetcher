#!/usr/bin/env python3
"""
CAPTCHA Debug Tool - Analyze Delhi High Court CAPTCHA system
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def debug_captcha_system():
    """Debug the CAPTCHA system on Delhi High Court website"""
    
    chrome_options = Options()
  
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
    except Exception:
        driver = webdriver.Chrome(options=chrome_options)
    
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    try:
        print("CAPTCHA Debug Analysis - Delhi High Court")
        print("=" * 60)
        
        #  search page
        url = "https://delhihighcourt.nic.in/app/get-case-type-status"
        print(f" Navigating to: {url}")
        driver.get(url)
        time.sleep(3)
        
        # Wait for page to load
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "select"))
        )
        
        print("Page loaded successfully")
        print(f" Page title: {driver.title}")
        print(f"Current URL: {driver.current_url}")
        
        # Analyze CAPTCHA elements
        print("\nCAPTCHA Element Analysis:")
        # ------------------------------------------------
        print("-" * 40)
        
        try:
           
            captcha_code_element = driver.find_element(By.ID, "captcha-code")
            displayed_captcha = captcha_code_element.text.strip()
            print(f"captcha-code span text: '{displayed_captcha}'")
            print(f"captcha-code element visible: {captcha_code_element.is_displayed()}")
            
            
            randomid_element = driver.find_element(By.ID, "randomid")
            randomid_value = randomid_element.get_attribute("value")
            print(f"randomid hidden value: '{randomid_value}'")
            
           
            if displayed_captcha == randomid_value:
                print("CAPTCHA code and randomid MATCH")
            else:
                print("CAPTCHA code and randomid DO NOT MATCH")
            
            # Check captcha input field
            captcha_input = driver.find_element(By.ID, "captchaInput")
            print(f"captchaInput field found: {captcha_input.is_displayed()}")
            
            # Check for image CAPTCHA
            try:
                captcha_image = driver.find_element(By.ID, "captcha-image")
                print(f"captcha-image found: {captcha_image.get_attribute('src')}")
            except:
                print("No captcha-image element found")
            
        except Exception as e:
            print(f"Error analyzing CAPTCHA elements: {e}")
        
        # Fill form with test data
        print("\nFilling Form with Test Data:")
        print("-" * 40)
        
        try:
            # Case Type
            case_type_dropdown = driver.find_element(By.ID, "case_type")
            case_type_select = Select(case_type_dropdown)
            case_type_select.select_by_value("CRL.A.")
            print(" Case Type: CRL.A.")
            
            # Case Number
            case_number_input = driver.find_element(By.ID, "case_number")
            case_number_input.clear()
            case_number_input.send_keys("1234")
            print(" Case Number: 1234")
            
            # Case Year
            case_year_dropdown = driver.find_element(By.ID, "case_year")
            case_year_select = Select(case_year_dropdown)
            case_year_select.select_by_value("2024")
            print("Case Year: 2024")
            
            # CAPTCHA - use displayed value
            captcha_input = driver.find_element(By.ID, "captchaInput")
            captcha_input.clear()
            captcha_input.send_keys(displayed_captcha)
            print(f"CAPTCHA Input: {displayed_captcha}")
            
        except Exception as e:
            print(f"Error filling form: {e}")
            return
        
        # Test CAPTCHA validation
        print("\nTesting CAPTCHA Validation:")
        print("-" * 40)
        
        print("Clicking search button...")
        submit_button = driver.find_element(By.ID, "search")
        submit_button.click()
        
        # Wait and observe
        print("Waiting for AJAX response...")
        time.sleep(5)
        
        # Check for SweetAlert
        try:
            swal_elements = driver.find_elements(By.CSS_SELECTOR, ".swal2-popup, .swal2-modal, .swal2-container")
            if swal_elements:
                for swal in swal_elements:
                    if swal.is_displayed():
                        swal_text = swal.text
                        print(f" SweetAlert detected: '{swal_text}'")
                        
                        if "incorrect" in swal_text.lower():
                            print(" CAPTCHA validation FAILED")
                        else:
                            print("CAPTCHA validation SUCCESS")
            else:
                print("ℹNo SweetAlert detected")
        except Exception as e:
            print(f"Error checking SweetAlert: {e}")
        
        # Check DataTable
        try:
            case_table = driver.find_element(By.ID, "caseTable")
            tbody = case_table.find_element(By.TAG_NAME, "tbody")
            rows = tbody.find_elements(By.TAG_NAME, "tr")
            print(f"DataTable rows found: {len(rows)}")
            
            if len(rows) > 0:
                print("DataTable has data - CAPTCHA validation likely succeeded")
            else:
                print("ℹDataTable empty - could be no results or CAPTCHA failed")
                
        except Exception as e:
            print(f"Error checking DataTable: {e}")
        
        # Final page analysis
        print("\nFinal Page Analysis:")
        print("-" * 40)
        
        page_source = driver.page_source
        
        # Check for error indicators
        error_indicators = [
            "CAPTCHA is incorrect",
            "Please try again",
            "validation failed"
        ]
        
        for indicator in error_indicators:
            if indicator.lower() in page_source.lower():
                print(f"Found error indicator: '{indicator}'")
        
        print(f"Page source length: {len(page_source)} characters")
        print(f"Contains 'caseTable': {'caseTable' in page_source}")
        print(f"Contains 'swal2': {'swal2' in page_source}")
        
        # Keep browser open for manual inspection
        print("\nBrowser kept open for manual inspection...")
        print("Press Enter to close...")
        input()
        
    except Exception as e:
        print(f"Error during debug: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        driver.quit()
        print("Debug session completed")

if __name__ == "__main__":
    debug_captcha_system()