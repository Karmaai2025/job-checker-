import os
import json
import google.generativeai as genai
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import PyPDF2
import docx
from dotenv import load_dotenv # Uncomment if you are using a local .env file

# --- Setup and Configuration ---

# Load environment variables (optional, but good practice for local development)
load_dotenv()

# Initialize the Flask application
app = Flask(__name__)
# Enable Cross-Origin Resource Sharing (CORS)
CORS(app)

# Configure the Gemini AI model
try:
    # IMPORTANT: Ensure your GEMINI_API_KEY environment variable is set.
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        # In a development environment, you might need to set this directly for testing
        # api_key = "YOUR_API_KEY_HERE" # DO NOT hardcode this in production
        raise ValueError("GEMINI_API_KEY not found. Please set it as an environment variable.")
    genai.configure(api_key=api_key)
    
    # Using the stable model name that fixed the 404 error
    model = genai.GenerativeModel('gemini-2.5-flash')
    print("Gemini AI model configured successfully.")
except Exception as e:
    print(f"⚠️ Warning: Could not configure Gemini AI. {e}")
    model = None

# --- Helper Functions for Text Extraction ---

def extract_text_from_pdf(file_stream):
    """Extracts text from a PDF file stream."""
    try:
        # PyPDF2 expects the file stream to be at the start
        file_stream.seek(0)
        pdf_reader = PyPDF2.PdfReader(file_stream)
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text() or ""
        return text
    except Exception as e:
        print(f"Error reading PDF: {e}")
        return None

def extract_text_from_docx(file_stream):
    """Extracts text from a DOCX file stream."""
    try:
        # docx.Document reads directly from the stream
        file_stream.seek(0)
        document = docx.Document(file_stream)
        text = "\n".join([para.text for para in document.paragraphs])
        return text
    except Exception as e:
        print(f"Error reading DOCX: {e}")
        return None

def get_text_from_file(file):
    """Determines file type and calls the appropriate text extraction function."""
    # Check if the file is present before accessing attributes
    if not file or not file.filename:
        return None

    filename = file.filename.lower()
    if filename.endswith('.pdf'):
        return extract_text_from_pdf(file.stream)
    elif filename.endswith('.docx'):
        return extract_text_from_docx(file.stream)
    else:
        return None

# --- AI Evaluation Function ---

def evaluate_with_gemini(job_description_text, document_text):
    """Sends job and document text to Gemini for evaluation."""
    if not model:
        raise ConnectionError("Gemini AI model is not configured. Check API key.")

    prompt = f"""
    SYSTEM_INSTRUCTION: Your ONLY output must be a JSON object that strictly conforms to the required schema. Do not include any other text, explanations, or markdown fences.
    
    TASK: You are an expert HR professional and resume analyst. Analyze the following candidate document against the provided job description.

    The JSON object must contain these exact keys: "parsed_resume" (object) and "evaluation" (object).

    The "parsed_resume" object should extract key information like "Name", "Contact", "Skills", and "Experience" from the candidate document.

    The "evaluation" object must contain:
    1. "Match": A simple "Yes" or "No" indicating if the candidate is a good fit.
    2. "Reasoning": A concise, one-paragraph explanation for your decision, highlighting key strengths/weaknesses relative to the job.

    **Job Description:**
    ---
    {job_description_text}
    ---

    **Candidate Document:**
    ---
    {document_text}
    ---
    """
    
    # FIX: Removed the unsupported 'system_instruction' argument and integrated its content into the main prompt for broader compatibility.
    response = model.generate_content(
        prompt,
        generation_config={
            "response_mime_type": "application/json",
        }
    )
    
    try:
        # The response text should already be clean JSON due to the response_mime_type setting
        return json.loads(response.text.strip())
    except json.JSONDecodeError:
        print(f"Error: Gemini AI returned a non-JSON response: {response.text}")
        raise ValueError("The AI model returned a response that was not in the expected JSON format.")


# --- Flask API Endpoints ---

@app.route('/')
def serve_index():
    """Serves the main index.html file."""
    # This assumes your frontend file is named index.html
    return send_from_directory('.', 'index.html')

@app.route('/evaluate', methods=['POST'])
def evaluate_candidates():
    """API endpoint to receive files and return AI evaluations."""
    if 'jobDescription' not in request.files or 'resumes' not in request.files:
        return jsonify({"error": "Missing job description or resume files"}), 400

    job_desc_file = request.files['jobDescription']
    # Use getlist for 'resumes' as the frontend sends multiple files under this key
    resume_files = request.files.getlist('resumes')
    
    job_desc_text = get_text_from_file(job_desc_file)
    if not job_desc_text:
        return jsonify({"error": f"Could not read job description file: {job_desc_file.filename}"}), 400

    results = []
    for resume_file in resume_files:
        print(f"Processing document: {resume_file.filename}")
        document_text = get_text_from_file(resume_file)
        
        if not document_text:
            results.append({"filename": resume_file.filename, "error": "Could not read or parse file content."})
            continue

        try:
            evaluation_data = evaluate_with_gemini(job_desc_text, document_text)
            results.append({
                "filename": resume_file.filename,
                "parsed_resume": evaluation_data.get("parsed_resume", {}),
                "evaluation": evaluation_data.get("evaluation", {})
            })
        except (ValueError, json.JSONDecodeError) as e:
            # Catches errors from non-JSON responses from the AI
            print(f"Data processing error for {resume_file.filename}: {e}")
            results.append({"filename": resume_file.filename, "error": f"AI response was malformed. Details: {str(e)}"})
        except Exception as e:
            # Catches other errors during the AI call (e.g., API errors, connection issues)
            print(f"Error during AI evaluation for {resume_file.filename}: {e}")
            results.append({"filename": resume_file.filename, "error": f"AI evaluation failed. Details: {str(e)}"})

    return jsonify(results)

# --- Main Execution ---

if __name__ == '__main__':
    # You might need to install 'waitress' for production use: pip install waitress
    # For simplicity, we use Flask's default server for this guide.
    print("Running Flask server on http://127.0.0.1:5000")
    app.run(host='0.0.0.0', port=5000, debug=True)
