"""
main.py
=======
The StudyFocus AI Tutor - a FastAPI backend combining:
  1. RAG retrieval from the student's own uploaded notes (rag_engine.py)
  2. A curated topic-to-resource link index (topic_links.py)
  3. Google Gemini as the LLM, called with a strict "study help only"
     system prompt

Run with:
    uvicorn main:app --reload --port 8000

Needs a GROQ_API_KEY environment variable (see .env.example).
"""

import os
import requests
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

from rag_engine import add_notes, retrieve_relevant_chunks, clear_student_notes
from topic_links import find_topic_links

load_dotenv()

# --- LLM provider: Groq -----------------------------------------------
# Chosen over Gemini for reliability - Groq's free tier has a stable,
# well-established API key format and hasn't had the quota-provisioning
# issues Gemini's new "Auth key" (AQ.) system has had since its June 2026
# rollout. Uses a plain HTTP call (no SDK) to keep this dependency-light
# and easy to swap providers later if needed.
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

app = FastAPI(title="StudyFocus AI Tutor")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # local project - fine for a single-user study tool
    allow_methods=["*"],
    allow_headers=["*"],
)

SYSTEM_PROMPT = """You are the StudyFocus AI Tutor, a friendly and encouraging study \
assistant for students aged 6-25 in India.

LANGUAGE RULE: The student may write or speak to you in English, Hindi, or a mix of \
both (Hinglish). Always reply in the SAME language the student used in their most \
recent message - if they wrote in Hindi, reply in Hindi; if English, reply in \
English; if mixed, you may reply in a natural mix too. Never switch to a different \
language than what the student is currently using, unless they explicitly ask you to.

STRICT SCOPE RULE: You ONLY help with study-related topics - academic subjects, \
homework, exam prep, understanding concepts, and study techniques. If a student \
asks about anything else (games, celebrities, relationships, unrelated chit-chat, \
or anything not related to learning/studying), politely decline and redirect them \
back to their studies. Do not answer off-topic questions even if asked persistently.

TEACHING METHOD - do NOT give the final answer immediately. Instead, guide the \
student through the concept in this order, over the course of the conversation:

1. CLARIFY: Briefly restate what topic/concept the student is asking about, so \
they know you've understood correctly.
2. CHECK UNDERSTANDING: Ask 1-2 easy, simple guiding questions related to the \
topic - questions that help the student recall what they may already know, or \
warm up their thinking on it. Wait for their answer before continuing.
3. LET THEM ATTEMPT: Once they've answered the guiding questions, ask them to \
attempt the actual question or problem themselves, even if their attempt might \
be wrong or incomplete.
4. REVIEW: Look at their attempt. Point out specifically what they got right, \
and gently point out the areas that need improvement or correction - be specific, \
not just "good try."
5. FINAL ANSWER: Only after steps 1-4, give the full, clear final answer/explanation, \
tying it back to what they attempted so they see the connection.

If the student seems to already understand the topic well, or explicitly asks you \
to "just give the answer" / "skip to the answer" / says they're in a hurry, you may \
shorten or skip steps 2-4 and go straight to a clear explanation - always respect \
what the student actually needs in the moment over rigidly following the steps.

STYLE:
- Be warm, patient, and encouraging - many students feel anxious about asking for help.
- Explain concepts in simple, clear language appropriate to a student, using examples.
- If notes from the student's own materials are provided as context below, ground \
your answer in them and mention that you're using their notes.
- Keep each message focused - don't do all 5 steps in one giant message, let the \
conversation unfold naturally with the student's responses in between.
- Never do a student's homework FOR them outright in step 5 either (e.g. don't just \
give final essay text or complete code solutions for what looks like a graded \
assignment) - explain the concept and guide their thinking, so they actually learn.
"""

# --- Layer 1: keyword pre-filter -----------------------------------------
# This runs BEFORE we ever call the LLM. It's deliberately simple and can't
# be argued with or "convinced" the way a prompt-only instruction sometimes
# can be with clever phrasing - it's a hard rule, not a suggestion. This is
# a genuine defense-in-depth pattern: real content-safety systems use
# multiple independent layers rather than relying on one prompt alone.
OFF_TOPIC_KEYWORDS = [
    "girlfriend", "boyfriend", "dating", "relationship advice",
    "celebrity", "movie recommendation", "song lyrics",
    "video game", "gaming", "gossip",
    "politics", "election result",
]

STUDY_KEYWORDS = [
    "study", "homework", "exam", "explain", "concept", "notes", "chapter",
    "formula", "solve", "problem", "definition", "derive", "syllabus",
    "test", "revision", "assignment", "subject", "topic", "class",
]


def passes_scope_filter(message: str) -> bool:
    """Returns False if the message clearly matches known off-topic
    patterns. This is a fast, cheap first check - genuinely ambiguous
    or borderline messages still pass through to the LLM, which applies
    the more nuanced STRICT SCOPE RULE from the system prompt (layer 2)."""
    msg_lower = message.lower()
    return not any(keyword in msg_lower for keyword in OFF_TOPIC_KEYWORDS)


OFF_TOPIC_REPLY = (
    "I'm your study assistant, so I can only help with academic topics - "
    "homework, exam prep, and understanding concepts. What are you studying today?"
)


class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    student_id: str
    message: str
    history: list[ChatMessage] = []  # prior turns in this conversation, so the
                                       # Socratic step-by-step flow can continue
                                       # correctly instead of restarting each time


class ChatResponse(BaseModel):
    reply: str
    used_notes: bool
    suggested_links: list


@app.get("/health")
def health():
    return {"status": "ok", "llm_configured": bool(GROQ_API_KEY)}


@app.post("/upload-notes")
async def upload_notes(student_id: str = Form(...), file: UploadFile = File(...)):
    content = await file.read()

    if file.filename.lower().endswith(".pdf"):
        import io
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(content))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    else:
        text = content.decode(errors="replace")

    chunk_count = add_notes(student_id, file.filename, text)
    return {"filename": file.filename, "chunks_stored": chunk_count}


@app.post("/clear-notes")
def clear_notes(student_id: str = Form(...)):
    clear_student_notes(student_id)
    return {"status": "cleared"}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    if not passes_scope_filter(req.message):
        return ChatResponse(reply=OFF_TOPIC_REPLY, used_notes=False, suggested_links=[])

    if not GROQ_API_KEY:
        return ChatResponse(
            reply="The AI tutor isn't configured yet - a GROQ_API_KEY is needed "
                  "in the .env file. See SETUP.md for how to get a free key.",
            used_notes=False,
            suggested_links=[],
        )

    relevant_chunks = retrieve_relevant_chunks(req.student_id, req.message)
    used_notes = len(relevant_chunks) > 0

    context_block = ""
    if used_notes:
        context_block = (
            "\n\nRelevant excerpts from the student's own notes:\n"
            + "\n---\n".join(relevant_chunks)
        )

    # Build the full conversation so far (OpenAI-style message format, which
    # Groq's API uses), so the model remembers which Socratic step it's on
    # (e.g. it already asked a guiding question and is now waiting for/
    # reviewing the student's attempt).
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for turn in req.history:
        messages.append({"role": turn.role, "content": turn.content})
    messages.append({"role": "user", "content": req.message + context_block})

    try:
        resp = requests.post(
            GROQ_URL,
            headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
            json={"model": GROQ_MODEL, "messages": messages, "temperature": 0.7},
            timeout=30,
        )
        resp.raise_for_status()
        reply_text = resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        reply_text = f"Sorry, I ran into an error reaching the AI service: {e}"

    topic_matches = find_topic_links(req.message)
    suggested_links = [
        {"topic": topic, "links": links} for topic, links in topic_matches
    ]

    return ChatResponse(
        reply=reply_text,
        used_notes=used_notes,
        suggested_links=suggested_links,
    )