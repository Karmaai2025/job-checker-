import streamlit as st
import google.generativeai as genai
import os
import json
import re
from PyPDF2 import PdfReader
from docx import Document
 
# Set up Gemini API (replace with your API key)
genai.configure(api_key='')
 
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
 
# Function to parse resume using Gemini
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
 
    Respond only in JSON format.
    """
    response = model.generate_content(prompt)
    return response.text
 
# Function to evaluate candidate suitability using Gemini
def evaluate_candidate(parsed_resume_json_str, job_description):
    prompt = f"""
    Given the candidate profile (in JSON):
 
    {parsed_resume_json_str}
 
    and the job description:
 
    {job_description}
 
    Determine whether this candidate is suitable for the role. Clearly state:
    - Match (Yes or No)
    - Reasoning (brief summary)
 
    Respond only in JSON format:
    {{
        "Match": "Yes" or "No",
        "Reasoning": "brief explanation"
    }}
    """
    response = model.generate_content(prompt)
    return response.text
 
# Improved JSON parser to handle malformed AI responses
def clean_json(response_text):
    response_text = response_text.strip()
 
    # Remove markdown-style JSON formatting
    cleaned_text = re.sub(r'^```json|```$', '', response_text, flags=re.MULTILINE).strip()
 
    # Try parsing the full cleaned text
    try:
        return json.loads(cleaned_text)
    except json.JSONDecodeError:
        try:
            # Try to extract the first valid JSON object
            match = re.search(r'\{(?:[^{}]|(?R))*\}', cleaned_text)
            if match:
                return json.loads(match.group(0))
        except Exception as e:
            st.error(f"JSON parsing failed: {e}")
            return {}
 
    st.error("Unable to parse JSON response.")
    return {}
 
# Streamlit UI
st.title("Candidate Suitability Checker")
 
resume_files = st.file_uploader("Upload Candidate Resumes (PDF or DOCX)", type=['pdf', 'docx'], accept_multiple_files=True)
job_description_file = st.file_uploader("Upload Job Description (PDF or DOCX)", type=['pdf', 'docx'])
 
if st.button("Evaluate Candidates"):
    if resume_files and job_description_file:
        with st.spinner("Analyzing..."):
            # Extract job description text
            if job_description_file.type == "application/pdf":
                job_description_text = extract_text_from_pdf(job_description_file)
            else:
                job_description_text = extract_text_from_docx(job_description_file)
 
            # Loop through each resume
            for resume_file in resume_files:
                st.markdown(f"---\n### Results for: {resume_file.name}")
 
                # Extract resume text
                if resume_file.type == "application/pdf":
                    resume_text = extract_text_from_pdf(resume_file)
                else:
                    resume_text = extract_text_from_docx(resume_file)
 
                # Parse and clean resume
                parsed_resume_text = parse_resume(resume_text)
                parsed_resume = clean_json(parsed_resume_text)
 
                # Evaluate suitability
                parsed_resume_json_str = json.dumps(parsed_resume)
                evaluation_result_text = evaluate_candidate(parsed_resume_json_str, job_description_text)
                result = clean_json(evaluation_result_text)
 
                # Display parsed info
                st.subheader("Parsed Resume")
                st.json(parsed_resume)
 
                # Display evaluation
                st.subheader("Evaluation Result")
                if result.get("Match", "").lower() == "yes":
                    st.success(f"✅ Candidate is suitable.\n**Reasoning:** {result.get('Reasoning', '')}")
                elif result.get("Match", "").lower() == "no":
                    st.error(f"❌ Candidate is not suitable.\n**Reasoning:** {result.get('Reasoning', '')}")
                else:
                    st.warning("Could not determine match. Please review the result manually.")
                    st.json(result)
    else:
        st.warning("Please upload both candidate resumes and the job description.")
