from copyreg import pickle
import smtplib, ssl
from os.path import basename
from email.mime.base import MIMEBase
from mimetypes import guess_type
from email.encoders import encode_base64
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import COMMASPACE, formatdate
from email.charset import Charset
import pickle
import datetime as dt

from __credentials import *

class Mail:
    @staticmethod
    def get_pilot_email(pilot_name:str)->str:
        with open(PILOT_MAIL_FILE, 'rb') as f:
            pilot_dict = pickle.load(f)
        if pilot_name in pilot_dict:
            return pilot_dict[pilot_name]
        else:
            print(f"No Mail Adress found for {pilot_name}!")
        return None

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

    def __init__(self, flight:dict, kml_file_name:str):
        #self.receiver_emails = [flight['pilot_email']]
        print(f"For pilot {flight['pilot_name']} we (would) send to {self.get_pilot_email(flight['pilot_name'])}")
        self.receiver_emails = ['gue@geder.at']
        self.message = self.get_mail_body(flight=flight)
        self.files = [kml_file_name]

        msg = MIMEMultipart()
        msg['From'] = sender
        msg['To'] = COMMASPACE.join(self.receiver_emails)
        msg['Date'] = formatdate(localtime=True)
        msg['Subject'] = subject

        msg.attach(MIMEText(self.message))

        for f in self.files:
            mimetype, _ = guess_type(f)
            mimetype = mimetype.split('/', 1)
            with open(f, "rb") as fil:
                part = MIMEBase(mimetype[0], mimetype[1])
                part.set_payload(fil.read())
                encode_base64(part)
            filename_rfc2047 = self.encode_header_param(basename(f))

            # The default RFC 2231 encoding of Message.add_header() works in Thunderbird but not GMail
            # so we fix it by using RFC 2047 encoding for the filename instead.
            part.set_param('name', filename_rfc2047)
            part.add_header('Content-Disposition', 'attachment', filename=filename_rfc2047)
            msg.attach(part)

        # with smtplib.SMTP_SSL(host, port) as server:
        #     if tls:
        #         server.ehlo()
        #         server.starttls()
        #         server.ehlo()

        #     server.login(smtp_username, smtp_password)
        #     server.sendmail(sender, self.receiver_emails, msg.as_string())

        s = smtplib.SMTP(host, port)

        if tls:
            s.ehlo()
            s.starttls()
            s.ehlo()

        if smtp_username and smtp_password:
            s.login(smtp_username, smtp_password)

        #print ("sending %s to %s" % (subject, headers['To']))
        s.sendmail(sender, self.receiver_emails, msg.as_string())
        s.quit()


    def get_mail_body(self, flight:dict, contest="FlyForFun Cup 2022")->str:
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

    # def send_email(self, subject, content, receiver:str ):
    #     """ Send a simple, stupid, text, UTF-8 mail in Python """

    #     for ill in [ "\n", "\r" ]:
    #         subject = subject.replace(ill, ' ')

    #     headers = {
    #         'Content-Type': 'text/html; charset=utf-8',
    #         'Content-Disposition': 'inline',
    #         'Content-Transfer-Encoding': '8bit',
    #         'From': sender,
    #         'To': receiver,
    #         'Date': dt.datetime.now().strftime('%a, %d %b %Y  %H:%M:%S %Z'),
    #         'X-Mailer': 'python',
    #         'Subject': subject
    #     }

    #     # create the message
    #     msg = ''
    #     for key, value in headers.items():
    #         msg += "%s: %s\n" % (key, value)

    #     # add contents
    #     msg += f"\n{content}\n"

    #     s = smtplib.SMTP(host, port)

    #     if tls:
    #         s.ehlo()
    #         s.starttls()
    #         s.ehlo()

    #     if smtp_username and smtp_password:
    #         s.login(smtp_username, smtp_password)

    #     print ("sending %s to %s" % (subject, headers['To']))
    #     s.sendmail(headers['From'], headers['To'], msg.encode("utf8"))
    #     s.quit()