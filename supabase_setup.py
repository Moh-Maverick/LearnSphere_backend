import os
from supabase import create_client, Client

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://ldqqpeeugvujfynwalzj.supabase.co")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxkcXFwZWV1Z3Z1amZ5bndhbHpqIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MTA5NjYyNiwiZXhwIjoyMDY2NjcyNjI2fQ.vDivZw-nyo5GPLGvSzqockrdwhQs20gp8IpvhF1zM1E")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY) 