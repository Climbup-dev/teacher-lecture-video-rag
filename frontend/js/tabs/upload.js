// Video Upload & Ingestion Pipeline Tab Module
import { api } from "../api.js";
import { appState } from "../state.js";

export function initUploadTab() {
  const uploadCourseSelect = document.getElementById("upload-course-select");
  const uploadTargetCourseName = document.getElementById("upload-target-course-name");
  const lectureUploadForm = document.getElementById("lecture-upload-form");
  const lectureTitleInput = document.getElementById("lecture-title-input");
  const btnModeFile = document.getElementById("btn-mode-file");
  const btnModeUrl = document.getElementById("btn-mode-url");
  const btnModeVault = document.getElementById("btn-mode-vault");
  const dropZone = document.getElementById("drop-zone");
  const fileInput = document.getElementById("file-input");
  const selectedFileName = document.getElementById("selected-file-name");
  const urlContainer = document.getElementById("url-container");
  const mediaUrlInput = document.getElementById("media-url-input");
  const vaultPickerContainer = document.getElementById("vault-picker-container");
  const vaultPickerList = document.getElementById("vault-picker-list");
  const stepperProgress = document.getElementById("stepper-progress");
  const indexedLecturesList = document.getElementById("indexed-lectures-list");
  const totalLessonsBadge = document.getElementById("total-lessons-badge");
  const kpiLectures = document.getElementById("kpi-total-lectures");

  let selectedUploadFile = null;
  let uploadMode = "file";

  // Mode toggling
  if (btnModeFile) {
    btnModeFile.addEventListener("click", () => {
      uploadMode = "file";
      btnModeFile.classList.add("active");
      if (btnModeUrl) btnModeUrl.classList.remove("active");
      if (btnModeVault) btnModeVault.classList.remove("active");
      if (dropZone) dropZone.style.display = "flex";
      if (urlContainer) urlContainer.style.display = "none";
      if (vaultPickerContainer) vaultPickerContainer.style.display = "none";
    });
  }

  if (btnModeUrl) {
    btnModeUrl.addEventListener("click", () => {
      uploadMode = "url";
      btnModeUrl.classList.add("active");
      if (btnModeFile) btnModeFile.classList.remove("active");
      if (btnModeVault) btnModeVault.classList.remove("active");
      if (dropZone) dropZone.style.display = "none";
      if (urlContainer) urlContainer.style.display = "flex";
      if (vaultPickerContainer) vaultPickerContainer.style.display = "none";
    });
  }

  if (btnModeVault) {
    btnModeVault.addEventListener("click", () => {
      uploadMode = "vault";
      btnModeVault.classList.add("active");
      if (btnModeFile) btnModeFile.classList.remove("active");
      if (btnModeUrl) btnModeUrl.classList.remove("active");
      if (dropZone) dropZone.style.display = "none";
      if (urlContainer) urlContainer.style.display = "none";
      if (vaultPickerContainer) vaultPickerContainer.style.display = "flex";
      renderVaultPicker();
    });
  }

  // Dropzone handling
  if (dropZone && fileInput) {
    dropZone.addEventListener("click", () => fileInput.click());
    fileInput.addEventListener("change", (e) => {
      if (e.target.files && e.target.files.length > 0) {
        selectedUploadFile = e.target.files[0];
        const sizeMb = (selectedUploadFile.size / (1024 * 1024)).toFixed(1);
        if (selectedFileName) selectedFileName.textContent = `Selected: ${selectedUploadFile.name} (${sizeMb} MB) - Ready to process`;
        if (lectureTitleInput && !lectureTitleInput.value) {
          lectureTitleInput.value = selectedUploadFile.name.replace(/\.[^/.]+$/, "").replace(/[-_]/g, " ");
        }
      }
    });

    dropZone.addEventListener("dragover", (e) => {
      e.preventDefault();
      dropZone.style.borderColor = "var(--primary)";
    });

    dropZone.addEventListener("dragleave", () => {
      dropZone.style.borderColor = "rgba(99, 102, 241, 0.35)";
    });

    dropZone.addEventListener("drop", (e) => {
      e.preventDefault();
      dropZone.style.borderColor = "rgba(99, 102, 241, 0.35)";
      if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
        selectedUploadFile = e.dataTransfer.files[0];
        const sizeMb = (selectedUploadFile.size / (1024 * 1024)).toFixed(1);
        if (selectedFileName) selectedFileName.textContent = `Selected: ${selectedUploadFile.name} (${sizeMb} MB) - Ready to process`;
        if (lectureTitleInput && !lectureTitleInput.value) {
          lectureTitleInput.value = selectedUploadFile.name.replace(/\.[^/.]+$/, "").replace(/[-_]/g, " ");
        }
      }
    });
  }

  // 1-Click URL presets
  document.querySelectorAll(".preset-tag").forEach(tag => {
    tag.addEventListener("click", () => {
      if (mediaUrlInput) mediaUrlInput.value = tag.dataset.url;
      if (lectureTitleInput && !lectureTitleInput.value) {
        lectureTitleInput.value = tag.textContent;
      }
    });
  });

  function renderVaultPicker() {
    if (!vaultPickerList) return;
    vaultPickerList.innerHTML = "";
    const driveFiles = appState.get("driveFiles") || [];
    if (driveFiles.length === 0) {
      vaultPickerList.innerHTML = `<div class="empty-state">No Drive files detected. Check Cloud tab.</div>`;
      return;
    }

    driveFiles.forEach(f => {
      const item = document.createElement("div");
      item.className = "vault-picker-item";
      const sizeMb = f.size ? (parseInt(f.size, 10) / (1024 * 1024)).toFixed(1) : "?";
      item.innerHTML = `
        <span style="font-size: 0.82rem; font-weight: 600; color: #fff;">${f.name}</span>
        <span style="font-size: 0.72rem; color: var(--text-dim);">${sizeMb} MB</span>
      `;
      item.addEventListener("click", () => {
        document.querySelectorAll(".vault-picker-item").forEach(i => i.classList.remove("selected"));
        item.classList.add("selected");
        if (mediaUrlInput) mediaUrlInput.value = `https://drive.google.com/file/d/${f.id}/view`;
        if (lectureTitleInput && !lectureTitleInput.value) {
          lectureTitleInput.value = f.name.replace(/\.[^/.]+$/, "").replace(/[-_]/g, " ");
        }
      });
      vaultPickerList.appendChild(item);
    });
  }

  // Handle Video Upload Submit
  if (lectureUploadForm) {
    lectureUploadForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const courseId = (uploadCourseSelect && uploadCourseSelect.value) || appState.get("currentCourseId");
      const title = lectureTitleInput ? lectureTitleInput.value.trim() : "";

      if (!title) {
        alert("Please enter a lecture title.");
        return;
      }

      const courses = appState.get("courses") || [];
      const activeCourse = courses.find(c => c.id === courseId);
      const courseName = activeCourse ? activeCourse.title : "University Course";

      const formData = new FormData();
      formData.append("title", title);
      formData.append("course_id", courseId);
      formData.append("course_name", courseName);

      if (uploadMode === "file") {
        if (!selectedUploadFile) {
          alert("Please select a video file to upload.");
          return;
        }
        formData.append("file", selectedUploadFile);
      } else {
        const urlVal = mediaUrlInput ? mediaUrlInput.value.trim() : "";
        if (!urlVal) {
          alert("Please enter a media URL or select a video from Drive.");
          return;
        }
        formData.append("media_url", urlVal);
      }

      // Stepper UI
      if (stepperProgress) stepperProgress.style.display = "block";
      const step1 = document.getElementById("step-1");
      const step2 = document.getElementById("step-2");
      const step3 = document.getElementById("step-3");
      const step4 = document.getElementById("step-4");
      const steps = [step1, step2, step3, step4].filter(Boolean);

      steps.forEach(s => {
        s.classList.remove("completed", "processing");
        const statusEl = s.querySelector(".step-status");
        if (statusEl) statusEl.textContent = "Pending";
      });

      if (step1) {
        step1.classList.add("processing");
        step1.querySelector(".step-status").textContent = "Queuing...";
      }

      try {
        const initData = await api.processVideo(formData);
        const jobId = initData.job_id;

        // Immediately refresh lectures list so video is visible & accessible to user right away!
        await refreshLessons();

        // Poll job status until complete
        let pollCount = 0;
        const maxPolls = 600;
        const pollInterval = setInterval(async () => {
          pollCount++;
          if (pollCount > maxPolls) {
            clearInterval(pollInterval);
            alert("Job is still processing in the background. You can check back shortly.");
            return;
          }

          try {
            const job = await api.getJob(jobId);
            const stage = job.current_stage || job.stage || "QUEUED";
            const status = job.status || "IN_PROGRESS";

            if (stage === "AUDIO_EXTRACTION") {
              if (step1) { step1.classList.remove("processing"); step1.classList.add("completed"); step1.querySelector(".step-status").textContent = "Done"; }
              if (step2) { step2.classList.add("processing"); step2.querySelector(".step-status").textContent = "Extracting..."; }
            } else if (stage === "TRANSCRIPTION") {
              if (step1) { step1.classList.add("completed"); step1.querySelector(".step-status").textContent = "Done"; }
              if (step2) { step2.classList.add("processing"); step2.querySelector(".step-status").textContent = "Transcribing..."; }
            } else if (stage === "SEMANTIC_PROCESSING") {
              if (step1) { step1.classList.add("completed"); step1.querySelector(".step-status").textContent = "Done"; }
              if (step2) { step2.classList.remove("processing"); step2.classList.add("completed"); step2.querySelector(".step-status").textContent = "Done"; }
              if (step3) { step3.classList.add("processing"); step3.querySelector(".step-status").textContent = "Chunking..."; }
            } else if (stage === "EMBEDDING" || stage === "VECTOR_SYNC") {
              if (step1) { step1.classList.add("completed"); step1.querySelector(".step-status").textContent = "Done"; }
              if (step2) { step2.classList.add("completed"); step2.querySelector(".step-status").textContent = "Done"; }
              if (step3) { step3.classList.remove("processing"); step3.classList.add("completed"); step3.querySelector(".step-status").textContent = "Done"; }
              if (step4) { step4.classList.add("processing"); step4.querySelector(".step-status").textContent = "Embedding..."; }
            }

            if (status === "COMPLETED") {
              clearInterval(pollInterval);
              if (step1) { step1.classList.add("completed"); step1.querySelector(".step-status").textContent = "Done"; }
              if (step2) { step2.classList.add("completed"); step2.querySelector(".step-status").textContent = "Done"; }
              if (step3) { step3.classList.add("completed"); step3.querySelector(".step-status").textContent = "Done"; }
              if (step4) {
                step4.classList.remove("processing");
                step4.classList.add("completed");
                step4.querySelector(".step-status").textContent = "Indexed";
              }

              alert(`✓ Lecture "${title}" successfully processed with Deepgram Nova-2 and indexed into Supabase!`);

              selectedUploadFile = null;
              if (selectedFileName) selectedFileName.textContent = "Supports MP4, WebM, MKV, MP3, WAV (Direct Google Drive offload)";
              if (lectureTitleInput) lectureTitleInput.value = "";
              if (mediaUrlInput) mediaUrlInput.value = "";
              if (stepperProgress) stepperProgress.style.display = "none";

              await refreshLessons();

              if (confirm("Would you like to open this lecture immediately in the Interactive Studio?")) {
                appState.setActiveLesson(job.lesson_id || initData.lesson_id);
                const studioTab = document.getElementById("tab-nav-studio");
                if (studioTab) studioTab.click();
              }
            } else if (status === "FAILED") {
              clearInterval(pollInterval);
              alert("Ingestion error: " + (job.error_message || "Video processing failed."));
              if (stepperProgress) stepperProgress.style.display = "none";
            }
          } catch (e) {
            console.warn("Upload tab poll error:", e);
          }
        }, 2000);

      } catch (err) {
        alert("Ingestion error: " + err.message);
        if (stepperProgress) stepperProgress.style.display = "none";
      }
    });
  }

  // Render indexed lectures
  function renderLectures(lessons) {
    if (!indexedLecturesList) return;
    indexedLecturesList.innerHTML = "";

    if (!lessons || lessons.length === 0) {
      indexedLecturesList.innerHTML = `<div class="empty-state">No indexed lectures in database.</div>`;
      return;
    }

    lessons.forEach(l => {
      const card = document.createElement("div");
      card.className = "lecture-item-card";
      const uttLen = l.utterances ? l.utterances.length : 0;
      const durMin = l.duration_seconds ? Math.floor(l.duration_seconds / 60) : 0;
      const isIndexing = l.processing_status === "indexing";
      const statusBadge = isIndexing 
        ? `<span class="badge-mini" style="background: rgba(245, 158, 11, 0.15); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.35);">⚡ AI Indexing</span>`
        : `<span class="badge-mini">✓ Ready</span>`;

      card.innerHTML = `
        <div class="lecture-item-top">
          <span class="lecture-item-title">${l.title}</span>
          ${statusBadge}
        </div>
        <div class="lecture-item-stats">
          <span>⏱️ ${durMin > 0 ? durMin + " mins" : "Live Stream"}</span>
          <span>🗣️ ${isIndexing ? "Transcribing..." : uttLen + " utterances"}</span>
          <span>${isIndexing ? "⏳ Vector Sync" : "⚡ 768-dim RAG"}</span>
        </div>
        <div class="lecture-item-actions">
          <button class="btn btn-sm btn-primary btn-play-lecture" data-id="${l.id}">▶ Play in Studio</button>
          <button class="btn btn-sm btn-danger-outline btn-delete-lecture" data-id="${l.id}" title="Delete Lecture">🗑️</button>
        </div>
      `;

      card.querySelector(".btn-play-lecture").addEventListener("click", () => {
        appState.setActiveLesson(l.id);
        const studioTab = document.getElementById("tab-nav-studio");
        if (studioTab) studioTab.click();
      });

      card.querySelector(".btn-delete-lecture").addEventListener("click", async () => {
        if (confirm(`Delete lecture "${l.title}"?`)) {
          await api.deleteLesson(l.id);
          await refreshLessons();
        }
      });

      indexedLecturesList.appendChild(card);
    });
  }

  async function refreshLessons() {
    try {
      const lessons = await api.getLessons();
      appState.set("lessons", lessons);
      if (kpiLectures) kpiLectures.textContent = lessons.length;
      if (totalLessonsBadge) totalLessonsBadge.textContent = `${lessons.length} Lectures`;
      renderLectures(lessons);
    } catch (e) {
      console.warn("refreshLessons error:", e);
    }
  }

  // Update target course display when state changes
  function updateTargetCourse() {
    const courses = appState.get("courses") || [];
    const courseId = appState.get("currentCourseId");
    if (uploadCourseSelect) {
      uploadCourseSelect.value = courseId;
    }
    const current = courses.find(c => c.id === courseId);
    if (current && uploadTargetCourseName) {
      uploadTargetCourseName.textContent = current.title;
    }
  }

  appState.subscribe("currentCourseId", updateTargetCourse);
  appState.subscribe("courses", updateTargetCourse);
  appState.subscribe("lessons", renderLectures);
  appState.subscribe("driveFiles", renderVaultPicker);

  refreshLessons();
}
