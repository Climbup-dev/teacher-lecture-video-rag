// Interactive Lecture Studio & Video Player Tab Module
import { api } from "../api.js";
import { appState } from "../state.js";

let videoEl = null;
let driveIframeEl = null;
let currentUtterances = [];
let currentChunks = [];
let currentHlsInstance = null;
let watermarkTimer = null;

function startForensicWatermarking(userLabel) {
  const canvas = document.getElementById("watermark-canvas");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  if (!ctx) return;

  function resizeCanvas() {
    if (videoEl && videoEl.clientWidth) {
      canvas.width = videoEl.clientWidth;
      canvas.height = videoEl.clientHeight;
    } else {
      const parent = canvas.parentElement;
      canvas.width = parent ? parent.clientWidth : 800;
      canvas.height = parent ? parent.clientHeight : 450;
    }
  }

  resizeCanvas();
  window.removeEventListener("resize", resizeCanvas);
  window.addEventListener("resize", resizeCanvas);

  if (watermarkTimer) clearInterval(watermarkTimer);

  function drawWatermark() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    const now = new Date();
    const timeStr = now.toLocaleTimeString();
    const label = userLabel || (appState.currentUser?.email || "Student ID: EDU-8924");
    const fullText = `${label} • ${timeStr}`;

    ctx.save();
    ctx.font = "500 13px 'Inter', sans-serif";
    ctx.fillStyle = "rgba(255, 255, 255, 0.22)";
    ctx.shadowColor = "rgba(0, 0, 0, 0.4)";
    ctx.shadowBlur = 4;

    const padding = 30;
    const maxX = Math.max(padding, canvas.width - 240);
    const maxY = Math.max(padding, canvas.height - 40);
    const posX = padding + Math.floor(Math.random() * (maxX - padding));
    const posY = padding + Math.floor(Math.random() * (maxY - padding));

    ctx.fillText(fullText, posX, posY);
    ctx.restore();
  }

  drawWatermark();
  watermarkTimer = setInterval(drawWatermark, 4000);
}

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

      // Video Source handling: High-performance streaming via AES-128 HLS or signed progressive stream
      const vUrl = lesson.video_url || "";
      const lessonId = lesson.id;

      // 1. Fetch short-lived signed stream token (HMAC-SHA256, 5 min)
      let streamToken = "";
      try {
        const tokenRes = await fetch(`/api/lessons/${lessonId}/stream-token`, {
          method: "POST"
        });
        if (tokenRes.ok) {
          const tokenData = await tokenRes.json();
          streamToken = tokenData.signed_token || "";
        }
      } catch (e) {
        console.warn("Notice fetching stream token:", e);
      }

      // 2. Start dynamic anti-piracy forensic watermark
      startForensicWatermarking(appState.currentUser?.email || `Student: ${lesson.course_id || "ClimbUP"}`);

      // 3. URLs
      const hlsPlaylistUrl = `/api/lessons/${lessonId}/hls/master.m3u8${streamToken ? `?st=${streamToken}` : ""}`;
      const progressiveUrl = `/api/lessons/${lessonId}/stream${streamToken ? `?st=${streamToken}` : ""}`;

      if (driveIframeEl) driveIframeEl.style.display = "none";
      if (videoEl) {
        videoEl.style.display = "block";
        if (videoOverlay) videoOverlay.style.display = "flex";

        // Hardened anti-piracy video element configuration
        videoEl.setAttribute("controlsList", "nodownload noplaybackrate");
        videoEl.setAttribute("disablePictureInPicture", "true");
        videoEl.oncontextmenu = (e) => { e.preventDefault(); return false; };

        // Clean up any existing HLS instance
        if (currentHlsInstance) {
          currentHlsInstance.destroy();
          currentHlsInstance = null;
        }

        // Test if HLS playlist is available with player handshake
        let hlsAvailable = false;
        try {
          const testHls = await fetch(hlsPlaylistUrl, {
            method: "HEAD",
            headers: { "X-Climbup-Player": "authorized-hls-player-v3" }
          });
          hlsAvailable = testHls.ok;
        } catch (_) {
          hlsAvailable = false;
        }

        if (hlsAvailable && window.Hls && window.Hls.isSupported()) {
          console.log("[HLS Engine] Initializing AES-128 Encrypted HLS Player for:", lessonId);
          const hls = new window.Hls({
            enableWorker: true,
            lowLatencyMode: false,
            xhrSetup: (xhr, url) => {
              xhr.setRequestHeader("X-Climbup-Player", "authorized-hls-player-v3");
              if (streamToken && !url.includes("st=")) {
                const sep = url.includes("?") ? "&" : "?";
                xhr.open("GET", `${url}${sep}st=${streamToken}`, true);
              }
            }
          });
          currentHlsInstance = hls;
          hls.loadSource(hlsPlaylistUrl);
          hls.attachMedia(videoEl);
          hls.on(window.Hls.Events.ERROR, (event, data) => {
            if (data.fatal) {
              console.warn("[HLS Error] Fallback to progressive stream:", data);
              hls.destroy();
              currentHlsInstance = null;
              videoEl.src = progressiveUrl;
              videoEl.load();
            }
          });
        } else if (hlsAvailable && videoEl.canPlayType("application/vnd.apple.mpegurl")) {
          // Native Safari / iOS HLS
          videoEl.src = hlsPlaylistUrl;
          videoEl.load();
        } else {
          // Standard Progressive Stream Fallback
          videoEl.onerror = () => {
            console.warn("[Stream Notice] Stream error, attempting preview fallback...");
            const match = vUrl.match(/\/d\/([a-zA-Z0-9_-]+)/);
            const fileId = match ? match[1] : null;
            if (fileId && driveIframeEl) {
              videoEl.style.display = "none";
              if (videoOverlay) videoOverlay.style.display = "none";
              driveIframeEl.dataset.fileId = fileId;
              driveIframeEl.src = `https://drive.google.com/file/d/${fileId}/preview`;
              driveIframeEl.style.display = "block";
            }
          };

          videoEl.src = progressiveUrl;
          videoEl.load();
        }
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
