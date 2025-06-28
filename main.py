from fastapi import FastAPI, File, UploadFile, Form, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from supabase_setup import supabase
import os
from groq import Groq
from dotenv import load_dotenv
import re
import httpx

app = FastAPI()

# Allow CORS for local frontend dev and deployment
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

load_dotenv()

@app.get("/notes")
async def get_notes(planet_id: str, authorization: str = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing token")
    token = authorization.replace("Bearer ", "")
    user = supabase.auth.get_user(token)
    if not user or not user.user or not user.user.id:
        raise HTTPException(status_code=401, detail="Invalid token")
    user_id = user.user.id
    res = supabase.table("notes").select("*").eq("planet_id", planet_id).eq("user_id", user_id).execute()
    return res.data

@app.post("/notes")
async def upload_note(
    file: UploadFile = File(...),
    planet_id: str = Form(...),
    authorization: str = Header(None)
):
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing token")
    token = authorization.replace("Bearer ", "")
    user = supabase.auth.get_user(token)
    if not user or not user.user or not user.user.id:
        raise HTTPException(status_code=401, detail="Invalid token")
    user_id = user.user.id
    file_path = f"{user_id}/{planet_id}/{file.filename}"
    file_bytes = await file.read()
    supabase.storage.from_("notes").upload(file_path, file_bytes)
    supabase_url = os.environ.get("SUPABASE_URL")
    file_url = f"{supabase_url}/storage/v1/object/public/notes/{file_path}"
    res = supabase.table("notes").insert({
        "planet_id": planet_id,
        "user_id": user_id,
        "title": file.filename,
        "file_url": file_url
    }).execute()
    return res.data[0]

@app.get("/planets")
async def get_planets(authorization: str = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing token")
    token = authorization.replace("Bearer ", "")
    user = supabase.auth.get_user(token)
    if not user or not user.user or not user.user.id:
        raise HTTPException(status_code=401, detail="Invalid token")
    user_id = user.user.id
    res = supabase.table("planets").select("*").eq("user_id", user_id).execute()
    return res.data

@app.post("/planets")
async def create_planet(name: str = Form(...), authorization: str = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing token")
    token = authorization.replace("Bearer ", "")
    user = supabase.auth.get_user(token)
    if not user or not user.user or not user.user.id:
        raise HTTPException(status_code=401, detail="Invalid token")
    user_id = user.user.id
    res = supabase.table("planets").insert({"name": name, "user_id": user_id}).execute()
    return res.data[0]

async def fetch_note_content(note):
    # Try to fetch the actual note content from file_url if available
    file_url = note.get("file_url")
    if file_url:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(file_url)
                if resp.status_code == 200:
                    return resp.text
        except Exception:
            pass
    # Fallback to content/text/body/title
    return note.get("content") or note.get("text") or note.get("body") or note["title"]

@app.post("/ai-tutor")
async def ai_tutor(request: Request, authorization: str = Header(None)):
    data = await request.json()
    question = data.get("question")
    planet_id = data.get("planet_id")
    if not question or not planet_id:
        raise HTTPException(status_code=400, detail="Missing question or planet_id")
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing token")
    token = authorization.replace("Bearer ", "")
    user = supabase.auth.get_user(token)
    if not user or not user.user or not user.user.id:
        raise HTTPException(status_code=401, detail="Invalid token")
    user_id = user.user.id

    # Fetch notes for the subject/planet
    notes_res = supabase.table("notes").select("*").eq("planet_id", planet_id).eq("user_id", user_id).execute()
    # Fetch actual content for each note
    notes_texts = []
    for n in notes_res.data:
        content = await fetch_note_content(n)
        notes_texts.append(content)
    notes_text = "\n\n".join(notes_texts)

    # Truncate to max chars for model context window
    MAX_TOKENS = 120_000  # Safe margin for 131,072 token model
    MAX_CHARS = MAX_TOKENS * 4  # Rough estimate
    if len(notes_text) > MAX_CHARS:
        notes_text = notes_text[:MAX_CHARS]

    # Prepare prompt for Groq AI: allow use of both notes and own knowledge, but reference notes if possible
    prompt = (
        "You are an AI tutor. Use the following notes and your own knowledge to answer the user's question. "
        "If possible, reference the notes in your answer. "
        "Format your answer using Markdown (use bold, lists, and headings where appropriate)."
        "\n\nNotes:\n"
        f"{notes_text}\n\nUser's question: {question}\n\n"
        "Answer using both the notes and your own knowledge, but prefer the notes if relevant."
    )

    # Call Groq AI
    client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
    chat_completion = client.chat.completions.create(
        messages=[
            {"role": "user", "content": prompt}
        ],
        model="deepseek-r1-distill-llama-70b",
    )
    answer = chat_completion.choices[0].message.content
    # Remove <think>...</think> blocks
    answer = re.sub(r"<think>[\s\S]*?</think>", "", answer, flags=re.IGNORECASE).strip()
    return JSONResponse(content={"answer": answer})

@app.post("/quiz-generator")
async def quiz_generator(request: Request, authorization: str = Header(None)):
    data = await request.json()
    planet_id = data.get("planet_id")
    topic = data.get("topic", "")
    if not planet_id:
        raise HTTPException(status_code=400, detail="Missing planet_id")
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing token")
    token = authorization.replace("Bearer ", "")
    user = supabase.auth.get_user(token)
    if not user or not user.user or not user.user.id:
        raise HTTPException(status_code=401, detail="Invalid token")
    user_id = user.user.id

    # Fetch notes for the subject/planet
    notes_res = supabase.table("notes").select("*").eq("planet_id", planet_id).eq("user_id", user_id).execute()
    # Fetch actual content for each note
    notes_texts = []
    for n in notes_res.data:
        content = await fetch_note_content(n)
        notes_texts.append(content)
    notes_text = "\n\n".join(notes_texts)

    # Truncate to max chars for model context window
    MAX_TOKENS = 120_000
    MAX_CHARS = MAX_TOKENS * 4
    if len(notes_text) > MAX_CHARS:
        notes_text = notes_text[:MAX_CHARS]

    # Prepare prompt for Groq AI
    prompt = (
        "You are an AI quiz generator. Use the following notes and your own knowledge to generate 5 multiple-choice questions for the user to test their understanding. "
        "Each question should have 4 options (a, b, c, d) and indicate the correct answer at the end as 'Answer: x'. "
        "If a topic is provided, focus the questions on that topic. "
        "Format the questions exactly as: \n1. Question text\na) Option 1\nb) Option 2\nc) Option 3\nd) Option 4\nAnswer: b\n\n"
        "If possible, reference the notes in your questions.\n\n"
        f"Notes:\n{notes_text}\n\n"
        f"Topic: {topic}\n\n"
        "Generate 5 multiple-choice questions."
    )

    client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
    chat_completion = client.chat.completions.create(
        messages=[
            {"role": "user", "content": prompt}
        ],
        model="deepseek-r1-distill-llama-70b",
    )
    answer = chat_completion.choices[0].message.content
    # Remove <think>...</think> blocks
    answer = re.sub(r"<think>[\s\S]*?</think>", "", answer, flags=re.IGNORECASE).strip()
    return JSONResponse(content={"quiz": answer})

@app.post("/summarize")
async def summarize(request: Request, authorization: str = Header(None)):
    data = await request.json()
    planet_id = data.get("planet_id")
    topic = data.get("topic", "")
    if not planet_id:
        raise HTTPException(status_code=400, detail="Missing planet_id")
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing token")
    token = authorization.replace("Bearer ", "")
    user = supabase.auth.get_user(token)
    if not user or not user.user or not user.user.id:
        raise HTTPException(status_code=401, detail="Invalid token")
    user_id = user.user.id

    # Fetch notes for the subject/planet
    notes_res = supabase.table("notes").select("*").eq("planet_id", planet_id).eq("user_id", user_id).execute()
    # Fetch actual content for each note
    notes_texts = []
    for n in notes_res.data:
        content = await fetch_note_content(n)
        notes_texts.append(content)
    notes_text = "\n\n".join(notes_texts)

    # Truncate to max chars for model context window
    MAX_TOKENS = 120_000
    MAX_CHARS = MAX_TOKENS * 4
    if len(notes_text) > MAX_CHARS:
        notes_text = notes_text[:MAX_CHARS]

    # Prepare prompt for Groq AI
    prompt = (
        "You are an AI summarizer. Summarize the following notes in a concise and clear way, using bullet points or short paragraphs where appropriate. "
        "Focus on the key concepts, facts, and important details.\n\n"
        f"Notes Content:\n{notes_text}\n\n"
        "Summary:"
    )

    client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
    chat_completion = client.chat.completions.create(
        messages=[
            {"role": "user", "content": prompt}
        ],
        model="deepseek-r1-distill-llama-70b",
    )
    answer = chat_completion.choices[0].message.content
    # Remove <think>...</think> blocks
    answer = re.sub(r"<think>[\s\S]*?</think>", "", answer, flags=re.IGNORECASE).strip()
    return JSONResponse(content={"summary": answer})