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

  // ── Full-featured lightweight Markdown → HTML renderer ──────────────────
  function formatChatMarkdown(text) {
    if (!text) return "";

    // Normalize line endings
    let lines = text.replace(/\r\n/g, "\n").split("\n");
    let html = "";
    let i = 0;

    while (i < lines.length) {
      const line = lines[i];

      // ── Fenced code block ```...``` ──────────────────────────────────
      if (line.trim().startsWith("```")) {
        let code = "";
        i++;
        while (i < lines.length && !lines[i].trim().startsWith("```")) {
          code += escapeHtml(lines[i]) + "\n";
          i++;
        }
        html += `<pre class="chat-code-block"><code>${code.trimEnd()}</code></pre>`;
        i++;
        continue;
      }

      // ── Markdown table (line starts with |) ──────────────────────────
      if (line.trim().startsWith("|") && i + 1 < lines.length && lines[i + 1].trim().match(/^\|[-| :]+\|$/)) {
        // Header row
        const headers = line.trim().split("|").slice(1, -1).map(h => `<th>${renderInline(h.trim())}</th>`).join("");
        i += 2; // skip header + separator
        let rows = "";
        while (i < lines.length && lines[i].trim().startsWith("|")) {
          const cells = lines[i].trim().split("|").slice(1, -1).map(c => `<td>${renderInline(c.trim())}</td>`).join("");
          rows += `<tr>${cells}</tr>`;
          i++;
        }
        html += `<div class="chat-table-wrap"><table class="chat-table"><thead><tr>${headers}</tr></thead><tbody>${rows}</tbody></table></div>`;
        continue;
      }

      // ── Horizontal rule ───────────────────────────────────────────────
      if (line.trim().match(/^[-*_]{3,}$/)) {
        html += `<hr class="chat-hr">`;
        i++;
        continue;
      }

      // ── ATX Headings ## / ### ─────────────────────────────────────────
      const h3Match = line.match(/^###\s+(.+)/);
      if (h3Match) {
        html += `<h4 class="chat-h3">${renderInline(h3Match[1])}</h4>`;
        i++;
        continue;
      }
      const h2Match = line.match(/^##\s+(.+)/);
      if (h2Match) {
        html += `<h3 class="chat-h2">${renderInline(h2Match[1])}</h3>`;
        i++;
        continue;
      }
      const h1Match = line.match(/^#\s+(.+)/);
      if (h1Match) {
        html += `<h3 class="chat-h2">${renderInline(h1Match[1])}</h3>`;
        i++;
        continue;
      }

      // ── Numbered heading e.g. "1. What a container is" ────────────────
      const numHeadMatch = line.match(/^(\d+)\.\s+(.+)/);
      if (numHeadMatch && line === line.trim() && !line.match(/^\s/)) {
        // Only treat as heading if it's at the start with no leading whitespace
        // and not inside a list context — heuristic: short enough to be a heading
        const content = numHeadMatch[2];
        if (content.length < 80) {
          html += `<h4 class="chat-numbered-heading"><span class="chat-num">${numHeadMatch[1]}.</span> ${renderInline(content)}</h4>`;
          i++;
          continue;
        }
      }

      // ── Bullet list block (* or -) ────────────────────────────────────
      if (line.trim().match(/^[*\-]\s/)) {
        let items = "";
        while (i < lines.length && lines[i].trim().match(/^[*\-]\s/)) {
          items += `<li>${renderInline(lines[i].trim().replace(/^[*\-]\s/, ""))}</li>`;
          i++;
        }
        html += `<ul class="chat-ul">${items}</ul>`;
        continue;
      }

      // ── Timestamp jump lines (⏱️ ... [MM:SS]) ─────────────────────────
      if (line.includes("⏱") || line.includes("[0") && line.includes("]")) {
        html += `<p class="chat-ts-line">${renderInline(line)}</p>`;
        i++;
        continue;
      }

      // ── Pro tip / callout ─────────────────────────────────────────────
      if (line.trim().startsWith("💡")) {
        html += `<div class="chat-protip">${renderInline(line)}</div>`;
        i++;
        continue;
      }

      // ── Empty line → paragraph break ─────────────────────────────────
      if (line.trim() === "") {
        i++;
        continue;
      }

      // ── Default: paragraph ───────────────────────────────────────────
      // Collect consecutive non-special lines
      let para = "";
      while (
        i < lines.length &&
        lines[i].trim() !== "" &&
        !lines[i].trim().match(/^[*\-]\s/) &&
        !lines[i].trim().startsWith("|") &&
        !lines[i].trim().startsWith("#") &&
        !lines[i].trim().startsWith("```") &&
        !lines[i].trim().match(/^[-*_]{3,}$/) &&
        !lines[i].trim().startsWith("💡")
      ) {
        para += (para ? "<br>" : "") + renderInline(lines[i]);
        i++;
      }
      if (para) html += `<p class="chat-p">${para}</p>`;
    }

    return html;
  }

  // ── Inline element renderer (bold, italic, code, timestamps, links) ───────
  function renderInline(text) {
    if (!text) return "";

    // Preserve any raw <button class="ts-badge"...> already in the string
    // (the backend sometimes sends pre-rendered badges)
    // Pass them through by temporarily escaping other HTML first.
    let out = text;

    // Raw pre-rendered timestamp badge HTML from backend → keep as-is
    // We process inline patterns on text outside of existing HTML tags.

    // Inline code `code`
    out = out.replace(/`([^`]+)`/g, '<code class="chat-code">$1</code>');

    // Bold **text**
    out = out.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');

    // Italic *text* or _text_
    out = out.replace(/(?<!\*)\*([^*]+)\*(?!\*)/g, '<em>$1</em>');
    out = out.replace(/(?<!_)_([^_]+)_(?!_)/g, '<em>$1</em>');

    // Timestamp badge [MM:SS] or [HH:MM:SS] — convert to button
    out = out.replace(/\[(\d{1,2}:\d{2}(?::\d{2})?)\]/g, (match, ts) => {
      return `<button class="ts-badge" data-time="${ts}">[${ts}]</button>`;
    });

    // ✅ / ❌ — keep as-is
    return out;
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

  let currentChatSessionId = `session_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;

  async function submitChatQuery(query) {
    appendUserMessage(query);
    const thinkingId = appendThinkingBubble();
    const lessonId = appState.get("currentLessonId") || "masterclass_os_3hours";

    try {
      const data = await api.sendChat(query, lessonId, currentChatSessionId);
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
      const oldSession = currentChatSessionId;
      currentChatSessionId = `session_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
      chatMessages.innerHTML = `
        <div class="message-wrapper ai">
          <div class="msg-avatar">AI</div>
          <div class="msg-content">
            <div class="msg-bubble">
              👋 <strong>Chat session reset.</strong> Ask any lecture doubt to test grounded retrieval and clickable video timestamp badges <code>[MM:SS]</code>.
            </div>
          </div>
        </div>
      `;
      if (oldSession) {
        api.clearChat(oldSession);
      }
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
