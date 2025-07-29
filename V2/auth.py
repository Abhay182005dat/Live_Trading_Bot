# auth_manager.py

import pyrebase
from firebaseconfig import firebaseConfig

firebase = pyrebase.initialize_app(firebaseConfig)
auth = firebase.auth()

def signup_user(email, password):
    try:
        user = auth.create_user_with_email_and_password(email, password)
        return user
    except Exception as e:
        return str(e)

def login_user(email, password):
    try:
        user = auth.sign_in_with_email_and_password(email, password)
        return user
    except Exception as e:
        return str(e)

def get_user_email(user):
    try:
        return auth.get_account_info(user['idToken'])['users'][0]['email']
    except:
        return None
