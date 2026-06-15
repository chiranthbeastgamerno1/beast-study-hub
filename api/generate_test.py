import json
import os
from http.server import BaseHTTPRequestHandler
from openai import OpenAI
import fitz  # This is PyMuPDF

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        # 1. Read the incoming request
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        request_body = json.loads(post_data)
        
        subject = request_body.get('subject', 'Physics')
        test_type = request_body.get('type', 'SAT')
        
        # 2. Locate the specific subject folder
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        subject_dir = os.path.join(base_dir, 'data', subject.lower())
        
        book_text = ""
        
        # 3. Read ALL PDF files inside that folder
        if os.path.exists(subject_dir):
            for filename in os.listdir(subject_dir):
                if filename.endswith(".pdf"):
                    pdf_path = os.path.join(subject_dir, filename)
                    try:
                        doc = fitz.open(pdf_path)
                        for page in doc:
                            book_text += page.get_text() + "\n"
                        doc.close()
                    except Exception as e:
                        print(f"Error reading {filename}: {e}")

        # If no PDFs are found, fallback to AI's general brain
        if not book_text.strip():
            book_text = f"No PDF data found. Use your general ICSE Class 8 knowledge for {subject}."

        # 4. Connect to OpenAI
        client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        
        # 5. Instruct the AI (Limiting text size to prevent crashing the API)
        prompt = f"Create a {test_type} exam for Class 8 {subject} using ONLY this textbook context: {book_text[:100000]}. "
        if test_type == "SAT":
            prompt += "Make it short (25 marks style)."
        else:
            prompt += "Make it a full exam (80 marks style)."
            
        # 6. Generate the test
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            response_format={ "type": "json_object" },
            messages=[
                {"role": "system", "content": "You are a strict ICSE examiner. Output JSON exactly like this: {\"questions\": [{\"q\": \"Question text here?\", \"a\": \"Detailed explanation here.\"}]}"},
                {"role": "user", "content": prompt}
            ]
        )
        
        ai_output = response.choices[0].message.content
        
        # 7. Send back to the website
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(ai_output.encode('utf-8'))