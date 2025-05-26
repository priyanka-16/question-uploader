from pdf2image import convert_from_path
from PIL import Image
import pytesseract
from pytesseract import Output
import re
from drive_upload import upload_pil_image_to_drive
from PyPDF2 import PdfReader

def get_question_index(ocr, pattern):
    for i, word in enumerate(ocr["text"]):
        if pattern.match(word.strip()):
            return i
    return None

def find_word_index(ocr, keywords):
    for i, word in enumerate(ocr["text"]):
        if word.strip().upper() in keywords:
            return i
    return None

def load_ocr_image(pdf_path, page_num, poppler_path=None):
    images = convert_from_path(pdf_path, dpi=300, first_page=page_num, last_page=page_num, poppler_path=poppler_path)
    if not images:
        return None, None
    image = images[0]
    ocr = pytesseract.image_to_data(image, output_type=Output.DICT)
    return image, ocr

def is_last_page(pdf_path, page_num):
    reader = PdfReader(pdf_path)
    return page_num >= len(reader.pages)

def stitch_cropped(image, left, top, right, next_index, ocr):
    bottom = 2955
    left_next = ocr["left"][next_index]
    top_next = 350
    right_next = left_next + 905
    bottom_next = ocr["top"][next_index] - 15
    cropped_1 = image.crop((left, top, right, bottom))
    cropped_2 = image.crop((left_next, top_next, right_next, bottom_next))
    return stitch_images_vertically(cropped_1, cropped_2)

def stitch_cropped_across_pages(image1, image2, left, top, right, ocr2, next_index2):
    bottom1 = 2955
    left2 = ocr2["left"][next_index2]
    top2 = 350
    right2 = left2 + 905
    bottom2 = ocr2["top"][next_index2] - 15
    cropped_1 = image1.crop((left, top, right, bottom1))
    cropped_2 = image2.crop((left2, top2, right2, bottom2))
    return stitch_images_vertically(cropped_1, cropped_2)

def stitch_images_vertically(img1, img2):
    new_height = img1.height + img2.height
    stitched = Image.new("RGB", (img1.width, new_height))
    stitched.paste(img1, (0, 0))
    stitched.paste(img2, (0, img1.height))
    return stitched

def crop_question(pdf_path, page_num, question_number, full_path, poppler_path=None):
    image, ocr = load_ocr_image(pdf_path, page_num, poppler_path)
    if not image:
        print("Page not found.")
        return

    q_num_pattern = re.compile(rf"^{question_number}\.?$")
    next_q_pattern = re.compile(rf"^{question_number + 1}\.?$")
    q_index = get_question_index(ocr, q_num_pattern)
    next_q_index = get_question_index(ocr, next_q_pattern)

    if q_index is None:
        print(f"Question {question_number} not found.")
        return

    left = ocr["left"][q_index] + 50
    top = ocr["top"][q_index] - 15
    right = left + 905

    if next_q_index is not None:
        bottom = ocr["top"][next_q_index] - 15
        if bottom > top:
            cropped = image.crop((left, top, right, bottom))
        else:
            cropped = stitch_cropped(image, left, top, right, next_q_index, ocr)
    else:
        if not is_last_page(pdf_path, page_num):
            image_next, ocr_next = load_ocr_image(pdf_path, page_num + 1, poppler_path)
            if not image_next:
                print("Next page missing.")
                return

            next_q_index = get_question_index(ocr_next, next_q_pattern)
            if next_q_index is not None:
                cropped = stitch_cropped_across_pages(image, image_next, left, top, right, ocr_next, next_q_index)
            else:
                w_index = find_word_index(ocr, {"SOLUTIONS"})
                if w_index is not None:
                    bottom = ocr["top"][w_index] - 15
                    cropped = image.crop((left, top, right, bottom))
                else:
                    print("End marker not found.")
                    return
        else:
            bottom = ocr["top"][-1]  # fallback to end of page
            cropped = image.crop((left, top, right, bottom))

    link = upload_pil_image_to_drive(cropped, f"{full_path}.png")
    return link
