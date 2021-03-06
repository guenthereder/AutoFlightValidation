#!/usr/bin/env python3

from ast import expr_context
import glob
import os
import subprocess
import time
from typing import Tuple
from bs4 import BeautifulSoup
import argparse

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as ec
from selenium.common.exceptions import TimeoutException

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


def scrap_approval_flight(args, driver, url, manual_eval_set:set):
    """ SCRAP and approve/disapprove flights """
    flights_approved, flights_disapproved, flights_error, pilot_not_approved, flight_inactive = [], [], [], [], []
    driver.set_page_load_timeout(30)

    '''Since this is an ADMIN only page, we need to be logged in'''
    login(driver)

    wait = WebDriverWait(driver, 30)
    driver.get(url)

    wait.until(ec.element_to_be_clickable((By.CLASS_NAME, 'flights')))

    flight_dict = get_flight_info_dict(driver.page_source)

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

        '''check if flight is already in our manual eval directory'''
        if flight_id in manual_eval_set:
            if args.verbose:
                print(f'Skipping filght {flight_id}, its already in manual.')
            continue

        a_tags = row.find_elements(by=By.TAG_NAME, value="a")
        link_igc = [l for l in a_tags if 'IGC' in l.text.upper()]
        link_approval = [l for l in a_tags if 'action=A' in l.get_attribute('href')]
        link_disapproval = [l for l in a_tags if 'action=D' in l.get_attribute('href')]

        #print(args.disable_approval, flight_id, flight_id in flight_dict)

        #if link_igc and (link_approval or args.disable_approval) and link_disapproval and flight_id and flight_id in flight_dict:
        if link_igc and (link_approval or args.disable_approval) and flight_id and flight_id in flight_dict:
            #print("1")
            link_igc = link_igc[0]; #link_disapproval = link_disapproval[0]
            flight_infos = flight_dict[flight_id]

            if not flight_infos['pilot_approved']:
                pilot_not_approved.append(flight_infos)
            elif not flight_infos['active']:
                flight_inactive.append(flight_infos)
            else:
                link_igc.click()

                igc_file_name = get_downloaded_file()
                if args.verbose:
                    print(igc_file_name)

                if os.path.isfile(igc_file_name):
                    verdict, detail, kml_file_name = validte_flight(igc_file_name)
                    
                    if (verdict == 0 or verdict == 1) and flight_infos['points'] > 0.0:
                        flights_approved.append(flight_infos)
                        if not args.disable_approval:
                            link_approval = link_approval[0]
                            if args.verbose: print("approving flight")
                            approve_disapprove_flight(link=link_approval, driver=driver)
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
                else:
                    flights_error.append(flight_infos)
        else:
            continue

        idx -= 1
        if idx <= 0 and args.num_flights != 0:
            break

    return flights_approved, flights_disapproved, flights_error, pilot_not_approved, flight_inactive


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
    link.click()
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



'''
0: all ok / 1: should be ok / 2: vioaltion
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


def get_manual_eval_set()->set:
    ids = [f.split('_')[2] for f in os.listdir(MANUAL_EVAL_DIR) if f.endswith('.txt')]
    return set(ids)


def main():
    global URL_APPROVAL

    parser = argparse.ArgumentParser(description='XContest FlyForFun Automatic Flight Approval')
    parser.add_argument('-v','--verbose', action="store_true", default=False, help='print debug information')   
    parser.add_argument('--disable-approval', action="store_true", default=False, help='approval link is not clicked')
    parser.add_argument('--url', type=str, default='', help='alternate approval url')
    parser.add_argument('--num-flights', type=int, default=0, help='number of flights to check (default: 0 = inf)')
    parser.add_argument('--non-headless', action="store_true", default=False, help='see browser')
    args = parser.parse_args()

    driver = init_webdriver(headless=not args.non_headless)

    if args.url != '':
        URL_APPROVAL = args.url

    try:
        manual_eval_set = get_manual_eval_set()

        # flight scrapping
        app, dis, err, nonpilot, inactive = scrap_approval_flight(args=args, driver=driver,url=URL_APPROVAL, manual_eval_set=manual_eval_set)

        print(f"Approved {len(app)}, disapproved {len(dis)}, errors {len(err)}, pilot not approved {len(nonpilot)}, flights inactive {len(inactive)}")
    except Exception as e:
        print(f"Error occured: {e}")

    driver.close()


if __name__ == '__main__':
    main()
