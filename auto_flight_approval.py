#!/usr/bin/env python3

from __credentials import *
from tools import *
from Mail import Mail

URL_LOGIN = "https://www.xcontest.org/"
#URL_APPROVAL = "https://www.xcontest.org/flyforfuncup/approval/flights/"
URL_APPROVAL = "https://www.xcontest.org/flyforfuncup/approval/flights/?filter%5Bstatus%5D=W&filter%5Bscored%5D=&filter%5B"+ \
    "date%5D=&filter%5Bcountry%5D=&filter%5Bcatg%5D=&filter%5Bpilot%5D=&list%5Bsort%5D=pts&list%5Bdir%5D=down&filter%5Bviolation%5D=&filter%5Bairspace%5D="

JAVA_CORRETTO = "/Library/Java/JavaVirtualMachines/amazon-corretto-8.jdk/Contents/Home/bin/java"
AIR_SPACE_CHECKER = "airspace-check.jar"

DL_DIR = "flights/"
CHROMEPATH = './chromedriver'
FIREFOXPATH = '/opt/homebrew/bin/geckodriver'


# for years < current_year use 'https://www.xcontest.org/YEAR/world/en/flights/'

if __name__ == '__main__' and __package__ is None:
    import os
    __LEVEL = 1
    os.sys.path.append(os.path.abspath(os.path.join(*([os.path.dirname(__file__)] + ['..']*__LEVEL))))

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as ec
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities


import glob
import os
import subprocess
import time
from typing import Tuple

from bs4 import BeautifulSoup
import argparse


def init_webdriver(headless:bool=True):
    """Simple Function to initialize and configure Webdriver"""
    if FIREFOXPATH != None:
        from selenium.webdriver.firefox.options import Options
        from selenium.webdriver.firefox.service import Service

        ABS_DL_DIR = os.path.join( os.getcwd(), DL_DIR)

        options = Options()
        options.binary = FIREFOXPATH
        if headless:
            options.add_argument("-headless")

        options.set_preference("browser.download.folderList", 2)
        options.set_preference("browser.download.manager.showWhenStarting", False)
        options.set_preference("browser.download.dir", ABS_DL_DIR)
        options.set_preference("browser.download.downloadDir", ABS_DL_DIR)
        options.set_preference("browser.download.defaultFolder", ABS_DL_DIR)
        options.set_preference("browser.helperApps.neverAsk.saveToDisk", "application/x-gzip")

        binary = r'/Applications/Firefox.app/Contents/MacOS/firefox'
        options.binary = binary
        DesiredCapabilities.FIREFOX["unexpectedAlertBehaviour"] = "accept"
        service = Service(FIREFOXPATH)
        return webdriver.Firefox(service=service, options=options)

    elif CHROMEPATH != None:
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service

        options = Options()
        options.binary_location = CHROMEPATH
        if headless:
            options.add_argument("--headless")
        prefs = {"download.default_directory" : DL_DIR}
        options.add_experimental_option("prefs",prefs)
        service = Service(CHROMEPATH)
        return webdriver.Chrome(service=service, options=options, service_args=['--verbose'])


def scrap_approval_flight(args, driver, url):
    """ SCRAP and approve/disapprove flights """
    flights_approved, flights_disapproved, flights_error, pilot_not_approved = [], [], [], []
    flight_dict = dict()
    driver.set_page_load_timeout(30)

    '''Since this is an ADMIN only page, we need to be logged in'''
    login(driver)

    wait = WebDriverWait(driver, 30)
    driver.get(url)

    wait.until(ec.element_to_be_clickable((By.CLASS_NAME, 'flights')))

    content = driver.page_source
    soup = BeautifulSoup(content, "lxml")
    flight_list = soup.find('table', {"class": "flights wide"}).find('tbody').find_all('tr')
    for flight in flight_list:
        tds = flight.find_all('td')
        assert(len(tds) == 15)
        flight_d = get_flight_from_soup(tds)
        flight_dict[flight_d['flight_id']] = flight_d

    idx = args.num_flights

    tables = driver.find_element(by=By.CLASS_NAME, value="flights")
    rows = tables.find_elements(by=By.TAG_NAME, value="tr")
    for row in rows:
        tds = row.find_elements(by=By.TAG_NAME, value="td")
        flight_id = [td for td in tds if 'FLID:' in td.get_attribute('title')]
        if flight_id:
            flight_id = flight_id[0]
            flight_id = flight_id.get_attribute('title').split(':')[-1]
        else:
            flight_id = None
            continue

        a_tags = row.find_elements(by=By.TAG_NAME, value="a")
        link_igc = [l for l in a_tags if 'IGC' in l.text.upper()]
        link_approval = [l for l in a_tags if 'action=A' in l.get_attribute('href')]
        link_disapproval = [l for l in a_tags if 'action=D' in l.get_attribute('href')]

        if link_igc and link_approval and link_disapproval and flight_id and flight_id in flight_dict:
            link_igc = link_igc[0]; link_approval = link_approval[0]; link_disapproval = link_disapproval[0]
            flight_infos = flight_dict[flight_id]

            if not flight_infos['pilot_approved']:
                pilot_not_approved.append(flight_infos)
            else:
                link_igc.click()

                igc_file_name = ""
                retry = 5
                while (not igc_file_name.lower().endswith('.igc') or '.part' in igc_file_name) and retry > 0:
                    time.sleep(0.8)
                    list_of_files = glob.glob(os.path.join(DL_DIR,'*')) # * means all if need specific format then *.csv
                    list_of_files = [f for f in list_of_files if '*' not in f]
                    if list_of_files:
                        igc_file_name = max(list_of_files, key=os.path.getctime)
                    retry -= 1
                print(igc_file_name)

                if os.path.isfile(igc_file_name):
                    verdict, detail, kml_file_name = validte_flight(igc_file_name)
                    print(f"{flight_infos['pilot_name']} glider {flight_infos['glider']} {flight_infos['points']} p. and {flight_infos['km']} km")
                    if verdict == 0 or verdict == 1:
                        flights_approved.append(flight_infos)
                        '''click the approval link'''
                        link_approval.click()

                        '''first popup to be sure to approve'''
                        try:
                            WebDriverWait(driver, 5).until (ec.alert_is_present())
                            alert = driver.switch_to.alert
                            alert.accept()
                        except TimeoutException:
                            if args.verbose:
                                print("1st alert does not exist")

                        '''second popup for comments'''
                        try:
                            WebDriverWait(driver, 5).until (ec.alert_is_present())
                            alert = driver.switch_to.alert
                            alert.accept()
                        except TimeoutException:
                            if args.verbose:
                                print("2nd alert does not exist")

                        if verdict == 1:
                            print(f'MAYBE-OK: look at {kml_file_name}, might be aigen/uberg LZ')
                    else:
                        '''SANITY CHECKS'''
                        if 'HG' in flight_infos['glider']:
                            print(f"VIOLATION: maybe new HG LZ -> check manually  {flight_infos['link_flight_info']}")
                        else:
                            '''check if a single data point is faulty'''
                            flights_disapproved.append(flight_infos)
                            print('VIOLATION: click disapprove and send mail with explaination', link_disapproval.get_attribute('href'), detail, kml_file_name)
                            mail = Mail(flight=flight_infos, kml_file_name=kml_file_name)
                else:
                    flights_error.append(flight_infos)
        else:
            continue

        idx -= 1
        if idx <= 0 and args.num_flights != 0:
            break

    return flights_approved, flights_disapproved, flights_error, pilot_not_approved


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

'''
0: all ok
1: maybe-violation
2: vioaltion
'''
def validte_flight(igc_file_name:str)->Tuple[int,str,str]:
    result = subprocess.run([JAVA_CORRETTO, '-jar', AIR_SPACE_CHECKER, igc_file_name], stdout=subprocess.PIPE)
    verdict = str(result.stdout.decode("utf-8"))
    os.remove(igc_file_name)
    if '=> OK' in verdict:
        '''flight OK'''
        os.remove(igc_file_name + '.kml')
        return (0,verdict,'')
    elif '=> VIOLATION' in verdict:
        '''prep mail containing kml file'''
        kml_file_for_mail = igc_file_name + '.kml'
        return (2,verdict,kml_file_for_mail)
    else:
        print('look into flight', verdict)
        '''prep mail containing kml file'''
        kml_file_for_mail = igc_file_name + '.kml'
        return (1,verdict,kml_file_for_mail)


def main():
    parser = argparse.ArgumentParser(description='XContest FlyForFun Automatic Flight Approval')
    parser.add_argument('--verbose', action="store_true", default=False, help='print debug information')
    parser.add_argument('--num-flights', type=int, default=5, help='numbers of flights to process in one run (default: 5, 0 for all')
    parser.add_argument('--non-headless', action="store_true", default=False, help='print debug information')
    args = parser.parse_args()

    driver = init_webdriver(headless=not args.non_headless)

    # flight scrapping
    app, dis, err, nonpilot = scrap_approval_flight(args=args, driver=driver,url=URL_APPROVAL)

    print(f"Approved {len(app)}, disapproved {len(dis)}, errors {len(err)}, pilot not approved {len(nonpilot)}")

    driver.close()


if __name__ == '__main__':
    main()
