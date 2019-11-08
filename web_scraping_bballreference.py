from urllib.request import urlopen
from bs4 import BeautifulSoup
import pandas as pd
import requests
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.select import Select


"""
# NBA season 
year = 2020
# Basketball Reference URL
url = "https://www.basketball-reference.com/leagues/NBA_{}_per_game.html".format(year)
#HTML from given URL
html = urlopen(url)

soup = BeautifulSoup(html,features="lxml")

headers = [th.getText() for th in soup.findAll('tr', limit = 1)[0].findAll('th')][1:]

rows = soup.findAll('tr')[1:]

players_stats = [[td.getText() for td in rows[i].findAll('td')] for i in range(len(rows))]

stats = pd.DataFrame(players_stats, columns = headers)
"""

"""
url = "https://basketballmonster.com/DailyEaseRankings.aspx"
html = urlopen(url)
soup = BeautifulSoup(html,features="lxml")
whole_table = soup.findAll('tr', limit = 2)[1]
headers = [th.getText() for th in whole_table.findAll('tr', limit = 1)[0].findAll('td')]
rows = whole_table.findAll('tr')[1:]
dvp_stats = [[td.getText() for td in rows[i].findAll('td')] for i in range(len(rows))]

for i in range(len(dvp_stats)):
    print(dvp_stats[i][0])
    dvp_stats[i][0] = dvp_stats[i][0].replace("vs", "")

dvp_stats_df = pd.DataFrame(dvp_stats, columns = headers)

print (dvp_stats_df.head(31))
"""

driver = webdriver.Chrome(r"C:\Users\jimro\AppData\Local\Programs\Python\Python37-32\Lib\site-packages\selenium\webdriver\chromedriver_win32\chromedriver.exe")

url = "https://basketballmonster.com/DailyEaseRankings.aspx"

driver.get(url)
element = WebDriverWait(driver, 10).until(
	    EC.presence_of_element_located((By.XPATH, "//select[@name='ctl00$ContentPlaceHolder1$PositionDropDownList']/option[@value='"+str(3)+"']"))
)

element.click()

WebDriverWait(driver, 3).until(
    EC.text_to_be_present_in_element(
        (By.XPATH, "//select[@name='ctl00$ContentPlaceHolder1$PositionDropDownList']/option[@selected='selected']"),
        'C'
    )
)

page = driver.page_source
soup = BeautifulSoup(page, 'html.parser')

whole_table = soup.findAll('tr', limit = 2)[1]
headers = [th.getText() for th in whole_table.findAll('tr', limit = 1)[0].findAll('td')]
rows = whole_table.findAll('tr')[1:]
dvp_stats = [[td.getText() for td in rows[i].findAll('td')] for i in range(len(rows))]

for i in range(len(dvp_stats)):
    dvp_stats[i][0] = dvp_stats[i][0].replace("vs", "")
    dvp_stats[i][0] = dvp_stats[i][0].strip()

dvp_stats_df = pd.DataFrame(dvp_stats, columns = headers)

print (dvp_stats_df.head(31))

driver.quit()

"""
with requests.Session() as session:

    session.headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/40.0.2214.115 Safari/537.36'}

    response = session.get(url)

    soup = BeautifulSoup(response.content)
    time.sleep(1)

    data = {
    	'ContentPlaceHolder1_PositionDropDownList': 2
    }

    response = session.post(url, data = data)

    soup = BeautifulSoup(response.content, features = "lxml")

    whole_table = soup.findAll('tr', limit = 2)[1]

    headers = [th.getText() for th in whole_table.findAll('tr', limit = 1)[0].findAll('td')]
    rows = whole_table.findAll('tr')[1:]
    dvp_stats = [[td.getText() for td in rows[i].findAll('td')] for i in range(len(rows))]
    for i in range(len(dvp_stats)):
        dvp_stats[i][0] = dvp_stats[i][0].replace("vs", "")

    dvp_stats_df = pd.DataFrame(dvp_stats, columns = headers)

    print (dvp_stats_df.head(31))

"""