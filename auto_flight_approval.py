#!/usr/bin/env python3

### next time mechanical soup

from Flights import *
from __credentials import *


URL_LOGIN = "https://www.xcontest.org/"
#URL_APPROVAL = "https://www.xcontest.org/flyforfuncup/approval/flights/"
URL_APPROVAL = "https://www.xcontest.org/flyforfuncup/approval/flights/?filter%5Bstatus%5D=W&filter%5Bscored%5D=&filter%5B"+ \
    "date%5D=&filter%5Bcountry%5D=&filter%5Bcatg%5D=&filter%5Bpilot%5D=&list%5Bsort%5D=pts&list%5Bdir%5D=down&filter%5Bviolation%5D=&filter%5Bairspace%5D="

AIR_SPACE_CHECKER = "run.sh"

DL_DIR = "flights/"
chrome_driver_path = './chromedriver'

# for years < current_year use 'https://www.xcontest.org/YEAR/world/en/flights/'

if __name__ == '__main__' and __package__ is None:
    import os
    __LEVEL = 1
    os.sys.path.append(os.path.abspath(os.path.join(*([os.path.dirname(__file__)] + ['..']*__LEVEL))))

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as ec
from selenium.common.exceptions import TimeoutException

import glob
import os
import subprocess
import time

from tqdm import tqdm

from bs4 import BeautifulSoup
import datetime as dt
import argparse

import string

chrome_options = Options()
chrome_options.headless = True
service = Service(chrome_driver_path)

prefs = {"download.default_directory" : DL_DIR}
chrome_options.add_experimental_option("prefs",prefs)

driver = webdriver.Chrome(service=service, options=chrome_options)

def scrap_approval_flight(args, url):
    """ SCRAP XContest approval for flights """
    flights = []
    driver.set_page_load_timeout(30)

    '''Since this is an ADMIN only page, we need to be logged in'''
    login(driver)

    scrapping = True


    ''' FLIGHT TR FOR SINGLE FLIGHT FOR APPROVAL
    <tr id="flight-3081471" class="  ">
    00 flight nr / edit link  <td title="FLID:3081471"><a href="/flyforfuncup/approval/flights/edit:3081471">1</a></td>
    01 flug datum startzeit <td title="übertragen: 30.04. 037:21 UTC"><div class="full">30.04.22 <em>09:11</em><span class="XCutcOffset">UTC+02:00</span></div></td>
    02 pilot info name / link to profile <td><a class="plt1" href="/flyforfuncup/piloten/detail:almo">al mo</a></td>
    03 Startplatz / link zum SP <td><div class="full"><span class="cic" style="background-image:url(https://s.xcontest.org/img/flag/at.gif)" title="Austria">AT</span><a class="lau" href="/world/de/flugsuche/?filter[point]=13.109665 47.803172&amp;list[sort]=pts&amp;list[dir]=down">Gaisberg SW</a> <span class="lau" style="color:green" title="registered takeoff">✔</span></div></td>
    04 Flugtyp (freie Strecke / flaches Dreieck / FAI Dreieck) <td><div class="disc-vp" title="freie Strecke"><em class="hide">VP</em></div></td>
    05 Länge km <td class="km"><strong>4.35</strong> km</td>
    06 Punkte <td class="pts"><strong>4.35</strong> P.</td>
    07 Schirm <td class="cat-A"><div title="GIN GLIDERS Explorer" class="sponsor gin"><span class="hide">A</span></div></td>
    08 flight submitted at <td>30.04. <em>07:21</em></td>
    09 flug info link <td><div><a class="detail" title="Flugdaten" href="/flyforfuncup/fluge/detail:almo/30.4.2022/07:11"><span class="hide">Flugdaten</span></a></div></td>
    10 airspace violation / flight approved / pilot approved <td><img class="warning with-info" src="/img/warning.gif" width="16" height="16"><div class="violations" style="display: none;"><div class="schranka"><div class="violation"><ul><li><strong>airspaceName:</strong> CTR/TRA GAISBERG/SCHWARZENBERG A [0ft AGL - 5000ft AMSL]</li><li><strong>airspaceTimes:</strong> 09:11:01 - 09:20:29 [00:09:28]</li><li><strong>airspaceMaxViolation:</strong> 762 m</li></ul></div></div></div>
            <strong class="flight-status" title="flight was not yet approved/disapproved">f?</strong>
            <strong class="flight-status approved" title="pilot is approved">p.OK</strong>
        </td>
    11 IGC File Link <td><a title="tracklog ke stažení ve formátu IGC" href="/track.php?t=1651303260.69_626ce35ca9980.igc">IGC</a></td>
    12 APPROVE URL <td><a onclick="return (confirm('Are you sure you want to APPROVE this flight?') ? (Page.validationPrompt('You can add comment if you want:', this) ? true : true) : false)" class="activate" title="Flug akzeptieren" href="/flyforfuncup/approval/flights/?action=A&amp;flight=3081471"><span class="hide">Flug akzeptieren</span></a></td>
    13 DISAPPROVE URL <td><a onclick="return (confirm('Are you sure you want to DISAPPROVE this flight?') ? (Page.validationPrompt('You can add comment if you want:', this) ? true : true) : false)" class="deactivate" title="Flug zurückweisen" href="/flyforfuncup/approval/flights/?action=D&amp;flight=3081471"><span class="hide">Flug zurückweisen</span></a></td>
    14 scored info <td><strong title="flights is a part of score">scored</strong></td>
    </tr>
    '''

    while scrapping:
        wait = WebDriverWait(driver, 30)
        driver.get(url)

        wait.until(ec.element_to_be_clickable((By.CLASS_NAME, 'flights')))
        content = driver.page_source
        soup = BeautifulSoup(content, "lxml")

        flight_list = soup.find('table', {"class": "flights wide"}).find('tbody').find_all('tr')

        for flight in flight_list:
            flight_info = []
            flight_link = []
            tds = flight.find_all('td')
            assert(len(tds) == 15)

            flight_nr = tds[0].text
            link_flight_edit = tds[0].find('a').get('href') if tds[0].find('a') is not None else None

            start_date_time = tds[1].text

            pilot_name = tds[2].text
            link_pilot_profile = tds[2].find('a').get('href') if tds[2].find('a') is not None else None

            launch_site = tds[3].text
            flight_type = tds[4].text
            flight_km = tds[5].text
            flight_points = tds[6].text
            glider = tds[7].text
            flight_submitted = tds[8].text
            link_flight_info = tds[9].find('a').get('href') if tds[9].find('a') is not None else None
            airspace_info = tds[10].text
            pilot_approved = tds[10].find('strong', attrs={'class': 'flight-status approved'}).text
            link_flight_igc = tds[11].find('a').get('href') if tds[11].find('a') is not None else None
            link_approval = tds[12].find('a').get('href') if tds[12].find('a') is not None else None
            link_disapproval = tds[13].find('a').get('href') if tds[13].find('a') is not None else None
            flight_scored_info = tds[14].text

            flight_km = float(flight_km.split(' ')[0])
            flight_points = float(flight_points.split(' ')[0])

            fligth_dict = {
                'flight_nr': flight_nr,
                'link_flight_edit': link_flight_edit,
                'start_date': start_date_time,
                'pilot_name': pilot_name,
                'link_pilot_profile': link_pilot_profile,
                'launch_site': launch_site,
                'type': flight_type,
                'km': flight_km,
                'points': flight_points,
                'glider': glider,
                'date_submitted': flight_submitted,
                'link_flight_info': link_flight_info,
                'airspace_info': airspace_info,
                'pilot_approved': pilot_approved,
                'link_flight_igc': link_flight_igc,
                'link_approval': link_approval,
                'link_disapproval': link_disapproval,
                'flight_scored_info': flight_scored_info,
                'airspace_violation': False,
            }

            flights.append(Flight(**fligth_dict))
            for key in fligth_dict:
                print(f"{key} \t {fligth_dict[key]}")
            scrapping = False
            return flights

            break

        next_page = soup.find('a', {"title": "next page"})
        if type(next_page) is not type(None):
            next_page_url = next_page['href']
            from_flight_old = url.split('=')[-1]
            from_flight_new = next_page_url.split('=')[-1]

            scrapping = (from_flight_old is not from_flight_new)
            url = next_page_url
        else:
            scrapping = False

        if len(flights) >= args.num_flights and args.num_flights != 0:
            scrapping = False

    return flights


def login(driver):
    wait = WebDriverWait(driver, 30)
    driver.get(URL_LOGIN)
    wait.until(ec.element_to_be_clickable((By.CLASS_NAME, 'submit')))

    username_field = driver.find_element(by=By.ID, value="login-username")
    password_field = driver.find_element(by=By.ID, value="login-password")
    login = driver.find_element(by=By.CLASS_NAME, value="submit")

    username_field.send_keys(username)
    password_field.send_keys(password)
    login.click()


def download_igc(args, flight:Flight)->str:
    dl_file_name = ""
    wait = WebDriverWait(driver, 30)
    flight_url = "https://www.xcontest.org" + flight.link_flight_info
    retry = 2
    while(retry > 0):
        try:
            if args.verbose:
                print(flight_url)
            driver.get(flight_url)
            wait.until(ec.element_to_be_clickable((By.CLASS_NAME, 'igc')))
            igc = driver.find_element(by=By.CLASS_NAME, value="igc")
            href = igc.find_element(by=By.TAG_NAME, value="a")

            if args.verbose:
                print(f"downloading {href.get_attribute('href')}")

            href.click()

            retry_2 = 2
            while not dl_file_name.lower().endswith('.igc') and retry_2 > 0:
                time.sleep(0.8)
                list_of_files = glob.glob(os.path.join(DL_DIR,'*')) # * means all if need specific format then *.csv
                list_of_files = [f for f in list_of_files if '*' not in f]
                dl_file_name = max(list_of_files, key=os.path.getctime)
                retry_2 -= 1

            retry = 0
        except TimeoutException as ex:
            print(f"Error downloading flight at {flight.flight_link}")
            retry-=1
            pass

    return dl_file_name

        
# def download_igc(args, flights):
#     wait = WebDriverWait(driver, 30)
#     for idx, flight in enumerate(flights):
#         flight_url = flight['link_flight_igc'] #f"https://www.xcontest.org{flight.flight_link}" if "xcontest.org" not in flight.flight_link else flight.flight_link
#         retry = 2
#         while(retry > 0):
#             try:
#                 print(flight_url)
#                 driver.get(flight_url)
#                 wait.until(ec.element_to_be_clickable((By.CLASS_NAME, 'igc')))
#                 igc = driver.find_element(by=By.CLASS_NAME, value="igc")
#                 href = igc.find_element(by=By.TAG_NAME, value="a")

#                 if args.verbose:
#                     print(f"downloading {href.get_attribute('href')}")

#                 href.click()

#                 time.sleep(0.5)
#                 list_of_files = glob.glob(os.path.join(DL_DIR,'*')) # * means all if need specific format then *.csv
#                 list_of_files = [f for f in list_of_files if '*' not in f]
#                 if list_of_files:
#                     dl_file_name = max(list_of_files, key=os.path.getctime)
#                     igc_file_name = flight.pilot + "-" + flight.glider + "-" + dl_file_name.split('/')[-1]
#                     #asciidata = str(igc_file_name.encode('ascii', 'replace'))

#                     if args.numbers_to_file:
#                         igc_file_name = f"{idx:02d}-{igc_file_name}"

#                     os.rename(dl_file_name, os.path.join(DL_DIR,igc_file_name))
#                     time.sleep(0.5)
#                 retry = 0
#             except TimeoutException as ex:
#                 print(f"Error downloading flight at {flight.flight_link}")
#                 retry-=1
#                 pass


def validte_flight(args,igc_file_name:str)->bool:
    result = subprocess.run([AIR_SPACE_CHECKER, igc_file_name], stdout=subprocess.PIPE)
    verdict = str(result.stdout)
    os.remove(igc_file_name)
    if '=> OK' in verdict:
        '''flight OK'''
        os.remove(igc_file_name + '.kml')
        return True
    else:
        print(verdict)
        '''prep mail containing kml file'''
        kml_file_for_mail = igc_file_name + '.kml'
        return False


def main():
    flights = []
    current_year = dt.datetime.now().year

    parser = argparse.ArgumentParser(description='XContest FlyForFun Automatic Flight Approval')
    parser.add_argument('--verbose', action="store_true", default=False, help='print debug information')
    parser.add_argument('--num-flights', type=int, default=5, help='number of flights to scrap (default: 5, 0 for all')

    args = parser.parse_args()

    # flight scrapping
    flights = scrap_approval_flight(args,URL_APPROVAL)

    if args.verbose:
        for flight in flights:
            print(f"{flight.get_flyforfun_points():.2f},{flight}")

    for flight in flights:
        igc_file_name = download_igc(args,flight)
        if validte_flight(args,igc_file_name):
            print('TODO: click approve')
        else:
            print('TODL: click disapprove and send mail with explaination')

    driver.close()



if __name__ == '__main__':
    main()
