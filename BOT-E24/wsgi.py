# This file contains the WSGI configuration required to serve up your
# web application at http://<your-username>.pythonanywhere.com/
# It works by setting the variable 'application' to a WSGI handler of some
# description.
#
# WSGI configuration for E-24 Schedule Bot

import sys
import os

# add your project directory to the sys.path
project_home = '/home/fuckfuckfucks/mysite'
if project_home not in sys.path:
    sys.path = [project_home] + sys.path

# Load environment variables
from dotenv import load_dotenv
load_dotenv(os.path.join(project_home, '.env'))

# import flask app but need to call it "application" for WSGI to work
from flask_app import app as application  # noqa

if __name__ == "__main__":
    application.run()
