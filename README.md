# Auto Flight Validation

This is a scapper that collects flights from [xcontest.org](xcontest.org) and applies the airspace-check from Alex Stumpfl. In case of an airspace violation an email is created and saved as draft on a gmail account (or optional sent to a given mail or the pilots mail). The code is currently designed to validate the flights for the FlyForFun Cup at Gaisberg/AT and is customized to it. In case of no violation the flight is approved. (A flight can also be disapproved.)
Feel free to fork and repurpose this code.

## Config

Create a `__credentials.py` file that contains `xc_username, xc_password, smtp_username, smtp_password` everything else can be found in the `config.py` file.

Note: we auto approve flights below 10km distance as the overhead for many flights is to hight and as these flights wont end up on the final competition score anyway. This can be set in the `config.py` using the `MINIMAL_VALIDATION_DISTANCE` variable.

## Requirements

- airspace-check as jar file (here is a [web version](https://airspace-check.appspot.com))
- For the drafts to work a google account otherwise simply a mail account
- `pip install -r requirements.txt`

## Google Token

Obtain a new access token for google is done using `server.js`, enter project settings at the top and start with
        node server.js

Then, using browser and also add the required fields, open:
    https://accounts.google.com/o/oauth2/auth?
        client_id=CLIENT_ID&
        redirect_uri=http://localhost:8000/callback&
        response_type=code&
        scope=https://www.googleapis.com/auth/gmail.compose&
        access_type=offline

### Requirements (node)

    npm install google-auth-library
    npm install express
