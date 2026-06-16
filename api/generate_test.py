import json
import os
import traceback
from http.server import BaseHTTPRequestHandler
from openai import OpenAI
from pypdf import PdfReader # Safer, pure Python library for Vercel

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            # 1. Read request from front-end
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            request_body = json.loads(post_data)
            
            subject = request_body.get('subject', 'Mathematics').lower()
            selected_chapters = request_body.get('chapters', ['all'])
            
            # 2. Bulletproof Path Resolution for Vercel Serverless
            # This mathematically finds the "data" folder relative to this exact python file
            current_dir = os.path.dirname(os.path.abspath(__file__))
            base_dir = os.path.dirname(current_dir) 
            subject_dir = os.path.join(base_dir, 'data', subject)
            
            book_text = ""
            
            # 3. Read PDFs using the safe PyPDF library
            if os.path.exists(subject_dir):
                for filename in os.listdir(subject_dir):
                    if 'all' in selected_chapters or filename in selected_chapters:
                        if filename.endswith(".pdf"):
                            pdf_path = os.path.join(subject_dir, filename)
                            try:
                                reader = PdfReader(pdf_path)
                                for page in reader.pages:
                                    extracted = page.extract_text()
                                    if extracted:
                                        book_text += extracted + "\n"
                            except Exception as pdf_err:
                                print(f"File skipped due to error: {filename} - {pdf_err}")

            # 4. Critical API Key Check
            api_key = os.environ.get("OPENROUTER_API_KEY")
            if not api_key:
                raise ValueError("The OPENROUTER_API_KEY is completely missing from Vercel Environment Variables.")
            
            # 5. Connect to OpenRouter
            client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=api_key,
            )
            
            prompt = f"Generate 5 challenging questions for {subject.capitalize()} based strictly on this exact textbook content: {book_text[:15000]}. Provide the questions and a highly detailed answer key."
                
            # 6. Contact GPT-4o
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
            # 7. ULTIMATE FAILSAFE: If anything breaks, print the exact error to the screen
            error_details = traceback.format_exc()
            print(error_details) # Logs to Vercel
            
            # Send the exact crash reason to your front-end UI
            ai_output = json.dumps({
                "questions": [{
                    "q": f"Backend Crash Detected: {str(e)}", 
                    "a": f"Full Error Log for debugging:\n{error_details}"
                }]
            })
        
        # Send data back to your HTML
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(ai_output.encode('utf-8'))
