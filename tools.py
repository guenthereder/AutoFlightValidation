import os
from pykml import parser
from pykml.factory import nsmap


def single_data_point_faulty(kml_file_name:str)->bool:
    namespace = {"ns2": nsmap[None]}
    with open(kml_file_name, 'r') as f:
        root = parser.parse(f).getroot()

    pms = root.findall(".//ns2:Placemark", namespaces=namespace)

    for pm in pms:
        print(pm.name)

    return False


''' FLIGHT TR FOR SINGLE FLIGHT FOR APPROVAL
<tr id="flight-3081471" class="  ">
00 flight nr / edit link  <td title="FLID:3081471"><a href="/flyforfuncup/approval/flights/edit:3081471">1</a></td>
01 flug datum startzeit <td title="übertragen: 30.04. 037:21 UTC"><div class="full">30.04.22 <em>09:11</em><span class="XCutcOffset">UTC+02:00</span></div></td>
02 pilot info name / link to profile <td><a class="plt1" href="/flyforfuncup/piloten/detail:almo">al mo</a></td>
03 Startplatz / link zum SP <td><div class="full"><span class="cic" style="background-image:url(https://s.xcontest.org/img/flag/at.gif)" \
    title="Austria">AT</span><a class="lau" href="/world/de/flugsuche/?filter[point]=13.109665 47.803172&amp;list[sort]=pts&amp;list[dir]=down">Gaisberg SW</a> \
        <span class="lau" style="color:green" title="registered takeoff">✔</span></div></td>
04 Flugtyp (freie Strecke / flaches Dreieck / FAI Dreieck) <td><div class="disc-vp" title="freie Strecke"><em class="hide">VP</em></div></td>
05 Länge km <td class="km"><strong>4.35</strong> km</td>
06 Punkte <td class="pts"><strong>4.35</strong> P.</td>
07 Schirm <td class="cat-A"><div title="GIN GLIDERS Explorer" class="sponsor gin"><span class="hide">A</span></div></td>
08 flight submitted at <td>30.04. <em>07:21</em></td>
09 flug info link <td><div><a class="detail" title="Flugdaten" href="/flyforfuncup/fluge/detail:almo/30.4.2022/07:11"><span class="hide">Flugdaten</span></a></div></td>
10 airspace violation / flight approved / pilot approved <td><img class="warning with-info" src="/img/warning.gif" width="16" height="16"><div class="violations" \
    style="display: none;"><div class="schranka"><div class="violation"><ul><li><strong>airspaceName:</strong> CTR/TRA GAISBERG/SCHWARZENBERG A [0ft AGL - 5000ft \
        AMSL]</li><li><strong>airspaceTimes:</strong> 09:11:01 - 09:20:29 [00:09:28]</li><li><strong>airspaceMaxViolation:</strong> 762 m</li></ul></div></div></div>
        <strong class="flight-status" title="flight was not yet approved/disapproved">f?</strong>
        <strong class="flight-status approved" title="pilot is approved">p.OK</strong>
    </td>
11 IGC File Link <td><a title="tracklog ke stažení ve formátu IGC" href="/track.php?t=1651303260.69_626ce35ca9980.igc">IGC</a></td>
12 APPROVE URL <td><a onclick="return (confirm('Are you sure you want to APPROVE this flight?') ? (Page.validationPrompt('You can add comment if you want:', this) ? \
    true : true) : false)" class="activate" title="Flug akzeptieren" href="/flyforfuncup/approval/flights/?action=A&amp;flight=3081471"><span class="hide">Flug akzeptieren\
        </span></a></td>
13 DISAPPROVE URL <td><a onclick="return (confirm('Are you sure you want to DISAPPROVE this flight?') ? (Page.validationPrompt('You can add comment if you want:', this)\
        ? true : true) : false)" class="deactivate" title="Flug zurückweisen" href="/flyforfuncup/approval/flights/?action=D&amp;flight=3081471"><span class="hide">Flug\
            zurückweisen</span></a></td>
14 scored info <td><strong title="flights is a part of score">scored</strong></td>
</tr>
'''
def get_flight_from_soup(tds)->dict:
    flight_nr = tds[0].get('title')
    if ':' in flight_nr: 
        flight_nr = flight_nr.split(':')[-1]

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

    pilot_approved = tds[10].find('strong', attrs={'class': 'flight-status approved'})
    pilot_approved = pilot_approved.text if pilot_approved else ""

    link_flight_igc = tds[11].find('a').get('href') if tds[11].find('a') is not None else None
    link_approval = tds[12].find('a').get('href') if tds[12].find('a') is not None else None
    link_disapproval = tds[13].find('a').get('href') if tds[13].find('a') is not None else None
    flight_scored_info = tds[14].text

    flight_km = float(flight_km.split(' ')[0])
    flight_points = float(flight_points.split(' ')[0])

    return {
        'flight_id': flight_nr,
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
        'pilot_approved': pilot_approved == "p.OK",
        'link_flight_igc': link_flight_igc,
        'link_approval': link_approval,
        'link_disapproval': link_disapproval,
        'flight_scored_info': flight_scored_info,
        'airspace_violation': False,
    }

