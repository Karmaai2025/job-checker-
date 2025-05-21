import streamlit as st
import google.generativeai as genai
import os
import json
import re
from PyPDF2 import PdfReader
from docx import Document

# Set up Gemini API (replace with your API key)
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
genai.configure(api_key='AIzaSyDW7lwmdh09DrXx0t0KJb-yVbpMPHusnLQ')

# Gemini model initialization
model = genai.GenerativeModel('gemini-1.5-pro-latest')

# Function to extract text from PDF
def extract_text_from_pdf(file):
    reader = PdfReader(file)
    text = ""
    for page in reader.pages:
        text += page.extract_text()
    return text

# Function to extract text from DOCX
def extract_text_from_docx(file):
    doc = Document(file)
    return "\n".join([para.text for para in doc.paragraphs])

# Function to parse resume
def parse_resume(resume_text):
    prompt = f"""
    Extract structured information from the following resume:

    {resume_text}

    Extract the following fields:
    - Name
    - Skills
    - Work Experience
    - Education
    - Certifications

    Respond in JSON.
    """
    response = model.generate_content(prompt)
    return response.text

# Function to evaluate candidate suitability
def evaluate_candidate(parsed_resume, job_description):
    prompt = f"""
    Given the candidate profile:

    {parsed_resume}

    and the job description:

    {job_description}

    Determine whether this candidate is suitable for the role. Clearly state:
    - Match (Yes or No)
    - Reasoning (brief summary)

    Respond in JSON format:
    {{"Match": "Yes/No", "Reasoning": "Explanation"}}
    """
    response = model.generate_content(prompt)
    return response.text

# Helper function to clean JSON response
def clean_json(response_text):
    json_text = re.sub(r'^```json|```$', '', response_text, flags=re.MULTILINE).strip()
    return json.loads(json_text)

# Streamlit UI
st.title("Candidate Suitability Checker")

resume_files = st.file_uploader("Upload Candidate Resumes (PDF or DOCX)", type=['pdf', 'docx'], accept_multiple_files=True)
job_description_file = st.file_uploader("Upload Job Description (PDF or DOCX)", type=['pdf', 'docx'])

if st.button("Evaluate Candidates"):
    if resume_files and job_description_file:
        with st.spinner("Analyzing..."):
            job_description_text = ""
            if job_description_file.type == "application/pdf":
                job_description_text = extract_text_from_pdf(job_description_file)
            else:
                job_description_text = extract_text_from_docx(job_description_file)

            for resume_file in resume_files:
                st.markdown(f"---\n### Results for: {resume_file.name}")
                if resume_file.type == "application/pdf":
                    resume_text = extract_text_from_pdf(resume_file)
                else:
                    resume_text = extract_text_from_docx(resume_file)

                parsed_resume_text = parse_resume(resume_text)
                parsed_resume = clean_json(parsed_resume_text)

                evaluation_result_text = evaluate_candidate(parsed_resume, job_description_text)
                result = clean_json(evaluation_result_text)

                st.subheader("Parsed Resume")
                st.json(parsed_resume)

                st.subheader("Evaluation Result")
                if result["Match"] == "Yes":
                    st.success(f"Candidate is suitable! ✅\nReasoning: {result['Reasoning']}")
                else:
                    st.error(f"Candidate is not suitable. ❌\nReasoning: {result['Reasoning']}")
    else:
        st.warning("Please upload both candidate resumes and the job description.")