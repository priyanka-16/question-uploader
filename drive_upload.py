import io
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

SCOPES = ['https://www.googleapis.com/auth/drive.file']

def create_folder_if_not_exists(service, name, parent_id=None):
    query = f"name='{name}' and mimeType='application/vnd.google-apps.folder'"
    if parent_id:
        query += f" and '{parent_id}' in parents"
    results = service.files().list(q=query, spaces='drive', fields="files(id, name)").execute()
    items = results.get('files', [])
    if items:
        return items[0]['id']
    file_metadata = {
        'name': name,
        'mimeType': 'application/vnd.google-apps.folder',
    }
    if parent_id:
        file_metadata['parents'] = [parent_id]
    folder = service.files().create(body=file_metadata, fields='id').execute()
    return folder.get('id')

def upload_pil_image_to_drive(pil_image, full_path, creds, mime_type='image/png'):
    # Get or request credentials
    # creds = get_drive_creds()
    # if creds is None:
    #     st.stop()

    service = build('drive', 'v3', credentials=creds)

    path_parts = full_path.strip("/").split("/")
    filename = path_parts[-1]
    folder_parts = path_parts[:-1]

    parent_id = None
    for folder_name in folder_parts:
        parent_id = create_folder_if_not_exists(service, folder_name, parent_id)

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

    service.permissions().create(fileId=file_id, body={'type': 'anyone', 'role': 'reader'}).execute()
    return file_id
