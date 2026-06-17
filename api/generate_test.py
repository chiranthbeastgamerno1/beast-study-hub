import json
import os
import traceback
from http.server import BaseHTTPRequestHandler
from openai import OpenAI
from pdfminer.high_level import extract_text

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            request_body = json.loads(post_data)
            
            action = request_body.get('action', 'generate')
            subject = request_body.get('subject', 'mathematics').lower()
            
            # Bulletproof Vercel Folder Pathing
            project_root = os.getcwd()
            subject_dir = os.path.join(project_root, 'data', subject)
            if not os.path.exists(subject_dir):
                subject_dir = os.path.join(project_root, '..', 'data', subject)
            
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

            # ACTION 2: The Pure Python Reading Engine
            selected_chapters = request_body.get('chapters', ['all'])
            clean_selected = [c.strip() for c in selected_chapters]
            
            book_text = ""
            diagnostic_log = []
            
            if os.path.exists(subject_dir):
                for filename in os.listdir(subject_dir):
                    if 'all' in clean_selected or filename.strip() in clean_selected:
                        if filename.endswith(".pdf"):
                            pdf_path = os.path.join(subject_dir, filename)
                            file_size = os.path.getsize(pdf_path)
                            diagnostic_log.append(f"[{filename}: {file_size} bytes]")
                            
                            try:
                                # Vercel-safe PDF extraction
                                extracted = extract_text(pdf_path)
                                if extracted and extracted.strip():
                                    book_text += extracted + "\n"
                                    diagnostic_log.append("[Text Extracted Successfully]")
                                else:
                                    diagnostic_log.append("[Read 0 Words - This is a Scanned Image PDF]")
                            except Exception as pdf_err:
                                diagnostic_log.append(f"[Read Error: {str(pdf_err)}]")
            else:
                raise FileNotFoundError(f"Vercel Server could not locate the folder: {subject_dir}")

            # THE DIAGNOSTIC CHECK
            if not book_text.strip():
                log_str = " ".join(diagnostic_log)
                raise ValueError(f"PDF extraction failed. Diagnostics: {log_str}. If it says 'Scanned Image PDF', your textbook is just photographs of pages. You must convert it using a free online OCR tool, or provide a text-based digital PDF.")

            # Connect to Groq API
            api_key = os.environ.get("GROQ_API_KEY")
            if not api_key:
                raise ValueError("GROQ_API_KEY missing from Vercel.")
            
            client = OpenAI(
                base_url="https://api.groq.com/openai/v1", 
                api_key=api_key
            )
            
            # Apply your strict grading rules
            if subject == 'mathematics':
                system_rule = "Create exactly 25 Multiple Choice Questions (MCQ). Total 25 marks. Each question is worth 1 mark. Every question MUST have exactly 4 options."
                json_format = """{"questions": [{"type": "mcq", "marks": 1, "q": "Question text?", "options": ["A. ...", "B. ...", "C. ...", "D. ..."], "a": "Correct Option + Explanation"}]}"""
            else:
                system_rule = "Total 25 marks. Section A: 5 Multiple Choice Questions (MCQ) worth 1 mark each. Every MCQ MUST have exactly 4 options. Section B: Subjective/Descriptive questions totaling exactly 20 marks (e.g., four 5-mark questions or five 4-mark questions)."
                json_format = """{"questions": [{"type": "mcq", "marks": 1, "q": "Question text?", "options": ["A. ...", "B. ...", "C. ...", "D. ..."], "a": "Correct Option + Explanation"}, {"type": "subjective", "marks": 5, "q": "Question text?", "a": "Detailed Answer"}]}"""

            prompt = f"Subject: {subject.capitalize()}.\nRules: {system_rule}\nExtract all context ONLY from this text: {book_text[:15000]}.\nOutput JSON matching this exact structure: {json_format}"
                
            # Groq Generation
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
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
                "questions": [{"type": "error", "marks": 0, "q": f"System Alert: {str(e)}", "a": f"Backend Logs:\n{error_details}"}]
            })
        
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(ai_output.encode('utf-8'))
