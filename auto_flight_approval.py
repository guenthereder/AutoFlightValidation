#!/usr/bin/env python3

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
from Scrapping import *
from Mail import Mail

if __name__ == '__main__' and __package__ is None:
    import os
    __LEVEL = 1
    os.sys.path.append(os.path.abspath(os.path.join(*([os.path.dirname(__file__)] + ['..']*__LEVEL))))


def scrap_approval_flight(args, driver, url, manual_eval_set:set):
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

        '''check if flight is already in our manual eval directory'''
        if flight_id in manual_eval_set:
            if args.verbose:
                print(f'Skipping filght {flight_id}, its already in manual.')
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
                    
                    if verdict == 0:
                        flights_approved.append(flight_infos)
                        approve_disapprove_flight(link=link_approval, driver=driver)
                        if args.verbose:
                            print(f"APPROVED {flight_infos['pilot_name']} glider {flight_infos['glider']} {flight_infos['points']} p. and {flight_infos['km']} km")

                    elif verdict == 1:
                        kml_file_name = store_for_manual_eval(flight_infos=flight_infos, kml_file_name=kml_file_name)
                        if args.verbose:
                            print(f"Minor-Violation {flight_infos['pilot_name']} glider {flight_infos['glider']} {flight_infos['points']} p. and {flight_infos['km']} km")
                    
                    else:
                        kml_file_name = store_for_manual_eval(flight_infos=flight_infos, kml_file_name=kml_file_name)
                        flights_disapproved.append(flight_infos)
                        '''SANITY CHECKS'''
                        if args.verbose:
                            print(f"VIOLATION {flight_infos['pilot_name']} glider {flight_infos['glider']} {flight_infos['points']} p. and {flight_infos['km']} km")
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

    return flights_approved, flights_disapproved, flights_error, pilot_not_approved


def store_for_manual_eval(flight_infos:dict, kml_file_name:str)->str:
    date_of_flight = flight_infos['start_date']
    if ' ' in date_of_flight:
        date_of_flight = date_of_flight.split(' ')[0]
    flight_id = flight_infos['flight_id']
    pilot_name = flight_infos['pilot_name']
    new_kml_file_name = f"{date_of_flight}_{pilot_name}_{flight_id}_{kml_file_name.replace('flights/', '')}"
    os.rename(kml_file_name, os.path.join(MANUAL_EVAL_DIR, new_kml_file_name))

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


def get_manual_eval_set()->set:
    ids = [f.split('_')[2] for f in os.listdir(MANUAL_EVAL_DIR) if f.endswith('.txt')]
    return set(ids)


def main():
    parser = argparse.ArgumentParser(description='XContest FlyForFun Automatic Flight Approval')
    parser.add_argument('--verbose', action="store_true", default=False, help='print debug information')
    parser.add_argument('--num-flights', type=int, default=0, help='numbers of flights to process in one run (default: 0)')
    parser.add_argument('--non-headless', action="store_true", default=False, help='print debug information')
    args = parser.parse_args()

    driver = init_webdriver(headless=not args.non_headless)

    manual_eval_set = get_manual_eval_set()

    # flight scrapping
    app, dis, err, nonpilot = scrap_approval_flight(args=args, driver=driver,url=URL_APPROVAL, manual_eval_set=manual_eval_set)

    print(f"Approved {len(app)}, disapproved {len(dis)}, errors {len(err)}, pilot not approved {len(nonpilot)}")

    driver.close()


if __name__ == '__main__':
    main()
