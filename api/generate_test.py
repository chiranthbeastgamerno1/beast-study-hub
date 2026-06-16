import json
import os
import traceback
from http.server import BaseHTTPRequestHandler
from openai import OpenAI
from pypdf import PdfReader

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            request_body = json.loads(post_data)
            
            action = request_body.get('action', 'generate')
            subject = request_body.get('subject', 'Mathematics').lower()
            
            # Mathematically locate the data folder
            current_dir = os.path.dirname(os.path.abspath(__file__))
            base_dir = os.path.dirname(current_dir) 
            subject_dir = os.path.join(base_dir, 'data', subject)
            
            # ACTION 1: Dynamic Chapter Fetching
            if action == 'get_chapters':
                chapters = []
                if os.path.exists(subject_dir):
                    chapters = [f for f in os.listdir(subject_dir) if f.endswith(".pdf")]
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({"chapters": chapters}).encode('utf-8'))
                return

            # ACTION 2: Generate the Test
            selected_chapters = request_body.get('chapters', ['all'])
            book_text = ""
            
            if os.path.exists(subject_dir):
                for filename in os.listdir(subject_dir):
                    if 'all' in selected_chapters or filename in selected_chapters:
                        if filename.endswith(".pdf"):
                            try:
                                reader = PdfReader(os.path.join(subject_dir, filename))
                                for page in reader.pages:
                                    extracted = page.extract_text()
                                    if extracted:
                                        book_text += extracted + "\n"
                            except Exception as pdf_err:
                                print(f"Error reading {filename}: {pdf_err}")

            # Connect to Groq API
            api_key = os.environ.get("GROQ_API_KEY")
            if not api_key:
                raise ValueError("GROQ_API_KEY missing from Vercel.")
            
            client = OpenAI(
                base_url="https://api.groq.com/openai/v1", 
                api_key=api_key
            )
            
            # Apply strict grading rules
            if subject == 'mathematics':
                system_rule = "Create exactly 25 Multiple Choice Questions (MCQ). Total 25 marks. Each question is worth 1 mark. Every question MUST have exactly 4 options."
                json_format = """{"questions": [{"type": "mcq", "marks": 1, "q": "Question text?", "options": ["A. ...", "B. ...", "C. ...", "D. ..."], "a": "Correct Option + Explanation"}]}"""
            else:
                system_rule = "Total 25 marks. Section A: 5 Multiple Choice Questions (MCQ) worth 1 mark each. Every MCQ MUST have exactly 4 options. Section B: Subjective/Descriptive questions totaling exactly 20 marks (e.g., four 5-mark questions or five 4-mark questions)."
                json_format = """{"questions": [{"type": "mcq", "marks": 1, "q": "Question text?", "options": ["A. ...", "B. ...", "C. ...", "D. ..."], "a": "Correct Option + Explanation"}, {"type": "subjective", "marks": 5, "q": "Question text?", "a": "Detailed Answer"}]}"""

            prompt = f"Subject: {subject.capitalize()}.\nRules: {system_rule}\nExtract all context ONLY from this text: {book_text[:15000]}.\nOutput JSON matching this exact structure: {json_format}"
                
            # Using Meta's massive Llama 3 model
            response = client.chat.completions.create(
                model="llama3-70b-8192",
                response_format={ "type": "json_object" },
                messages=[
                    {"role": "system", "content": "You are a precise ICSE examiner. Follow JSON format perfectly."},
                    {"role": "user", "content": prompt}
                ]
            )
            ai_output = response.choices[0].message.content
            
        except Exception as e:
            error_details = traceback.format_exc()
            print(error_details)
            ai_output = json.dumps({
                "questions": [{"type": "error", "marks": 0, "q": f"Backend Crash: {str(e)}", "a": f"Logs:\n{error_details}"}]
            })
        
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(ai_output.encode('utf-8'))
