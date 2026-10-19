// ClimbUp Mentor Studio - Hierarchical LMS Controller (Course -> Videos -> Notes & Assignments)
document.addEventListener("DOMContentLoaded", () => {
  // Auto-detect Backend API Host (supports port 8000, 8080, Live Server 5500, and Cloud Run)
  const API_BASE = (window.location.port === "8000" || window.location.port === "8080")
    ? ""
    : (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1" || window.location.protocol === "file:")
      ? "http://127.0.0.1:8000"
      : "https://teacher-lecture-video-rag-28929614461.asia-south1.run.app";
  
  const originalFetch = window.fetch;
  window.fetch = function(url, options) {
    if (typeof url === "string" && url.startsWith("/api/")) {
      url = API_BASE + url;
    }
    return originalFetch(url, options);
  };

  // ==========================================
  // GLOBAL STATE
  // ==========================================
  let currentCourseId = "course-applied-ai-rag";
  let coursesCache = [];
  let allLessonsCache = [];
  let courseResourcesCache = [];
  let currentLessonId = null;
  let currentUtterances = [];
  let currentChunks = [];
  let isVideoPlaying = false;

  // Upload modal state
  let modalVideoMode = "file";
  let modalSelectedVideoFile = null;

  // ==========================================
  // DOM ELEMENT REFERENCES
  // ==========================================
  const brandLogoBtn = document.getElementById("brand-logo-btn");
  const btnHeaderCreateCourse = document.getElementById("btn-header-create-course");
  const viewPanels = document.querySelectorAll(".view-panel");

  // Strictly 2 Workspace Tabs (Courses & Students)
  const tabBtnCourses = document.getElementById("tab-btn-courses");
  const tabBtnStudents = document.getElementById("tab-btn-students");
  const tabCoursesCount = document.getElementById("tab-courses-count");
  const tabStudentsCount = document.getElementById("tab-students-count");

  // Optional / Header Elements
  const globalCourseSelect = document.getElementById("global-course-select");
  const badgeCoursesCount = document.getElementById("badge-courses-count");
  const tabNavCourseName = document.getElementById("tab-nav-course-name");
  const tabNavCourseDetail = document.getElementById("tab-nav-course-detail");

  // Tab 2: Students Management Elements
  const btnShowEnrollStudent = document.getElementById("btn-show-enroll-student");
  const btnHideEnrollStudent = document.getElementById("btn-hide-enroll-student");
  const btnCancelEnrollStudent = document.getElementById("btn-cancel-enroll-student");
  const enrollStudentPanel = document.getElementById("enroll-student-panel");
  const enrollStudentForm = document.getElementById("enroll-student-form");
  const enrollStudentName = document.getElementById("enroll-student-name");
  const enrollStudentEmail = document.getElementById("enroll-student-email");
  const enrollStudentCourse = document.getElementById("enroll-student-course");
  const enrollStudentFeedback = document.getElementById("enroll-student-feedback");
  const studentSearchInput = document.getElementById("student-search-input");
  const studentCourseFilter = document.getElementById("student-course-filter");
  const studentsTableBody = document.getElementById("students-table-body");
  const kpiTotalStudents = document.getElementById("kpi-total-students");
  const kpiActiveEnrolledCourses = document.getElementById("kpi-active-enrolled-courses");
  const kpiTotalDoubtsAsked = document.getElementById("kpi-total-doubts-asked");
  const kpiAvgProgress = document.getElementById("kpi-avg-progress");

  let studentsCache = [];

  // KPI Dashboard Cards
  const kpiTotalCourses = document.getElementById("kpi-total-courses");
  const kpiTotalLectures = document.getElementById("kpi-total-lectures");
  const kpiTotalResources = document.getElementById("kpi-total-resources");
  const kpiTotalChunks = document.getElementById("kpi-total-chunks");

  // Level 1: All Courses Elements
  const btnShowCreateCourse = document.getElementById("btn-show-create-course");
  const btnHideCreateCourse = document.getElementById("btn-hide-create-course");
  const btnCancelCreateCourse = document.getElementById("btn-cancel-create-course");
  const createCoursePanel = document.getElementById("create-course-panel");
  const createCourseForm = document.getElementById("create-course-form");
  const createCourseFeedback = document.getElementById("create-course-feedback");
  const coursesCardsContainer = document.getElementById("courses-cards-container");
  const courseSearchInput = document.getElementById("course-search-input");
  const courseCategoryFilters = document.querySelectorAll("#course-category-filters .filter-pill");

  // Level 2: Course Detail Workspace Elements
  const btnBackToCourses = document.getElementById("btn-back-to-courses");
  const btnCdRefresh = document.getElementById("btn-cd-refresh");
  const cdBreadcrumbTitle = document.getElementById("cd-breadcrumb-title");
  const cdCourseCategory = document.getElementById("cd-course-category");
  const cdCourseInstructor = document.getElementById("cd-course-instructor");
  const cdCourseLevel = document.getElementById("cd-course-level");
  const cdCourseTitle = document.getElementById("cd-course-title");
  const cdCourseDesc = document.getElementById("cd-course-desc");
  const cdLecturesCount = document.getElementById("cd-lectures-count");
  const cdMaterialsCount = document.getElementById("cd-materials-count");
  const cdLecturesBadge = document.getElementById("cd-lectures-badge");
  const cdCourseMatsBadge = document.getElementById("cd-course-mats-badge");
  const btnCourseUploadVideo = document.getElementById("btn-course-upload-video");
  const btnSectionUploadVideo = document.getElementById("btn-section-upload-video");
  const btnCourseUploadMaterial = document.getElementById("btn-course-upload-material");
  const btnAddCourseLevelMaterial = document.getElementById("btn-add-course-level-material");
  const cdLecturesGrid = document.getElementById("cd-lectures-grid");
  const cdCourseMaterialsGrid = document.getElementById("cd-course-materials-grid");

  // Course Detail Subtabs & Course-Specific Students Elements
  const cdTabBtns = document.querySelectorAll(".cd-tab-btn");
  const cdSubviewPanels = document.querySelectorAll(".cd-subview-panel");
  const cdSubtabVideoCount = document.getElementById("cd-subtab-video-count");
  const cdSubtabMatCount = document.getElementById("cd-subtab-mat-count");
  const cdSubtabStudentsCount = document.getElementById("cd-subtab-students-count");
  const cdEnrolledCountBadge = document.getElementById("cd-enrolled-count-badge");
  const cdStudentsTableBody = document.getElementById("cd-students-table-body");
  const cdKpiEnrolled = document.getElementById("cd-kpi-enrolled");
  const cdKpiAvgProgress = document.getElementById("cd-kpi-avg-progress");
  const cdKpiDoubts = document.getElementById("cd-kpi-doubts");
  const cdKpiCompleted = document.getElementById("cd-kpi-completed");
  const btnCdEnrollStudent = document.getElementById("btn-cd-enroll-student");
  const btnQuickAddVideo = document.getElementById("btn-quick-add-video");
  const btnQuickAddResource = document.getElementById("btn-quick-add-resource");

  // Level 3: Modal 1 - Upload Video to Course
  const modalUploadVideo = document.getElementById("modal-upload-video");
  const btnCloseVideoModal = document.getElementById("btn-close-video-modal");
  const btnCancelModalVideo = document.getElementById("btn-cancel-modal-video");
  const modalLectureUploadForm = document.getElementById("modal-lecture-upload-form");
  const modalUploadCourseId = document.getElementById("modal-upload-course-id");
  const modalUploadTargetCourse = document.getElementById("modal-upload-target-course");
  const modalLectureTitleInput = document.getElementById("modal-lecture-title-input");
  const modalBtnModeVault = document.getElementById("modal-btn-mode-vault");
  const modalBtnModeFile = document.getElementById("modal-btn-mode-file");
  const modalBtnModeUrl = document.getElementById("modal-btn-mode-url");
  const modalVaultPickerContainer = document.getElementById("modal-vault-picker-container");
  const modalVaultPickerList = document.getElementById("modal-vault-picker-list");
  const modalBtnRefreshVault = document.getElementById("modal-btn-refresh-vault");
  const modalDropZone = document.getElementById("modal-drop-zone");
  const modalFileInput = document.getElementById("modal-file-input");
  const modalSelectedFileName = document.getElementById("modal-selected-file-name");
  const modalUrlContainer = document.getElementById("modal-url-container");
  const modalMediaUrlInput = document.getElementById("modal-media-url-input");
  const modalStepperProgress = document.getElementById("modal-stepper-progress");
  const modalUploadFeedback = document.getElementById("modal-upload-feedback");
  const modalBtnSubmitVideo = document.getElementById("modal-btn-submit-video");

  // Level 3: Modal 2 - Upload Notes & Assignments (attached to Video or Course)
  const modalUploadMaterial = document.getElementById("modal-upload-material");
  const btnCloseMatModal = document.getElementById("btn-close-mat-modal");
  const btnCancelModalMat = document.getElementById("btn-cancel-modal-mat");
  const modalMaterialUploadForm = document.getElementById("modal-material-upload-form");
  const modalMatCourseId = document.getElementById("modal-mat-course-id");
  const modalMatTargetCourse = document.getElementById("modal-mat-target-course");
  const modalMatLectureId = document.getElementById("modal-mat-lecture-id");
  const modalMatLectureTitle = document.getElementById("modal-mat-lecture-title");
  const modalMatTargetLectureBadge = document.getElementById("modal-mat-target-lecture-badge");
  const modalMatType = document.getElementById("modal-mat-type");
  const modalMatTitle = document.getElementById("modal-mat-title");
  const modalAssignmentExtra = document.getElementById("modal-assignment-extra");
  const modalMatDueDate = document.getElementById("modal-mat-due-date");
  const modalMatMaxPoints = document.getElementById("modal-mat-max-points");
  const modalMatDesc = document.getElementById("modal-mat-desc");
  const modalMatFile = document.getElementById("modal-mat-file");
  const modalMatFeedback = document.getElementById("modal-mat-feedback");
  const modalBtnSubmitMat = document.getElementById("modal-btn-submit-mat");

  // Studio & Player Elements
  const btnBackToCourseFromStudio = document.getElementById("btn-back-to-course-from-studio");
  const studioBackCourseName = document.getElementById("studio-back-course-name");
  const video = document.getElementById("lecture-video");
  const driveIframe = document.getElementById("drive-iframe");
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
  const studioSubtabBtns = document.querySelectorAll(".subtab-btn");
  const studioSubtabContents = document.querySelectorAll(".subtab-content");
  const studioMaterialsList = document.getElementById("studio-materials-list");
  const btnStudioAddMaterial = document.getElementById("btn-studio-add-material");

  // AI Chat Elements
  const chatMessages = document.getElementById("chat-messages");
  const chatForm = document.getElementById("chat-form");
  const chatInput = document.getElementById("chat-input");
  const btnClearChat = document.getElementById("btn-clear-chat");
  const chipsScroll = document.querySelector(".chips-scroll");

  // Settings Modal Elements
  const settingsModal = document.getElementById("settings-modal");
  const btnSettings = document.getElementById("btn-settings");
  const btnCloseSettings = document.getElementById("btn-close-settings");
  const btnCancelSettings = document.getElementById("btn-cancel-settings");
  const settingsForm = document.getElementById("settings-form");

  // ==========================================
  // 1. PAGE VIEW SWITCHER
  // ==========================================
  function switchView(viewName) {
    viewPanels.forEach(p => {
      if (p.id === `view-${viewName}`) {
        p.classList.add("active");
      } else {
        p.classList.remove("active");
      }
    });

    // Update active state on the two navbar tabs
    if (viewName === "courses" || viewName === "course-detail" || viewName === "lecture-studio") {
      if (tabBtnCourses) tabBtnCourses.classList.add("active");
      if (tabBtnStudents) tabBtnStudents.classList.remove("active");
    } else if (viewName === "students") {
      if (tabBtnStudents) tabBtnStudents.classList.add("active");
      if (tabBtnCourses) tabBtnCourses.classList.remove("active");
      loadStudents();
    }

    if (viewName === "courses") {
      renderCourseCards(coursesCache);
    } else if (viewName === "lecture-studio") {
      syncStudioLecturePicker();
    }
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  // Click logo -> go to Courses
  if (brandLogoBtn) {
    brandLogoBtn.addEventListener("click", () => {
      switchView("courses");
    });
  }

  // Strictly 2 Workspace Tabs: Courses and Students
  if (tabBtnCourses) {
    tabBtnCourses.addEventListener("click", () => {
      switchView("courses");
    });
  }

  if (tabBtnStudents) {
    tabBtnStudents.addEventListener("click", () => {
      switchView("students");
    });
  }

  // Click header "+ Create Course" button
  if (btnHeaderCreateCourse) {
    btnHeaderCreateCourse.addEventListener("click", () => {
      switchView("courses");
      if (createCoursePanel) {
        createCoursePanel.style.display = "block";
        createCoursePanel.scrollIntoView({ behavior: "smooth" });
      }
    });
  }

  if (btnBackToCourses) {
    btnBackToCourses.addEventListener("click", () => {
      switchView("courses");
    });
  }

  if (btnBackToCourseFromStudio) {
    btnBackToCourseFromStudio.addEventListener("click", () => {
      if (currentCourseId) {
        openCourseWorkspace(currentCourseId);
      } else {
        switchView("courses");
      }
    });
  }

  if (btnCdRefresh) {
    btnCdRefresh.addEventListener("click", () => {
      if (currentCourseId) {
        openCourseWorkspace(currentCourseId);
      }
    });
  }

  // ==========================================
  // 1C. STUDENTS MANAGEMENT (Tab 2)
  // ==========================================
  async function loadStudents() {
    try {
      const res = await fetch("/api/students");
      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data)) {
          studentsCache = data;
        } else {
          studentsCache = [];
        }
      } else {
        studentsCache = [];
      }
    } catch (err) {
      console.warn("Could not fetch students from API:", err);
      studentsCache = [];
    }

    updateStudentKPIs();
    syncStudentCourseDropdowns();
    renderStudentsTable();
  }

  function updateStudentKPIs() {
    const total = studentsCache.length;
    if (tabStudentsCount) tabStudentsCount.textContent = total;
    if (kpiTotalStudents) kpiTotalStudents.textContent = total;

    const uniqueCourses = new Set(studentsCache.map(s => s.course_id || s.course_title)).size;
    if (kpiActiveEnrolledCourses) kpiActiveEnrolledCourses.textContent = uniqueCourses;

    const totalDoubts = studentsCache.reduce((sum, s) => sum + (parseInt(s.doubts_asked) || 0), 0);
    if (kpiTotalDoubtsAsked) kpiTotalDoubtsAsked.textContent = totalDoubts;

    if (kpiAvgProgress) {
      if (total === 0) {
        kpiAvgProgress.textContent = "0%";
      } else {
        const totalProgress = studentsCache.reduce((sum, s) => {
          const val = parseInt(s.progress) || 0;
          return sum + val;
        }, 0);
        kpiAvgProgress.textContent = Math.round(totalProgress / total) + "%";
      }
    }
  }

  function syncStudentCourseDropdowns() {
    if (enrollStudentCourse) {
      const prevVal = enrollStudentCourse.value;
      enrollStudentCourse.innerHTML = '<option value="">Select a Course...</option>';
      coursesCache.forEach(c => {
        const opt = document.createElement("option");
        opt.value = c.id;
        opt.textContent = c.title;
        enrollStudentCourse.appendChild(opt);
      });
      if (prevVal) enrollStudentCourse.value = prevVal;
    }

    if (studentCourseFilter) {
      const prevVal = studentCourseFilter.value;
      studentCourseFilter.innerHTML = '<option value="all">All Enrolled Courses</option>';
      coursesCache.forEach(c => {
        const opt = document.createElement("option");
        opt.value = c.id;
        opt.textContent = c.title;
        studentCourseFilter.appendChild(opt);
      });
      if (prevVal) studentCourseFilter.value = prevVal;
    }
  }

  function renderStudentsTable() {
    if (!studentsTableBody) return;

    const searchTerm = (studentSearchInput?.value || "").toLowerCase().trim();
    const filterCourse = studentCourseFilter?.value || "all";

    const filtered = studentsCache.filter(std => {
      const matchesSearch = !searchTerm ||
        (std.name && std.name.toLowerCase().includes(searchTerm)) ||
        (std.email && std.email.toLowerCase().includes(searchTerm)) ||
        (std.course_title && std.course_title.toLowerCase().includes(searchTerm));

      const matchesCourse = filterCourse === "all" || std.course_id === filterCourse;
      return matchesSearch && matchesCourse;
    });

    if (filtered.length === 0) {
      studentsTableBody.innerHTML = `
        <tr>
          <td colspan="7" style="text-align: center; padding: 48px; color: var(--text-muted);">
            <div style="font-size: 2rem; margin-bottom: 8px;">👥</div>
            <div style="font-size: 0.95rem; font-weight: 600; color: #fff;">No Students Found</div>
            <p style="font-size: 0.8rem; margin-top: 4px;">Try adjusting your search query or enroll a new student.</p>
          </td>
        </tr>`;
      return;
    }

    studentsTableBody.innerHTML = filtered.map(std => {
      const initials = std.name ? std.name.split(" ").map(n => n[0]).join("").toUpperCase().slice(0, 2) : "ST";
      const progressNum = parseInt(std.progress) || 0;
      const avatarHtml = std.avatar_url
        ? `<img src="${escapeHtml(std.avatar_url)}" alt="${escapeHtml(std.name)}" onerror="this.remove();">`
        : initials;

      return `
        <tr>
          <td>
            <div class="student-profile">
              <div class="student-avatar">${avatarHtml}</div>
              <div class="student-name-group">
                <span class="student-name">${escapeHtml(std.name)}</span>
                <span class="student-email">${escapeHtml(std.email)}</span>
              </div>
            </div>
          </td>
          <td>
            <span class="student-course-badge" title="${escapeHtml(std.course_title || '')}">
              🎓 ${escapeHtml(std.course_title || 'General Course')}
            </span>
          </td>
          <td style="color: var(--text-muted); font-size: 0.82rem; white-space: nowrap;">
            ${escapeHtml(std.enrolled_date || '2026-10-18')}
          </td>
          <td>
            <div class="student-progress-wrap">
              <div class="progress-info">
                <span>Progress</span>
                <span>${progressNum}%</span>
              </div>
              <div class="progress-track">
                <div class="progress-fill" style="width: ${progressNum}%;"></div>
              </div>
            </div>
          </td>
          <td>
            <span class="student-doubts-pill">
              🤖 ${std.doubts_asked || 0} doubts
            </span>
          </td>
          <td>
            <span class="student-status-pill active">
              <span class="dot"></span> ${escapeHtml(std.status || 'Active')}
            </span>
          </td>
          <td style="text-align: right;">
            <button class="btn-student-delete" data-student-id="${std.id}" title="Unenroll Student">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="3 6 5 6 21 6"></polyline>
                <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
              </svg>
              Unenroll
            </button>
          </td>
        </tr>`;
    }).join("");

    studentsTableBody.querySelectorAll(".btn-student-delete").forEach(btn => {
      btn.addEventListener("click", async () => {
        const studentId = btn.dataset.studentId;
        const targetStd = studentsCache.find(s => s.id === studentId);
        const stdName = targetStd ? targetStd.name : "this student";
        
        if (!confirm(`Are you sure you want to unenroll ${stdName}?`)) return;

        try {
          await fetch(`/api/students/${studentId}`, { method: "DELETE" });
        } catch (e) {
          console.warn("Delete API call failed, removing locally:", e);
        }

        studentsCache = studentsCache.filter(s => s.id !== studentId);
        updateStudentKPIs();
        renderStudentsTable();
      });
    });
  }

  // Toggle Enroll Student Form
  if (btnShowEnrollStudent && enrollStudentPanel) {
    btnShowEnrollStudent.addEventListener("click", () => {
      const isHidden = enrollStudentPanel.style.display === "none";
      enrollStudentPanel.style.display = isHidden ? "block" : "none";
      if (isHidden) {
        syncStudentCourseDropdowns();
        enrollStudentPanel.scrollIntoView({ behavior: "smooth" });
      }
    });
  }

  if (btnHideEnrollStudent && enrollStudentPanel) {
    btnHideEnrollStudent.addEventListener("click", () => {
      enrollStudentPanel.style.display = "none";
    });
  }

  if (btnCancelEnrollStudent && enrollStudentPanel) {
    btnCancelEnrollStudent.addEventListener("click", () => {
      enrollStudentPanel.style.display = "none";
    });
  }

  // Search and Filter Events
  if (studentSearchInput) {
    studentSearchInput.addEventListener("input", renderStudentsTable);
  }

  if (studentCourseFilter) {
    studentCourseFilter.addEventListener("change", renderStudentsTable);
  }

  // Enroll Student Form Submit
  if (enrollStudentForm) {
    enrollStudentForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const name = enrollStudentName ? enrollStudentName.value.trim() : "";
      const email = enrollStudentEmail ? enrollStudentEmail.value.trim() : "";
      const courseId = enrollStudentCourse ? enrollStudentCourse.value : "";

      if (!name || !email || !courseId) {
        if (enrollStudentFeedback) {
          enrollStudentFeedback.textContent = "Please fill in all required fields.";
          enrollStudentFeedback.style.color = "#fda4af";
        }
        return;
      }

      const selectedCourse = coursesCache.find(c => c.id === courseId);
      const courseTitle = selectedCourse ? selectedCourse.title : "University Course";

      const submitBtn = document.getElementById("btn-submit-enroll-student");
      if (submitBtn) submitBtn.disabled = true;
      if (enrollStudentFeedback) {
        enrollStudentFeedback.textContent = "Enrolling student...";
        enrollStudentFeedback.style.color = "#a5b4fc";
      }

      try {
        const res = await fetch("/api/students", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name, email, course_id: courseId })
        });

        if (res.ok) {
          const newStudent = await res.json();
          studentsCache.unshift(newStudent);
        } else {
          throw new Error("Enroll API failed");
        }
      } catch (err) {
        console.warn("Backend enroll API failed, adding locally:", err);
        const localNew = {
          id: `std_${Date.now()}`,
          name: name,
          email: email,
          course_id: courseId,
          course_title: courseTitle,
          enrolled_date: new Date().toISOString().split("T")[0],
          progress: "0%",
          doubts_asked: 0,
          status: "Active"
        };
        studentsCache.unshift(localNew);
      }

      if (submitBtn) submitBtn.disabled = false;
      if (enrollStudentFeedback) {
        enrollStudentFeedback.textContent = "✓ Student successfully enrolled!";
        enrollStudentFeedback.style.color = "#34d399";
      }

      enrollStudentForm.reset();
      updateStudentKPIs();
      renderStudentsTable();

      setTimeout(() => {
        if (enrollStudentFeedback) enrollStudentFeedback.textContent = "";
        if (enrollStudentPanel) enrollStudentPanel.style.display = "none";
      }, 1500);
    });
  }

  // ==========================================
  // 2. LEVEL 1: ALL COURSES CATALOG
  // ==========================================
  async function loadCourses() {
    try {
      const res = await fetch("/api/courses");
      if (res.ok) {
        const data = await res.json();
        coursesCache = Array.isArray(data) ? data : [];
      } else {
        coursesCache = [];
      }
    } catch (err) {
      console.warn("Could not load courses from backend:", err);
      coursesCache = [];
    }

    if (badgeCoursesCount) badgeCoursesCount.textContent = coursesCache.length;
    if (tabCoursesCount) tabCoursesCount.textContent = coursesCache.length;
    if (kpiTotalCourses) kpiTotalCourses.textContent = coursesCache.length;

    syncGlobalCourseSelect();
    syncStudentCourseDropdowns();
    renderCourseCards(coursesCache);
  }

  function syncGlobalCourseSelect() {
    if (!globalCourseSelect) return;
    globalCourseSelect.innerHTML = "";
    coursesCache.forEach(c => {
      const opt = document.createElement("option");
      opt.value = c.id;
      opt.textContent = c.title;
      globalCourseSelect.appendChild(opt);
    });
    if (coursesCache.find(c => c.id === currentCourseId)) {
      globalCourseSelect.value = currentCourseId;
    } else if (coursesCache.length > 0) {
      currentCourseId = coursesCache[0].id;
      globalCourseSelect.value = currentCourseId;
    }
  }

  if (globalCourseSelect) {
    globalCourseSelect.addEventListener("change", (e) => {
      openCourseWorkspace(e.target.value);
    });
  }

  function renderCourseCards(courses) {
    if (!coursesCardsContainer) return;
    coursesCardsContainer.innerHTML = "";

    if (!courses || courses.length === 0) {
      coursesCardsContainer.innerHTML = `
        <div class="empty-state" style="grid-column: 1 / -1; padding: 40px; text-align: center;">
          <div style="font-size: 2.2rem; margin-bottom: 12px;">🎓</div>
          <h3 style="color: #fff; margin-bottom: 8px;">No Courses Created Yet</h3>
          <p style="color: var(--text-muted); max-width: 440px; margin: 0 auto 16px;">
            Click <strong>"+ Create New Course"</strong> above to set up your first university curriculum and upload video lectures.
          </p>
        </div>`;
      return;
    }

    courses.forEach(c => {
      const isActive = c.id === currentCourseId;
      const card = document.createElement("div");
      card.className = `course-card ${isActive ? "is-active" : ""}`;
      
      const thumb = c.thumbnail || "https://images.unsplash.com/photo-1516321318423-f06f85e504b3?w=800&auto=format&fit=crop&q=80";
      const lessonsCount = allLessonsCache.filter(l => l.course_id === c.id).length || c.total_lessons || 0;
      const category = c.category || "Computer Science";
      const level = c.level || "All Levels";
      const instructor = c.instructor_name || "Course Instructor";

      card.innerHTML = `
        ${isActive ? `<div class="active-ribbon">Active Teaching</div>` : ""}
        <div class="course-thumb-wrap">
          <img src="${thumb}" alt="${escapeHtml(c.title)}" class="course-thumb-img" onerror="this.src='https://images.unsplash.com/photo-1516321318423-f06f85e504b3?w=800'">
          <div class="course-thumb-badges">
            <span class="category-tag">${category}</span>
            <span class="level-tag">${level}</span>
          </div>
        </div>
        <div class="course-body">
          <h3 class="course-card-title">${escapeHtml(c.title)}</h3>
          <p class="course-tagline">${escapeHtml(c.tagline || c.description || "Master core concepts with synchronized video RAG and doubt assistant.")}</p>
          
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
          <button class="btn btn-sm btn-primary btn-open-course" data-id="${c.id}" style="width: 100%; justify-content: center;">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path></svg>
            Open Course Workspace & Videos
          </button>
          <button class="btn btn-sm btn-danger-outline btn-delete-course" data-id="${c.id}" title="Delete Course" style="padding: 6px 10px;">🗑️</button>
        </div>
      `;

      // Click card body or Open button to open course
      card.querySelector(".btn-open-course").addEventListener("click", (e) => {
        e.stopPropagation();
        openCourseWorkspace(c.id);
      });

      card.querySelector(".course-body").addEventListener("click", () => {
        openCourseWorkspace(c.id);
      });

      card.querySelector(".btn-delete-course").addEventListener("click", async (e) => {
        e.stopPropagation();
        if (confirm(`Are you sure you want to delete course "${c.title}" and its associated lectures?`)) {
          await deleteCourse(c.id);
        }
      });

      coursesCardsContainer.appendChild(card);
    });
  }

  async function deleteCourse(courseId) {
    try {
      const res = await fetch(`/api/courses/${courseId}`, { method: "DELETE" });
      if (res.ok) {
        await loadCourses();
        await loadAllLessons();
        if (currentCourseId === courseId && coursesCache.length > 0) {
          openCourseWorkspace(coursesCache[0].id);
        } else {
          switchView("courses");
        }
      } else {
        alert("Failed to delete course.");
      }
    } catch (e) {
      alert("Error deleting course: " + e.message);
    }
  }

  // Course Filter & Search
  if (courseSearchInput) {
    courseSearchInput.addEventListener("input", (e) => {
      const query = e.target.value.toLowerCase().trim();
      const filtered = coursesCache.filter(c => 
        (c.title && c.title.toLowerCase().includes(query)) ||
        (c.category && c.category.toLowerCase().includes(query)) ||
        (c.instructor_name && c.instructor_name.toLowerCase().includes(query))
      );
      renderCourseCards(filtered);
    });
  }

  courseCategoryFilters.forEach(pill => {
    pill.addEventListener("click", () => {
      courseCategoryFilters.forEach(p => p.classList.remove("active"));
      pill.classList.add("active");
      const cat = pill.dataset.category;
      if (cat === "all") {
        renderCourseCards(coursesCache);
      } else {
        const filtered = coursesCache.filter(c => (c.category || "").toLowerCase().includes(cat.toLowerCase()));
        renderCourseCards(filtered);
      }
    });
  });

  // Toggle Create Course Form
  if (btnShowCreateCourse && createCoursePanel) {
    btnShowCreateCourse.addEventListener("click", () => {
      createCoursePanel.style.display = "block";
      createCoursePanel.scrollIntoView({ behavior: "smooth" });
    });
  }
  if (btnHideCreateCourse && createCoursePanel) {
    btnHideCreateCourse.addEventListener("click", () => {
      createCoursePanel.style.display = "none";
    });
  }
  if (btnCancelCreateCourse && createCoursePanel) {
    btnCancelCreateCourse.addEventListener("click", () => {
      createCoursePanel.style.display = "none";
    });
  }

  // Submit Create Course Form
  if (createCourseForm) {
    createCourseForm.addEventListener("submit", async (e) => {
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
      createCourseFeedback.innerHTML = `<span style="color: var(--accent-cyan);">Saving course to Supabase & local store...</span>`;

      try {
        const res = await fetch("/api/courses", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            title,
            category,
            level,
            instructor_name: instructor,
            thumbnail,
            tagline,
            description: desc
          })
        });

        if (!res.ok) {
          const err = await res.json();
          throw new Error(err.detail || "Failed to create course");
        }

        const data = await res.json();
        createCourseFeedback.innerHTML = `<span style="color: var(--accent-emerald);">✓ Course '${title}' created successfully!</span>`;
        createCourseForm.reset();

        setTimeout(() => {
          createCourseFeedback.innerHTML = "";
          createCoursePanel.style.display = "none";
        }, 1200);

        await loadCourses();
        if (data.course && data.course.id) {
          openCourseWorkspace(data.course.id);
        }
      } catch (err) {
        createCourseFeedback.innerHTML = `<span style="color: var(--accent-rose);">Error: ${err.message}</span>`;
      } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = "Create Course";
      }
    });
  }

  // ==========================================
  // 3. LEVEL 2: COURSE WORKSPACE & LECTURES
  // ==========================================
  async function openCourseWorkspace(courseId) {
    currentCourseId = courseId;
    const course = coursesCache.find(c => c.id === courseId);
    if (!course) {
      await loadCourses();
    }
    const activeCourse = coursesCache.find(c => c.id === courseId) || {
      id: courseId,
      title: "Course Workspace",
      category: "Computer Science",
      level: "All Levels",
      instructor_name: "Instructor",
      description: "Manage course lecture videos, notes, and assignments."
    };

    // Update navbar and breadcrumb
    if (tabNavCourseName) tabNavCourseName.textContent = activeCourse.title;
    if (tabNavCourseDetail) tabNavCourseDetail.style.display = "inline-flex";
    if (cdBreadcrumbTitle) cdBreadcrumbTitle.textContent = activeCourse.title;
    if (studioBackCourseName) studioBackCourseName.textContent = activeCourse.title;

    // Update course hero banner
    if (cdCourseTitle) cdCourseTitle.textContent = activeCourse.title;
    if (cdCourseCategory) cdCourseCategory.textContent = activeCourse.category || "Computer Science";
    if (cdCourseInstructor) cdCourseInstructor.textContent = activeCourse.instructor_name || "Course Instructor";
    if (cdCourseLevel) cdCourseLevel.textContent = activeCourse.level || "All Levels";
    if (cdCourseDesc) cdCourseDesc.textContent = activeCourse.description || activeCourse.tagline || "Master core concepts with synchronized video RAG and doubt assistant.";

    if (globalCourseSelect) globalCourseSelect.value = courseId;

    switchView("course-detail");

    // Load and render videos, resources & enrolled students for this course
    await loadCourseLectures(courseId);
    await loadCourseResources(courseId);
    await loadCourseStudents(courseId);

    // Reset subtab to Lectures & Videos by default
    const videosTabBtn = document.getElementById("cd-tab-videos");
    if (videosTabBtn) videosTabBtn.click();
  }

  // Connect Course-level "+ Upload Video" buttons
  if (btnCourseUploadVideo) {
    btnCourseUploadVideo.addEventListener("click", () => {
      openUploadVideoModal(currentCourseId);
    });
  }
  if (btnSectionUploadVideo) {
    btnSectionUploadVideo.addEventListener("click", () => {
      openUploadVideoModal(currentCourseId);
    });
  }

  // Connect Course-level "+ Add Notes / Materials" buttons
  if (btnCourseUploadMaterial) {
    btnCourseUploadMaterial.addEventListener("click", () => {
      openUploadMaterialModal(currentCourseId, null, null, "notes");
    });
  }
  if (btnAddCourseLevelMaterial) {
    btnAddCourseLevelMaterial.addEventListener("click", () => {
      openUploadMaterialModal(currentCourseId, null, null, "notes");
    });
  }

  // Fetch all lessons from server
  async function loadAllLessons() {
    try {
      const res = await fetch("/api/lessons");
      if (res.ok) {
        allLessonsCache = await res.json();
      }
    } catch (e) {
      console.warn("Could not load all lessons:", e);
    }

    if (!Array.isArray(allLessonsCache)) {
      allLessonsCache = [];
    }

    if (kpiTotalLectures) kpiTotalLectures.textContent = allLessonsCache.length;
    syncStudioLecturePicker();
  }

  async function loadCourseLectures(courseId) {
    if (!cdLecturesGrid) return;
    cdLecturesGrid.innerHTML = `<div class="empty-state">Loading course lecture videos...</div>`;

    await loadAllLessons();

    const courseLessons = allLessonsCache.filter(l => l.course_id === courseId);
    if (cdLecturesCount) cdLecturesCount.textContent = courseLessons.length;
    if (cdLecturesBadge) cdLecturesBadge.textContent = `${courseLessons.length} Videos`;
    if (cdSubtabVideoCount) cdSubtabVideoCount.textContent = courseLessons.length;

    renderCourseLectures(courseLessons, courseId);
  }

  function renderCourseLectures(lessons, courseId) {
    if (!cdLecturesGrid) return;
    cdLecturesGrid.innerHTML = "";

    if (!lessons || lessons.length === 0) {
      cdLecturesGrid.innerHTML = `
        <div class="empty-state" style="padding: 40px 24px; text-align: center; border: 2px dashed rgba(99, 102, 241, 0.3); border-radius: var(--radius-lg); background: rgba(18, 25, 45, 0.5);">
          <div style="font-size: 2.4rem; margin-bottom: 12px;">🎬</div>
          <h4 style="font-size: 1.18rem; color: #fff; margin-bottom: 6px;">No Video Lectures Uploaded to this Course Yet</h4>
          <p style="font-size: 0.86rem; color: var(--text-muted); max-width: 520px; margin: 0 auto 18px;">
            Upload your lecture MP4 or stream URL. We'll transcribe it with Deepgram Nova-2, segment concept boundaries with Gemini, and index 768-dim embeddings in Supabase.
          </p>
          <button class="btn btn-primary" onclick="document.getElementById('btn-section-upload-video').click()">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="23 7 16 12 23 17 23 7"></polygon><rect x="1" y="5" width="15" height="14" rx="2" ry="2"></rect></svg>
            + Upload First Lecture Video
          </button>
        </div>
      `;
      return;
    }

    lessons.forEach((l, idx) => {
      const card = document.createElement("div");
      card.className = "lecture-card-v2";

      const durMin = l.duration_seconds ? Math.floor(l.duration_seconds / 60) : 0;
      const durSec = l.duration_seconds ? (l.duration_seconds % 60) : 0;
      const durFormatted = `${durMin}m ${durSec.toString().padStart(2, "0")}s`;
      const uttLen = l.utterances ? l.utterances.length : 0;

      // Find materials attached to this video (by ID in description or title match)
      const attachedMaterials = courseResourcesCache.filter(r => {
        const desc = r.description || "";
        const title = r.title || "";
        return desc.includes(l.id) || desc.includes(l.title) || title.includes(l.title);
      });

      card.innerHTML = `
        <div class="lecture-card-v2-header">
          <div class="lecture-title-group">
            <div class="lecture-play-icon">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor">
                <polygon points="5 3 19 12 5 21 5 3"></polygon>
              </svg>
            </div>
            <div class="lecture-info-col">
              <h4>${escapeHtml(l.title)}</h4>
              <div class="lecture-meta-badges">
                <span class="badge-duration">⏱️ ${durFormatted}</span>
                <span class="badge-rag-active">⚡ Supabase 768-dim RAG</span>
                <span class="badge-mini">🗣️ ${uttLen} Utterances</span>
                <span class="badge-materials-count">📁 ${attachedMaterials.length} Materials Attached</span>
              </div>
            </div>
          </div>
          <div class="lecture-card-v2-actions">
            <button class="btn btn-primary btn-play-in-studio" data-id="${l.id}">
              ▶ Play in Studio & AI Chat
            </button>
            <button class="btn btn-sm btn-secondary btn-upload-lecture-notes" data-id="${l.id}" data-title="${escapeHtml(l.title)}" title="Upload PDF Notes for this lecture">
              + Upload Notes
            </button>
            <button class="btn btn-sm btn-secondary btn-upload-lecture-assignment" data-id="${l.id}" data-title="${escapeHtml(l.title)}" title="Upload Assignment for this lecture">
              + Upload Assignment
            </button>
            <button class="btn btn-sm btn-danger-outline btn-delete-lecture" data-id="${l.id}" title="Delete Lecture">
              🗑️
            </button>
          </div>
        </div>

        <!-- Attached Notes & Assignments Section -->
        <div class="attached-materials-box">
          <div class="attached-materials-label">
            <span>📎 Attached to this Video:</span>
          </div>
          <div class="attached-materials-list" id="attached-list-${l.id}">
            ${attachedMaterials.length === 0 ? `
              <span class="attached-empty-hint">No notes or assignments attached yet. Click <strong>"+ Upload Notes"</strong> or <strong>"+ Upload Assignment"</strong> above to attach directly to this lecture.</span>
            ` : attachedMaterials.map(m => {
              const type = (m.file_type || "pdf").toLowerCase();
              const isHw = type.includes("assignment");
              const icon = isHw ? "📝" : type.includes("slide") ? "📊" : type.includes("lab") || type.includes("zip") ? "💻" : "📘";
              return `
                <div class="attached-mat-pill">
                  <span>${icon}</span>
                  <a href="${m.download_url}" target="_blank" rel="noopener noreferrer" style="color: inherit; text-decoration: none;" title="Download / Open file">
                    <strong>${escapeHtml(m.title)}</strong> (${m.file_size || "Doc"})
                  </a>
                  <button class="btn-delete-mat-pill" data-id="${m.id}" title="Remove file" style="background: none; border: none; color: rgba(255,255,255,0.4); cursor: pointer; padding: 0 4px; font-weight: 700;">&times;</button>
                </div>
              `;
            }).join("")}
          </div>
        </div>
      `;

      // Event Listeners on this Lecture Card
      card.querySelector(".btn-play-in-studio").addEventListener("click", () => {
        playLessonInStudio(l.id);
      });

      card.querySelector(".btn-upload-lecture-notes").addEventListener("click", () => {
        openUploadMaterialModal(courseId, l.id, l.title, "notes");
      });

      card.querySelector(".btn-upload-lecture-assignment").addEventListener("click", () => {
        openUploadMaterialModal(courseId, l.id, l.title, "assignment");
      });

      card.querySelector(".btn-delete-lecture").addEventListener("click", async () => {
        if (confirm(`Delete lecture "${l.title}"? This will remove transcripts and vector index.`)) {
          await fetch(`/api/lessons/${l.id}`, { method: "DELETE" });
          await loadCourseLectures(courseId);
        }
      });

      card.querySelectorAll(".btn-delete-mat-pill").forEach(delBtn => {
        delBtn.addEventListener("click", async (e) => {
          e.stopPropagation();
          const matId = delBtn.dataset.id;
          if (confirm("Remove this attached file?")) {
            await fetch(`/api/resources/${matId}`, { method: "DELETE" });
            await loadCourseResources(courseId);
            await loadCourseLectures(courseId);
          }
        });
      });

      cdLecturesGrid.appendChild(card);
    });
  }

  // Load Course-wide Resources
  async function loadCourseResources(courseId) {
    try {
      const res = await fetch(`/api/courses/${courseId}/resources`);
      if (res.ok) {
        courseResourcesCache = await res.json();
      }
    } catch (e) {
      console.warn("Could not load resources from backend:", e);
    }

    if (cdMaterialsCount) cdMaterialsCount.textContent = courseResourcesCache.length;
    if (kpiTotalResources) kpiTotalResources.textContent = courseResourcesCache.length;
    if (cdSubtabMatCount) cdSubtabMatCount.textContent = courseResourcesCache.length;

    // Filter course-level materials (not tagged with a specific lecture)
    const courseLevelMaterials = courseResourcesCache.filter(r => {
      const desc = r.description || "";
      return !desc.includes("[Lecture:");
    });

    if (cdCourseMatsBadge) cdCourseMatsBadge.textContent = `${courseLevelMaterials.length} Documents`;
    renderCourseLevelMaterials(courseLevelMaterials);
  }

  function renderCourseLevelMaterials(materials) {
    if (!cdCourseMaterialsGrid) return;
    cdCourseMaterialsGrid.innerHTML = "";

    if (!materials || materials.length === 0) {
      cdCourseMaterialsGrid.innerHTML = `
        <div class="empty-state" style="grid-column: 1 / -1; font-size: 0.85rem; color: var(--text-dim);">
          No general course-level syllabus or cheatsheets uploaded yet. Use the button above to upload.
        </div>
      `;
      return;
    }

    materials.forEach(m => {
      const card = document.createElement("div");
      const rawType = (m.file_type || "pdf").toLowerCase();
      const isAssignment = rawType.includes("assignment");
      card.className = `material-card ${isAssignment ? "assignment" : rawType}`;

      const iconLabel = isAssignment ? "HW" : rawType.includes("slide") ? "PPT" : rawType.includes("lab") || rawType.includes("zip") ? "CODE" : "PDF";

      card.innerHTML = `
        <div class="mat-card-header">
          <div class="mat-icon-badge ${rawType}">${iconLabel}</div>
          <div class="mat-info">
            <h4 class="mat-title">${escapeHtml(m.title)}</h4>
            <div class="mat-meta-row">
              <span>${m.file_size || "Document"}</span>
              <span>&bull;</span>
              <span>Supabase Storage</span>
            </div>
          </div>
        </div>
        <p class="mat-desc">${escapeHtml(m.description || "Course material")}</p>
        <div class="mat-actions-row">
          <a href="${m.download_url}" target="_blank" rel="noopener noreferrer" class="btn btn-sm btn-primary">
            Download / View
          </a>
          <button class="btn btn-sm btn-danger-outline btn-del-gen-mat" data-id="${m.id}">🗑️</button>
        </div>
      `;

      card.querySelector(".btn-del-gen-mat").addEventListener("click", async () => {
        if (confirm(`Delete material "${m.title}"?`)) {
          await fetch(`/api/resources/${m.id}`, { method: "DELETE" });
          await loadCourseResources(currentCourseId);
          await loadCourseLectures(currentCourseId);
        }
      });

      cdCourseMaterialsGrid.appendChild(card);
    });
  }

  // Course Detail Subtabs Switching Logic
  cdTabBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      const targetId = btn.getAttribute("data-target");
      cdTabBtns.forEach(b => b.classList.remove("active"));
      btn.classList.add("active");

      cdSubviewPanels.forEach(panel => {
        if (panel.id === targetId) {
          panel.style.display = "block";
          panel.classList.add("active");
        } else {
          panel.style.display = "none";
          panel.classList.remove("active");
        }
      });
    });
  });

  // Quick Action Buttons inside Course Workspace
  if (btnQuickAddVideo) {
    btnQuickAddVideo.addEventListener("click", () => {
      openUploadVideoModal(currentCourseId);
    });
  }
  if (btnQuickAddResource) {
    btnQuickAddResource.addEventListener("click", () => {
      openUploadMaterialModal(currentCourseId, null, null, "notes");
    });
  }
  if (btnCdEnrollStudent) {
    btnCdEnrollStudent.addEventListener("click", () => {
      switchView("students");
      const enrollPanel = document.getElementById("enroll-student-panel");
      if (enrollPanel) enrollPanel.style.display = "block";
      const enrollCourseSelect = document.getElementById("enroll-student-course");
      if (enrollCourseSelect && currentCourseId) {
        enrollCourseSelect.value = currentCourseId;
      }
    });
  }

  // Load and Render Enrolled Students for this specific Course
  async function loadCourseStudents(courseId) {
    if (!studentsCache || studentsCache.length === 0) {
      try {
        const res = await fetch("/api/students");
        if (res.ok) {
          studentsCache = await res.json();
        }
      } catch (err) {
        console.warn("Could not fetch students:", err);
      }
    }

    const courseObj = coursesCache.find(c => c.id === courseId);
    const courseTitle = courseObj ? courseObj.title : "";

    const enrolledStudents = (studentsCache || []).filter(s => {
      return s.course_id === courseId || (courseTitle && s.course_title === courseTitle);
    });

    const totalCourseStudents = enrolledStudents.length;
    if (cdSubtabStudentsCount) cdSubtabStudentsCount.textContent = totalCourseStudents;
    if (cdEnrolledCountBadge) cdEnrolledCountBadge.textContent = `${totalCourseStudents} Students`;
    if (cdKpiEnrolled) cdKpiEnrolled.textContent = totalCourseStudents;

    // Course Doubts Sum
    const totalDoubts = enrolledStudents.reduce((acc, s) => acc + (parseInt(s.doubts_asked) || 0), 0);
    if (cdKpiDoubts) cdKpiDoubts.textContent = totalDoubts;

    // Average Progress Calculation
    let avgProg = 0;
    let completedCount = 0;
    if (totalCourseStudents > 0) {
      const sumProg = enrolledStudents.reduce((acc, s) => {
        const p = parseInt(s.progress) || 0;
        if (p >= 100 || s.status === "Completed") completedCount++;
        return acc + p;
      }, 0);
      avgProg = Math.round(sumProg / totalCourseStudents);
    }
    if (cdKpiAvgProgress) cdKpiAvgProgress.textContent = `${avgProg}%`;
    if (cdKpiCompleted) cdKpiCompleted.textContent = completedCount;

    renderCourseStudentsTable(enrolledStudents);
  }

  function renderCourseStudentsTable(students) {
    if (!cdStudentsTableBody) return;
    cdStudentsTableBody.innerHTML = "";

    if (!students || students.length === 0) {
      cdStudentsTableBody.innerHTML = `
        <tr>
          <td colspan="6" style="text-align: center; padding: 40px; color: var(--text-muted);">
            <div style="font-size: 2rem; margin-bottom: 8px;">👥</div>
            <div style="font-size: 0.95rem; font-weight: 600; color: #fff;">No Students Enrolled in this Course Yet</div>
            <div style="font-size: 0.8rem; margin-top: 4px;">Click "+ Enroll Student to this Course" above to add students.</div>
          </td>
        </tr>
      `;
      return;
    }

    cdStudentsTableBody.innerHTML = students.map(std => {
      const initials = std.name ? std.name.split(" ").map(n => n[0]).join("").toUpperCase().slice(0, 2) : "ST";
      const progressNum = parseInt(std.progress) || 0;
      const avatarHtml = std.avatar_url
        ? `<img src="${escapeHtml(std.avatar_url)}" alt="${escapeHtml(std.name)}" onerror="this.remove();">`
        : initials;

      return `
        <tr>
          <td>
            <div class="student-profile">
              <div class="student-avatar">${avatarHtml}</div>
              <div class="student-name-group">
                <span class="student-name">${escapeHtml(std.name)}</span>
                <span class="student-email">${escapeHtml(std.email)}</span>
              </div>
            </div>
          </td>
          <td style="color: var(--text-muted); font-size: 0.82rem; white-space: nowrap;">
            ${escapeHtml(std.enrolled_date || '2026-10-18')}
          </td>
          <td>
            <div class="student-progress-wrap" style="min-width: 140px;">
              <div class="progress-info">
                <span>Progress</span>
                <span style="color: #67e8f9; font-weight: 700;">${progressNum}%</span>
              </div>
              <div class="progress-track" style="height: 7px;">
                <div class="progress-fill" style="width: ${progressNum}%;"></div>
              </div>
            </div>
          </td>
          <td>
            <span class="student-doubts-pill">
              🤖 ${std.doubts_asked || 0} doubts
            </span>
          </td>
          <td>
            <span class="student-status-pill ${progressNum >= 100 || std.status === 'Completed' ? '' : 'active'}" style="${progressNum >= 100 ? 'background: rgba(16, 185, 129, 0.2); color: #6ee7b7;' : ''}">
              <span class="dot"></span> ${escapeHtml(std.status || (progressNum >= 100 ? 'Completed' : 'Active'))}
            </span>
          </td>
          <td style="text-align: right;">
            <button class="btn-student-delete btn-cd-student-del" data-student-id="${std.id}" title="Unenroll Student from this course">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="3 6 5 6 21 6"></polyline>
                <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
              </svg>
              Unenroll
            </button>
          </td>
        </tr>
      `;
    }).join("");

    // Unenroll actions inside course student table
    cdStudentsTableBody.querySelectorAll(".btn-cd-student-del").forEach(btn => {
      btn.addEventListener("click", async () => {
        const studentId = btn.dataset.studentId;
        const targetStd = studentsCache.find(s => s.id === studentId);
        const sName = targetStd ? targetStd.name : "this student";

        if (confirm(`Unenroll ${sName} from this course?`)) {
          try {
            await fetch(`/api/students/${studentId}`, { method: "DELETE" });
          } catch (e) {
            console.warn("Delete student request failed:", e);
          }
          studentsCache = studentsCache.filter(s => s.id !== studentId);
          await loadCourseStudents(currentCourseId);
          renderStudentsTable();
        }
      });
    });
  }

  // ==========================================
  // 4. MODAL 1: UPLOAD VIDEO TO COURSE (DRIVE VAULT ZERO-DISK STREAMING)
  // ==========================================
  async function loadModalDriveFiles() {
    if (!modalVaultPickerList) return;
    modalVaultPickerList.innerHTML = `<div style="padding: 16px; text-align: center; color: var(--text-muted); font-size: 0.82rem;">Loading files from Google Drive...</div>`;
    try {
      const res = await fetch("/api/drive/files");
      const data = await res.json();
      const files = data.files || [];
      if (!files.length) {
        modalVaultPickerList.innerHTML = `
          <div style="padding: 16px; text-align: center; color: var(--text-muted); font-size: 0.82rem;">
            No files found in central Drive folder.<br>
            <a href="https://drive.google.com/drive/folders/1VDrNYA5GE6l9h21D2Co0HuuuD87Ain6d" target="_blank" rel="noopener noreferrer" style="color: #38d399; font-weight: 600; text-decoration: underline; margin-top: 6px; display: inline-block;">
              📁 Open Folder to Drag & Drop Videos
            </a>
          </div>
        `;
        return;
      }

      modalVaultPickerList.innerHTML = "";
      files.forEach(f => {
        const item = document.createElement("div");
        item.className = "vault-picker-item";
        const sizeMb = f.size ? (parseInt(f.size, 10) / (1024 * 1024)).toFixed(1) : "?";
        const isVideo = f.mimeType?.includes("video") || f.name.match(/\.(mp4|webm|mkv|mov|avi)$/i);
        const icon = isVideo ? "📹" : "📄";

        item.innerHTML = `
          <div style="display: flex; align-items: center; gap: 9px; overflow: hidden;">
            <span style="font-size: 1.15rem; flex-shrink: 0;">${icon}</span>
            <div style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
              <div style="font-size: 0.82rem; font-weight: 600; color: #fff; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${f.name}</div>
              <div style="font-size: 0.7rem; color: var(--text-muted);">${f.mimeType || "media"}</div>
            </div>
          </div>
          <span style="font-size: 0.72rem; color: var(--text-dim); background: rgba(255,255,255,0.06); padding: 2px 8px; border-radius: 6px; flex-shrink: 0;">${sizeMb} MB</span>
        `;

        item.addEventListener("click", () => {
          document.querySelectorAll("#modal-vault-picker-list .vault-picker-item").forEach(el => el.classList.remove("selected"));
          item.classList.add("selected");
          modalMediaUrlInput.value = `https://drive.google.com/file/d/${f.id}/view`;
          modalLectureTitleInput.value = f.name.replace(/\.[^/.]+$/, "").replace(/[-_]/g, " ");
          if (modalUploadFeedback) {
            modalUploadFeedback.innerHTML = `<span style="color: var(--accent-emerald); font-size: 0.76rem;">✓ Selected: <strong>${f.name}</strong> (Ready to Ingest)</span>`;
          }
        });
        modalVaultPickerList.appendChild(item);
      });
    } catch (err) {
      modalVaultPickerList.innerHTML = `<div style="padding: 16px; text-align: center; color: var(--accent-rose); font-size: 0.82rem;">Could not load Drive files: ${err.message}</div>`;
    }
  }

  function openUploadVideoModal(courseId) {
    const course = coursesCache.find(c => c.id === courseId);
    const courseTitle = course ? course.title : "Current Course";

    modalUploadCourseId.value = courseId;
    modalUploadTargetCourse.textContent = courseTitle;

    modalLectureTitleInput.value = "";
    modalMediaUrlInput.value = "";
    modalSelectedVideoFile = null;
    modalSelectedFileName.textContent = "Supports MP4, WebM, MKV, MP3, WAV (Direct 0-disk streaming)";
    modalStepperProgress.style.display = "none";
    modalUploadFeedback.innerHTML = "";

    // Default to Direct File Upload mode (Auto-synced to 5TB Drive Vault + RAG)
    modalVideoMode = "file";
    if (modalBtnModeFile) modalBtnModeFile.classList.add("active");
    if (modalBtnModeVault) modalBtnModeVault.classList.remove("active");
    if (modalBtnModeUrl) modalBtnModeUrl.classList.remove("active");
    if (modalDropZone) modalDropZone.style.display = "flex";
    if (modalVaultPickerContainer) modalVaultPickerContainer.style.display = "none";
    if (modalUrlContainer) modalUrlContainer.style.display = "none";

    modalUploadVideo.style.display = "flex";
  }

  if (btnCloseVideoModal) btnCloseVideoModal.addEventListener("click", () => modalUploadVideo.style.display = "none");
  if (btnCancelModalVideo) btnCancelModalVideo.addEventListener("click", () => modalUploadVideo.style.display = "none");

  if (modalBtnModeVault) {
    modalBtnModeVault.addEventListener("click", () => {
      modalVideoMode = "vault";
      modalBtnModeVault.classList.add("active");
      if (modalBtnModeUrl) modalBtnModeUrl.classList.remove("active");
      if (modalBtnModeFile) modalBtnModeFile.classList.remove("active");
      if (modalVaultPickerContainer) modalVaultPickerContainer.style.display = "flex";
      if (modalUrlContainer) modalUrlContainer.style.display = "none";
      if (modalDropZone) modalDropZone.style.display = "none";
      loadModalDriveFiles();
    });
  }

  if (modalBtnModeUrl) {
    modalBtnModeUrl.addEventListener("click", () => {
      modalVideoMode = "url";
      modalBtnModeUrl.classList.add("active");
      if (modalBtnModeVault) modalBtnModeVault.classList.remove("active");
      if (modalBtnModeFile) modalBtnModeFile.classList.remove("active");
      if (modalVaultPickerContainer) modalVaultPickerContainer.style.display = "none";
      if (modalUrlContainer) modalUrlContainer.style.display = "flex";
      if (modalDropZone) modalDropZone.style.display = "none";
    });
  }

  if (modalBtnModeFile) {
    modalBtnModeFile.addEventListener("click", () => {
      modalVideoMode = "file";
      modalBtnModeFile.classList.add("active");
      if (modalBtnModeVault) modalBtnModeVault.classList.remove("active");
      if (modalBtnModeUrl) modalBtnModeUrl.classList.remove("active");
      if (modalVaultPickerContainer) modalVaultPickerContainer.style.display = "none";
      if (modalUrlContainer) modalUrlContainer.style.display = "none";
      if (modalDropZone) modalDropZone.style.display = "flex";
    });
  }

  if (modalBtnRefreshVault) {
    modalBtnRefreshVault.addEventListener("click", () => {
      loadModalDriveFiles();
    });
  }

  // Dropzone handling in modal
  if (modalDropZone && modalFileInput) {
    modalDropZone.addEventListener("click", () => modalFileInput.click());
    modalFileInput.addEventListener("change", (e) => {
      if (e.target.files && e.target.files.length > 0) {
        modalSelectedVideoFile = e.target.files[0];
        const sizeMb = (modalSelectedVideoFile.size / (1024 * 1024)).toFixed(1);
        modalSelectedFileName.textContent = `Selected: ${modalSelectedVideoFile.name} (${sizeMb} MB) - Ready to process`;
        if (!modalLectureTitleInput.value) {
          modalLectureTitleInput.value = modalSelectedVideoFile.name.replace(/\.[^/.]+$/, "").replace(/[-_]/g, " ");
        }
      }
    });

    modalDropZone.addEventListener("dragover", (e) => {
      e.preventDefault();
      modalDropZone.style.borderColor = "var(--primary)";
    });

    modalDropZone.addEventListener("dragleave", () => {
      modalDropZone.style.borderColor = "rgba(99, 102, 241, 0.35)";
    });

    modalDropZone.addEventListener("drop", (e) => {
      e.preventDefault();
      modalDropZone.style.borderColor = "rgba(99, 102, 241, 0.35)";
      if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
        modalSelectedVideoFile = e.dataTransfer.files[0];
        const sizeMb = (modalSelectedVideoFile.size / (1024 * 1024)).toFixed(1);
        modalSelectedFileName.textContent = `Selected: ${modalSelectedVideoFile.name} (${sizeMb} MB) - Ready to process`;
        if (!modalLectureTitleInput.value) {
          modalLectureTitleInput.value = modalSelectedVideoFile.name.replace(/\.[^/.]+$/, "").replace(/[-_]/g, " ");
        }
      }
    });
  }

  // 1-Click modal presets
  document.querySelectorAll(".modal-preset").forEach(tag => {
    tag.addEventListener("click", () => {
      modalMediaUrlInput.value = tag.dataset.url;
      if (!modalLectureTitleInput.value) {
        modalLectureTitleInput.value = tag.textContent;
      }
    });
  });

  // Modal Video Form Submit
  if (modalLectureUploadForm) {
    modalLectureUploadForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const courseId = modalUploadCourseId.value || currentCourseId;
      const title = modalLectureTitleInput.value.trim();

      if (!title) {
        alert("Please enter a lecture title.");
        return;
      }

      const activeCourse = coursesCache.find(c => c.id === courseId);
      const courseName = activeCourse ? activeCourse.title : "University Course";

      const formData = new FormData();
      formData.append("title", title);
      formData.append("course_id", courseId);
      formData.append("course_name", courseName);

      if (modalVideoMode === "file") {
        if (!modalSelectedVideoFile) {
          alert("Please select a video file to upload.");
          return;
        }

        modalBtnSubmitVideo.disabled = true;
        modalBtnSubmitVideo.textContent = "Uploading to Drive...";
        modalUploadFeedback.innerHTML = `<span style="color: var(--accent-cyan);">☁️ Uploading directly to 5TB Google Drive Vault (0 MB Cloud Run load)...</span>`;

        // 1. Get Google Drive direct resumable upload URL
        const initRes = await fetch("/api/drive/init-upload", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            filename: modalSelectedVideoFile.name,
            mime_type: modalSelectedVideoFile.type || "video/mp4",
            file_size: modalSelectedVideoFile.size
          })
        });

        if (!initRes.ok) {
          const errData = await initRes.json().catch(() => ({}));
          throw new Error(errData.detail || "Could not initialize Google Drive direct upload session.");
        }

        const { upload_url } = await initRes.json();

        // 2. Stream video file DIRECTLY from browser to Google Drive (Bypasses Cloud Run 32MB limit!)
        const driveFile = await new Promise((resolve, reject) => {
          const xhr = new XMLHttpRequest();
          xhr.open("PUT", upload_url, true);
          xhr.setRequestHeader("Content-Type", modalSelectedVideoFile.type || "video/mp4");

          xhr.upload.onprogress = (e) => {
            if (e.lengthComputable) {
              const pct = Math.round((e.loaded / e.total) * 100);
              modalUploadFeedback.innerHTML = `<span style="color: var(--accent-cyan);">☁️ Direct Upload to Drive Vault: <strong>${pct}%</strong></span>`;
            }
          };

          xhr.onload = () => {
            if (xhr.status === 200 || xhr.status === 201) {
              try {
                resolve(JSON.parse(xhr.responseText));
              } catch (ex) {
                resolve({ id: null });
              }
            } else {
              reject(new Error(`Drive direct upload failed (${xhr.status}): ${xhr.responseText}`));
            }
          };

          xhr.onerror = () => reject(new Error("Network error during direct Drive upload. Check internet connection."));
          xhr.send(modalSelectedVideoFile);
        });

        const driveFileId = driveFile.id;
        if (!driveFileId) {
          throw new Error("Google Drive did not return a valid file ID.");
        }

        modalUploadFeedback.innerHTML = `<span style="color: var(--accent-emerald);">✓ Saved to Google Drive Vault! Starting AI pipeline...</span>`;
        formData.append("media_url", `https://drive.google.com/file/d/${driveFileId}/view`);
      } else {
        const urlVal = modalMediaUrlInput.value.trim();
        if (!urlVal) {
          alert("Please select a video from Central Drive Vault or enter a video URL.");
          return;
        }
        formData.append("media_url", urlVal);
      }

      // Stepper UI in modal
      modalStepperProgress.style.display = "block";
      const s1 = document.getElementById("modal-step-1");
      const s2 = document.getElementById("modal-step-2");
      const s3 = document.getElementById("modal-step-3");
      const s4 = document.getElementById("modal-step-4");
      const modalSteps = [s1, s2, s3, s4];

      modalSteps.forEach(s => {
        s.classList.remove("completed", "processing");
        s.querySelector(".step-status").textContent = "Pending";
      });

      s1.classList.add("processing");
      s1.querySelector(".step-status").textContent = "Running...";

      setTimeout(() => {
        s1.classList.remove("processing"); s1.classList.add("completed");
        s1.querySelector(".step-status").textContent = "Done";
        s2.classList.add("processing");
        s2.querySelector(".step-status").textContent = "Transcribing...";
      }, 3000);

      setTimeout(() => {
        s2.classList.remove("processing"); s2.classList.add("completed");
        s2.querySelector(".step-status").textContent = "Done";
        s3.classList.add("processing");
        s3.querySelector(".step-status").textContent = "Chunking...";
      }, 7000);

      setTimeout(() => {
        s3.classList.remove("processing"); s3.classList.add("completed");
        s3.querySelector(".step-status").textContent = "Done";
        s4.classList.add("processing");
        s4.querySelector(".step-status").textContent = "Embedding...";
      }, 11000);

      modalBtnSubmitVideo.disabled = true;
      modalBtnSubmitVideo.textContent = "Processing Lecture Pipeline...";

      try {
        const res = await fetch("/api/process-video", {
          method: "POST",
          body: formData
        });

        if (!res.ok) {
          let errDetail = `Server error (${res.status})`;
          try {
            const raw = await res.text();
            try {
              const j = JSON.parse(raw);
              errDetail = j.detail || j.message || j.error || errDetail;
            } catch {
              const match = raw.match(/<title>(.*?)<\/title>/i);
              errDetail = match ? `${match[1].trim()} (HTTP ${res.status})` : raw.slice(0, 150).replace(/<[^>]*>/g, "").trim() || `HTTP ${res.status}`;
            }
          } catch {}
          throw new Error(errDetail);
        }

        const data = await res.json();
        s4.classList.remove("processing"); s4.classList.add("completed");
        s4.querySelector(".step-status").textContent = "Indexed";

        modalUploadFeedback.innerHTML = `<span style="color: var(--accent-emerald);">🎉 Lecture indexed successfully!</span>`;

        setTimeout(async () => {
          modalUploadVideo.style.display = "none";
          modalBtnSubmitVideo.disabled = false;
          modalBtnSubmitVideo.textContent = "Process & Ingest Lecture";
          await openCourseWorkspace(courseId);
        }, 1200);

      } catch (err) {
        modalUploadFeedback.innerHTML = `<span style="color: var(--accent-rose);">Error: ${err.message}</span>`;
        modalBtnSubmitVideo.disabled = false;
        modalBtnSubmitVideo.textContent = "Process & Ingest Lecture";
      }
    });
  }

  // ==========================================
  // 5. MODAL 2: UPLOAD NOTES & ASSIGNMENTS
  // ==========================================
  function openUploadMaterialModal(courseId, lectureId, lectureTitleText, defaultType = "notes") {
    const course = coursesCache.find(c => c.id === courseId);
    const courseTitle = course ? course.title : "Current Course";

    modalMatCourseId.value = courseId;
    modalMatTargetCourse.textContent = courseTitle;

    modalMatLectureId.value = lectureId || "";
    modalMatLectureTitle.value = lectureTitleText || "";

    if (lectureTitleText) {
      modalMatTargetLectureBadge.style.display = "inline-block";
      modalMatTargetLectureBadge.textContent = `🎬 Video: ${lectureTitleText}`;
      modalMatTitle.value = `${lectureTitleText} - ${defaultType === "assignment" ? "Assignment 1" : "Lecture Notes"}`;
    } else {
      modalMatTargetLectureBadge.style.display = "none";
      modalMatTitle.value = "";
    }

    modalMatType.value = defaultType;
    if (defaultType === "assignment") {
      modalAssignmentExtra.style.display = "grid";
    } else {
      modalAssignmentExtra.style.display = "none";
    }

    modalMatDesc.value = "";
    modalMatFile.value = "";
    modalMatFeedback.innerHTML = "";

    modalUploadMaterial.style.display = "flex";
  }

  if (btnCloseMatModal) btnCloseMatModal.addEventListener("click", () => modalUploadMaterial.style.display = "none");
  if (btnCancelModalMat) btnCancelModalMat.addEventListener("click", () => modalUploadMaterial.style.display = "none");

  if (modalMatType) {
    modalMatType.addEventListener("change", (e) => {
      if (e.target.value === "assignment") {
        modalAssignmentExtra.style.display = "grid";
      } else {
        modalAssignmentExtra.style.display = "none";
      }
    });
  }

  // Modal Material Form Submit
  if (modalMaterialUploadForm) {
    modalMaterialUploadForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const courseId = modalMatCourseId.value || currentCourseId;
      const type = modalMatType.value;
      const title = modalMatTitle.value.trim();
      const desc = modalMatDesc.value.trim();
      const file = modalMatFile.files[0];
      const lectureId = modalMatLectureId.value;
      const lectureTitleText = modalMatLectureTitle.value;

      if (!file) {
        alert("Please select a document or code file.");
        return;
      }

      let fullDesc = desc;
      const metaParts = [];
      if (lectureId) metaParts.push(`Lecture: ${lectureId}`);
      if (type === "assignment") {
        const due = modalMatDueDate.value;
        const pts = modalMatMaxPoints.value;
        if (due) metaParts.push(`Due: ${due}`);
        if (pts) metaParts.push(`Points: ${pts}`);
      }
      if (metaParts.length > 0) {
        fullDesc = `[${metaParts.join(" | ")}] ${desc}`;
      }

      const formData = new FormData();
      formData.append("course_id", courseId);
      formData.append("title", title);
      formData.append("file_type", type);
      formData.append("description", fullDesc);
      formData.append("file", file);

      modalBtnSubmitMat.disabled = true;
      modalBtnSubmitMat.textContent = "Uploading to Supabase Storage...";
      modalMatFeedback.innerHTML = `<span style="color: var(--accent-cyan);">Uploading to Supabase Storage bucket...</span>`;

      try {
        const res = await fetch("/api/resources/upload", {
          method: "POST",
          body: formData
        });

        if (!res.ok) {
          const err = await res.json();
          throw new Error(err.detail || "Upload failed");
        }

        modalMatFeedback.innerHTML = `<span style="color: var(--accent-emerald);">✓ Uploaded successfully!</span>`;

        setTimeout(async () => {
          modalUploadMaterial.style.display = "none";
          modalBtnSubmitMat.disabled = false;
          modalBtnSubmitMat.textContent = "Upload to Supabase Storage";
          await loadCourseResources(courseId);
          await loadCourseLectures(courseId);
        }, 1200);

      } catch (err) {
        modalMatFeedback.innerHTML = `<span style="color: var(--accent-rose);">Upload error: ${err.message}</span>`;
        modalBtnSubmitMat.disabled = false;
        modalBtnSubmitMat.textContent = "Upload to Supabase Storage";
      }
    });
  }

  // ==========================================
  // 6. INTERACTIVE STUDIO & VIDEO PLAYER
  // ==========================================
  function playLessonInStudio(lessonId) {
    currentLessonId = lessonId;
    switchView("lecture-studio");
    loadLesson(lessonId);
  }

  function syncStudioLecturePicker() {
    if (!studioLectureSelect) return;
    studioLectureSelect.innerHTML = "";

    allLessonsCache.forEach(l => {
      const opt = document.createElement("option");
      opt.value = l.id;
      opt.textContent = l.title;
      studioLectureSelect.appendChild(opt);
    });

    if (currentLessonId && allLessonsCache.find(l => l.id === currentLessonId)) {
      studioLectureSelect.value = currentLessonId;
    } else if (allLessonsCache.length > 0) {
      studioLectureSelect.value = allLessonsCache[0].id;
    }
  }

  if (studioLectureSelect) {
    studioLectureSelect.addEventListener("change", (e) => {
      loadLesson(e.target.value);
    });
  }

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

  function togglePlayPause() {
    if (!video) return;
    if (video.paused || video.ended) {
      video.play().then(() => {
        isVideoPlaying = true;
        if (videoOverlay) videoOverlay.classList.add("hidden");
        if (iconPlay) iconPlay.style.display = "none";
        if (iconPause) iconPause.style.display = "block";
      }).catch(err => {
        console.warn("Video play error:", err);
      });
    } else {
      video.pause();
      isVideoPlaying = false;
      if (videoOverlay) videoOverlay.classList.remove("hidden");
      if (iconPlay) iconPlay.style.display = "block";
      if (iconPause) iconPause.style.display = "none";
    }
  }

  if (btnOverlayPlay) btnOverlayPlay.addEventListener("click", togglePlayPause);
  if (videoOverlay) videoOverlay.addEventListener("click", togglePlayPause);
  if (ctrlPlayPause) ctrlPlayPause.addEventListener("click", togglePlayPause);

  if (video) {
    video.addEventListener("timeupdate", () => {
      const cur = video.currentTime;
      if (timeCurrent) timeCurrent.textContent = formatTime(cur);
      if (seekBar) seekBar.value = cur;
      updateActiveConceptAndUtterance(cur);
    });

    video.addEventListener("loadedmetadata", () => {
      if (seekBar) seekBar.max = video.duration;
      if (timeDuration) timeDuration.textContent = formatTime(video.duration);
    });

    video.addEventListener("ended", () => {
      isVideoPlaying = false;
      if (videoOverlay) videoOverlay.classList.remove("hidden");
      if (iconPlay) iconPlay.style.display = "block";
      if (iconPause) iconPause.style.display = "none";
    });
  }

  if (seekBar) {
    seekBar.addEventListener("input", () => {
      video.currentTime = seekBar.value;
      if (timeCurrent) timeCurrent.textContent = formatTime(seekBar.value);
    });
  }

  if (playbackSpeed) {
    playbackSpeed.addEventListener("change", () => {
      video.playbackRate = parseFloat(playbackSpeed.value);
    });
  }

  function seekVideoTo(seconds) {
    switchView("lecture-studio");
    if (driveIframe && driveIframe.style.display !== "none") {
      const fid = driveIframe.dataset.fileId;
      if (fid) {
        driveIframe.src = `https://drive.google.com/file/d/${fid}/preview#t=${Math.floor(seconds)}`;
      }
    } else if (video) {
      video.currentTime = seconds;
      video.play().then(() => {
        isVideoPlaying = true;
        if (videoOverlay) videoOverlay.classList.add("hidden");
        if (iconPlay) iconPlay.style.display = "none";
        if (iconPause) iconPause.style.display = "block";
      }).catch(e => console.warn(e));
    }
  }

  function updateActiveConceptAndUtterance(currentTime) {
    if (currentChunks && currentChunks.length > 0) {
      const activeChunk = currentChunks.find(c => currentTime >= c.start_seconds && currentTime <= c.end_seconds);
      if (activeChunk && currentConceptName) {
        currentConceptName.textContent = `${activeChunk.timestamp_label} - ${activeChunk.topic_name}`;
      }
    }

    if (!utterancesContainer) return;
    const allUtts = utterancesContainer.querySelectorAll(".utterance-item");
    allUtts.forEach(el => {
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

  // Studio Subtabs
  studioSubtabBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      studioSubtabBtns.forEach(b => b.classList.remove("active"));
      studioSubtabContents.forEach(c => c.classList.remove("active"));
      btn.classList.add("active");
      const target = document.getElementById(`subtab-${btn.dataset.subtab}`);
      if (target) target.classList.add("active");
    });
  });

  // Load Lecture Data into Studio
  async function loadLesson(lessonId) {
    if (!lessonId) return;
    currentLessonId = lessonId;

    try {
      const res = await fetch(`/api/lessons/${lessonId}`);
      if (!res.ok) return;
      const lesson = await res.json();

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
        if (fileId) {
          driveIframe.dataset.fileId = fileId;
          driveIframe.src = `https://drive.google.com/file/d/${fileId}/preview`;
          driveIframe.style.display = "block";
          video.style.display = "none";
          if (videoOverlay) videoOverlay.style.display = "none";
        }
      } else {
        if (driveIframe) driveIframe.style.display = "none";
        if (video) {
          video.style.display = "block";
          if (videoOverlay) videoOverlay.style.display = "flex";
          video.src = vUrl || "/uploads/berkeley_cs61c.mp4";
          video.load();
        }
      }

      updateQuickChips(lesson.id);
      renderUtterances(currentUtterances);
      renderChunks(currentChunks);
      renderStudioMaterials(lesson.id, lesson.title);

      if (video) {
        video.currentTime = 0;
        if (seekBar) seekBar.value = 0;
        if (timeCurrent) timeCurrent.textContent = "00:00";
      }
    } catch (err) {
      console.error("Failed to load lesson:", err);
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
          <p class="utt-text">${escapeHtml(utt.text)}</p>
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
          <span class="chunk-topic">${escapeHtml(c.topic_name || "Concept Chunk")}</span>
          <button class="ts-badge" data-time="${(c.timestamp_label || '00:00').split(' - ')[0]}">${c.timestamp_label || '00:00'}</button>
        </div>
        <p class="chunk-text">${escapeHtml(c.cleaned_text || c.chunk_text)}</p>
        <div class="chunk-tags">
          ${(c.key_concepts || []).map(k => `<span class="chunk-tag">${escapeHtml(k)}</span>`).join("")}
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

  function renderStudioMaterials(lessonId, lessonTitleText) {
    if (!studioMaterialsList) return;
    studioMaterialsList.innerHTML = "";

    const attached = courseResourcesCache.filter(r => {
      const desc = r.description || "";
      const title = r.title || "";
      return desc.includes(lessonId) || desc.includes(lessonTitleText) || title.includes(lessonTitleText);
    });

    if (attached.length === 0) {
      studioMaterialsList.innerHTML = `
        <div class="empty-state" style="padding: 24px; text-align: center;">
          <p style="color: var(--text-dim); margin-bottom: 12px;">No notes or assignments attached to this lecture yet.</p>
        </div>
      `;
    } else {
      attached.forEach(m => {
        const item = document.createElement("div");
        item.className = "studio-mat-item";
        item.style.cssText = "display: flex; align-items: center; justify-content: space-between; padding: 10px 14px; background: rgba(255,255,255,0.04); border: 1px solid var(--border-color); border-radius: var(--radius-md); margin-bottom: 8px;";
        const isHw = (m.file_type || "").includes("assignment");
        const icon = isHw ? "📝" : "📘";

        item.innerHTML = `
          <div style="display: flex; align-items: center; gap: 10px;">
            <span style="font-size: 1.2rem;">${icon}</span>
            <div>
              <div style="font-size: 0.86rem; font-weight: 600; color: #fff;">${escapeHtml(m.title)}</div>
              <div style="font-size: 0.72rem; color: var(--text-dim);">${m.file_size || "Doc"} &bull; Supabase Storage</div>
            </div>
          </div>
          <a href="${m.download_url}" target="_blank" rel="noopener noreferrer" class="btn btn-sm btn-secondary" style="font-size: 0.78rem;">
            Download
          </a>
        `;
        studioMaterialsList.appendChild(item);
      });
    }

    if (btnStudioAddMaterial) {
      btnStudioAddMaterial.onclick = () => {
        openUploadMaterialModal(currentCourseId, lessonId, lessonTitleText, "notes");
      };
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

  // ==========================================
  // 7. AI DOUBT MENTOR
  // ==========================================
  if (chatForm) {
    chatForm.addEventListener("submit", (e) => {
      e.preventDefault();
      const q = chatInput.value.trim();
      if (!q) return;
      chatInput.value = "";
      submitChatQuery(q);
    });
  }

  if (btnClearChat) {
    btnClearChat.addEventListener("click", () => {
      chatMessages.innerHTML = `
        <div class="message-wrapper ai">
          <div class="msg-avatar">AI</div>
          <div class="msg-content">
            <div class="msg-bubble">
              Chat cleared. Ask any doubt to test grounded retrieval and clickable timestamp jump badges <code>[MM:SS]</code>.
            </div>
          </div>
        </div>
      `;
    });
  }

  async function submitChatQuery(query) {
    appendUserMessage(query);
    const thinkingId = appendThinkingBubble();

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query,
          lesson_id: currentLessonId || "masterclass_os_3hours"
        })
      });

      removeElement(thinkingId);

      if (!res.ok) {
        appendAiMessage("Sorry, I could not complete the RAG query. Please check server logs.", []);
        return;
      }

      const data = await res.json();
      appendAiMessage(data.answer, data.retrieved_evidence || []);
    } catch (err) {
      removeElement(thinkingId);
      appendAiMessage(`Connection error: ${err.message}`, []);
    }
  }

  function appendUserMessage(text) {
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
                <button class="ts-badge" data-time="${e.timestamp_label.split(' - ')[0]}">${e.timestamp_label.split(' - ')[0]}</button>
                <span>${escapeHtml(e.topic_name)}</span>
              </div>
              <span class="similarity-score">${Math.round(e.similarity_score * 100)}% match</span>
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
          🔍 Searching 768-dim Supabase vector embeddings & assembling lecture proof...
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
    let html = text.replace(/\[(\d{1,2}:\d{2}:\d{2}|\d{1,3}:\d{2})\]/g, (match, p1) => {
      return `<button class="ts-badge" data-time="${p1}">[${p1}]</button>`;
    });

    html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');

    html = html.split('\n\n').map(p => {
      if (p.startsWith('###')) {
        return `<h4 style="margin: 8px 0 4px; color: var(--accent-cyan);">${escapeHtml(p.replace('###', ''))}</h4>`;
      }
      if (p.startsWith('* ') || p.startsWith('- ')) {
        const items = p.split('\n').map(li => `<li>${escapeHtml(li.replace(/^[\*\-]\s*/, ''))}</li>`).join('');
        return `<ul>${items}</ul>`;
      }
      return `<p>${p.replace(/\n/g, '<br>')}</p>`;
    }).join('');

    return html;
  }

  function escapeHtml(str) {
    if (!str) return "";
    return String(str).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  // ==========================================
  // 8. SETTINGS MODAL
  // ==========================================
  if (btnSettings) {
    btnSettings.addEventListener("click", () => { settingsModal.style.display = "flex"; });
  }
  if (btnCloseSettings) {
    btnCloseSettings.addEventListener("click", () => { settingsModal.style.display = "none"; });
  }
  if (btnCancelSettings) {
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
        const res = await fetch("/api/update-config", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });
        if (res.ok) {
          settingsModal.style.display = "none";
          alert("Cloud settings updated successfully!");
        }
      } catch (err) {
        alert("Failed to update settings.");
      }
    });
  }

  // ==========================================
  // 9. INITIAL BOOT
  // ==========================================
  async function init() {
    try {
      const res = await fetch("/api/status");
      if (res.ok) {
        const status = await res.json();
        if (kpiTotalChunks) kpiTotalChunks.textContent = status.total_chunks_indexed || 0;
      }
    } catch (e) {
      console.warn("Backend status check failed:", e);
    }

    await loadCourses();
    await loadAllLessons();
    await loadStudents();

    // Default to the first course or applied AI
    if (coursesCache.length > 0) {
      const defaultCourse = coursesCache.find(c => c.id === currentCourseId) || coursesCache[0];
      currentCourseId = defaultCourse.id;
    }
  }

  init();
});
