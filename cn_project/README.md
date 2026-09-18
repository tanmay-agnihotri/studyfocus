# StudyFocus

**A student-built network protocol project that grew into a complete, distraction-free study platform.**

Built by Aditi Raj — B.Tech CSE (AI/ML), VIT Bhopal.

---

## Why this exists

This project didn't start as a study app. It started as a Computer Networks assignment, with one
goal: build something that actually demonstrates how the internet's plumbing works, instead of
another Wireshark screenshot or a basic socket chat app.

It ended up becoming something I genuinely use myself.

## How it evolved — the real timeline

**1. A transport protocol from raw sockets.**
Before touching anything application-level, I built a custom reliable transport protocol on top
of plain UDP — a 3-way handshake, sequencing, retransmission on packet loss, a sliding window,
and a real AIMD congestion-control algorithm (the same slow-start / congestion-avoidance /
multiplicative-decrease idea TCP itself uses). I deliberately simulated packet loss to prove the
retransmission logic actually works, and plotted the congestion window over time to produce the
classic "AIMD sawtooth" graph every networking textbook shows — except this one came from code I
wrote, not a diagram I copied.

*(`/protocol`)*

**2. A real network gateway.**
Next came a forward proxy — the same architectural pattern ISPs, schools, and corporate networks
use for content filtering and data quotas. It started simple (domain blocklist, byte-based quota,
a captive-portal page) and at one point grew into a full TLS-interception (MITM) proxy with a
self-signed certificate authority, dynamic per-site certificate generation, and live HTTPS request
inspection — genuinely advanced territory for a student project. That version taught a lot (and
broke a lot, in the way real infrastructure work does), and ultimately I made a deliberate
architecture call: **an allowlist-based model is both simpler and a better fit for the actual goal**
— letting only approved study sites through, rather than trying to inspect and classify every
byte of encrypted traffic.

*(`/gateway`)*

**3. Turning "network filtering" into something a student would actually want to use.**
A proxy that just blocks things isn't useful on its own — so it grew a real product layer:
per-domain time tracking with proper session/dwell-time logic (not just summing download
durations, which massively undercounts real browsing), age-appropriate allowlists (6-12, 13-18,
18-25) with per-site time limits (YouTube capped at 1 hour for younger students, unlimited for
older ones), a task list with self-controlled stopwatches per task, a Pomodoro timer, and — instead
of just telling a distracted student "no" — a set of actual brain-break mini-games (trivia, word
scramble, emoji riddles, sentence builder) so a study break doesn't have to mean opening Instagram.

*(`/dashboard`)*

**4. An AI tutor that teaches instead of answering.**
The last piece was a RAG-powered (Retrieval-Augmented Generation) study chatbot — but built around
a specific belief: a chatbot that just gives students the answer isn't actually helping them learn.

*(`/chatbot`)*

## What makes this chatbot different from "just wire up an LLM"

Most student chatbot projects are a thin wrapper: send the question to an API, print the answer.
This one is built around real pedagogy and real safety constraints:

- **It won't just answer.** The system prompt enforces a Socratic teaching sequence: clarify the
  topic → ask the student easy warm-up questions → let them attempt the real problem → review
  their attempt specifically → *then* give the final explanation, tied back to what they tried.
  A student who explicitly says "just give me the answer" gets one immediately — the method
  adapts, it isn't rigid.
- **It's grounded in the student's own notes**, not just general knowledge — notes are chunked
  and retrieved with TF-IDF similarity (a deliberate choice over a neural embedding model, since
  it needs no external model download and works identically every time, which matters for a demo
  that has to be reliable).
- **It's scope-locked to studying, with two independent enforcement layers** — a keyword
  pre-filter that blocks obvious off-topic requests before the LLM is ever called (so a clever
  prompt can't argue its way past it), plus a strict instruction layer in the system prompt for
  anything more ambiguous.
- **It's bilingual** — replies in whichever language the student used (English, Hindi, or
  Hinglish), with matching text-to-speech and speech-to-text, so a student who's more comfortable
  thinking in Hindi doesn't have to translate their doubt into English first.
- **It recommends real resources**, not invented links — a small curated map of topics to
  trusted explanation pages, YouTube tutorials, and practice problems, all pointing to domains
  already on the study allowlist, so a recommendation never sends a student somewhere the
  proxy would then block.
- **Voice is a real two-way conversation, not a read-aloud button** — start voice mode, speak
  a question, hear the answer spoken back, and the microphone automatically starts listening
  again for your follow-up — a continuous spoken dialogue instead of typing.

## Project structure

```
cn_project/
├── protocol/       Custom UDP-based transport protocol + AIMD congestion control
├── gateway/         StudyFocus proxy - allowlist filtering, per-site time limits
├── dashboard/        Onboarding, task list, Pomodoro, brain-break games, live usage tracking
└── chatbot/
    ├── backend/       FastAPI + RAG retrieval + Groq LLM + Socratic teaching + scope enforcement
    └── (chat UI is integrated into dashboard.html as the "AI Tutor" tab)
```

## Running it locally

**1. The network proxy** (blocks distracting sites, tracks study time):
```
cd gateway
python3 proxy_server.py
```
Then point your system's HTTP/HTTPS proxy at `127.0.0.1:8888` (steps are also in-app, under the
Setup Guide tab).

**2. The AI tutor backend:**
```
cd chatbot/backend
pip install -r requirements.txt
cp .env.example .env   # then add your free Groq API key
uvicorn main:app --reload --port 8000
```

**3. Open `dashboard/dashboard.html`** in your browser — that's the whole app: dashboard, AI
tutor, and setup guide, all in one page.

## What's genuinely deployable vs. what has to stay local

Being upfront about this, because it's an architecture decision, not a limitation I didn't notice:
a proxy that intercepts a device's network traffic **cannot** run as a hosted website — no browser
can reach into another device's system network settings, for the same reason no legitimate website
can silently take over your internet connection. This is true of every real tool in this space
(Pi-hole, parental-control software, enterprise firewalls) — they all run locally, by design.

- **The dashboard UI** is a static site and deploys cleanly to Vercel.
- **The AI tutor backend** is a normal stateless API and deploys cleanly to Render.
- **The proxy** runs on each student's own machine, the same way Pi-hole or a school's real
  content filter does — this is the correct production architecture, not a workaround.

## Tech stack

Python (raw sockets, `http.server`, `ssl`, `cryptography`), FastAPI, scikit-learn (TF-IDF
retrieval), Groq (LLM), the browser's native Web Speech API (voice, zero cost), vanilla
JS/HTML/CSS for the frontend (no framework/build step, by choice — reliability over polish
for a project built under real time pressure).