from urllib.request import urlopen
from bs4 import BeautifulSoup
import pandas as pd

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



url = "https://basketballmonster.com/DailyEaseRankings.aspx"
html = urlopen(url)
soup = BeautifulSoup(html,features="lxml")
