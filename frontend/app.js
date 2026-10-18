// EduRAG Frontend Application Logic
document.addEventListener("DOMContentLoaded", () => {
  // DOM Elements
  const video = document.getElementById("lecture-video");
  const videoOverlay = document.getElementById("video-overlay");
  const btnOverlayPlay = document.getElementById("btn-overlay-play");
  const ctrlPlayPause = document.getElementById("ctrl-play-pause");
  const iconPlay = document.getElementById("icon-play");
  const iconPause = document.getElementById("icon-pause");
  const seekBar = document.getElementById("seek-bar");
  const timeCurrent = document.getElementById("time-current");
  const timeDuration = document.getElementById("time-duration");
  const playbackSpeed = document.getElementById("playback-speed");
  
  const lectureTitle = document.getElementById("lecture-title");
  const lectureCategory = document.getElementById("lecture-category");
  const lectureSelect = document.getElementById("lecture-select");
  const currentConceptName = document.getElementById("current-concept-name");
  const uttCount = document.getElementById("utt-count");
  const chunkCount = document.getElementById("chunk-count");
  const utterancesContainer = document.getElementById("utterances-container");
  const chunksContainer = document.getElementById("chunks-container");

  const chatMessages = document.getElementById("chat-messages");
  const chatForm = document.getElementById("chat-form");
  const chatInput = document.getElementById("chat-input");
  const btnClearChat = document.getElementById("btn-clear-chat");
  const btnLoadSample = document.getElementById("btn-load-sample");
  const chipsScroll = document.querySelector(".chips-scroll");

  // Modals
  const uploadModal = document.getElementById("upload-modal");
  const btnOpenUpload = document.getElementById("btn-open-upload");
  const btnCloseModal = document.getElementById("btn-close-modal");
  const btnCancelModal = document.getElementById("btn-cancel-modal");
  const uploadForm = document.getElementById("upload-form");
  const dropZone = document.getElementById("drop-zone");
  const urlContainer = document.getElementById("url-container");
  const btnModeFile = document.getElementById("btn-mode-file");
  const btnModeUrl = document.getElementById("btn-mode-url");
  const mediaUrlInput = document.getElementById("media-url-input");
  const fileInput = document.getElementById("file-input");
  const selectedFileName = document.getElementById("selected-file-name");
  const stepperProgress = document.getElementById("stepper-progress");

  const settingsModal = document.getElementById("settings-modal");
  const btnSettings = document.getElementById("btn-settings");
  const btnCloseSettings = document.getElementById("btn-close-settings");
  const btnCancelSettings = document.getElementById("btn-cancel-settings");
  const settingsForm = document.getElementById("settings-form");

  // App State
  let currentLessonId = null;
  let currentUtterances = [];
  let currentChunks = [];
  let isVideoPlaying = false;
  let selectedFile = null;
  let uploadMode = "file"; // 'file' or 'url'

  // Format seconds to HH:MM:SS or MM:SS
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

  // Parse HH:MM:SS or MM:SS to seconds
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

  // Check system status & populate lectures dropdown
  async function checkStatus() {
    try {
      const res = await fetch("/api/status");
      const data = await res.json();
      
      const pDeep = document.getElementById("pill-deepgram");
      const pGem = document.getElementById("pill-gemini");
      const pVec = document.getElementById("pill-vector");

      if (data.deepgram_configured) pDeep.classList.add("active"); else pDeep.classList.remove("active");
      if (data.gemini_configured) pGem.classList.add("active"); else pGem.classList.remove("active");
      pVec.classList.add("active");

      // Populate lecture selector dropdown
      const lessonsRes = await fetch("/api/lessons");
      const lessons = await lessonsRes.json();
      
      lectureSelect.innerHTML = "";
      if (lessons && lessons.length > 0) {
        // Filter out empty lessons if any
        const validLessons = lessons.filter(l => (l.utterances && l.utterances.length > 0) || l.title);
        validLessons.forEach(l => {
          const opt = document.createElement("option");
          opt.value = l.id;
          const count = l.utterances ? l.utterances.length : 0;
          opt.textContent = `${l.title} (${count} utterances)`;
          lectureSelect.appendChild(opt);
        });

        // Default to 3-hour masterclass or first valid lesson
        const preferred = validLessons.find(l => l.id === "masterclass_os_3hours") || validLessons.find(l => l.id === "online_lecture_real") || validLessons[0];
        lectureSelect.value = preferred.id;
        loadLesson(preferred.id);
      } else {
        loadSampleLecture();
      }
    } catch (err) {
      console.warn("Status check failed:", err);
    }
  }

  // Change lecture on dropdown selection
  lectureSelect.addEventListener("change", (e) => {
    if (e.target.value) {
      loadLesson(e.target.value);
    }
  });

  // Load a lesson by ID
  async function loadLesson(lessonId) {
    try {
      const res = await fetch(`/api/lessons/${lessonId}`);
      if (!res.ok) return;
      const lesson = await res.json();
      
      currentLessonId = lesson.id;
      currentUtterances = lesson.utterances || [];
      currentChunks = lesson.chunks || [];

      lectureTitle.textContent = lesson.title || "Lecture";
      uttCount.textContent = currentUtterances.length;
      chunkCount.textContent = currentChunks.length;

      // Set video duration
      const durationSec = lesson.duration_seconds || 810;
      timeDuration.textContent = formatTime(durationSec);
      seekBar.max = durationSec;

      // Update video source if real URL is provided
      const videoSrc = document.getElementById("video-source");
      if (videoSrc && lesson.video_url) {
        videoSrc.src = lesson.video_url;
        video.load();
      }

      // Sync selector dropdown
      if (lectureSelect) {
        lectureSelect.value = lesson.id;
      }

      // Update category badge
      if (lectureCategory) {
        if (lesson.id === "masterclass_os_3hours") {
          lectureCategory.textContent = "3-Hour Masterclass • OS Kernel Architecture";
        } else if (lesson.id === "online_lecture_real") {
          lectureCategory.textContent = "Distributed Systems & Cryptography";
        } else {
          lectureCategory.textContent = "Computer Science • 4th Semester";
        }
      }

      // Update quick doubt chips
      updateQuickChips(lesson.id);

      // Render utterances and chunks
      renderUtterances(currentUtterances);
      renderChunks(currentChunks);

      // Reset playback
      video.currentTime = 0;
      seekBar.value = 0;
      timeCurrent.textContent = "00:00";
    } catch (err) {
      console.error("Failed to load lesson:", err);
    }
  }

  function updateQuickChips(lessonId) {
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
    } else if (lessonId === "online_lecture_real") {
      chips = [
        { label: "Who is Charles Hoskinson?", query: "Who is Charles Hoskinson and what did he cofound?" },
        { label: "Cardano vs Ethereum", query: "What is Cardano and how does it relate to Ethereum?" },
        { label: "Technical Background", query: "What technical knowledge did the professor highlight?" },
        { label: "Mongolian Hawk Story", query: "Tell me about the Mongolian hawk anecdote." }
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
      btn.dataset.query = c.query;
      btn.addEventListener("click", () => submitChatQuery(c.query));
      chipsScroll.appendChild(btn);
    });
  }

  // Render utterances list
  function renderUtterances(utterances) {
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

  // Render RAG chunks list
  function renderChunks(chunks) {
    chunksContainer.innerHTML = "";
    if (!chunks || chunks.length === 0) {
      chunksContainer.innerHTML = `<div class="empty-state">No semantic chunks indexed.</div>`;
      return;
    }

    chunks.forEach((chunk) => {
      const card = document.createElement("div");
      card.className = "chunk-card";

      const hydeHtml = (chunk.hypothetical_questions && chunk.hypothetical_questions.length > 0)
        ? `
          <div class="chunk-hyde-section">
            <div class="chunk-hyde-title">Hypothetical Student Queries (HyDE):</div>
            <ul class="chunk-hyde-list">
              ${chunk.hypothetical_questions.map(q => `<li class="hyde-query">${q}</li>`).join("")}
            </ul>
          </div>
        `
        : "";

      card.innerHTML = `
        <div class="chunk-header">
          <span class="chunk-topic">${chunk.topic_name || "Concept Chunk"}</span>
          <span class="chunk-time-badge" data-start="${chunk.start_seconds}">${chunk.timestamp_label}</span>
        </div>
        <div class="chunk-context-breadcrumb">${chunk.context_header || ""}</div>
        <p class="chunk-cleaned-text">${chunk.cleaned_text || chunk.chunk_text}</p>
        ${hydeHtml}
      `;

      card.querySelector(".chunk-time-badge").addEventListener("click", () => {
        seekVideoTo(chunk.start_seconds);
      });

      // Clicking any hyde query asks it in the chatbot
      card.querySelectorAll(".hyde-query").forEach(li => {
        li.addEventListener("click", () => {
          submitChatQuery(li.textContent.trim());
        });
      });

      chunksContainer.appendChild(card);
    });
  }

  // Seek video and highlight
  function seekVideoTo(seconds) {
    if (video.duration && !isNaN(video.duration) && video.duration > 0) {
      if (seconds <= video.duration) {
        video.currentTime = seconds;
      } else {
        // If testing multi-hour lecture with sample video, loop position smoothly
        video.currentTime = seconds % video.duration;
      }
    } else {
      try { video.currentTime = seconds; } catch (e) {}
    }
    seekBar.value = seconds;
    timeCurrent.textContent = formatTime(seconds);
    playVideo();
    highlightActiveElements(seconds);
  }

  // Highlight active utterance & concept based on currentTime
  function highlightActiveElements(timeSec) {
    let activeUtt = null;
    let activeChunk = null;

    // Check utterances
    document.querySelectorAll(".utterance-item").forEach((el) => {
      const start = parseFloat(el.dataset.start);
      const end = parseFloat(el.dataset.end);
      if (timeSec >= start && timeSec <= end) {
        el.classList.add("active-playing");
        activeUtt = el;
      } else {
        el.classList.remove("active-playing");
      }
    });

    // Auto-scroll active utterance into view smoothly
    if (activeUtt) {
      activeUtt.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }

    // Check chunks for current concept name
    for (const c of currentChunks) {
      if (timeSec >= c.start_seconds && timeSec <= c.end_seconds) {
        activeChunk = c;
        break;
      }
    }

    if (activeChunk) {
      currentConceptName.textContent = `${activeChunk.timestamp_label} - ${activeChunk.topic_name}`;
    }
  }

  // Video playback controls
  function playVideo() {
    video.play().then(() => {
      isVideoPlaying = true;
      iconPlay.style.display = "none";
      iconPause.style.display = "block";
      videoOverlay.style.display = "none";
    }).catch(() => {
      // If autoplay blocked or no real source, simulate video progress timer!
      startSimulationTimer();
    });
  }

  function pauseVideo() {
    video.pause();
    isVideoPlaying = false;
    iconPlay.style.display = "block";
    iconPause.style.display = "none";
    videoOverlay.style.display = "flex";
    stopSimulationTimer();
  }

  // Simulation timer in case an uploaded video doesn't have an MP4 stream yet
  let simTimer = null;
  function startSimulationTimer() {
    if (simTimer) return;
    isVideoPlaying = true;
    iconPlay.style.display = "none";
    iconPause.style.display = "block";
    videoOverlay.style.display = "none";

    const rate = parseFloat(playbackSpeed.value) || 1.0;
    simTimer = setInterval(() => {
      let cur = parseFloat(seekBar.value) + (1 * rate);
      const max = parseFloat(seekBar.max) || 810;
      if (cur > max) cur = 0;
      seekBar.value = cur;
      timeCurrent.textContent = formatTime(cur);
      highlightActiveElements(cur);
    }, 1000);
  }

  function stopSimulationTimer() {
    if (simTimer) {
      clearInterval(simTimer);
      simTimer = null;
    }
  }

  ctrlPlayPause.addEventListener("click", () => {
    if (isVideoPlaying) pauseVideo(); else playVideo();
  });
  btnOverlayPlay.addEventListener("click", () => playVideo());

  video.addEventListener("timeupdate", () => {
    seekBar.value = video.currentTime;
    timeCurrent.textContent = formatTime(video.currentTime);
    highlightActiveElements(video.currentTime);
  });

  seekBar.addEventListener("input", (e) => {
    const val = parseFloat(e.target.value);
    video.currentTime = val;
    timeCurrent.textContent = formatTime(val);
    highlightActiveElements(val);
  });

  playbackSpeed.addEventListener("change", (e) => {
    video.playbackRate = parseFloat(e.target.value);
  });

  // Tab switching
  document.querySelectorAll(".tab-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
      document.querySelectorAll(".tab-content").forEach(c => c.classList.remove("active"));
      btn.classList.add("active");
      const targetId = `tab-${btn.dataset.tab}`;
      const targetEl = document.getElementById(targetId);
      if (targetEl) targetEl.classList.add("active");
    });
  });

  // Quick chips
  document.querySelectorAll(".chip").forEach(chip => {
    chip.addEventListener("click", () => {
      const q = chip.dataset.query;
      submitChatQuery(q);
    });
  });

  // Chat Submission
  async function submitChatQuery(query) {
    if (!query || !query.trim()) return;
    if (!currentLessonId) {
      alert("Please load or select a lecture first.");
      return;
    }

    // Append student message
    appendMessage("user", query);
    chatInput.value = "";

    // Show temporary AI thinking placeholder
    const thinkingId = appendThinkingBubble();

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: query,
          lesson_id: currentLessonId
        })
      });

      removeElement(thinkingId);

      if (!res.ok) {
        const err = await res.json();
        appendMessage("ai", `Error: ${err.detail || "Failed to retrieve answer."}`);
        return;
      }

      const data = await res.json();
      appendMessage("ai", data.answer, data.retrieved_evidence);
    } catch (err) {
      removeElement(thinkingId);
      appendMessage("ai", `Network error: ${err.message}`);
    }
  }

  chatForm.addEventListener("submit", (e) => {
    e.preventDefault();
    submitChatQuery(chatInput.value);
  });

  chatInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submitChatQuery(chatInput.value);
    }
  });

  btnClearChat.addEventListener("click", () => {
    chatMessages.innerHTML = "";
    appendMessage("ai", "Chat cleared. Ask any doubt about this lecture!");
  });

  function appendMessage(sender, text, evidence = null) {
    const wrap = document.createElement("div");
    wrap.className = `message-wrapper ${sender}`;

    const avatar = document.createElement("div");
    avatar.className = "msg-avatar";
    avatar.textContent = sender === "user" ? "ST" : "AI";

    const content = document.createElement("div");
    content.className = "msg-content";

    const bubble = document.createElement("div");
    bubble.className = "msg-bubble";

    // Format Markdown and Clickable Timestamp Badges
    const formattedHtml = formatChatMarkdown(text);
    bubble.innerHTML = formattedHtml;

    // Attach click handlers to any timestamp buttons inside the answer
    bubble.querySelectorAll(".ts-badge").forEach(badge => {
      badge.addEventListener("click", () => {
        const targetSec = parseTimestamp(badge.dataset.time);
        seekVideoTo(targetSec);
        badge.style.transform = "scale(1.2)";
        setTimeout(() => badge.style.transform = "scale(1)", 200);
      });
    });

    content.appendChild(bubble);

    // If evidence chunks returned, show expandable drawer
    if (evidence && evidence.length > 0) {
      const evidenceCard = document.createElement("div");
      evidenceCard.className = "evidence-card";
      evidenceCard.innerHTML = `
        <div class="evidence-header">
          <span>📚 Retrieved Lecture Evidence (${evidence.length} Chunks)</span>
          <span class="evidence-toggle">▾</span>
        </div>
        <div class="evidence-list">
          ${evidence.map(e => `
            <div class="evidence-item">
              <div class="evidence-item-left">
                <button class="ts-badge" data-time="${e.timestamp_label.split(' - ')[0]}">${e.timestamp_label.split(' - ')[0]}</button>
                <span>${e.topic_name}</span>
              </div>
              <span class="similarity-score">${Math.round(e.similarity_score * 100)}% match</span>
            </div>
          `).join("")}
        </div>
      `;

      evidenceCard.querySelectorAll(".ts-badge").forEach(badge => {
        badge.addEventListener("click", () => {
          const targetSec = parseTimestamp(badge.dataset.time);
          seekVideoTo(targetSec);
        });
      });

      const header = evidenceCard.querySelector(".evidence-header");
      const list = evidenceCard.querySelector(".evidence-list");
      header.addEventListener("click", () => {
        const isHidden = list.style.display === "none";
        list.style.display = isHidden ? "flex" : "none";
        header.querySelector(".evidence-toggle").textContent = isHidden ? "▾" : "▸";
      });

      content.appendChild(evidenceCard);
    }

    wrap.appendChild(avatar);
    wrap.appendChild(content);
    chatMessages.appendChild(wrap);
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  function appendThinkingBubble() {
    const id = `thinking-${Date.now()}`;
    const wrap = document.createElement("div");
    wrap.className = "message-wrapper ai";
    wrap.id = id;
    wrap.innerHTML = `
      <div class="msg-avatar">AI</div>
      <div class="msg-content">
        <div class="msg-bubble" style="color: var(--accent-cyan); font-style: italic;">
          🔍 Searching 768-dim vector embeddings & assembling lecture proof...
        </div>
      </div>
    `;
    chatMessages.appendChild(wrap);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return id;
  }

  function removeElement(id) {
    const el = document.getElementById(id);
    if (el) el.remove();
  }

  function formatChatMarkdown(text) {
    // 1. Replace [HH:MM:SS] or [MM:SS] or [MMM:SS] with interactive timestamp badge
    let html = text.replace(/\[(\d{1,2}:\d{2}:\d{2}|\d{1,3}:\d{2})\]/g, (match, p1) => {
      return `<button class="ts-badge" data-time="${p1}">[${p1}]</button>`;
    });

    // 2. Bold text **word**
    html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');

    // 3. Newlines to paragraphs
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

  // Load OS Sample lecture
  btnLoadSample.addEventListener("click", async () => {
    await loadSampleLecture();
  });

  async function loadSampleLecture() {
    btnLoadSample.disabled = true;
    btnLoadSample.textContent = "Loading Sample...";
    try {
      const res = await fetch("/api/load-sample", { method: "POST" });
      const data = await res.json();
      await loadLesson(data.lesson_id);
    } catch (err) {
      console.error("Failed to load sample:", err);
    } finally {
      btnLoadSample.disabled = false;
      btnLoadSample.innerHTML = `
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>
        Load OS Lecture Sample
      `;
    }
  }

  // Upload Modal handling
  btnOpenUpload.addEventListener("click", () => {
    uploadModal.style.display = "flex";
  });
  btnCloseModal.addEventListener("click", () => {
    uploadModal.style.display = "none";
  });
  btnCancelModal.addEventListener("click", () => {
    uploadModal.style.display = "none";
  });

  // Source Mode Toggle (File vs Online URL)
  btnModeFile.addEventListener("click", () => {
    uploadMode = "file";
    btnModeFile.classList.add("active");
    btnModeUrl.classList.remove("active");
    dropZone.style.display = "block";
    urlContainer.style.display = "none";
  });

  btnModeUrl.addEventListener("click", () => {
    uploadMode = "url";
    btnModeUrl.classList.add("active");
    btnModeFile.classList.remove("active");
    dropZone.style.display = "none";
    urlContainer.style.display = "block";
  });

  // Preset Buttons for 1-Click Online Testing
  const preset1hr = document.getElementById("preset-1hr");
  const preset2hr = document.getElementById("preset-2hr");

  if (preset1hr) {
    preset1hr.addEventListener("click", () => {
      mediaUrlInput.value = "https://archive.org/download/part-1_20240128/Part%201.mp3";
      document.getElementById("lecture-name-input").value = "Computer Science & Cryptography: Distributed Consensus";
      document.getElementById("course-name-input").value = "Distributed Systems & Blockchains";
    });
  }

  if (preset2hr) {
    preset2hr.addEventListener("click", () => {
      mediaUrlInput.value = "https://archive.org/download/science_gettingrich_1005_librivox/scienceofgettingrich_01_wattles_64kb.mp3";
      document.getElementById("lecture-name-input").value = "The Science of Getting Rich (2-Hour Series)";
      document.getElementById("course-name-input").value = "Philosophy of Science";
    });
  }

  dropZone.addEventListener("click", () => fileInput.click());
  fileInput.addEventListener("change", (e) => {
    if (e.target.files && e.target.files[0]) {
      selectedFile = e.target.files[0];
      selectedFileName.textContent = `Selected: ${selectedFile.name} (${(selectedFile.size / (1024 * 1024)).toFixed(1)} MB)`;
    }
  });

  dropZone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropZone.classList.add("dragover");
  });
  dropZone.addEventListener("dragleave", () => dropZone.classList.remove("dragover"));
  dropZone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropZone.classList.remove("dragover");
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      selectedFile = e.dataTransfer.files[0];
      selectedFileName.textContent = `Selected: ${selectedFile.name} (${(selectedFile.size / (1024 * 1024)).toFixed(1)} MB)`;
    }
  });

  // Submit Upload Form
  uploadForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    
    const title = document.getElementById("lecture-name-input").value;
    const course = document.getElementById("course-name-input").value;
    const formData = new FormData();
    formData.append("title", title);
    formData.append("course_name", course);

    if (uploadMode === "file") {
      if (!selectedFile) {
        alert("Please select a lecture video or audio file.");
        return;
      }
      formData.append("file", selectedFile);
    } else {
      const urlVal = mediaUrlInput.value.trim();
      if (!urlVal) {
        alert("Please enter a direct audio or video URL, or click a 1-click preset.");
        return;
      }
      formData.append("media_url", urlVal);
    }

    // Show stepper
    stepperProgress.style.display = "block";
    const step1 = document.getElementById("step-1");
    const step2 = document.getElementById("step-2");
    const step3 = document.getElementById("step-3");
    const step4 = document.getElementById("step-4");

    step1.classList.add("processing");

    // Advance stepper visual states as stages proceed
    setTimeout(() => {
      step1.classList.remove("processing"); step1.classList.add("completed");
      step2.classList.add("processing");
    }, 2500);

    setTimeout(() => {
      step2.classList.remove("processing"); step2.classList.add("completed");
      step3.classList.add("processing");
    }, 6000);

    setTimeout(() => {
      step3.classList.remove("processing"); step3.classList.add("completed");
      step4.classList.add("processing");
    }, 9500);

    try {
      const res = await fetch("/api/process-video", {
        method: "POST",
        body: formData
      });

      if (!res.ok) {
        const err = await res.json();
        alert(`Upload error: ${err.detail || "Processing failed"}`);
        stepperProgress.style.display = "none";
        return;
      }

      const result = await res.json();
      step4.classList.remove("processing"); step4.classList.add("completed");

      setTimeout(() => {
        uploadModal.style.display = "none";
        stepperProgress.style.display = "none";
        selectedFile = null;
        selectedFileName.textContent = "Supports MP4, WebM, MKV, MP3, WAV (up to 3 hours)";
        loadLesson(result.lesson_id);
      }, 1000);

    } catch (err) {
      alert(`Upload request failed: ${err.message}`);
      stepperProgress.style.display = "none";
    }
  });

  // Settings Modal handling
  btnSettings.addEventListener("click", () => {
    settingsModal.style.display = "flex";
  });
  btnCloseSettings.addEventListener("click", () => {
    settingsModal.style.display = "none";
  });
  btnCancelSettings.addEventListener("click", () => {
    settingsModal.style.display = "none";
  });

  settingsForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const deepKey = document.getElementById("set-deepgram").value;
    const gemKey = document.getElementById("set-gemini").value;
    const supUrl = document.getElementById("set-supabase-url").value;
    const supKey = document.getElementById("set-supabase-key").value;

    const payload = {};
    if (deepKey) payload.deepgram_key = deepKey;
    if (gemKey) payload.gemini_key = gemKey;
    if (supUrl) payload.supabase_url = supUrl;
    if (supKey) payload.supabase_key = supKey;

    try {
      const res = await fetch("/api/update-config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      if (res.ok) {
        settingsModal.style.display = "none";
        checkStatus();
      }
    } catch (err) {
      alert("Failed to update settings.");
    }
  });

  // Initial Boot
  checkStatus();
});
