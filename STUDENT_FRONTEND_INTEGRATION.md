# ClimbUP Student Frontend Integration Guide
## Connecting Student Chatbot to EduRAG Lecture Video RAG Server

This document provides a step-by-step guide to seamlessly connect the **ClimbUP Student Frontend** (Next.js / React) with the live **EduRAG Backend Server** (`https://teacher-lecture-rag-28929614461.asia-south1.run.app` or local `http://127.0.0.1:8000`).

---

## 1. Architecture Overview

```mermaid
graph LR
    A[Student Browser / Next.js] -->|1. Ask Doubt with lesson_id| B[EduRAG Server /api/chat]
    B -->|2. Cosine Vector Search| C[(Supabase pgvector 768-dim)]
    B -->|3. Grounded Prompt with Citations| D[Google Gemini 2.5 Flash]
    D -->|4. Answer with [MM:SS] Badges| B
    B -->|5. JSON with Clickable Timestamps| A
    A -->|6. Click Timestamp| E[HTML5 Video / Drive Player Seeks]
```

### Key Highlights
- **Zero Hallucination:** Answers are 100% grounded in the professor's spoken lecture transcripts.
- **Clickable Timestamps:** Every concept cited contains `[MM:SS]` badges. Clicking the badge seeks the video player right to that exact second.
- **Stateless Cloud Storage:** Videos are hosted on Google Drive / CDN; the server uses minimal bandwidth and zero persistent disk.

---

## 2. Environment Configuration (Next.js)

In your `climbup-nextjs/.env.local` file, add the backend server URL:

```env
# Local Development
NEXT_PUBLIC_RAG_SERVER_URL=http://127.0.0.1:8000

# Production (Google Cloud Run)
# NEXT_PUBLIC_RAG_SERVER_URL=https://teacher-lecture-rag-28929614461.asia-south1.run.app
```

---

## 3. Core API Endpoints

| Endpoint | Method | Purpose | Sample Request Body |
| :--- | :---: | :--- | :--- |
| `/api/chat` | `POST` | Ask doubt on a specific lecture | `{"query": "...", "lesson_id": "..."}` |
| `/api/lessons` | `GET` | List all indexed lectures | None |
| `/api/lessons/{id}` | `GET` | Get lecture metadata & transcript | None |
| `/api/courses` | `GET` | List courses from Supabase | None |
| `/api/status` | `GET` | Check RAG system & Supabase health | None |

### Sample `POST /api/chat` Request & Response

#### Request:
```json
{
  "query": "Explain Round Robin scheduling and what happens if time quantum is too large.",
  "lesson_id": "sample_os_scheduling",
  "session_id": "student_session_123"
}
```

#### Response:
```json
{
  "answer": "Round Robin (RR) is a preemptive CPU scheduling algorithm designed for time-sharing systems [04:21]. If the time quantum is extremely large, Round Robin degrades into First-Come First-Served (FCFS) [07:31].",
  "query": "Explain Round Robin...",
  "lesson_id": "sample_os_scheduling",
  "session_id": "student_session_123",
  "retrieved_evidence": [
    {
      "chunk_index": 3,
      "topic_name": "Round Robin (RR) Algorithm & Time Quantum Effects",
      "timestamp_label": "04:21 - 10:30",
      "start_seconds": 261.0,
      "end_seconds": 630.0,
      "similarity_score": 0.85
    }
  ]
}
```

---

## 4. Production-Ready Next.js React Hook

Save this file as `src/hooks/useLectureRAG.ts` (or `.js`):

```typescript
import { useState, useCallback } from 'react';

const RAG_BASE_URL = process.env.NEXT_PUBLIC_RAG_SERVER_URL || 'http://127.0.0.1:8000';

export interface RetrievedEvidence {
  chunk_index: number;
  topic_name: string;
  timestamp_label: string;
  start_seconds: number;
  end_seconds: number;
  similarity_score: number;
}

export interface ChatMessage {
  id: string;
  sender: 'student' | 'ai';
  text: string;
  evidence?: RetrievedEvidence[];
  timestamp?: string;
}

export function useLectureRAG(lessonId: string) {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'welcome',
      sender: 'ai',
      text: 'Hello! I am your AI Teaching Assistant for this lecture. Ask me any doubt and I will answer with exact video timestamps!'
    }
  ]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const askDoubt = useCallback(async (query: string) => {
    if (!query.trim() || !lessonId) return;

    const studentMsgId = `student-${Date.now()}`;
    const userMessage: ChatMessage = {
      id: studentMsgId,
      sender: 'student',
      text: query,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };

    setMessages((prev) => [...prev, userMessage]);
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`${RAG_BASE_URL}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query,
          lesson_id: lessonId,
          session_id: 'climbup-student-session'
        })
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.detail || `Server returned ${response.status}`);
      }

      const data = await response.json();
      const aiMessage: ChatMessage = {
        id: `ai-${Date.now()}`,
        sender: 'ai',
        text: data.answer,
        evidence: data.retrieved_evidence || [],
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      };

      setMessages((prev) => [...prev, aiMessage]);
    } catch (err: any) {
      console.error('[RAG Client Error]:', err);
      setError(err.message || 'Failed to retrieve answer.');
      setMessages((prev) => [
        ...prev,
        {
          id: `err-${Date.now()}`,
          sender: 'ai',
          text: `⚠️ Error: ${err.message || 'Could not connect to the lecture assistant server. Please ensure the server is online.'}`
        }
      ]);
    } finally {
      setLoading(false);
    }
  }, [lessonId]);

  const clearChat = useCallback(() => {
    setMessages([
      {
        id: 'welcome',
        sender: 'ai',
        text: 'Chat cleared. Ask any doubt about this lecture!'
      }
    ]);
  }, []);

  return {
    messages,
    loading,
    error,
    askDoubt,
    clearChat
  };
}
```

---

## 5. Timestamp Formatter & Video Seeker Helper

Save this file as `src/utils/ragHelpers.ts`:

```typescript
/**
 * Converts HH:MM:SS or MM:SS string into seconds
 */
export function parseTimestampToSeconds(ts: string): number {
  const clean = ts.replace(/[\[\]]/g, '').trim();
  const parts = clean.split(':').map((p) => parseInt(p, 10));
  if (parts.length === 3) {
    return parts[0] * 3600 + parts[1] * 60 + parts[2];
  } else if (parts.length === 2) {
    return parts[0] * 60 + parts[1];
  }
  return 0;
}

/**
 * Splits text into segments, identifying [MM:SS] or [HH:MM:SS] timestamps
 * so React can render them as interactive clickable badges.
 */
export function parseTextWithTimestamps(text: string): Array<{ type: 'text' | 'timestamp'; content: string }> {
  const regex = /\[(\d{1,2}:\d{2}:\d{2}|\d{1,3}:\d{2})\]/g;
  const parts: Array<{ type: 'text' | 'timestamp'; content: string }> = [];
  let lastIndex = 0;
  let match;

  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push({ type: 'text', content: text.substring(lastIndex, match.index) });
    }
    parts.push({ type: 'timestamp', content: match[1] });
    lastIndex = regex.lastIndex;
  }

  if (lastIndex < text.length) {
    parts.push({ type: 'text', content: text.substring(lastIndex) });
  }

  return parts;
}
```

---

## 6. Student Chatbot Component (`LectureChatbot.tsx`)

Create `src/components/LectureChatbot.tsx`:

```tsx
'use client';

import React, { useState, useRef, useEffect } from 'react';
import { useLectureRAG } from '../hooks/useLectureRAG';
import { parseTimestampToSeconds, parseTextWithTimestamps } from '../utils/ragHelpers';

interface LectureChatbotProps {
  lessonId: string;
  onSeekVideo?: (seconds: number) => void;
}

export const LectureChatbot: React.FC<LectureChatbotProps> = ({ lessonId, onSeekVideo }) => {
  const { messages, loading, askDoubt, clearChat } = useLectureRAG(lessonId);
  const [input, setInput] = useState('');
  const chatBottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || loading) return;
    askDoubt(input);
    setInput('');
  };

  const handleTimestampClick = (timeStr: string) => {
    const seconds = parseTimestampToSeconds(timeStr);
    if (onSeekVideo) {
      onSeekVideo(seconds);
    }
  };

  return (
    <div className="flex flex-col h-full bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-2xl">
      {/* Chat Header */}
      <div className="flex items-center justify-between px-4 py-3 bg-slate-950/80 border-b border-slate-800 backdrop-blur-md">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-indigo-600/20 text-indigo-400 flex items-center justify-center font-bold text-sm border border-indigo-500/30">
            AI
          </div>
          <div>
            <h3 className="text-sm font-semibold text-slate-100">Lecture Teaching Assistant</h3>
            <p className="text-xs text-emerald-400 flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
              Grounded in Video Transcripts
            </p>
          </div>
        </div>
        <button
          onClick={clearChat}
          className="text-xs text-slate-400 hover:text-slate-200 transition-colors px-2 py-1 rounded bg-slate-800/50 hover:bg-slate-800"
        >
          Clear
        </button>
      </div>

      {/* Messages Scroll Area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex gap-3 ${msg.sender === 'student' ? 'flex-row-reverse' : 'flex-row'}`}
          >
            <div
              className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-semibold flex-shrink-0 ${
                msg.sender === 'student'
                  ? 'bg-indigo-600 text-white'
                  : 'bg-emerald-600/20 text-emerald-400 border border-emerald-500/30'
              }`}
            >
              {msg.sender === 'student' ? 'ST' : 'AI'}
            </div>

            <div className={`max-w-[80%] ${msg.sender === 'student' ? 'text-right' : 'text-left'}`}>
              <div
                className={`inline-block p-3.5 rounded-2xl text-sm leading-relaxed ${
                  msg.sender === 'student'
                    ? 'bg-indigo-600 text-white rounded-tr-none'
                    : 'bg-slate-800/80 text-slate-200 border border-slate-700/50 rounded-tl-none shadow-md'
                }`}
              >
                {/* Render with clickable timestamps */}
                {parseTextWithTimestamps(msg.text).map((part, i) =>
                  part.type === 'timestamp' ? (
                    <button
                      key={i}
                      onClick={() => handleTimestampClick(part.content)}
                      className="inline-flex items-center gap-1 mx-1 px-2 py-0.5 rounded-md bg-indigo-500/20 hover:bg-indigo-500/40 text-indigo-300 border border-indigo-500/40 text-xs font-mono font-medium transition-all hover:scale-105 active:scale-95"
                      title="Jump to this video moment"
                    >
                      ▶ {part.content}
                    </button>
                  ) : (
                    <span key={i} className="whitespace-pre-wrap">{part.content}</span>
                  )
                )}
              </div>

              {/* Retrieved Evidence Badges */}
              {msg.evidence && msg.evidence.length > 0 && (
                <div className="mt-2 text-left bg-slate-950/60 p-2 rounded-lg border border-slate-800/80">
                  <span className="text-[11px] font-semibold text-slate-400 block mb-1">
                    📚 Ground Truth Evidence:
                  </span>
                  <div className="flex flex-wrap gap-1.5">
                    {msg.evidence.map((ev, idx) => (
                      <button
                        key={idx}
                        onClick={() => handleTimestampClick(ev.timestamp_label.split(' - ')[0])}
                        className="text-[11px] px-2 py-0.5 rounded bg-slate-800 hover:bg-indigo-900/40 text-slate-300 border border-slate-700 hover:border-indigo-500/50 transition-all flex items-center gap-1 font-mono"
                      >
                        <span className="text-emerald-400">{Math.round(ev.similarity_score * 100)}%</span>
                        {ev.timestamp_label.split(' - ')[0]}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex items-center gap-3 text-slate-400 text-xs italic bg-slate-800/30 p-3 rounded-lg border border-slate-800 animate-pulse">
            <span className="w-2 h-2 rounded-full bg-cyan-400 animate-ping"></span>
            Searching 768-dim embeddings in Supabase & synthesizing explanation...
          </div>
        )}
        <div ref={chatBottomRef} />
      </div>

      {/* Input Form */}
      <form onSubmit={handleSubmit} className="p-3 bg-slate-950/90 border-t border-slate-800 flex gap-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask any doubt about this lecture..."
          className="flex-1 bg-slate-900 border border-slate-700/80 rounded-lg px-3.5 py-2 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition-colors"
          disabled={loading}
        />
        <button
          type="submit"
          disabled={loading || !input.trim()}
          className="bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white px-4 py-2 rounded-lg text-sm font-semibold transition-all flex items-center justify-center shadow-lg shadow-indigo-600/20"
        >
          Send
        </button>
      </form>
    </div>
  );
};
```

---

## 7. Video Synchronizer Integration in Lesson Page

In your lesson viewing page (e.g. `src/app/courses/[slug]/lessons/[lessonId]/page.tsx`):

```tsx
'use client';

import { useRef } from 'react';
import { LectureChatbot } from '@/components/LectureChatbot';

export default function LessonViewPage({ params }: { params: { lessonId: string } }) {
  const videoRef = useRef<HTMLVideoElement>(null);

  const handleSeekVideo = (seconds: number) => {
    if (videoRef.current) {
      videoRef.current.currentTime = seconds;
      videoRef.current.play();
    }
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 p-6 h-[calc(100vh-80px)]">
      {/* Left 2 Cols: Video Player */}
      <div className="lg:col-span-2 flex flex-col gap-4">
        <div className="relative aspect-video bg-black rounded-xl overflow-hidden shadow-2xl border border-slate-800">
          <video
            ref={videoRef}
            controls
            className="w-full h-full object-contain"
            src="https://your-storage-or-drive-stream-url"
          />
        </div>
      </div>

      {/* Right 1 Col: AI Assistant Chatbot */}
      <div className="lg:col-span-1 h-full">
        <LectureChatbot
          lessonId={params.lessonId}
          onSeekVideo={handleSeekVideo}
        />
      </div>
    </div>
  );
}
```

---

## 8. Testing & Verification

1. Start your local EduRAG backend:
   ```bash
   python -m uvicorn backend.app:app --host 0.0.0.0 --port 8000
   ```
2. In `climbup-nextjs`:
   ```bash
   npm run dev
   ```
3. Open `http://localhost:3000` and test asking:
   - *"Explain Round Robin with time quantum"*
   - *"What is context switching overhead?"*
4. Click on any `▶ [04:21]` badge and observe the video player immediately jump to that timestamp!
