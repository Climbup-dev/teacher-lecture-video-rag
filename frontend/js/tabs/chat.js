// AI Doubt Assistant / ClimbUp Mentor Chat Tab Module
import { api } from "../api.js";
import { appState } from "../state.js";
import { seekVideoTo } from "./studio.js";

export function initChatTab() {
  const chatMessages = document.getElementById("chat-messages");
  const chatForm = document.getElementById("chat-form");
  const chatInput = document.getElementById("chat-input");
  const btnClearChat = document.getElementById("btn-clear-chat");
  const chipsScroll = document.querySelector(".chips-scroll");

  function parseTimestamp(tsStr) {
    const clean = tsStr.replace(/[\[\]]/g, "").trim();
    const parts = clean.split(":").map(p => parseInt(p, 10));
    if (parts.length === 3) {
      return (parts[0] * 3600) + (parts[1] * 60) + parts[2];
    } else if (parts.length === 2) {
      return (parts[0] * 60) + parts[1];
    }
    return 0;
  }

  function escapeHtml(str) {
    return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  function formatChatMarkdown(text) {
    let html = text.replace(/\[(\d{1,2}:\d{2}:\d{2}|\d{1,3}:\d{2})\]/g, (match, p1) => {
      return `<button class="ts-badge" data-time="${p1}">[${p1}]</button>`;
    });

    html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');

    html = html.split('\n\n').map(p => {
      if (p.startsWith('###')) {
        return `<h4 style="margin: 8px 0 4px; color: var(--accent-cyan);">${p.replace('###', '')}</h4>`;
      }
      if (p.startsWith('* ') || p.startsWith('- ')) {
        const items = p.split('\n').map(li => `<li>${li.replace(/^[\*\-]\s*/, '')}</li>`).join('');
        return `<ul>${items}</ul>`;
      }
      return `<p>${p.replace(/\n/g, '<br>')}</p>`;
    }).join('');

    return html;
  }

  function appendUserMessage(text) {
    if (!chatMessages) return;
    const wrap = document.createElement("div");
    wrap.className = "message-wrapper user";
    wrap.innerHTML = `
      <div class="msg-avatar">ME</div>
      <div class="msg-content">
        <div class="msg-bubble">${escapeHtml(text)}</div>
      </div>
    `;
    chatMessages.appendChild(wrap);
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  function appendAiMessage(rawText, evidence) {
    if (!chatMessages) return;
    const wrap = document.createElement("div");
    wrap.className = "message-wrapper ai";

    const avatar = document.createElement("div");
    avatar.className = "msg-avatar";
    avatar.textContent = "AI";

    const content = document.createElement("div");
    content.className = "msg-content";

    const bubble = document.createElement("div");
    bubble.className = "msg-bubble";
    bubble.innerHTML = formatChatMarkdown(rawText);

    bubble.querySelectorAll(".ts-badge").forEach(badge => {
      badge.addEventListener("click", () => {
        const targetSec = parseTimestamp(badge.dataset.time);
        seekVideoTo(targetSec);
      });
    });

    content.appendChild(bubble);

    if (evidence && evidence.length > 0) {
      const evidenceCard = document.createElement("div");
      evidenceCard.className = "evidence-card";
      evidenceCard.innerHTML = `
        <div class="evidence-header">
          <span>📚 Ground Truth Evidence (${evidence.length} Chunks in Supabase)</span>
          <span class="evidence-toggle">▾</span>
        </div>
        <div class="evidence-list">
          ${evidence.map(e => `
            <div class="evidence-item">
              <div style="display:flex; align-items:center; gap:6px;">
                <button class="ts-badge" data-time="${(e.timestamp_label || '00:00').split(' - ')[0]}">${(e.timestamp_label || '00:00').split(' - ')[0]}</button>
                <span>${e.topic_name || "Concept Evidence"}</span>
              </div>
              <span class="similarity-score">${Math.round((e.similarity_score || 0.85) * 100)}% match</span>
            </div>
          `).join("")}
        </div>
      `;

      evidenceCard.querySelectorAll(".ts-badge").forEach(b => {
        b.addEventListener("click", () => {
          seekVideoTo(parseTimestamp(b.dataset.time));
        });
      });

      const header = evidenceCard.querySelector(".evidence-header");
      const list = evidenceCard.querySelector(".evidence-list");
      if (header && list) {
        header.addEventListener("click", () => {
          const isHidden = list.style.display === "none";
          list.style.display = isHidden ? "flex" : "none";
          header.querySelector(".evidence-toggle").textContent = isHidden ? "▾" : "▸";
        });
      }

      content.appendChild(evidenceCard);
    }

    wrap.appendChild(avatar);
    wrap.appendChild(content);
    chatMessages.appendChild(wrap);
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  function appendThinkingBubble() {
    if (!chatMessages) return null;
    const id = `thinking-${Date.now()}`;
    const wrap = document.createElement("div");
    wrap.className = "message-wrapper ai";
    wrap.id = id;
    wrap.innerHTML = `
      <div class="msg-avatar">AI</div>
      <div class="msg-content">
        <div class="msg-bubble" style="color: var(--accent-cyan); font-style: italic;">
          🔍 Searching 768-dim Supabase vector embeddings & assembling lecture proof...
        </div>
      </div>
    `;
    chatMessages.appendChild(wrap);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return id;
  }

  async function submitChatQuery(query) {
    appendUserMessage(query);
    const thinkingId = appendThinkingBubble();
    const lessonId = appState.get("currentLessonId") || "masterclass_os_3hours";

    try {
      const data = await api.sendChat(query, lessonId);
      const thinkingEl = document.getElementById(thinkingId);
      if (thinkingEl) thinkingEl.remove();
      appendAiMessage(data.answer, data.retrieved_evidence || []);
    } catch (err) {
      const thinkingEl = document.getElementById(thinkingId);
      if (thinkingEl) thinkingEl.remove();
      appendAiMessage(`Connection error: ${err.message}`, []);
    }
  }

  if (chatForm) {
    chatForm.addEventListener("submit", (e) => {
      e.preventDefault();
      const q = chatInput ? chatInput.value.trim() : "";
      if (!q) return;
      if (chatInput) chatInput.value = "";
      submitChatQuery(q);
    });
  }

  if (btnClearChat && chatMessages) {
    btnClearChat.addEventListener("click", () => {
      chatMessages.innerHTML = `
        <div class="message-wrapper ai">
          <div class="msg-avatar">AI</div>
          <div class="msg-content">
            <div class="msg-bubble">
              Chat cleared. Ask any doubt to test ClimbUp Mentor grounded retrieval and clickable timestamp jump badges <code>[MM:SS]</code>.
            </div>
          </div>
        </div>
      `;
    });
  }

  function updateChips(lessonId) {
    if (!chipsScroll) return;
    chipsScroll.innerHTML = "";

    let chips = [];
    if (lessonId === "masterclass_os_3hours") {
      chips = [
        { label: "PCB & Context Switching (Hr 1)", query: "What is a Process Control Block (PCB) and what exact hardware state is saved during a context switch?" },
        { label: "Round Robin Trade-offs (Hr 2)", query: "Explain Round Robin scheduling. What mathematical trade-off exists when setting the time quantum too large vs too small?" },
        { label: "80% Rule of Thumb (Hr 2)", query: "What is the 80% rule of thumb for CPU bursts and how does it balance waiting time with context switch overhead?" },
        { label: "Banker's Algorithm & Deadlocks (Hr 3)", query: "How does the Banker's Algorithm prevent deadlocks, and what are the 4 Coffman conditions explained by the professor?" },
        { label: "TLB Virtual Memory (Hr 3)", query: "How does Translation Lookaside Buffer (TLB) paging reduce memory access overhead in virtual memory systems?" }
      ];
    } else {
      chips = [
        { label: "Round Robin & Time Quantum", query: "Explain Round Robin scheduling with time quantum." },
        { label: "Preemptive vs Non-Preemptive", query: "What is the difference between preemptive and non-preemptive scheduling?" },
        { label: "Time Quantum Limits", query: "What happens if time quantum is too large or too small?" },
        { label: "80% Rule of Thumb", query: "What is the 80% rule of thumb for time quantum?" }
      ];
    }

    chips.forEach(c => {
      const btn = document.createElement("button");
      btn.className = "chip";
      btn.textContent = c.label;
      btn.addEventListener("click", () => submitChatQuery(c.query));
      chipsScroll.appendChild(btn);
    });
  }

  appState.subscribe("currentLessonId", (lessonId) => {
    updateChips(lessonId);
  });

  updateChips(appState.get("currentLessonId"));
}
