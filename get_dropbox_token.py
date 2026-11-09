"""One-off helper: get a Dropbox refresh token for the exercise tracker.

    pip install dropbox
    python get_dropbox_token.py

It asks for your Dropbox app key and secret, opens a link for you to approve
access, then prints the [dropbox] block to paste into your Streamlit secrets.
Nothing is saved or sent anywhere other than Dropbox.
"""
from dropbox.oauth import DropboxOAuth2FlowNoRedirect

app_key = input("Dropbox app key: ").strip()
app_secret = input("Dropbox app secret: ").strip()

flow = DropboxOAuth2FlowNoRedirect(app_key, app_secret, token_access_type="offline")
print("\n1. Open this link and click 'Allow':\n")
print("   " + flow.start())
code = input("\n2. Paste the code Dropbox shows you here: ").strip()
result = flow.finish(code)

print("\nDone. Put this in .streamlit/secrets.toml (or Streamlit Cloud > App settings > Secrets):\n")
print("[dropbox]")
print(f'app_key = "{app_key}"')
print(f'app_secret = "{app_secret}"')
print(f'refresh_token = "{result.refresh_token}"')
print('folder = "/Exercise Tracker"')
