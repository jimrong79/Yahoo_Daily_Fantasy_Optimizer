from selenium import webdriver
from selenium.webdriver.common.by import By

import sqlite3
import getpass
import os

DB_PATH = "credentials.db"

def get_credentials():
    # Check if database exists and read credentials
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS credentials (id INTEGER PRIMARY KEY, username TEXT, password TEXT)")
    cursor.execute("SELECT username, password FROM credentials LIMIT 1")
    row = cursor.fetchone()

    if row:
        username, password = row
        conn.close()
        return username, password
    else:
        conn.close()
        return None, None

def store_credentials(username, password):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # Clear old credentials if any
    cursor.execute("DELETE FROM credentials")
    cursor.execute("INSERT INTO credentials (username, password) VALUES (?,?)", (username, password))
    conn.commit()
    conn.close()

def prompt_for_credentials():
    username = input("Enter your DraftKings user ID: ")
    password = getpass.getpass("Enter your DraftKings password: ")
    return username, password

def login_to_draftkings(username, password):
    """
    Finds the first DraftKings contest's contest_id and draft_group_id from the lobby using Selenium.

    Returns:
        dict: A dictionary containing the contest_id, draft_group_id, and constructed URLs.
    """
    url = "https://www.draftkings.com/lobby#/NBA/0/All"

    # Initialize Selenium WebDriver
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")  # Run Chrome in headless mode
    driver = webdriver.Chrome(options=options)
    driver.get(url)

    try:
        # Navigate to the DraftKings registration page
        driver.get("https://myaccount.draftkings.com/login")

        email_field = driver.find_element(by= By.NAME, value="EmailOrUsername")
        password_field = driver.find_element(by= By.NAME, value="Password")
        # Interact with the fields
        email_field.send_keys(username)
        password_field.send_keys(password)
        print("Successfully interacted with the registration fields.")
        return True

    except Exception as e:
        print(f"Error: {e}")
        # print(driver.page_source)  # Debug if needed
        return False
    finally:
        driver.quit()

def main():
    username, password = get_credentials()

    if username is None or password is None:
        # Prompt the user
        username, password = prompt_for_credentials()

        # Attempt login
        if login_to_draftkings(username, password):
            # Store credentials after successful login
            store_credentials(username, password)
            print("Credentials stored successfully.")
        else:
            print("Login failed. Credentials not stored.")
            return
    else:
        # We have credentials; proceed to login
        if login_to_draftkings(username, password):
            print("Login successful using stored credentials.")
        else:
            print("Stored credentials are invalid. Please re-enter.")
            # If desired, prompt again and update credentials
            username, password = prompt_for_credentials()
            if login_to_draftkings(username, password):
                store_credentials(username, password)
                print("Credentials updated successfully.")
            else:
                print("Login failed again.")

if __name__ == "__main__":
    # Set restrictive permissions on the DB file (if on a Unix-like system)
    if not os.path.exists(DB_PATH):
        open(DB_PATH, 'w').close()
    os.chmod(DB_PATH, 0o600)
    
    main()
