// Interactive Lecture Studio – Admin Management Module
// Video playback removed. Manages lecture data, transcripts, chunks & materials only.
import { api } from "../api.js";
import { appState } from "../state.js";

let currentUtterances = [];
let currentChunks = [];

// Stub: exported so any existing import of seekVideoTo doesn't break.
// No-op since video playback is removed from the admin panel.
export function seekVideoTo(_seconds) {
  // Video playback is disabled in admin management mode.
}

export function initStudioTab() {
  const studioLectureSelect = document.getElementById("studio-lecture-select");
  const lectureTitle        = document.getElementById("lecture-title");
  const lectureCategory     = document.getElementById("lecture-category");
  const uttCount            = document.getElementById("utt-count");
  const chunkCount          = document.getElementById("chunk-count");
  const utterancesContainer = document.getElementById("utterances-container");
  const chunksContainer     = document.getElementById("chunks-container");
  const subtabBtns          = document.querySelectorAll(".subtab-btn");
  const subtabContents      = document.querySelectorAll(".subtab-content");

  // ── Subtab switching ───────────────────────────────────────────────────────
  subtabBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      subtabBtns.forEach(b => b.classList.remove("active"));
      subtabContents.forEach(c => c.classList.remove("active"));
      btn.classList.add("active");
      const target = document.getElementById(`subtab-${btn.dataset.subtab}`);
      if (target) target.classList.add("active");
    });
  });

  // ── Load selected lecture data ─────────────────────────────────────────────
  async function loadLesson(lessonId) {
    if (!lessonId) return;
    try {
      const lesson = await api.getLesson(lessonId);

      if (lectureTitle)    lectureTitle.textContent    = lesson.title    || "Untitled Lecture";
      if (lectureCategory) lectureCategory.textContent = lesson.category || "General";

      currentUtterances = lesson.utterances || [];
      currentChunks     = lesson.chunks     || [];

      if (uttCount)   uttCount.textContent   = currentUtterances.length;
      if (chunkCount) chunkCount.textContent = currentChunks.length;

      renderUtterances(currentUtterances);
      renderChunks(currentChunks);
    } catch (err) {
      console.warn("[Studio] loadLesson error:", err);
    }
  }

  // ── Render utterances (read-only, no seek on click) ────────────────────────
  function renderUtterances(utterances) {
    if (!utterancesContainer) return;
    utterancesContainer.innerHTML = "";

    if (!utterances || utterances.length === 0) {
      utterancesContainer.innerHTML = `<div class="empty-state">No spoken utterances found for this lecture.</div>`;
      return;
    }

    utterances.forEach((utt, idx) => {
      const isTeacher = (utt.speaker_label || "").toLowerCase().includes("teacher");
      const item = document.createElement("div");
      item.className = `utterance-item ${isTeacher ? "teacher" : "student"}`;
      item.id = `utt-${idx}`;

      item.innerHTML = `
        <span class="utt-badge">${utt.speaker_label}</span>
        <div class="utt-body">
          <div class="utt-top">
            <span class="utt-speaker">${utt.speaker_label}</span>
            <span class="utt-time">${utt.timestamp_label}</span>
          </div>
          <p class="utt-text">${utt.text}</p>
        </div>
      `;

      utterancesContainer.appendChild(item);
    });
  }

  // ── Render semantic chunks (read-only, timestamp badge is display-only) ────
  function renderChunks(chunks) {
    if (!chunksContainer) return;
    chunksContainer.innerHTML = "";

    if (!chunks || chunks.length === 0) {
      chunksContainer.innerHTML = `<div class="empty-state">No semantic chunks indexed for this lecture.</div>`;
      return;
    }

    chunks.forEach(c => {
      const item = document.createElement("div");
      item.className = "chunk-card";
      item.innerHTML = `
        <div class="chunk-header">
          <span class="chunk-topic">${c.topic_name || "Concept Chunk"}</span>
          <span class="ts-badge">${c.timestamp_label || "00:00"}</span>
        </div>
        <p class="chunk-text">${c.cleaned_text || c.chunk_text}</p>
        <div class="chunk-tags">
          ${(c.key_concepts || []).map(k => `<span class="chunk-tag">${k}</span>`).join("")}
        </div>
      `;
      chunksContainer.appendChild(item);
    });
  }

  // ── Lecture picker sync ────────────────────────────────────────────────────
  function syncLecturePicker() {
    if (!studioLectureSelect) return;
    const lessons = appState.get("lessons") || [];
    studioLectureSelect.innerHTML = "";

    lessons.forEach(l => {
      const opt = document.createElement("option");
      opt.value = l.id;
      opt.textContent = l.title;
      studioLectureSelect.appendChild(opt);
    });

    const activeId = appState.get("currentLessonId");
    if (activeId && lessons.find(l => l.id === activeId)) {
      studioLectureSelect.value = activeId;
      loadLesson(activeId);
    } else if (lessons.length > 0) {
      studioLectureSelect.value = lessons[0].id;
      appState.setActiveLesson(lessons[0].id);
      loadLesson(lessons[0].id);
    }
  }

  if (studioLectureSelect) {
    studioLectureSelect.addEventListener("change", e => {
      appState.setActiveLesson(e.target.value);
    });
  }

  appState.subscribe("currentLessonId", id => {
    if (studioLectureSelect) studioLectureSelect.value = id;
    loadLesson(id);
  });

  appState.subscribe("lessons", syncLecturePicker);
}
