# temp_keyauth.py
from keyauth import api, getchecksum

def load_keyauth(username, password, name, ownerid, version):
    keyauthapp = api(
        name=name,
        ownerid=ownerid,
        version=version,
        hash_to_check=getchecksum()
    )
    try:
        keyauthapp.login(username, password)
        return True, f"✅ Connected as {username}"
    except Exception as e:
        return False, f"❌ Login failed: {e}"
