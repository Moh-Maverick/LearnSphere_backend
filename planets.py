import json
from .supabase_setup import supabase

def handler(request):
    # Only allow GET and POST
    if request.method == "GET":
        # Auth
        auth = request.headers.get("authorization")
        if not auth:
            return (401, {}, json.dumps({"error": "Missing token"}))
        token = auth.replace("Bearer ", "")
        user = supabase.auth.api.get_user(token)
        if not user or not user.get("id"):
            return (401, {}, json.dumps({"error": "Invalid token"}))
        user_id = user["id"]
        res = supabase.table("planets").select("*").eq("user_id", user_id).execute()
        return (200, {}, json.dumps(res.data))
    elif request.method == "POST":
        auth = request.headers.get("authorization")
        if not auth:
            return (401, {}, json.dumps({"error": "Missing token"}))
        token = auth.replace("Bearer ", "")
        user = supabase.auth.api.get_user(token)
        if not user or not user.get("id"):
            return (401, {}, json.dumps({"error": "Invalid token"}))
        user_id = user["id"]
        body = request.json()
        name = body.get("name")
        color = body.get("color", "#fff")
        res = supabase.table("planets").insert({"user_id": user_id, "name": name, "color": color}).execute()
        return (200, {}, json.dumps(res.data[0]))
    else:
        return (405, {}, json.dumps({"error": "Method not allowed"})) 