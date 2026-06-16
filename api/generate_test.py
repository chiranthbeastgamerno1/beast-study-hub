import json
import os
from http.server import BaseHTTPRequestHandler
from openai import OpenAI
import fitz 

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        request_body = json.loads(post_data)
        
        # Get subject and chapters from the front-end UI
        subject = request_body.get('subject', 'Mathematics').lower()
        selected_chapters = request_body.get('chapters', ['all'])
        
        # Locate the specific subject folder
        base_dir = os.getcwd()
        subject_dir = os.path.join(base_dir, 'data', subject)
        
        book_text = ""
        
        # Extract text ONLY from the selected PDF files
        if os.path.exists(subject_dir):
            for filename in os.listdir(subject_dir):
                if 'all' in selected_chapters or filename in selected_chapters:
                    if filename.endswith(".pdf"):
                        pdf_path = os.path.join(subject_dir, filename)
                        try:
                            doc = fitz.open(pdf_path)
                            for page in doc:
                                book_text += page.get_text() + "\n"
                            doc.close()
                        except Exception as e:
                            print(f"Error reading {filename}: {e}")

        # Connect to OpenRouter
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=os.environ.get("OPENROUTER_API_KEY"),
        )
        
        # Force gpt-4o for high reasoning and accurate math/formulas
        prompt = f"Generate 5 challenging questions for {subject.capitalize()} based strictly on this content: {book_text[:20000]}. Provide the questions and a highly detailed answer key."
            
        try:
            response = client.chat.completions.create(
                model="openai/gpt-4o",
                response_format={ "type": "json_object" },
                messages=[
                    {"role": "system", "content": "You are a precise ICSE examiner. Output strictly JSON matching this format: {\"questions\": [{\"q\": \"...\", \"a\": \"...\"}]}"},
                    {"role": "user", "content": prompt}
                ]
            )
            ai_output = response.choices[0].message.content
        except Exception as e:
            ai_output = json.dumps({"questions": [{"q": "System Error: Could not connect to AI.", "a": str(e)}]})
        
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(ai_output.encode('utf-8'))
