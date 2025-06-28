import json
import os
from supabase import create_client, Client
from http.server import BaseHTTPRequestHandler
import urllib.parse
import cgi
import io

# Initialize Supabase client
supabase_url = os.environ.get("SUPABASE_URL")
supabase_key = os.environ.get("SUPABASE_ANON_KEY")
supabase: Client = create_client(supabase_url, supabase_key)

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            # Get authorization header
            auth = self.headers.get("authorization")
            if not auth:
                self.send_response(401)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Missing token"}).encode())
                return

            token = auth.replace("Bearer ", "")
            
            # Get user from token
            try:
                user = supabase.auth.get_user(token)
                user_id = user.user.id
            except:
                self.send_response(401)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Invalid token"}).encode())
                return

            # Parse query parameters
            parsed_url = urllib.parse.urlparse(self.path)
            query_params = urllib.parse.parse_qs(parsed_url.query)
            planet_id = query_params.get("planet_id", [None])[0]
            
            if not planet_id:
                self.send_response(400)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Missing planet_id"}).encode())
                return

            # Get notes for the planet
            res = supabase.table("notes").select("*").eq("planet_id", planet_id).eq("user_id", user_id).execute()
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(res.data).encode())

        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())

    def do_POST(self):
        try:
            # Get authorization header
            auth = self.headers.get("authorization")
            if not auth:
                self.send_response(401)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Missing token"}).encode())
                return

            token = auth.replace("Bearer ", "")
            
            # Get user from token
            try:
                user = supabase.auth.get_user(token)
                user_id = user.user.id
            except:
                self.send_response(401)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Invalid token"}).encode())
                return

            # Parse multipart form data
            content_type = self.headers.get('Content-Type', '')
            if not content_type.startswith('multipart/form-data'):
                self.send_response(400)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Content-Type must be multipart/form-data"}).encode())
                return

            # Read the request body
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            
            # Parse multipart data
            environ = {
                'REQUEST_METHOD': 'POST',
                'CONTENT_TYPE': content_type,
                'CONTENT_LENGTH': str(content_length)
            }
            
            fp = io.BytesIO(post_data)
            form = cgi.FieldStorage(fp=fp, environ=environ, headers=self.headers)
            
            # Get form data
            if 'file' not in form or not form['file'].file:
                self.send_response(400)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Missing file"}).encode())
                return

            file_field = form['file']
            planet_id = form.getfirst('planet_id')
            
            if not planet_id:
                self.send_response(400)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Missing planet_id"}).encode())
                return

            # Upload file to Supabase storage
            file_path = f"{user_id}/{planet_id}/{file_field.filename}"
            file_content = file_field.file.read()
            supabase.storage.from_("notes").upload(file_path, file_content)
            
            # Get public URL
            file_url = f"{supabase_url}/storage/v1/object/public/notes/{file_path}"
            
            # Insert note record
            res = supabase.table("notes").insert({
                "planet_id": planet_id,
                "user_id": user_id,
                "title": file_field.filename,
                "file_url": file_url
            }).execute()
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(res.data[0]).encode())

        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode()) 