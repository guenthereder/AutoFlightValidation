#!/usr/bin/env python3

from __future__ import print_function

from copyreg import pickle
import smtplib
from os.path import basename
from email.mime.base import MIMEBase
from mimetypes import guess_type
from email import encoders
from email.header import Header
from email.encoders import encode_base64
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import COMMASPACE, formatdate
from email.charset import Charset
from urllib.error import HTTPError
import base64
import csv

import os.path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from email.utils import formataddr

from config import *
from __credentials import *

class Mail:
    def __init__(self, flight:dict, kml_file_name:str, save_as_draft:bool=True):
        self.receiver_emails = [self.get_pilot_email(flight['pilot_name'])]
        self.message = self.get_mail_body(flight=flight)
        self.files = [kml_file_name]

        msg = MIMEMultipart()
        msg['From'] = sender
        # msg['To'] = COMMASPACE.join(self.receiver_emails)
        # recipient = f"{Header(flight['pilot_name'], 'utf-8')} <{COMMASPACE.join(self.receiver_emails)}>"
        msg['To'] = formataddr((flight['pilot_name'], self.receiver_emails[0])) if len(self.receiver_emails)>0 else "" 
        msg['Date'] = formatdate(localtime=True)
        msg['Subject'] = subject

        msg.attach(MIMEText(self.message))

        for f in self.files:
            mimetype, _ = guess_type(f)
            mimetype = mimetype.split('/', 1)
            with open(f, "rb") as fil:
                part = MIMEBase(mimetype[0], mimetype[1])
                part.set_payload(fil.read())
                encoders.encode_base64(part)
                # encode_base64(part)

            filename_rfc2047 = self.encode_header_param(basename(f))

            # The default RFC 2231 encoding of Message.add_header() works in Thunderbird but not GMail
            # so we fix it by using RFC 2047 encoding for the filename instead.
            # part.set_param('name', filename_rfc2047)
            part.add_header('Content-Disposition', 'attachment', filename=filename_rfc2047)
            msg.attach(part)

        if save_as_draft:
            self.service = self.get_google_service()
            body = {'raw': base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")}
            
            if self.service is not None:
                self.create_draft(service=self.service, user_id="me", message_body=body)
            else:
                print("Error: could not create google_service!")
        else:
            s = smtplib.SMTP(host, port)

            if tls:
                s.ehlo()
                s.starttls()
                s.ehlo()

            if smtp_username and smtp_password:
                s.login(smtp_username, smtp_password)

            s.sendmail(sender, self.receiver_emails, msg.as_string())
            s.quit()


    @staticmethod
    def get_pilot_email(pilot_name:str)->str:
        with open(PILOT_MAIL_FILE, mode='r') as f:
            reader = csv.reader(f)
            pilot_dict = {row[0]:row[1] for row in reader}

        if pilot_name in pilot_dict:
            print(pilot_name, pilot_dict[pilot_name])
            return pilot_dict[pilot_name]
        else:
            print(f"No Mail Adress found for {pilot_name}!")
        return ""


    @staticmethod
    def try_coerce_ascii(string_utf8:str)->str:
        """Attempts to decode the given utf8-encoded string
        as ASCII after coercing it to UTF-8, then return
        the confirmed 7-bit ASCII string.
    
        If the process fails (because the string
        contains non-ASCII characters) returns ``None``.
        """
        try:
            string_utf8.encode('ascii')
        except UnicodeEncodeError:
            return
        return string_utf8


    @staticmethod
    def encode_header_param(param_text:str)->str:
        """Returns an appropriate RFC 2047 encoded representation of the given
        header parameter value, suitable for direct assignation as the
        param value (e.g. via Message.set_param() or Message.add_header())
        RFC 2822 assumes that headers contain only 7-bit characters,
        so we ensure it is the case, using RFC 2047 encoding when needed.
    
        :param param_text: unicode or utf-8 encoded string with header value
        :rtype: string
        :return: if ``param_text`` represents a plain ASCII string,
                    return the same 7-bit string, otherwise returns an
                    ASCII string containing the RFC2047 encoded text.
        """
        if not param_text: return ""
        param_text_ascii = Mail.try_coerce_ascii(param_text)
        return param_text_ascii if param_text_ascii\
            else Charset('utf8').header_encode(param_text)


    @staticmethod
    def get_google_service():
        creds = None
        # The file token.json stores the user's access and refresh tokens, and is
        # created automatically when the authorization flow completes for the first
        # time.
        if os.path.exists(TOKEN_FILE):
            creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    CREDENTIALS_FILE, SCOPES)
                creds = flow.run_local_server(port=5000)
            # Save the credentials for the next run
            with open(TOKEN_FILE, 'w') as token:
                token.write(creds.to_json())

        try:
            # Call the Gmail API # prompt='consent'
            service = build('gmail', 'v1', credentials=creds)
            return service

        except HttpError as error:
            print(f'An error occurred: {error}')

        return None

    @staticmethod
    def create_draft(service, user_id, message_body):
        """Create and insert a draft email. Print the returned draft's message and id.

        Args:
            service: Authorized Gmail API service instance.
            user_id: User's email address. The special value "me"
            can be used to indicate the authenticated user.
            message_body: The body of the email message, including headers.

        Returns:
            Draft object, including draft id and message meta data.
        """
        try:
            message = {'message': message_body}
            draft = service.users().drafts().create(userId=user_id, body=message).execute()

            print('Draft id: %s\nDraft message: %s' % (draft['id'], draft['message']))

            return draft
        except HTTPError as error:
            print('An error occurred: %s' % error)
            return None


    @staticmethod
    def get_mail_body(flight:dict, contest="FlyForFun Cup 2022")->str:
        return f'''Lieber {flight['pilot_name']}.

    Dein Wettkampfflug vom {flight['start_date']} mit {flight['points']}P / {flight['km']}km kann wegen einer Luftraumverletzung
    nicht im {contest} gewertet werden (siehe roter Track im kml-File).
    Maßgeblich für die Wertung ist Dein eingereichter GPS-Track (igc-File). Bitte deaktiviere den Flug im
    ● Fly for Fun Cup und
    ● XContest World.

    Beim 'Deaktivieren' (im Gegensatz zum 'Löschen') bleibt Dein Flug in Deiner Flugliste erhalten.
    Der Flug ist aber für Dritte (wie Luftraumkontrolle) nicht mehr (ohne Link) sichtbar.
    Nützliche Links:
    ● Alex Airspace-Check, damit Du Deine Flüge selbst überprüfen kannst. (https://airspace-check.appspot.com/)
    ● Luftraumsinfos, damit Deine nächsten Flüge 100% passen. (https://www.google.com/maps/d/u/0/viewer?mid=1zT6OXNY8kBTJTksekzNC6wMSRrA&ll=47.776113095368636%2C13.206335961163973&z=12)

    Beste Grüße,
    Günther
    FlyForFun Salzburg

    PS: Dies ist einen neue automatisierte Auswertung, wenn eine Entscheidung unklar ist oder sogar falsch bitte einfach melden.

    '''


''' for testing only '''
if __name__ == '__main__':
    flight_dict = {
        "pilot_name": "Günther Eder",
        "start_date": "05.05.2022",
        "points": 24,
        "km": 24,
    }
    """ just for testing, you have to create a test.kml file """
    mail = Mail(flight=flight_dict, kml_file_name="test.kml")

    

