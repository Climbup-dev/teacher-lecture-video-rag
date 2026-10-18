// Courses Management Tab Module
import { api } from "../api.js";
import { appState } from "../state.js";

export function initCoursesTab() {
  const btnShowCreate = document.getElementById("btn-show-create-course");
  const btnHideCreate = document.getElementById("btn-hide-create-course");
  const btnCancelCreate = document.getElementById("btn-cancel-create-course");
  const createPanel = document.getElementById("create-course-panel");
  const createForm = document.getElementById("create-course-form");
  const feedbackMsg = document.getElementById("create-course-feedback");
  const cardsContainer = document.getElementById("courses-cards-container");
  const searchInput = document.getElementById("course-search-input");
  const categoryFilters = document.querySelectorAll("#course-category-filters .filter-pill");

  const kpiCourses = document.getElementById("kpi-total-courses");
  const badgeCourses = document.getElementById("badge-courses-count");

  // Toggle Create Course Form
  if (btnShowCreate && createPanel) {
    btnShowCreate.addEventListener("click", () => {
      createPanel.style.display = "block";
      createPanel.scrollIntoView({ behavior: "smooth" });
    });
  }
  if (btnHideCreate && createPanel) {
    btnHideCreate.addEventListener("click", () => {
      createPanel.style.display = "none";
    });
  }
  if (btnCancelCreate && createPanel) {
    btnCancelCreate.addEventListener("click", () => {
      createPanel.style.display = "none";
    });
  }

  // Handle Create Course Form Submit
  if (createForm) {
    createForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const title = document.getElementById("new-course-title").value.trim();
      const category = document.getElementById("new-course-category").value;
      const level = document.getElementById("new-course-level").value;
      const instructor = document.getElementById("new-course-instructor").value.trim() || "Course Instructor";
      const thumbnail = document.getElementById("new-course-thumbnail").value.trim();
      const tagline = document.getElementById("new-course-tagline").value.trim();
      const desc = document.getElementById("new-course-desc").value.trim();
      const submitBtn = document.getElementById("btn-submit-course");

      if (!title) {
        alert("Please provide a course title.");
        return;
      }

      submitBtn.disabled = true;
      submitBtn.textContent = "Creating Course...";
      if (feedbackMsg) feedbackMsg.innerHTML = `<span style="color: var(--accent-cyan);">Saving course to Supabase & local store...</span>`;

      try {
        const data = await api.createCourse({
          title,
          category,
          level,
          instructor_name: instructor,
          thumbnail,
          tagline,
          description: desc
        });

        if (feedbackMsg) feedbackMsg.innerHTML = `<span style="color: var(--accent-emerald);">✓ Course '${title}' created successfully!</span>`;
        createForm.reset();

        setTimeout(() => {
          if (feedbackMsg) feedbackMsg.innerHTML = "";
          if (createPanel) createPanel.style.display = "none";
        }, 1500);

        await refreshCourses();
        if (data.course && data.course.id) {
          appState.setActiveCourse(data.course.id);
        }
      } catch (err) {
        if (feedbackMsg) feedbackMsg.innerHTML = `<span style="color: var(--accent-rose);">Error: ${err.message}</span>`;
      } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = "Create Course";
      }
    });
  }

  // Filter & Search listeners
  if (searchInput) {
    searchInput.addEventListener("input", (e) => {
      const q = e.target.value.toLowerCase().trim();
      const courses = appState.get("courses") || [];
      const filtered = courses.filter(c => 
        (c.title && c.title.toLowerCase().includes(q)) ||
        (c.category && c.category.toLowerCase().includes(q)) ||
        (c.instructor_name && c.instructor_name.toLowerCase().includes(q))
      );
      renderCards(filtered);
    });
  }

  categoryFilters.forEach(pill => {
    pill.addEventListener("click", () => {
      categoryFilters.forEach(p => p.classList.remove("active"));
      pill.classList.add("active");
      const cat = pill.dataset.category;
      const courses = appState.get("courses") || [];
      if (cat === "all") {
        renderCards(courses);
      } else {
        const filtered = courses.filter(c => (c.category || "").toLowerCase().includes(cat.toLowerCase()));
        renderCards(filtered);
      }
    });
  });

  // Render course cards
  function renderCards(courses) {
    if (!cardsContainer) return;
    cardsContainer.innerHTML = "";

    if (!courses || courses.length === 0) {
      cardsContainer.innerHTML = `<div class="empty-state">No courses found. Click "+ Create New Course" above to create your first curriculum.</div>`;
      return;
    }

    const currentCourseId = appState.get("currentCourseId");

    courses.forEach(c => {
      const isActive = c.id === currentCourseId;
      const card = document.createElement("div");
      card.className = `course-card ${isActive ? "is-active" : ""}`;

      const thumb = c.thumbnail || "https://images.unsplash.com/photo-1516321318423-f06f85e504b3?w=800&auto=format&fit=crop&q=80";
      const lessonsCount = c.total_lessons || 0;
      const category = c.category || "Computer Science";
      const level = c.level || "All Levels";
      const instructor = c.instructor_name || "Course Instructor";

      card.innerHTML = `
        ${isActive ? `<div class="active-ribbon">Active Teaching</div>` : ""}
        <div class="course-thumb-wrap">
          <img src="${thumb}" alt="${c.title}" class="course-thumb-img" onerror="this.src='https://images.unsplash.com/photo-1516321318423-f06f85e504b3?w=800'">
          <div class="course-thumb-badges">
            <span class="category-tag">${category}</span>
            <span class="level-tag">${level}</span>
          </div>
        </div>
        <div class="course-body">
          <h3 class="course-card-title">${c.title}</h3>
          <p class="course-tagline">${c.tagline || c.description || "Master core concepts with synchronized video RAG and doubt assistant."}</p>
          
          <div class="course-instructor-row">
            <div class="instructor-avatar">${instructor.substring(0, 2).toUpperCase()}</div>
            <span class="instructor-name">${instructor}</span>
          </div>

          <div class="course-stats-row">
            <span>🎬 ${lessonsCount} Video Lectures</span>
            <span>⚡ 768-dim Supabase RAG</span>
          </div>
        </div>
        <div class="course-card-footer">
          ${!isActive ? `<button class="btn btn-sm btn-secondary btn-set-active" data-id="${c.id}">⭐ Set Active</button>` : `<span class="badge-mini">Currently Active</span>`}
          <div class="btn-group">
            <button class="btn btn-sm btn-primary btn-open-studio" data-id="${c.id}">Open Studio</button>
            <button class="btn btn-sm btn-danger-outline btn-delete-course" data-id="${c.id}" title="Delete Course">🗑️</button>
          </div>
        </div>
      `;

      const btnActive = card.querySelector(".btn-set-active");
      if (btnActive) {
        btnActive.addEventListener("click", () => {
          appState.setActiveCourse(c.id);
        });
      }

      card.querySelector(".btn-open-studio").addEventListener("click", () => {
        appState.setActiveCourse(c.id);
        const studioTab = document.getElementById("tab-nav-studio");
        if (studioTab) studioTab.click();
      });

      card.querySelector(".btn-delete-course").addEventListener("click", async () => {
        if (confirm(`Are you sure you want to delete course "${c.title}" and its associated lectures?`)) {
          try {
            await api.deleteCourse(c.id);
            await refreshCourses();
          } catch (e) {
            alert("Delete failed: " + e.message);
          }
        }
      });

      cardsContainer.appendChild(card);
    });
  }

  // Refresh courses from backend
  async function refreshCourses() {
    try {
      const courses = await api.getCourses();
      appState.set("courses", courses);
      if (kpiCourses) kpiCourses.textContent = courses.length;
      if (badgeCourses) badgeCourses.textContent = courses.length;

      const currentId = appState.get("currentCourseId");
      if (courses.length > 0 && !courses.find(c => c.id === currentId)) {
        appState.setActiveCourse(courses[0].id);
      }

      renderCards(courses);
    } catch (err) {
      console.warn("refreshCourses error:", err);
    }
  }

  // Subscribe to state changes
  appState.subscribe("currentCourseId", () => {
    const courses = appState.get("courses") || [];
    renderCards(courses);
  });

  appState.subscribe("courses", (courses) => {
    renderCards(courses);
  });

  // Initial fetch
  refreshCourses();
}
