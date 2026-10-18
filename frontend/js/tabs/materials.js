// Notes & Assignments Tab Module
import { api } from "../api.js";
import { appState } from "../state.js";

export function initMaterialsTab() {
  const btnToggleForm = document.getElementById("btn-toggle-material-form");
  const btnClosePanel = document.getElementById("btn-close-material-panel");
  const uploadPanel = document.getElementById("material-upload-panel");
  const resourceForm = document.getElementById("dedicated-resource-form");
  const matCourseSelect = document.getElementById("mat-course-select");
  const matTypeSelect = document.getElementById("mat-type-select");
  const matTitleInput = document.getElementById("mat-title-input");
  const matDescInput = document.getElementById("mat-desc-input");
  const matFileInput = document.getElementById("mat-file-input");
  const matDueDate = document.getElementById("mat-due-date");
  const matMaxPoints = document.getElementById("mat-max-points");
  const assignmentExtraFields = document.getElementById("assignment-extra-fields");
  const uploadStatus = document.getElementById("mat-upload-status");
  const cardsContainer = document.getElementById("materials-cards-container");
  const activeCourseNameLabel = document.getElementById("mats-active-course-name");

  const countAll = document.getElementById("count-all-mats");
  const countNotes = document.getElementById("count-notes");
  const countAssignments = document.getElementById("count-assignments");
  const countSlides = document.getElementById("count-slides");
  const countLabs = document.getElementById("count-labs");
  const filterPills = document.querySelectorAll("#materials-filter-pills .filter-pill");
  const badgeNotes = document.getElementById("badge-notes-count");
  const kpiResources = document.getElementById("kpi-total-resources");

  let activeFilter = "all";

  // Toggle Upload Panel
  if (btnToggleForm && uploadPanel) {
    btnToggleForm.addEventListener("click", () => {
      const isHidden = uploadPanel.style.display === "none";
      uploadPanel.style.display = isHidden ? "block" : "none";
      if (isHidden) uploadPanel.scrollIntoView({ behavior: "smooth" });
    });
  }

  if (btnClosePanel && uploadPanel) {
    btnClosePanel.addEventListener("click", () => {
      uploadPanel.style.display = "none";
    });
  }

  // Dynamic assignment extra fields
  if (matTypeSelect && assignmentExtraFields) {
    matTypeSelect.addEventListener("change", (e) => {
      if (e.target.value === "assignment") {
        assignmentExtraFields.style.display = "grid";
      } else {
        assignmentExtraFields.style.display = "none";
      }
    });
  }

  // Handle Form Submission
  if (resourceForm) {
    resourceForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const courseId = (matCourseSelect && matCourseSelect.value) || appState.get("currentCourseId");
      const type = matTypeSelect.value;
      const title = matTitleInput.value.trim();
      const desc = matDescInput.value.trim();
      const file = matFileInput.files[0];
      const submitBtn = document.getElementById("btn-submit-mat");

      if (!file) {
        alert("Please select a file to upload.");
        return;
      }

      let fullDesc = desc;
      if (type === "assignment") {
        const due = matDueDate.value;
        const pts = matMaxPoints.value;
        const extra = [];
        if (due) extra.push(`Due: ${due}`);
        if (pts) extra.push(`Points: ${pts}`);
        if (extra.length > 0) {
          fullDesc = `[${extra.join(" | ")}] ${desc}`;
        }
      }

      const formData = new FormData();
      formData.append("course_id", courseId);
      formData.append("title", title);
      formData.append("file_type", type);
      formData.append("description", fullDesc);
      formData.append("file", file);

      if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.textContent = "Uploading to Supabase Storage...";
      }
      if (uploadStatus) uploadStatus.innerHTML = `<span style="color: var(--accent-cyan);">Uploading file to Supabase bucket ('course_resources')...</span>`;

      try {
        await api.uploadResource(formData);

        if (uploadStatus) uploadStatus.innerHTML = `<span style="color: var(--accent-emerald);">✓ Successfully uploaded to Supabase Storage!</span>`;
        resourceForm.reset();
        if (assignmentExtraFields) assignmentExtraFields.style.display = "none";

        setTimeout(() => {
          if (uploadStatus) uploadStatus.innerHTML = "";
          if (uploadPanel) uploadPanel.style.display = "none";
        }, 1500);

        await refreshMaterials();
      } catch (err) {
        if (uploadStatus) uploadStatus.innerHTML = `<span style="color: var(--accent-rose);">Upload error: ${err.message}</span>`;
      } finally {
        if (submitBtn) {
          submitBtn.disabled = false;
          submitBtn.textContent = "Upload to Supabase Storage";
        }
      }
    });
  }

  // Filter Pills
  filterPills.forEach(pill => {
    pill.addEventListener("click", () => {
      filterPills.forEach(p => p.classList.remove("active"));
      pill.classList.add("active");
      activeFilter = pill.dataset.type;
      renderCards(filterMaterials(appState.get("materials") || [], activeFilter));
    });
  });

  function filterMaterials(mats, type) {
    if (type === "all") return mats;
    if (type === "notes") return mats.filter(m => (m.file_type || "").match(/notes|pdf|cheatsheet/i));
    if (type === "assignment") return mats.filter(m => (m.file_type || "").match(/assignment|hw|problem/i));
    if (type === "slides") return mats.filter(m => (m.file_type || "").match(/slides|ppt/i));
    if (type === "lab") return mats.filter(m => (m.file_type || "").match(/lab|zip|code|ipynb/i));
    return mats;
  }

  function updateCounts(mats) {
    if (countAll) countAll.textContent = mats.length;
    const notes = mats.filter(m => (m.file_type || "").match(/notes|pdf|cheatsheet/i));
    const assignments = mats.filter(m => (m.file_type || "").match(/assignment|hw|problem/i));
    const slides = mats.filter(m => (m.file_type || "").match(/slides|ppt/i));
    const labs = mats.filter(m => (m.file_type || "").match(/lab|zip|code|ipynb/i));

    if (countNotes) countNotes.textContent = notes.length;
    if (countAssignments) countAssignments.textContent = assignments.length;
    if (countSlides) countSlides.textContent = slides.length;
    if (countLabs) countLabs.textContent = labs.length;
    if (badgeNotes) badgeNotes.textContent = mats.length;
    if (kpiResources) kpiResources.textContent = mats.length;
  }

  function renderCards(mats) {
    if (!cardsContainer) return;
    cardsContainer.innerHTML = "";

    if (!mats || mats.length === 0) {
      cardsContainer.innerHTML = `<div class="empty-state">No materials found in this category. Click "+ Upload Material" above to upload lecture slides, PDF notes, or assignments directly to Supabase.</div>`;
      return;
    }

    mats.forEach(m => {
      const card = document.createElement("div");
      const rawType = (m.file_type || "pdf").toLowerCase();
      const isAssignment = rawType.includes("assignment");
      card.className = `material-card ${isAssignment ? "assignment" : rawType}`;

      let assignmentMeta = null;
      let cleanDesc = m.description || "Official course material.";
      const metaMatch = cleanDesc.match(/^\[(.*?)\]\s*(.*)$/);
      if (metaMatch) {
        assignmentMeta = metaMatch[1];
        cleanDesc = metaMatch[2];
      }

      const iconLabel = rawType.includes("assignment") ? "HW" : rawType.includes("slide") ? "PPT" : rawType.includes("lab") || rawType.includes("zip") ? "CODE" : "PDF";

      card.innerHTML = `
        <div class="mat-card-header">
          <div class="mat-icon-badge ${rawType}">
            ${iconLabel}
          </div>
          <div class="mat-info">
            <h4 class="mat-title">${m.title}</h4>
            <div class="mat-meta-row">
              <span>${m.file_size || "Document"}</span>
              <span>&bull;</span>
              <span>Supabase Storage</span>
            </div>
          </div>
        </div>

        ${assignmentMeta ? `
          <div class="mat-assignment-banner">
            <span>📋 ${assignmentMeta}</span>
          </div>
        ` : ""}

        <p class="mat-desc">${cleanDesc}</p>

        <div class="mat-actions-row">
          <a href="${m.download_url}" target="_blank" rel="noopener noreferrer" class="btn btn-sm btn-primary">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>
            Download / View
          </a>
          <button class="btn btn-sm btn-danger-outline btn-delete-mat" data-id="${m.id}" title="Delete Material">🗑️ Delete</button>
        </div>
      `;

      card.querySelector(".btn-delete-mat").addEventListener("click", async () => {
        if (confirm(`Delete material "${m.title}"?`)) {
          await api.deleteResource(m.id);
          await refreshMaterials();
        }
      });

      cardsContainer.appendChild(card);
    });
  }

  async function refreshMaterials() {
    const courseId = appState.get("currentCourseId");
    try {
      const mats = await api.getCourseResources(courseId);
      appState.set("materials", mats);
      updateCounts(mats);
      renderCards(filterMaterials(mats, activeFilter));
    } catch (e) {
      console.warn("refreshMaterials error:", e);
    }
  }

  function updateCourseLabel() {
    const courses = appState.get("courses") || [];
    const courseId = appState.get("currentCourseId");
    if (matCourseSelect) matCourseSelect.value = courseId;
    const active = courses.find(c => c.id === courseId);
    if (active && activeCourseNameLabel) {
      activeCourseNameLabel.textContent = active.title;
    }
    refreshMaterials();
  }

  appState.subscribe("currentCourseId", updateCourseLabel);
  appState.subscribe("courses", updateCourseLabel);

  refreshMaterials();
}
