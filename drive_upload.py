import io
import streamlit as st
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import json

SCOPES = ['https://www.googleapis.com/auth/drive.file']

def get_drive_service():
    creds = None

    # Load creds from session state if available
    if "credentials" in st.session_state:
        creds_data = st.session_state["credentials"]
        creds = Credentials.from_authorized_user_info(creds_data, SCOPES)

    # If no creds or expired, do OAuth flow
    if not creds or not creds.valid:
        # Load client config from secrets
        client_config = {
            "installed": {
                "client_id": st.secrets["google"]["client_id"],
                "client_secret": st.secrets["google"]["client_secret"],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": ["http://localhost"]
            }
        }
        flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
        creds = flow.run_console()

        # Save creds info to session state for reuse
        st.session_state["credentials"] = json.loads(creds.to_json())

    return build('drive', 'v3', credentials=creds)


def create_folder_if_not_exists(service, name, parent_id=None):
    query = f"name='{name}' and mimeType='application/vnd.google-apps.folder'"
    if parent_id:
        query += f" and '{parent_id}' in parents"
    results = service.files().list(q=query, spaces='drive', fields="files(id, name)").execute()
    items = results.get('files', [])
    if items:
        return items[0]['id']
    # Create folder
    file_metadata = {
        'name': name,
        'mimeType': 'application/vnd.google-apps.folder',
    }
    if parent_id:
        file_metadata['parents'] = [parent_id]
    folder = service.files().create(body=file_metadata, fields='id').execute()
    return folder.get('id')


def upload_pil_image_to_drive(pil_image, full_path, mime_type='image/png'):
    path_parts = full_path.strip("/").split("/")
    filename = path_parts[-1]
    folder_parts = path_parts[:-1]

    service = get_drive_service()

    # Navigate/create folders
    parent_id = None
    for folder_name in folder_parts:
        parent_id = create_folder_if_not_exists(service, folder_name, parent_id)

    # Save image to BytesIO
    img_byte_arr = io.BytesIO()
    pil_image.save(img_byte_arr, format='PNG')
    img_byte_arr.seek(0)

    media = MediaIoBaseUpload(img_byte_arr, mimetype=mime_type)
    file_metadata = {
        'name': filename,
        'parents': [parent_id] if parent_id else []
    }

    uploaded_file = service.files().create(body=file_metadata, media_body=media, fields='id, webViewLink').execute()
    file_id = uploaded_file['id']
    print(f"Uploaded to Google Drive! File ID: {file_id}")
    print(f"View URL: {uploaded_file['webViewLink']}")

    # Make file public
    service.permissions().create(fileId=file_id, body={'type': 'anyone', 'role': 'reader'}).execute()
    return file_id
