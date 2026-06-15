import json
import os
from http.server import BaseHTTPRequestHandler
from openai import OpenAI
import fitz  # PyMuPDF

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        # 1. Read the incoming request
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        request_body = json.loads(post_data)
        
        subject = request_body.get('subject', 'Physics')
        test_type = request_body.get('type', 'SAT')
        
        # 2. Locate the specific subject folder
        base_dir = os.getcwd()
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

        # Fallback if no PDF data found
        if not book_text.strip():
            book_text = f"General Class 8 syllabus for {subject}."

        # 4. Connect to OpenRouter
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=os.environ.get("OPENROUTER_API_KEY"),
        )
        
        # 5. Build the prompt
        prompt = f"Create a {test_type} exam for Class 8 {subject} using ONLY this textbook context: {book_text[:20000]}. "
        if test_type == "SAT":
            prompt += "Make it exactly 5 questions (25 marks style)."
        else:
            prompt += "Make it a full exam (80 marks style)."
            
        # 6. Generate the test
        try:
            response = client.chat.completions.create(
                model="openai/gpt-4o-mini",
                response_format={ "type": "json_object" },
                messages=[
                    {"role": "system", "content": "You are a strict ICSE examiner. Output JSON exactly like this: {\"questions\": [{\"q\": \"Question text here?\", \"a\": \"Detailed explanation here.\"}]}"},
                    {"role": "user", "content": prompt}
                ]
            )
            ai_output = response.choices[0].message.content
        except Exception as e:
            ai_output = json.dumps({"questions": [{"q": "Error loading AI", "a": str(e)}]})
        
        # 7. Send back to the website
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(ai_output.encode('utf-8'))
