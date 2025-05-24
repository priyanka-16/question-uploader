import io
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import os

# If modifying scopes, delete token.json
SCOPES = ['https://www.googleapis.com/auth/drive.file']

def get_drive_service():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
        creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return build('drive', 'v3', credentials=creds)

def upload_pil_image_to_drive(pil_image, filename, mime_type='image/png'):
    # Save to a BytesIO stream
    img_byte_arr = io.BytesIO()
    pil_image.save(img_byte_arr, format='PNG')
    img_byte_arr.seek(0)

    # Create media upload from stream
    media = MediaIoBaseUpload(img_byte_arr, mimetype=mime_type)

    file_metadata = {'name': filename}
    service = get_drive_service()
    uploaded_file = service.files().create(body=file_metadata, media_body=media, fields='id,webViewLink').execute()

    print(f"Uploaded to Google Drive! File ID: {uploaded_file['id']}")
    print(f"View URL: {uploaded_file['webViewLink']}")
    file_id = uploaded_file.get('id')

    service.permissions().create(fileId=file_id, body={'type': 'anyone', 'role': 'reader'}).execute()
    return file_id
