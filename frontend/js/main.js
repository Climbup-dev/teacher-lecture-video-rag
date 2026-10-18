// ClimbUp Mentor Studio - Main Controller & Modular Loader
import { api } from "./api.js";
import { appState } from "./state.js";
import { initCoursesTab } from "./tabs/courses.js";
import { initUploadTab } from "./tabs/upload.js";
import { initMaterialsTab } from "./tabs/materials.js";
import { initStudioTab } from "./tabs/studio.js";
import { initChatTab } from "./tabs/chat.js";


document.addEventListener("DOMContentLoaded", async () => {
  const navTabs = document.querySelectorAll(".nav-tab");
  const viewPanels = document.querySelectorAll(".view-panel");
  const globalCourseSelect = document.getElementById("global-course-select");
  const kpiTotalChunks = document.getElementById("kpi-total-chunks");

  // Tab Navigation Routing
  function switchView(viewName) {
    navTabs.forEach(t => {
      if (t.dataset.view === viewName) {
        t.classList.add("active");
      } else {
        t.classList.remove("active");
      }
    });

    viewPanels.forEach(p => {
      if (p.id === `view-${viewName}`) {
        p.classList.add("active");
      } else {
        p.classList.remove("active");
      }
    });
  }

  navTabs.forEach(tab => {
    tab.addEventListener("click", () => {
      switchView(tab.dataset.view);
    });
  });

  // Global Course Select in Navbar
  function syncGlobalCourseSelect(courses) {
    if (!globalCourseSelect) return;
    const currentId = appState.get("currentCourseId");
    globalCourseSelect.innerHTML = "";

    courses.forEach(c => {
      const opt = document.createElement("option");
      opt.value = c.id;
      opt.textContent = c.title;
      globalCourseSelect.appendChild(opt);
    });

    if (currentId && courses.find(c => c.id === currentId)) {
      globalCourseSelect.value = currentId;
    } else if (courses.length > 0) {
      globalCourseSelect.value = courses[0].id;
      appState.setActiveCourse(courses[0].id);
    }
  }

  if (globalCourseSelect) {
    globalCourseSelect.addEventListener("change", (e) => {
      appState.setActiveCourse(e.target.value);
    });
  }

  appState.subscribe("courses", syncGlobalCourseSelect);
  appState.subscribe("currentCourseId", (id) => {
    if (globalCourseSelect) globalCourseSelect.value = id;
  });

  // Fetch initial system status
  try {
    const status = await api.getStatus();
    if (kpiTotalChunks) {
      kpiTotalChunks.textContent = status.total_chunks_indexed || 0;
    }
  } catch (err) {
    console.warn("Initial status error:", err);
  }

  // Initialize individual tab modules
  initCoursesTab();
  initUploadTab();
  initMaterialsTab();
  initStudioTab();
  initChatTab();

  // Settings Modal Handlers
  const settingsModal = document.getElementById("settings-modal");
  const btnSettings = document.getElementById("btn-settings");
  const btnCloseSettings = document.getElementById("btn-close-settings");
  const btnCancelSettings = document.getElementById("btn-cancel-settings");
  const settingsForm = document.getElementById("settings-form");

  if (btnSettings && settingsModal) {
    btnSettings.addEventListener("click", () => { settingsModal.style.display = "flex"; });
  }
  if (btnCloseSettings && settingsModal) {
    btnCloseSettings.addEventListener("click", () => { settingsModal.style.display = "none"; });
  }
  if (btnCancelSettings && settingsModal) {
    btnCancelSettings.addEventListener("click", () => { settingsModal.style.display = "none"; });
  }

  if (settingsForm) {
    settingsForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const gemKey = document.getElementById("set-gemini")?.value?.trim();
      const deepKey = document.getElementById("set-deepgram")?.value?.trim();

      const payload = {};
      if (gemKey) payload.gemini_key = gemKey;
      if (deepKey) payload.deepgram_key = deepKey;

      try {
        await api.updateConfig(payload);
        if (settingsModal) settingsModal.style.display = "none";
        alert("Cloud keys updated successfully!");
      } catch (err) {
        alert("Failed to update settings: " + err.message);
      }
    });
  }

  // Preload Drive files for upload modal picker in background
  api.getDriveFiles().then(data => {
    if (data && data.configured && data.files) {
      appState.set("driveFiles", data.files);
    }
  }).catch(() => {});
});
