from google import generativeai
import json
import re
import streamlit as st
import tempfile
import os
from image_handler import crop_question
from db_handler import save_to_mongodb
import platform
from PyPDF2 import PdfReader, PdfWriter
import ast
from get_drive_creds import get_drive_creds

if platform.system() == "Windows":
    poppler_path = r"C:\Users\Aayush Gajwani\Downloads\Release-24.08.0-0\poppler-24.08.0\Library\bin"
else:
    poppler_path = "/usr/bin"  # Where poppler-utils installs on Streamlit Cloud
subject_ids={"maths":"66cf8a7fb60054fa64dad203","physics":"66cf8ad9b60054fa64dad207","biology":"66cf8aeab60054fa64dad20b","chemistry":"66cf8ae3b60054fa64dad209"}
generativeai.configure(api_key=st.secrets['gemini']['api_key'])

PROMPT_TEMPLATE = """Please pick question number {quenos} from first file attached and convert to text / latex code in following json format. Answers and solutions of all question are also given in second file attached. Please match question number and pick answer and solution from these pages as well.
    class: {class_},
    subject: {subject_id},
    topic: {topic},
    subTopic: Joi.string().required(),
    difficulty: Joi.number().integer().min(1).max(5).required(),
    type: "MCQ",
    queText: Joi.string().allow(null, ""),
    queImg: Joi.string().allow(null, ""), //If any diagram either in question or option is there put yes here
    optA: Joi.string().allow(null, ""),
    optB: Joi.string().allow(null, ""),
    optC: Joi.string().allow(null, ""),
    optD: Joi.string().allow(null, ""),
    answer: Joi.string().required().valid("A", "B", "C", "D"),
    solutionText: Joi.string().allow(null, ""),
    solutionImage: Joi.string().allow(null, ""), //If any diagram in solution is there put yes here
    source: :”Karnataka study material”,
    queNo:Joi.number().integer()
    nAttempted: 0,
    nCorrect: 0,
    nWrong: 0,

 Just match the question number and  populate quetext, optA, optB, optC, optD for each question after converting each question in the attached pdf to latex code if required. Please don't create new question of your own. Populate difficulty as per your assessment of question (5 being hardest and 1 is easiest). Subtopics names you can select one of - {subtopics}
 """

def extract_json_from_response(text):
    print(text)
    match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
    return json.loads(match.group(1)) if match else []

def load_topics(subject, grade):
    file_path = f"topics/{subject.lower()}_{grade}.json"

    if not os.path.exists(file_path):
        return {}

    with open(file_path, 'r', encoding='utf-8') as file:
        return json.load(file)

def extract_pdf_pages(original_path, page_numbers):
    reader = PdfReader(original_path)
    writer = PdfWriter()

    for page_num in page_numbers:
        if 0 <= page_num < len(reader.pages):
            print(f"writing page {page_num}")
            writer.add_page(reader.pages[page_num])

    temp_out = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    with open(temp_out.name, "wb") as out_pdf:
        writer.write(out_pdf)

    return temp_out.name  # return path to the new PDF

def main():
    st.set_page_config(page_title="Question Uploader", layout="centered")
    st.title("📘 Question Uploader")
    st.sidebar.title("Upload file")

    # Form inputs
    class_ = st.sidebar.selectbox("Select Class", [11, 12])
    subject = st.sidebar.selectbox("Select Subject",["Physics","Chemistry","Maths","Biology"])
    subject_id=subject_ids[subject.lower()]
    topics_available = load_topics(subject, class_)
    topic = st.sidebar.selectbox("Select Topic", list(topics_available.keys()) if topics_available else [])
    subtopics = topics_available[topic]
    quenos = st.sidebar.text_input("Question Numbers")
    question_page_numbers = st.sidebar.text_input("Question Page Numbers")
    solution_page_numbers = st.sidebar.text_input("Solution Page Numbers")
    uploaded_file = st.sidebar.file_uploader("Upload PDF", type=["pdf"])
    creds = get_drive_creds()

    if st.sidebar.button("Process file & Generate Questions"):
        if not uploaded_file:
            st.sidebar.warning("Please upload a PDF file.")
            return

        if creds is None:
            st.stop()

        print(f"quenos:{quenos}, quepg:{question_page_numbers}, solpg:{solution_page_numbers}, class:{class_}, subject:{subject}, topic:{topic}")
        print(f"subtopics:{subtopics}")

        with st.spinner("Processing..."):
            prompt = PROMPT_TEMPLATE.format(class_=class_, topic=topic, quenos=quenos, subtopics=subtopics, subject_id=subject_id)

            # Save uploaded file temporarily
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                tmp_file.write(uploaded_file.read())
                temp_pdf_path = tmp_file.name

            try:
                model = generativeai.GenerativeModel("gemini-2.0-flash")
                # response = model.generate_content([prompt, generativeai.upload_file(temp_pdf_path)])
                # Convert 1-based page numbers (user input) to 0-based for PyPDF2Add commentMore actions
                q_pages = [int(p) - 1 for p in ast.literal_eval(question_page_numbers)]
                s_pages = [int(p) - 1 for p in ast.literal_eval(solution_page_numbers)]

                # Extract PDFs
                question_pdf_path = extract_pdf_pages(temp_pdf_path, q_pages)
                solution_pdf_path = extract_pdf_pages(temp_pdf_path, s_pages)

                # Upload separately
                q_pdf = generativeai.upload_file(question_pdf_path)
                s_pdf = generativeai.upload_file(solution_pdf_path)

                # Send both with the prompt
                response = model.generate_content([prompt, q_pdf, s_pdf])
                print("response received")
                questions = extract_json_from_response(response.text)
                print("response converted to JSON")
                if not questions:
                    st.error("Failed to extract JSON from Gemini response.")
                    return

                for question in questions:
                    if question.get('queImg'):
                        print(f"since question#{question['queNo']} requires image trying to crop")
                        question['queImg'] = crop_question(question_pdf_path,question['queNo'],f"{subject}/{topic}/questions/{question['queNo']}",creds, poppler_path)
                    if question.get('solutionImage'):
                        print(f"since solution#{question['queNo']} requires image trying to crop")
                        question['solutionImage'] = crop_question(solution_pdf_path,question['queNo'],f"{subject}/{topic}/solutions/{question['queNo']}",creds, poppler_path)

                results = save_to_mongodb(questions)
                for idx, (question, inserted_id) in enumerate(zip(questions, results), start=1):
                    st.success(f"✅ Question {idx} uploaded successfully!")

                    # Render question text (LaTeX or plain)
                    st.markdown(f"**Q{idx}.**")
                    if question.get('queImg'):
                        drive_img_url = f"https://drive.google.com/uc?export=view&id={question['queImg']}"
                        view_url = f"https://drive.google.com/file/d/{question['queImg']}/view?usp=sharing"

                        st.markdown(f"[🔗 View on Google Drive]({view_url})")
                        st.image(drive_img_url, caption="Question Image", output_format="auto")

                    elif question.get("queText"):
                        text = question["queText"]
                        if any(sym in text for sym in ["\\(", "\\)", "$"]):
                            # Render using markdown with MathJax support
                            st.markdown((text.replace("\\(", "$").replace("\\)", "$")).replace("$$","$"), unsafe_allow_html=True)
                        else:
                            st.write(text)

                        # Render options
                        options = ['A', 'B', 'C', 'D']
                        for opt in options:
                            key = f"opt{opt}"
                            value = question.get(key, "")
                            if value:
                                st.markdown(f"{opt}) {value}")
                    if question.get("answer"):
                        st.markdown(f"Answer: {question.get("answer")}", unsafe_allow_html=True)
                    solution = question.get("solutionText", "")
                    if question.get("solutionImage"):
                        drive_img_url = f"https://drive.google.com/uc?export=view&id={question['solutionImage']}"
                        view_url = f"https://drive.google.com/file/d/{question['solutionImage']}/view?usp=sharing"

                        st.markdown(f"[🔗 View on Google Drive]({view_url})")
                        st.image(drive_img_url, caption="Solution Image", output_format="auto")

                    elif solution:
                        if any(sym in solution for sym in ["\\(", "\\)", "$"]):
                            st.markdown(f"Solution: {solution.replace("\\(", "$").replace("\\)", "$")}", unsafe_allow_html=True)
                        else:
                            st.markdown(f"Solution: {solution}")

                    else:
                        st.error("No solution available.")

            except Exception as e:
                st.exception(f"An error occurred: {e}")
            finally:
                os.remove(temp_pdf_path)

if __name__ == "__main__":
    main()