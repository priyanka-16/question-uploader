# pdf_utils.py
from pdf2image import convert_from_path
from PIL import Image
import pytesseract
from pytesseract import Output
import re
from drive_upload import upload_pil_image_to_drive

def crop_question(pdf_path, page_num, question_number, poppler_path=None):
    images = convert_from_path(pdf_path, dpi=300, first_page=page_num, last_page=page_num, poppler_path=poppler_path)
    if not images:
        print("No image from PDF.")
        return
    image = images[0]

    ocr = pytesseract.image_to_data(image, output_type=Output.DICT)

    q_num_pattern = re.compile(rf"^{question_number}\.")
    q_next_num_pattern = re.compile(rf"^{question_number+1}\.$")

    q_index = None
    q_next_index = None

    for i, word in enumerate(ocr["text"]):
        if q_index is None and q_num_pattern.match(word):
            q_index = i
        elif q_next_index is None and q_next_num_pattern.match(word):
            q_next_index = i

    if q_index is None:
        print(f"Question {question_number} not found.")
        return

    left = ocr["left"][q_index]+50
    top = ocr["top"][q_index]-15
    right = left + 875
    bottom = ocr["top"][q_next_index] - 15
    print(f"({left}, {top}, {right}, {bottom})")
    # Crop the image
    cropped = image.crop((left, top, right, bottom))
    link = upload_pil_image_to_drive(cropped, f"{question_number}.png")
    return link
