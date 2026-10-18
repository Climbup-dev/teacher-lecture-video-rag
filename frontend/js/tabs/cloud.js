// Drive Vault & Cloud Infrastructure Tab Module
import { api } from "../api.js";
import { appState } from "../state.js";

export function initCloudTab() {
  const driveMainList = document.getElementById("drive-main-list");
  const btnRefreshDriveMain = document.getElementById("btn-refresh-drive-main");
  const driveSearchInput = document.getElementById("drive-search-input");
  const driveVaultStat = document.getElementById("drive-vault-stat");
  const badgeDrive = document.getElementById("badge-drive-count");

  const settingsModal = document.getElementById("settings-modal");
  const btnSettings = document.getElementById("btn-settings");
  const btnCloseSettings = document.getElementById("btn-close-settings");
  const btnCancelSettings = document.getElementById("btn-cancel-settings");
  const settingsForm = document.getElementById("settings-form");

  function renderDriveFiles(files) {
    if (!driveMainList) return;
    driveMainList.innerHTML = "";

    if (!files || files.length === 0) {
      driveMainList.innerHTML = `<div class="empty-state">No files detected in Google Drive folder.</div>`;
      return;
    }

    files.forEach(f => {
      const card = document.createElement("div");
      card.className = "drive-file-card";
      const sizeMb = f.size ? (parseInt(f.size, 10) / (1024 * 1024)).toFixed(1) : "?";

      card.innerHTML = `
        <div class="drive-card-info">
          <div class="drive-card-icon">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="23 7 16 12 23 17 23 7"></polygon><rect x="1" y="5" width="15" height="14" rx="2" ry="2"></rect></svg>
          </div>
          <div class="drive-card-text">
            <span class="drive-card-name" title="${f.name}">${f.name}</span>
            <span class="drive-card-meta">${sizeMb} MB &bull; Google Drive</span>
          </div>
        </div>
        <button class="btn btn-sm btn-primary btn-quick-ingest" data-id="${f.id}" data-name="${f.name}">
          ⚡ Ingest for RAG
        </button>
      `;

      card.querySelector(".btn-quick-ingest").addEventListener("click", () => {
        const uploadTab = document.getElementById("tab-nav-upload");
        if (uploadTab) uploadTab.click();

        const lectureTitleInput = document.getElementById("lecture-title-input");
        const mediaUrlInput = document.getElementById("media-url-input");
        const btnModeUrl = document.getElementById("btn-mode-url");

        if (lectureTitleInput) {
          lectureTitleInput.value = f.name.replace(/\.[^/.]+$/, "").replace(/[-_]/g, " ");
        }
        if (mediaUrlInput) {
          mediaUrlInput.value = `https://drive.google.com/file/d/${f.id}/view`;
        }
        if (btnModeUrl) {
          btnModeUrl.click();
        }
      });

      driveMainList.appendChild(card);
    });
  }

  async function refreshDriveFiles() {
    try {
      const data = await api.getDriveFiles();
      if (!data.configured) return;
      const files = data.files || [];
      appState.set("driveFiles", files);

      if (badgeDrive) badgeDrive.textContent = files.length;
      if (driveVaultStat) driveVaultStat.textContent = `Total Files: ${files.length} detected`;
      renderDriveFiles(files);
    } catch (e) {
      console.warn("refreshDriveFiles error:", e);
    }
  }

  if (driveSearchInput) {
    driveSearchInput.addEventListener("input", (e) => {
      const q = e.target.value.toLowerCase().trim();
      const files = appState.get("driveFiles") || [];
      const filtered = files.filter(f => (f.name && f.name.toLowerCase().includes(q)));
      renderDriveFiles(filtered);
    });
  }

  if (btnRefreshDriveMain) {
    btnRefreshDriveMain.addEventListener("click", refreshDriveFiles);
  }

  // Settings Modal
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
      const gemKey = document.getElementById("set-gemini").value.trim();
      const deepKey = document.getElementById("set-deepgram").value.trim();

      const payload = {};
      if (gemKey) payload.gemini_key = gemKey;
      if (deepKey) payload.deepgram_key = deepKey;

      try {
        await api.updateConfig(payload);
        if (settingsModal) settingsModal.style.display = "none";
        alert("Cloud keys updated successfully!");
        refreshDriveFiles();
      } catch (err) {
        alert("Failed to update settings: " + err.message);
      }
    });
  }

  appState.subscribe("driveFiles", renderDriveFiles);

  refreshDriveFiles();
}
