#!/usr/bin/env python3

from ast import expr_context
import glob
import os
import subprocess
import time
from typing import Tuple
from bs4 import BeautifulSoup
import argparse
from time import sleep
import pandas as pd

import signal
import sys

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as ec
from selenium.common.exceptions import TimeoutException
from selenium.common.exceptions import StaleElementReferenceException

from __credentials import *
from config import *
from Scrapping import *
from Mail import Mail

if __name__ == '__main__' and __package__ is None:
    import os
    __LEVEL = 1
    os.sys.path.append(os.path.abspath(os.path.join(*([os.path.dirname(__file__)] + ['..']*__LEVEL))))


def get_downloaded_file()->str:
    igc_file_name = ""
    retry = 6
    while (not igc_file_name.lower().endswith('.igc') or '.part' in igc_file_name) and retry > 0:
        time.sleep(0.9)
        list_of_files = glob.glob(os.path.join(DL_DIR,'*')) # * means all if need specific format then *.csv
        list_of_files = [f for f in list_of_files if '*' not in f]
        if list_of_files:
            igc_file_name = max(list_of_files, key=os.path.getctime)
        retry -= 1
    return igc_file_name


def get_page_description(content)->str:
    page_description:str = None
    soup = BeautifulSoup(content, "lxml")
    element_info = soup.find_all("div", {"class": "XCmoreInfo"})
    if len(element_info) > 0:
        description = element_info[0].find_all("div", {"class": "wsw"})
        if len(description) > 0 and description[0]:
            page_description = description[0].text

    return page_description


def get_page_links(content)->list:
    page_link_urls = []
    soup = BeautifulSoup(content, "lxml")
    element_paging = soup.find_all("div", {"class": "paging"})
    if len(element_paging) > 0:
        page_links = element_paging[0].find_all('a')
        for page_link in page_links:
            if page_link.has_attr('href') and str(page_link.text).isnumeric() and int(page_link.text) > 0:
                if str(page_link['href']).startswith('http'):
                    page_link_urls.append(page_link['href'])
                else:
                    page_link_urls.append("https://www.xcontest.org" + page_link['href'])

    return page_link_urls


def get_flight_info_dict(content)->dict:
    flight_dict = dict()
    soup = BeautifulSoup(content, "lxml")
    flight_list = soup.find('table', {"class": "flights wide"}).find('tbody').find_all('tr')
    for flight in flight_list:
        tds = flight.find_all('td')
        assert(len(tds) == 15)
        flight_d = get_flight_from_soup(tds)
        flight_d['active'] = True if 'inactive' not in flight['class'] else False
        flight_dict[flight_d['flight_id']] = flight_d
    return flight_dict


def get_all_page_urls(driver, url)->list:
    wait = WebDriverWait(driver, 30)
    driver.get(url)
    wait.until(ec.element_to_be_clickable((By.CLASS_NAME, 'flights')))
    return get_page_links(driver.page_source)


def get_flight_description(driver, args, url:str, retries:int=2, wait_time:int = 2)->str:
    error_file_name = 'manual_flight_description_check.txt'
    while retries > 0:
        try:
            sleep(2) # we have to wait, xcontest really does not like accessing the flights page to often
            wait = WebDriverWait(driver, 15)
            driver.get(url)
            wait.until(ec.element_to_be_clickable((By.CLASS_NAME, 'XCmoreInfo')))
            retries = 0
        except:
            #retries-=1
            retries = 0
            if args.verbose:
                print(f"No data received, skipping flight {url}")
                # print(f"Warning on flight description check, lets wait {wait_time} min and retry ")
            # sleep(wait_time * 60)

    if retries == 0 and not driver.page_source:
        if args.verbose:
            print(f"Error on flight description check, {url} check manually ")
        with open(error_file_name, '+a') as f:
            f.write(url + "\r\n")

    return get_page_description(driver.page_source)


def check_and_filter_flights(driver, args, flight_dict:dict, km_min:int=15)->list:
    filtered_moves = []
    checked = set()

    filter_file_name_links = f'FILTER_{args.filter}_LINKSONLY.txt'
    filter_file_name = f'FILTER_{args.filter}.txt'
    if os.path.isfile(filter_file_name):
        with open(filter_file_name, 'r+') as file:
            lines = [line.rstrip() for line in file]
            [checked.add(l) for l in lines]

    for flight_id, flight in flight_dict.items():        
        url = flight['link_flight_info'] if str(flight['link_flight_info']).startswith('http') else "https://www.xcontest.org" + flight['link_flight_info']
        if km_min < 1 or flight['km'] > km_min:
            if flight_id in checked:
                continue
            if not args.only_flight_links:
                flight_description = get_flight_description(driver, args, url)
                if flight_description and args.filter in flight_description.lower():
                    filtered_moves.append(flight)
                checked.add(flight_id)
                with open(filter_file_name, 'w+') as file:
                    file.writelines(checked)
            else:
                with open(filter_file_name_links, 'a+') as file:
                    file.write("https://www.xcontest.org" + flight['link_flight_info'] + "\n")
            

    return filtered_moves

def scrap_approval_flight(args, driver, start_url:str, manual_eval_set:set):
    """ SCRAP and approve/disapprove flights """
    flights_approved, flights_disapproved, flights_error, pilot_not_approved, flight_inactive = [], [], [], [], []
    filtered_flights = []
    driver.set_page_load_timeout(30)

    url_list = [start_url]

    '''Since this is an ADMIN only page, we need to be logged in'''
    login(driver)

    if args.auto_page:
        pages = get_all_page_urls(driver, start_url)
        url_list += pages

    for url in url_list:
        wait = WebDriverWait(driver, 30)
        driver.get(url)

        wait.until(ec.element_to_be_clickable((By.CLASS_NAME, 'flights')))

        flight_dict = get_flight_info_dict(driver.page_source)

        if args.filter:
            filtered_flights.extend(check_and_filter_flights(driver, args, flight_dict))
            continue

        idx = args.num_flights

        '''Step I: get all flight ids of the current page (we later need the approval links)'''
        tables = driver.find_element(by=By.CLASS_NAME, value="flights")
        rows = tables.find_elements(by=By.TAG_NAME, value="tr")
        flight_ids_on_page = []
        for row in rows:
            tds = row.find_elements(by=By.TAG_NAME, value="td")
            flight_id = [td for td in tds if 'FLID:' in td.get_attribute('title')]
            if flight_id and flight_id[0]:
                flight_ids_on_page.append(flight_id[0].get_attribute('title').split(':')[-1])

        '''Step II: check flights, if we approve we reload the page, this way we do not have to re-crawl the content'''
        for flight_id in flight_ids_on_page:
            '''check if flight is already in our manual eval directory'''
            if flight_id in manual_eval_set and not args.check_manual:
                if args.verbose:
                    print(f'Skipping filght {flight_id}, its already in manual.')
            
            if not flight_id in manual_eval_set and args.check_manual:
                if args.verbose:
                    print(f'Skipping filght {flight_id}, its not in manual.')
                continue

            tables = WebDriverWait(driver, 10).until(ec.element_to_be_clickable((By.CLASS_NAME, "flights")))
            rows = [row for row in tables.find_elements(by=By.TAG_NAME, value="tr") if any([f'FLID:{flight_id}' in td.get_attribute('title') for td in row.find_elements(by=By.TAG_NAME, value="td")])]
            row = rows[0]

            a_tags = row.find_elements(by=By.TAG_NAME, value="a")
            link_igc = [l for l in a_tags if 'IGC' in l.text.upper()]
            link_approval = [l for l in a_tags if 'action=A' in l.get_attribute('href')]
            link_disapproval = [l for l in a_tags if 'action=D' in l.get_attribute('href')]

            #if link_igc and (link_approval or args.disable_approval) and link_disapproval and flight_id and flight_id in flight_dict:
            if link_igc and (link_approval or args.disable_approval or args.only_download) and flight_id and flight_id in flight_dict:
                #print("1")
                link_igc = link_igc[0]; #link_disapproval = link_disapproval[0]
                flight_infos = flight_dict[flight_id]

                if not flight_infos['pilot_approved']:
                    pilot_not_approved.append(flight_infos)
                elif not flight_infos['active']:
                    flight_inactive.append(flight_infos)
                else:
                    do_flight_validation = flight_infos['km'] > MINIMAL_VALIDATION_DISTANCE
                    igc_file_name = None
                    if do_flight_validation:
                        link_igc.click()

                        igc_file_name = get_downloaded_file()
                        if args.verbose:
                            print(igc_file_name)

                    if not do_flight_validation or (os.path.isfile(igc_file_name) and not args.only_download):
                        verdict, detail, kml_file_name = 0, None, ""
                        if do_flight_validation:
                            verdict, detail, kml_file_name = validate_flight(igc_file_name)
                        
                        if (verdict == 0 or verdict == 1) and flight_infos['points'] > 0.0:
                            flights_approved.append(flight_infos)
                            if not args.disable_approval:
                                link_approval = link_approval[0]
                                if args.verbose: print("approving flight")
                                approve_disapprove_flight(link=link_approval, driver=driver)
                                time.sleep(5.0)
                            if args.verbose:
                                print(f"APPROVED({verdict}) {flight_infos['pilot_name']} glider {flight_infos['glider']} {flight_infos['points']} p. and {flight_infos['km']} km")

                        else:
                            kml_file_name = store_for_manual_eval(flight_infos=flight_infos, kml_file_name=kml_file_name)
                            flights_disapproved.append(flight_infos)
                            '''SANITY CHECKS'''
                            if args.verbose:
                                print(f"VIOLATION({verdict}) {flight_infos['pilot_name']} glider {flight_infos['glider']} {flight_infos['points']} p. and {flight_infos['km']} km")

                            if 'HG' in flight_infos['glider']:
                                if args.verbose:
                                    print(f"maybe new HG LZ, glider: {flight_infos['glider']}")
                            else:
                                '''check if a single data point is faulty'''
                                mail = Mail(flight=flight_infos, kml_file_name=kml_file_name)
                                if args.enable_decline:
                                    if args.verbose:
                                        print(f"auto decline flight: {flight_infos['flight_id']}")
                                    approve_disapprove_flight(link=link_disapproval, driver=driver) 
                    else:
                        flights_error.append(flight_infos)
            else:
                # print(f"{link_igc} {link_approval}  {args.disable_approval} {flight_id} {flight_id in flight_dict}")
                continue

            idx -= 1
            if idx <= 0 and args.num_flights != 0:
                break

    return flights_approved, flights_disapproved, flights_error, pilot_not_approved, flight_inactive, filtered_flights


def store_for_manual_eval(flight_infos:dict, kml_file_name:str)->str:
    date_of_flight = flight_infos['start_date']
    if ' ' in date_of_flight:
        date_of_flight = date_of_flight.split(' ')[0]
    flight_id = flight_infos['flight_id']
    pilot_name = flight_infos['pilot_name']
    new_kml_file_name = f"{date_of_flight}_{pilot_name}_{flight_id}_{kml_file_name.replace('flights/', '')}"
    try:
        os.rename(kml_file_name, os.path.join(MANUAL_EVAL_DIR, new_kml_file_name))
    except FileNotFoundError as err:
        print(f"{new_kml_file_name} not found, with error {err}")

    file_content = ""
    for key in flight_infos:
        file_content+= f"{key}: {flight_infos[key]}\n"

    with open(os.path.join(MANUAL_EVAL_DIR,f"{date_of_flight}_{pilot_name}_{flight_id}_info.txt"), 'w') as f:
        f.write(file_content)

    return os.path.join(MANUAL_EVAL_DIR, new_kml_file_name)


def approve_disapprove_flight(link, driver):
    try:
        link.click()
    except StaleElementReferenceException:
        print(f"WARNING: StaleElementReferenceException, retry link otherwise manually click url: {link}")
        # link.click()
    '''first popup to be sure to approve'''
    try:
        WebDriverWait(driver, 5).until (ec.alert_is_present())
        alert = driver.switch_to.alert
        alert.accept()
    except TimeoutException:
        pass

    '''second popup for comments'''
    try:
        WebDriverWait(driver, 5).until (ec.alert_is_present())
        alert = driver.switch_to.alert
        alert.accept()
    except TimeoutException:
        pass

# def signal_handler(sig, frame):
#     print('You pressed Ctrl+C!')
#     sys.exit(0)


'''
0: all ok / 1: should be ok / 2: vioaltion
'''
def validate_flight(igc_file_name:str)->Tuple[int,str,str]:
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


def get_manual_eval_set()->set:
    ids = [f.split('_')[2] for f in os.listdir(MANUAL_EVAL_DIR) if f.endswith('.txt')]
    return set(ids)


def write_filtered_flights_to_file(filtered_flights, file_name:str = "filtered_flights.csv"):
    with open(file_name, '+a') as f:
        for flight in filtered_flights:
            f.write(f"{flight['flight_id']};{flight['pilot_name']};{'https://www.xcontest.org' + flight['link_flight_info']};{flight['km']}\r\n")


SIG_INT_COUNT = 1

def filter_flights_by_url(args, driver):
    driver.set_page_load_timeout(30)
    filtered_flights = []
    if os.path.exists(args.filter_file):
        with open(args.filter_file, 'r') as file:
            flight_urls = [line.rstrip() for line in file]
            for url in flight_urls:
                if args.verbose:
                    print(f"checking {url}")
                flight_description = get_flight_description(driver, args, url)
                if args.verbose:
                    print(f"-- {flight_description}")
                if flight_description and args.filter in flight_description.lower():
                    filtered_flights.append(url)
    
    with open(str(args.filter_file).replace('.txt','_candidate.txt'), '+a') as f:
        for flight_url in filtered_flights:
            f.write(f"{flight_url}\r\n")

    return None    


def main():
    global URL_APPROVAL
    # global SIG_INT_COUNT

    app, dis, err, nonpilot, inactive, filtered_flights = [], [], [], [], [], []

    parser = argparse.ArgumentParser(description='XContest FlyForFun Automatic Flight Approval')
    parser.add_argument('-v','--verbose', action="store_true", default=False, help='print debug information')   
    parser.add_argument('--disable-approval', action="store_true", default=False, help='approval link is not clicked')
    parser.add_argument('--only-download', action="store_true", default=False, help='only download the igc files')
    parser.add_argument('--filter-file', type=str, default=None, help=f'input file to read the flight urls from')
    parser.add_argument('--filter', type=str, default=None, help=f'store flights in directory \'filter\' if <pattern> is contained in flight description')
    parser.add_argument('--only-flight-links', action="store_true", default=False, help='if filter is active, we only collect the flight links in a file')
    parser.add_argument('--url', type=str, default=None, help=f'alternate approval url')
    parser.add_argument('--num-flights', type=int, default=0, help='number of flights to check (default: 0 = inf)')
    parser.add_argument('--non-headless', action="store_true", default=False, help='see browser')
    parser.add_argument('--auto-page', action="store_true", default=False, help='try to iterate over all pages')
    parser.add_argument('--check-manual', action="store_true", default=False, help=f'retry all flights from folder \'manual\'')
    parser.add_argument('--enable-decline', action="store_true", default=False, help='automatic decline flights if violation occurs')
    parser.add_argument('--proxy', type=str, default=None, help='enter ip:port to use as proxy (default: off)')
    args = parser.parse_args()

    driver = init_webdriver(headless=not args.non_headless, option_proxy=args.proxy)

    if args.url:
        URL_APPROVAL = args.url

    try:
        manual_eval_set = get_manual_eval_set()

        if not args.filter_file:
            # flight scrapping
            app, dis, err, nonpilot, inactive, filtered_flights = scrap_approval_flight(args=args, driver=driver,start_url=URL_APPROVAL, manual_eval_set=manual_eval_set)
        else:
            filtered_flights = filter_flights_by_url(args=args, driver=driver)

        print(f"Approved {len(app)}, disapproved {len(dis)}, errors {len(err)}, pilot not approved {len(nonpilot)}, flights inactive {len(inactive)}, flights filtered {len(filtered_flights)}")
    
        if args.filter and filtered_flights:
            write_filtered_flights_to_file(filtered_flights=filtered_flights)

    except Exception as e:
        print(f"Error occured: {e}")

    driver.close()


if __name__ == '__main__':
    main()
