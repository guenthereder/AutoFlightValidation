# Auto Flight Validation

This is a scapper that collects flights from xcontest.org and applies Alex Stumpfels airspace-check. In case of an airspace violation an email is created and saved as draft on a gmail account (or optional sent to a given mail or the pilots mail). The code is currently designed to validate the filghts for the Fly for fun Cup at Gaisberg/AT and is customized to it. Feel free to fork and repurpose this code.

## Config

Create an `__credentials.py` file that contains `xc_username, xc_password, smtp_username, smtp_password` everything else can be found in the `config.py` file.

## Requirements

- Alex Stumpfels airspace-check [web version](https://airspace-check.appspot.com)
- For the drafts to work a google account otherwise simply a mail account
- `pip install -r requirements.txt`