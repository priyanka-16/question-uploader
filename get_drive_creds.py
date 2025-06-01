import streamlit as st
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
import json

# Set to "http://localhost:8501" when operating locally
redirect_uri = "https://mainpy-7m9yckcxfjfwwjujjwfrfs.streamlit.app/"

SCOPES = ['https://www.googleapis.com/auth/drive.file']

def get_drive_creds():
    if "credentials" in st.session_state and st.session_state["credentials"] is not None:
        creds_data = st.session_state["credentials"]
        return Credentials.from_authorized_user_info(creds_data, SCOPES)

    # Set up flow
    client_config = {
        "web": {
            "client_id": st.secrets["google"]["client_id"],
            "client_secret": st.secrets["google"]["client_secret"],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [redirect_uri]
        }
    }

    flow = Flow.from_client_config(client_config, scopes=SCOPES, redirect_uri=redirect_uri)

    # ✅ Use the new API
    query_params = st.query_params
    if "code" in query_params:
        try:
            flow.fetch_token(code=query_params["code"])
            creds = flow.credentials
            st.session_state["credentials"] = json.loads(creds.to_json())
            st.success("Authenticated successfully!")
            return creds
        except Exception as e:
            st.error(f"Authentication failed: {str(e)}")
            return None
    else:
        auth_url, _ = flow.authorization_url(prompt='consent', access_type='offline')
        st.markdown(f"[Click here to authenticate with Google]({auth_url})")
        st.stop()