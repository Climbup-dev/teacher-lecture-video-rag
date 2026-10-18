// Interactive Lecture Studio & Video Player Tab Module
import { api } from "../api.js";
import { appState } from "../state.js";

let videoEl = null;
let driveIframeEl = null;
let currentUtterances = [];
let currentChunks = [];

export function seekVideoTo(seconds) {
  const studioTab = document.getElementById("tab-nav-studio");
  if (studioTab && !studioTab.classList.contains("active")) {
    studioTab.click();
  }

  if (driveIframeEl && driveIframeEl.style.display !== "none") {
    const fid = driveIframeEl.dataset.fileId;
    if (fid) {
      driveIframeEl.src = `https://drive.google.com/file/d/${fid}/preview#t=${Math.floor(seconds)}`;
    }
  } else if (videoEl) {
    videoEl.currentTime = seconds;
    videoEl.play().then(() => {
      const overlay = document.getElementById("video-overlay");
      const iconPlay = document.getElementById("icon-play");
      const iconPause = document.getElementById("icon-pause");
      if (overlay) overlay.classList.add("hidden");
      if (iconPlay) iconPlay.style.display = "none";
      if (iconPause) iconPause.style.display = "block";
    }).catch(e => console.warn(e));
  }
}

export function initStudioTab() {
  videoEl = document.getElementById("lecture-video");
  driveIframeEl = document.getElementById("drive-iframe");
  const videoOverlay = document.getElementById("video-overlay");
  const btnOverlayPlay = document.getElementById("btn-overlay-play");
  const ctrlPlayPause = document.getElementById("ctrl-play-pause");
  const iconPlay = document.getElementById("icon-play");
  const iconPause = document.getElementById("icon-pause");
  const seekBar = document.getElementById("seek-bar");
  const timeCurrent = document.getElementById("time-current");
  const timeDuration = document.getElementById("time-duration");
  const playbackSpeed = document.getElementById("playback-speed");
  const studioLectureSelect = document.getElementById("studio-lecture-select");
  const lectureTitle = document.getElementById("lecture-title");
  const lectureCategory = document.getElementById("lecture-category");
  const currentConceptName = document.getElementById("current-concept-name");
  const uttCount = document.getElementById("utt-count");
  const chunkCount = document.getElementById("chunk-count");
  const utterancesContainer = document.getElementById("utterances-container");
  const chunksContainer = document.getElementById("chunks-container");
  const subtabBtns = document.querySelectorAll(".subtab-btn");
  const subtabContents = document.querySelectorAll(".subtab-content");

  function formatTime(seconds) {
    if (isNaN(seconds) || seconds < 0) return "00:00";
    const hrs = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    if (hrs > 0) {
      return `${hrs.toString().padStart(2, "0")}:${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
    }
    return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
  }

  function togglePlay() {
    if (!videoEl) return;
    if (videoEl.paused || videoEl.ended) {
      videoEl.play().then(() => {
        if (videoOverlay) videoOverlay.classList.add("hidden");
        if (iconPlay) iconPlay.style.display = "none";
        if (iconPause) iconPause.style.display = "block";
      }).catch(err => console.warn(err));
    } else {
      videoEl.pause();
      if (videoOverlay) videoOverlay.classList.remove("hidden");
      if (iconPlay) iconPlay.style.display = "block";
      if (iconPause) iconPause.style.display = "none";
    }
  }

  if (btnOverlayPlay) btnOverlayPlay.addEventListener("click", togglePlay);
  if (videoOverlay) videoOverlay.addEventListener("click", togglePlay);
  if (ctrlPlayPause) ctrlPlayPause.addEventListener("click", togglePlay);

  if (videoEl) {
    videoEl.addEventListener("timeupdate", () => {
      const cur = videoEl.currentTime;
      if (timeCurrent) timeCurrent.textContent = formatTime(cur);
      if (seekBar) seekBar.value = cur;
      updateActiveConceptAndUtterance(cur);
    });

    videoEl.addEventListener("loadedmetadata", () => {
      if (seekBar) seekBar.max = videoEl.duration;
      if (timeDuration) timeDuration.textContent = formatTime(videoEl.duration);
    });

    videoEl.addEventListener("ended", () => {
      if (videoOverlay) videoOverlay.classList.remove("hidden");
      if (iconPlay) iconPlay.style.display = "block";
      if (iconPause) iconPause.style.display = "none";
    });
  }

  if (seekBar) {
    seekBar.addEventListener("input", () => {
      if (videoEl) videoEl.currentTime = seekBar.value;
      if (timeCurrent) timeCurrent.textContent = formatTime(seekBar.value);
    });
  }

  if (playbackSpeed) {
    playbackSpeed.addEventListener("change", () => {
      if (videoEl) videoEl.playbackRate = parseFloat(playbackSpeed.value);
    });
  }

  function updateActiveConceptAndUtterance(currentTime) {
    if (currentChunks && currentChunks.length > 0) {
      const active = currentChunks.find(c => currentTime >= c.start_seconds && currentTime <= c.end_seconds);
      if (active && currentConceptName) {
        currentConceptName.textContent = `${active.timestamp_label} - ${active.topic_name}`;
      }
    }

    if (utterancesContainer) {
      const items = utterancesContainer.querySelectorAll(".utterance-item");
      items.forEach(el => {
        const start = parseFloat(el.dataset.start);
        const end = parseFloat(el.dataset.end);
        if (currentTime >= start && currentTime <= end) {
          if (!el.classList.contains("active")) {
            el.classList.add("active");
            el.scrollIntoView({ behavior: "smooth", block: "nearest" });
          }
        } else {
          el.classList.remove("active");
        }
      });
    }
  }

  // Subtab switching
  subtabBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      subtabBtns.forEach(b => b.classList.remove("active"));
      subtabContents.forEach(c => c.classList.remove("active"));
      btn.classList.add("active");
      const target = document.getElementById(`subtab-${btn.dataset.subtab}`);
      if (target) target.classList.add("active");
    });
  });

  // Load selected lecture into studio
  async function loadLesson(lessonId) {
    if (!lessonId) return;
    try {
      const lesson = await api.getLesson(lessonId);
      if (lectureTitle) lectureTitle.textContent = lesson.title;
      currentUtterances = lesson.utterances || [];
      currentChunks = lesson.chunks || [];

      if (uttCount) uttCount.textContent = currentUtterances.length;
      if (chunkCount) chunkCount.textContent = currentChunks.length;

      // Video Source handling
      const vUrl = lesson.video_url || "";
      if (vUrl.includes("drive.google.com/file/d/")) {
        const match = vUrl.match(/\/d\/([a-zA-Z0-9_-]+)/);
        const fileId = match ? match[1] : null;
        if (fileId && driveIframeEl) {
          driveIframeEl.dataset.fileId = fileId;
          driveIframeEl.src = `https://drive.google.com/file/d/${fileId}/preview`;
          driveIframeEl.style.display = "block";
          if (videoEl) videoEl.style.display = "none";
          if (videoOverlay) videoOverlay.style.display = "none";
        }
      } else if (videoEl) {
        if (driveIframeEl) driveIframeEl.style.display = "none";
        videoEl.style.display = "block";
        if (videoOverlay) videoOverlay.style.display = "flex";
        videoEl.src = vUrl || "/uploads/berkeley_cs61c.mp4";
        videoEl.load();
      }

      renderUtterances(currentUtterances);
      renderChunks(currentChunks);

      if (videoEl) {
        videoEl.currentTime = 0;
        if (seekBar) seekBar.value = 0;
        if (timeCurrent) timeCurrent.textContent = "00:00";
      }
    } catch (err) {
      console.warn("loadLesson error:", err);
    }
  }

  function renderUtterances(utterances) {
    if (!utterancesContainer) return;
    utterancesContainer.innerHTML = "";

    if (!utterances || utterances.length === 0) {
      utterancesContainer.innerHTML = `<div class="empty-state">No spoken utterances found.</div>`;
      return;
    }

    utterances.forEach((utt, idx) => {
      const isTeacher = (utt.speaker_label || "").toLowerCase().includes("teacher");
      const item = document.createElement("div");
      item.className = `utterance-item ${isTeacher ? "teacher" : "student"}`;
      item.id = `utt-${idx}`;
      item.dataset.start = utt.start_seconds;
      item.dataset.end = utt.end_seconds;

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

      item.addEventListener("click", () => {
        seekVideoTo(utt.start_seconds);
      });

      utterancesContainer.appendChild(item);
    });
  }

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
          <button class="ts-badge" data-time="${(c.timestamp_label || '00:00').split(' - ')[0]}">${c.timestamp_label || '00:00'}</button>
        </div>
        <p class="chunk-text">${c.cleaned_text || c.chunk_text}</p>
        <div class="chunk-tags">
          ${(c.key_concepts || []).map(k => `<span class="chunk-tag">${k}</span>`).join("")}
        </div>
      `;

      const badge = item.querySelector(".ts-badge");
      if (badge) {
        badge.addEventListener("click", () => {
          seekVideoTo(c.start_seconds);
        });
      }

      chunksContainer.appendChild(item);
    });
  }

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
    studioLectureSelect.addEventListener("change", (e) => {
      appState.setActiveLesson(e.target.value);
    });
  }

  appState.subscribe("currentLessonId", (id) => {
    if (studioLectureSelect) studioLectureSelect.value = id;
    loadLesson(id);
  });

  appState.subscribe("lessons", syncLecturePicker);
}
