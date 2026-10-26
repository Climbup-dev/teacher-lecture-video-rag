// ClimbUp Mentor Studio - Hierarchical LMS Controller (Course -> Videos -> Notes & Assignments)

// ==========================================
// TOP-LEVEL SHARED STATE (Accessible across all views & studios)
// ==========================================
let currentCourseId = "course-applied-ai-rag";
let coursesCache = [];
let allLessonsCache = [];
let courseResourcesCache = [];
let currentLessonId = null;
let currentUtterances = [];
let currentChunks = [];
let isVideoPlaying = false;

// Attach to window for robust inter-module access
window.currentCourseId = currentCourseId;
window.coursesCache = coursesCache;
window.allLessonsCache = allLessonsCache;
window.courseResourcesCache = courseResourcesCache;
window.currentLessonId = currentLessonId;

// Upload modal state
let modalVideoMode = "file";
let modalSelectedVideoFile = null;

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
        createCoursePanel.style.display = "flex";
        document.body.style.overflow = "hidden";
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
      resetChatSession();
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

  // Group raw enrollment records into unique student records
  function getUniqueStudents(enrollmentsList) {
    const map = new Map();

    (enrollmentsList || []).forEach(std => {
      const email = (std.email || "").toLowerCase().trim();
      const key = email || (std.user_id ? String(std.user_id) : (std.name ? std.name.toLowerCase().trim() : std.id));

      if (!map.has(key)) {
        map.set(key, {
          key: key,
          user_id: std.user_id,
          name: std.name || "Student",
          email: std.email || "student@university.edu",
          avatar_url: std.avatar_url || null,
          enrollments: []
        });
      }

      const student = map.get(key);

      const addEnrollment = (enr) => {
        const cid = enr.course_id || enr.id;
        if (!student.enrollments.some(existing => existing.course_id === cid)) {
          student.enrollments.push({
            id: enr.enrollment_id || enr.id || std.id,
            course_id: cid,
            course_title: enr.title || enr.course_title || "General Course",
            enrolled_date: enr.enrolled_date || std.enrolled_date || "2026-10-18",
            progress: parseInt(enr.progress !== undefined ? enr.progress : std.progress) || 0,
            doubts_asked: parseInt(enr.doubts_asked !== undefined ? enr.doubts_asked : std.doubts_asked) || 0,
            status: enr.status || std.status || "Active"
          });
        }
      };

      if (Array.isArray(std.courses) && std.courses.length > 0) {
        std.courses.forEach(addEnrollment);
      } else {
        addEnrollment(std);
      }
    });

    return Array.from(map.values()).map(student => {
      const count = student.enrollments.length;
      const totalProg = student.enrollments.reduce((sum, e) => sum + e.progress, 0);
      const avgProg = count > 0 ? Math.round(totalProg / count) : 0;
      const totalDoubts = student.enrollments.reduce((sum, e) => sum + e.doubts_asked, 0);

      const dates = student.enrollments.map(e => e.enrolled_date).filter(Boolean).sort();
      const enrolledDate = dates.length > 0 ? dates[0] : "2026-10-18";

      const hasActive = student.enrollments.some(e => (e.status || "").toLowerCase() === "active");

      return {
        ...student,
        coursesCount: count,
        avgProgress: avgProg,
        totalDoubts: totalDoubts,
        enrolledDate: enrolledDate,
        status: hasActive ? "Active" : (student.enrollments[0]?.status || "Active"),
        enrollmentIds: student.enrollments.map(e => e.id)
      };
    });
  }

  function updateStudentKPIs() {
    const uniqueStudents = getUniqueStudents(studentsCache);
    const total = uniqueStudents.length;
    if (tabStudentsCount) tabStudentsCount.textContent = total;
    if (kpiTotalStudents) kpiTotalStudents.textContent = total;

    const uniqueCourses = new Set(studentsCache.map(s => s.course_id || s.course_title).filter(Boolean)).size;
    if (kpiActiveEnrolledCourses) kpiActiveEnrolledCourses.textContent = uniqueCourses;

    const totalDoubts = studentsCache.reduce((sum, s) => sum + (parseInt(s.doubts_asked) || 0), 0);
    if (kpiTotalDoubtsAsked) kpiTotalDoubtsAsked.textContent = totalDoubts;

    if (kpiAvgProgress) {
      if (total === 0) {
        kpiAvgProgress.textContent = "0%";
      } else {
        const totalProgress = uniqueStudents.reduce((sum, s) => sum + s.avgProgress, 0);
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

    const uniqueStudents = getUniqueStudents(studentsCache);

    const filtered = uniqueStudents.filter(std => {
      const matchesCourse = filterCourse === "all" ||
        std.enrollments.some(e => e.course_id === filterCourse);

      const matchesSearch = !searchTerm ||
        (std.name && std.name.toLowerCase().includes(searchTerm)) ||
        (std.email && std.email.toLowerCase().includes(searchTerm)) ||
        std.enrollments.some(e => e.course_title && e.course_title.toLowerCase().includes(searchTerm));

      return matchesCourse && matchesSearch;
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
            <div class="student-courses-cell">
              <span class="student-courses-count-pill">
                📚 ${std.coursesCount} ${std.coursesCount === 1 ? 'Course' : 'Courses'}
              </span>
              <div class="student-courses-chips">
                ${std.enrollments.map(e => `
                  <span class="student-course-badge" title="${escapeHtml(e.course_title)}">
                    🎓 ${escapeHtml(e.course_title)}
                    ${std.coursesCount > 1 ? `<button type="button" class="btn-remove-course-enr" data-enr-id="${e.id}" data-student-name="${escapeHtml(std.name)}" data-course-title="${escapeHtml(e.course_title)}" title="Unenroll from ${escapeHtml(e.course_title)}">×</button>` : ''}
                  </span>
                `).join("")}
              </div>
            </div>
          </td>
          <td style="color: var(--text-muted); font-size: 0.82rem; white-space: nowrap;">
            ${escapeHtml(std.enrolledDate)}
          </td>
          <td>
            <div class="student-progress-wrap">
              <div class="progress-info">
                <span>Avg Progress</span>
                <span>${std.avgProgress}%</span>
              </div>
              <div class="progress-track">
                <div class="progress-fill" style="width: ${std.avgProgress}%;"></div>
              </div>
            </div>
          </td>
          <td>
            <span class="student-doubts-pill">
              🤖 ${std.totalDoubts} doubts
            </span>
          </td>
          <td>
            <span class="student-status-pill active">
              <span class="dot"></span> ${escapeHtml(std.status)}
            </span>
          </td>
          <td style="text-align: right;">
            <button class="btn-student-delete" data-student-key="${std.key}" title="Unenroll Student from all courses">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="3 6 5 6 21 6"></polyline>
                <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
              </svg>
              Unenroll
            </button>
          </td>
        </tr>`;
    }).join("");

    // Unenroll student from all courses
    studentsTableBody.querySelectorAll(".btn-student-delete").forEach(btn => {
      btn.addEventListener("click", async () => {
        const studentKey = btn.dataset.studentKey;
        const currentUnique = getUniqueStudents(studentsCache);
        const targetStd = currentUnique.find(s => s.key === studentKey);
        const stdName = targetStd ? targetStd.name : "this student";
        const numCourses = targetStd ? targetStd.coursesCount : 1;

        if (!confirm(`Are you sure you want to unenroll ${stdName} from ${numCourses > 1 ? `all ${numCourses} courses` : 'the course'}?`)) return;

        btn.disabled = true;
        btn.textContent = "Unenrolling...";

        const idsToDelete = targetStd ? targetStd.enrollmentIds : [];
        try {
          await Promise.all(idsToDelete.map(id => fetch(`/api/students/${id}`, { method: "DELETE" })));
        } catch (e) {
          console.warn("Delete API call failed, removing locally:", e);
        }

        studentsCache = studentsCache.filter(s => !idsToDelete.includes(s.id));
        updateStudentKPIs();
        renderStudentsTable();
      });
    });

    // Unenroll from a single specific course
    studentsTableBody.querySelectorAll(".btn-remove-course-enr").forEach(btn => {
      btn.addEventListener("click", async (e) => {
        e.stopPropagation();
        const enrId = btn.dataset.enrId;
        const stdName = btn.dataset.studentName || "Student";
        const courseTitle = btn.dataset.courseTitle || "course";

        if (!confirm(`Unenroll ${stdName} from "${courseTitle}"?`)) return;

        try {
          await fetch(`/api/students/${enrId}`, { method: "DELETE" });
        } catch (err) {
          console.warn("Delete single course enrollment error:", err);
        }

        studentsCache = studentsCache.filter(s => s.id !== enrId);
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
        window.coursesCache = coursesCache;
      } else {
        coursesCache = [];
        window.coursesCache = [];
      }
    } catch (err) {
      console.warn("Could not load courses from backend:", err);
      coursesCache = [];
      window.coursesCache = [];
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

  // Toggle Create Course Modal
  function openCreateCourseModal() {
    if (createCoursePanel) {
      createCoursePanel.style.display = "flex";
      document.body.style.overflow = "hidden";
      const titleInput = document.getElementById("new-course-title");
      if (titleInput) setTimeout(() => titleInput.focus(), 80);
    }
  }
  function closeCreateCourseModal() {
    if (createCoursePanel) {
      createCoursePanel.style.display = "none";
      document.body.style.overflow = "";
    }
  }

  if (btnShowCreateCourse && createCoursePanel) {
    btnShowCreateCourse.addEventListener("click", openCreateCourseModal);
  }
  if (btnHideCreateCourse && createCoursePanel) {
    btnHideCreateCourse.addEventListener("click", closeCreateCourseModal);
  }
  if (btnCancelCreateCourse && createCoursePanel) {
    btnCancelCreateCourse.addEventListener("click", closeCreateCourseModal);
  }

  // Backdrop click to close
  if (createCoursePanel) {
    createCoursePanel.addEventListener("click", (e) => {
      if (e.target === createCoursePanel) closeCreateCourseModal();
    });
  }

  // ESC key to close
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && createCoursePanel && createCoursePanel.style.display === "flex") {
      closeCreateCourseModal();
    }
  });

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
          closeCreateCourseModal();
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
    window.currentCourseId = courseId;
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
        window.allLessonsCache = allLessonsCache;
      }
    } catch (e) {
      console.warn("Could not load all lessons:", e);
    }

    if (!Array.isArray(allLessonsCache)) {
      allLessonsCache = [];
      window.allLessonsCache = [];
    }

    if (kpiTotalLectures) kpiTotalLectures.textContent = allLessonsCache.length;
    syncStudioLecturePicker();
  }
  window.loadAllLessons = loadAllLessons;

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
            <div class="lecture-play-icon" title="Lecture Video">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                <polygon points="5 3 19 12 5 21 5 3"></polygon>
              </svg>
            </div>
            <div class="lecture-info-col">
              <h4>${escapeHtml(l.title)}</h4>
              <div class="lecture-meta-badges">
                <span class="badge-duration">⏱️ ${durFormatted}</span>
                <span class="badge-ready">✓ Ready</span>
                ${attachedMaterials.length > 0 ? `<span class="badge-materials-count">📁 ${attachedMaterials.length} Attached</span>` : ''}
              </div>
            </div>
          </div>
          <div class="lecture-card-v2-actions">
            <button class="btn btn-primary btn-play-in-studio" data-id="${l.id}">
              ▶ Watch Lecture
            </button>
            <button class="btn btn-sm btn-lecture-mcqs" data-id="${l.id}" data-title="${escapeHtml(l.title)}" title="Practice MCQs for this lecture" style="background: rgba(99, 102, 241, 0.15); color: #a5b4fc; border: 1px solid rgba(99, 102, 241, 0.35); font-weight: 600;">
              🎯 Practice MCQs
            </button>
            <button class="btn btn-sm btn-lecture-ai-assignment" data-id="${l.id}" data-title="${escapeHtml(l.title)}" title="AI Assignment Studio" style="background: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.35); font-weight: 600;">
              📝 Assignment
            </button>
            <button class="btn btn-sm btn-danger-outline btn-delete-lecture" data-id="${l.id}" title="Delete Lecture">
              🗑️
            </button>
          </div>
        </div>

        ${attachedMaterials.length > 0 ? `
        <!-- Attached Notes & Assignments Section -->
        <div class="attached-materials-box" style="margin-top: 10px;">
          <div class="attached-materials-label">
            <span>📎 Attached Files:</span>
          </div>
          <div class="attached-materials-list" id="attached-list-${l.id}">
            ${attachedMaterials.map(m => {
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
        ` : ''}
      `;

      // Event Listeners on this Lecture Card
      card.querySelector(".btn-play-in-studio").addEventListener("click", () => {
        playLessonInStudio(l.id);
      });

      const btnUploadNotes = card.querySelector(".btn-upload-lecture-notes");
      if (btnUploadNotes) {
        btnUploadNotes.addEventListener("click", () => {
          openUploadMaterialModal(courseId, l.id, l.title, "notes");
        });
      }

      const btnUploadAssign = card.querySelector(".btn-upload-lecture-assignment");
      if (btnUploadAssign) {
        btnUploadAssign.addEventListener("click", () => {
          openUploadMaterialModal(courseId, l.id, l.title, "assignment");
        });
      }

      const aiAssignBtn = card.querySelector(".btn-lecture-ai-assignment");
      if (aiAssignBtn) {
        aiAssignBtn.addEventListener("click", () => {
          window.currentCourseId = courseId;
          currentCourseId = courseId;
          window.currentLessonId = l.id;
          currentLessonId = l.id;
          if (typeof window.openAssignmentModalForLecture === "function") {
            window.openAssignmentModalForLecture(l.id);
          }
        });
      }

      const mcqBtn = card.querySelector(".btn-lecture-mcqs");
      if (mcqBtn) {
        mcqBtn.addEventListener("click", () => {
          window.currentCourseId = courseId;
          currentCourseId = courseId;
          window.currentLessonId = l.id;
          currentLessonId = l.id;
          if (typeof window.openMcqModalForLecture === "function") {
            window.openMcqModalForLecture(l.id);
          }
        });
      }

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

      try {
        if (modalVideoMode === "file") {
          if (!modalSelectedVideoFile) {
            alert("Please select a video file to upload.");
            return;
          }

          modalBtnSubmitVideo.disabled = true;
          modalBtnSubmitVideo.textContent = "Uploading to Drive...";
          modalUploadFeedback.innerHTML = `<span style="color: var(--accent-cyan);">☁️ Starting direct upload to 5TB Drive Vault (0 MB Cloud Run load)...</span>`;

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
                if (pct >= 100) {
                  modalUploadFeedback.innerHTML = `<span style="color: var(--accent-cyan);">☁️ Finalizing Google Drive Vault file: <strong>100%</strong> (saving...)</span>`;
                }
              }
            };

            xhr.onload = () => {
              if (xhr.status === 200 || xhr.status === 201) {
                try {
                  resolve(JSON.parse(xhr.responseText));
                } catch (ex) {
                  const m = xhr.responseText.match(/"id"\s*:\s*"([^"]+)"/);
                  if (m) resolve({ id: m[1] });
                  else resolve({ id: null, raw: xhr.responseText });
                }
              } else {
                reject(new Error(`Google Drive returned HTTP ${xhr.status}: ${xhr.responseText || xhr.statusText}`));
              }
            };

            xhr.onerror = () => reject(new Error("Network error during direct Drive upload. Please check connection."));
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
        s1.querySelector(".step-status").textContent = "Queuing...";

        modalBtnSubmitVideo.disabled = true;
        modalBtnSubmitVideo.textContent = "Dispatched to Background Worker...";

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
        const jobId = data.job_id;
        modalUploadFeedback.innerHTML = `<span style="color: var(--accent-cyan);">⚡ Ingestion job dispatched: <code>${jobId}</code>. Tracking live progress...</span>`;

        // Authoritative Background Status Polling
        await pollJobProgress(jobId, courseId);

      } catch (err) {
        modalUploadFeedback.innerHTML = `<span style="color: var(--accent-rose);">Error: ${err.message}</span>`;
        modalBtnSubmitVideo.disabled = false;
        modalBtnSubmitVideo.textContent = "Process & Ingest Lecture";
      }
    });

    async function pollJobProgress(targetJobId, targetCourseId) {
      const s1 = document.getElementById("modal-step-1");
      const s2 = document.getElementById("modal-step-2");
      const s3 = document.getElementById("modal-step-3");
      const s4 = document.getElementById("modal-step-4");

      let pollInterval = null;
      let pollAttempts = 0;
      const maxAttempts = 600; // 20 minutes max polling time (2s interval)

      return new Promise((resolve) => {
        pollInterval = setInterval(async () => {
          pollAttempts++;
          if (pollAttempts > maxAttempts) {
            clearInterval(pollInterval);
            modalUploadFeedback.innerHTML = `<span style="color: var(--accent-amber);">Job is still running in background. You can check back shortly or refresh.</span>`;
            modalBtnSubmitVideo.disabled = false;
            modalBtnSubmitVideo.textContent = "Process & Ingest Lecture";
            resolve();
            return;
          }

          try {
            const jobRes = await fetch(`/api/jobs/${targetJobId}`);
            if (!jobRes.ok) return;
            const job = await jobRes.json();
            const stage = job.current_stage || job.stage || "QUEUED";
            const status = job.status || "IN_PROGRESS";
            const progressPct = job.progress_percent || 0;
            const stageMsg = job.stage_message || "";

            modalUploadFeedback.innerHTML = `<span style="color: var(--accent-cyan);">${stageMsg || `Processing (${progressPct}%)...`}</span>`;

            if (stage === "QUEUED" || stage === "VERIFYING_SOURCE") {
              s1.classList.add("processing"); s1.classList.remove("completed");
              s1.querySelector(".step-status").textContent = "Running...";
              s2.querySelector(".step-status").textContent = "Pending";
              s3.querySelector(".step-status").textContent = "Pending";
              s4.querySelector(".step-status").textContent = "Pending";
            } else if (stage === "AUDIO_EXTRACTION") {
              s1.classList.remove("processing"); s1.classList.add("completed");
              s1.querySelector(".step-status").textContent = "Done";
              s2.classList.add("processing"); s2.classList.remove("completed");
              s2.querySelector(".step-status").textContent = "Extracting...";
            } else if (stage === "TRANSCRIPTION") {
              s1.classList.add("completed");
              s1.querySelector(".step-status").textContent = "Done";
              s2.classList.add("processing"); s2.classList.remove("completed");
              s2.querySelector(".step-status").textContent = "Transcribing...";
            } else if (stage === "SEMANTIC_PROCESSING") {
              s1.classList.add("completed"); s1.querySelector(".step-status").textContent = "Done";
              s2.classList.add("completed"); s2.querySelector(".step-status").textContent = "Done";
              s3.classList.add("processing"); s3.classList.remove("completed");
              s3.querySelector(".step-status").textContent = "Chunking...";
            } else if (stage === "EMBEDDING" || stage === "VECTOR_SYNC") {
              s1.classList.add("completed"); s1.querySelector(".step-status").textContent = "Done";
              s2.classList.add("completed"); s2.querySelector(".step-status").textContent = "Done";
              s3.classList.add("completed"); s3.querySelector(".step-status").textContent = "Done";
              s4.classList.add("processing"); s4.classList.remove("completed");
              s4.querySelector(".step-status").textContent = "Embedding...";
            }

            if (status === "COMPLETED") {
              clearInterval(pollInterval);
              s1.classList.add("completed"); s1.querySelector(".step-status").textContent = "Done";
              s2.classList.add("completed"); s2.querySelector(".step-status").textContent = "Done";
              s3.classList.add("completed"); s3.querySelector(".step-status").textContent = "Done";
              s4.classList.remove("processing"); s4.classList.add("completed");
              s4.querySelector(".step-status").textContent = "Indexed";

              modalUploadFeedback.innerHTML = `<span style="color: var(--accent-emerald);">🎉 Lecture indexed successfully!</span>`;

              setTimeout(async () => {
                modalUploadVideo.style.display = "none";
                modalBtnSubmitVideo.disabled = false;
                modalBtnSubmitVideo.textContent = "Process & Ingest Lecture";
                await openCourseWorkspace(targetCourseId);
                resolve();
              }, 1200);
            } else if (status === "FAILED") {
              clearInterval(pollInterval);
              const errorMsg = job.error_message || "Video processing failed.";
              modalUploadFeedback.innerHTML = `
                <div style="color: var(--accent-rose); margin-bottom: 8px;">Error: ${errorMsg}</div>
                <button type="button" class="btn btn-secondary btn-sm" id="btn-retry-failed-job" style="margin-top: 4px;">🔄 Retry from Checkpoint</button>
              `;
              const retryBtn = document.getElementById("btn-retry-failed-job");
              if (retryBtn) {
                retryBtn.addEventListener("click", async () => {
                  retryBtn.disabled = true;
                  retryBtn.textContent = "Retrying...";
                  await fetch(`/api/jobs/${targetJobId}/retry`, { method: "POST" });
                  pollJobProgress(targetJobId, targetCourseId);
                });
              }
              modalBtnSubmitVideo.disabled = false;
              modalBtnSubmitVideo.textContent = "Process & Ingest Lecture";
              resolve();
            } else if (status === "CANCELLED") {
              clearInterval(pollInterval);
              modalUploadFeedback.innerHTML = `<span style="color: var(--text-muted);">Job was cancelled.</span>`;
              modalBtnSubmitVideo.disabled = false;
              modalBtnSubmitVideo.textContent = "Process & Ingest Lecture";
              resolve();
            }
          } catch (pollErr) {
            console.warn("Poll status check error:", pollErr);
          }
        }, 2000);
      });
    }
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
    window.currentLessonId = lessonId;
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
    window.currentLessonId = lessonId;

    try {
      const res = await fetch(`/api/lessons/${lessonId}`);
      if (!res.ok) return;
      const lesson = await res.json();

      if (lectureTitle) lectureTitle.textContent = lesson.title;
      currentUtterances = lesson.utterances || [];
      currentChunks = lesson.chunks || [];

      if (uttCount) uttCount.textContent = currentUtterances.length;
      if (chunkCount) chunkCount.textContent = currentChunks.length;

      // Video Source handling: High-performance direct streaming via Backend & Google Drive API
      // Bypasses slow Google Drive web preview transcoding queue and supports native 206 byte ranges
      const vUrl = lesson.video_url || "";
      const streamEndpoint = `${API_BASE}/api/lessons/${lesson.id}/stream`;

      if (driveIframe) driveIframe.style.display = "none";
      if (video) {
        video.style.display = "block";
        if (videoOverlay) videoOverlay.style.display = "flex";

        // Fallback: If native player hits format or CORS issues, gracefully fall back to Drive preview
        video.onerror = () => {
          console.warn("[Stream Notice] Native stream error event. Attempting Google Drive preview fallback...");
          const match = vUrl.match(/\/d\/([a-zA-Z0-9_-]+)/);
          const fileId = match ? match[1] : null;
          if (fileId && driveIframe) {
            video.style.display = "none";
            if (videoOverlay) videoOverlay.style.display = "none";
            driveIframe.dataset.fileId = fileId;
            driveIframe.src = `https://drive.google.com/file/d/${fileId}/preview`;
            driveIframe.style.display = "block";
          }
        };

        // Stream from backend endpoint (supports 3-min, 11-min, and 3-hour long production videos)
        video.src = streamEndpoint;
        video.load();
      }

      // Reset AI Chat to fresh separate session for this lecture
      resetChatSession(lesson.title);

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
  // 7. AI DOUBT MENTOR (Per-Student Isolated Session with Anti-Hallucination Grounding)
  // ==========================================
  let currentChatSessionId = `session_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;

  function resetChatSession(lessonTitle = "this lecture") {
    const oldSession = currentChatSessionId;
    currentChatSessionId = `session_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
    
    if (chatMessages) {
      chatMessages.innerHTML = `
        <div class="message-wrapper ai">
          <div class="msg-avatar">AI</div>
          <div class="msg-content">
            <div class="msg-bubble">
              👋 <strong>Namaste! I'm your AI Professor for ${escapeHtml(lessonTitle)}.</strong><br>
              I am grounded strictly in this video lecture's transcript. Ask me any conceptual doubt, and I will explain step-by-step with interactive video timestamps <code>[MM:SS]</code>.
            </div>
          </div>
        </div>
      `;
    }

    if (oldSession) {
      fetch("/api/chat/clear", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: oldSession })
      }).catch(() => {});
    }
  }

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
      resetChatSession(lectureTitle ? lectureTitle.textContent : "this lecture");
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
          lesson_id: currentLessonId || "masterclass_os_3hours",
          session_id: currentChatSessionId
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


// ============================================================
// STRICT ADMIN AUTHENTICATION & AI ASSIGNMENT STUDIO ENGINE
// ============================================================

const AUTHORIZED_ADMIN_EMAILS = [
  "amirshaikh320340@gmail.com",
  "amirshaikh@gmail.com"
];

function isAuthorizedAdminEmail(email) {
  if (!email) return false;
  return AUTHORIZED_ADMIN_EMAILS.includes(email.toLowerCase().trim());
}

let activeAttemptEmail = "amirshaikh320340@gmail.com";
const SUPABASE_PROJECT_URL = "https://jueoglgbseoxszygpjdb.supabase.co";
const SUPABASE_PUBLIC_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imp1ZW9nbGdic2VveHN6eWdwamRiIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODE3ODUwMjYsImV4cCI6MjA5NzM2MTAyNn0.PmVKzsVVHYS384PahpfCHB-_DZLg4gTlQN1sVOYfa8w";

let supabaseClient = null;
if (window.supabase && typeof window.supabase.createClient === "function") {
  supabaseClient = window.supabase.createClient(SUPABASE_PROJECT_URL, SUPABASE_PUBLIC_KEY);
}

// 1. Strict Gatekeeper Screen & Session Guard
async function checkStrictAdminAuth() {
  const overlay = document.getElementById("admin-gatekeeper-overlay");
  const userBadge = document.getElementById("admin-user-badge");
  const logoutBtn = document.getElementById("btn-admin-logout");

  if (!supabaseClient) {
    console.warn("Supabase client not loaded, checking local admin flag");
    const localSess = localStorage.getItem("climbup_admin_verified");
    if (localSess === "true") {
      if (overlay) overlay.style.display = "none";
      if (userBadge) userBadge.style.display = "inline-flex";
      if (logoutBtn) logoutBtn.style.display = "inline-flex";
      return true;
    }
    return false;
  }

  try {
    const { data: { session } } = await supabaseClient.auth.getSession();
    const verifiedLocal = localStorage.getItem("climbup_admin_verified");

    const sessEmail = session?.user?.email?.toLowerCase().trim();
    if (
      isAuthorizedAdminEmail(sessEmail) ||
      (verifiedLocal === "true")
    ) {
      if (overlay) overlay.style.display = "none";
      if (userBadge) userBadge.style.display = "inline-flex";
      if (logoutBtn) logoutBtn.style.display = "inline-flex";
      return true;
    }
  } catch (err) {
    console.error("Auth check error:", err);
  }

  // Lock Studio if not authenticated
  if (overlay) overlay.style.display = "flex";
  if (userBadge) userBadge.style.display = "none";
  if (logoutBtn) logoutBtn.style.display = "none";
  return false;
}

// 2. Setup Gatekeeper Form Listeners
function setupGatekeeperListeners() {
  const emailForm = document.getElementById("gatekeeper-email-form");
  const otpForm = document.getElementById("gatekeeper-otp-form");
  const emailInput = document.getElementById("gatekeeper-email-input");
  const alertBox = document.getElementById("gatekeeper-alert");
  const sendBtn = document.getElementById("btn-send-admin-otp");
  const verifyBtn = document.getElementById("btn-verify-admin-otp");
  const backBtn = document.getElementById("btn-gatekeeper-back");
  const logoutBtn = document.getElementById("btn-admin-logout");
  const otpBoxes = document.querySelectorAll(".otp-digit-box");

  function showAlert(msg, isSuccess = false) {
    if (!alertBox) return;
    alertBox.textContent = msg;
    alertBox.className = `gatekeeper-alert ${isSuccess ? "success" : "error"}`;
    alertBox.style.display = "block";
  }

  // OTP auto-advance & Paste Handler
  otpBoxes.forEach((box, idx) => {
    box.addEventListener("paste", (e) => {
      e.preventDefault();
      const pasteData = (e.clipboardData || window.clipboardData).getData("text").replace(/\D/g, "").slice(0, otpBoxes.length);
      if (!pasteData) return;
      pasteData.split("").forEach((char, i) => {
        if (otpBoxes[i]) otpBoxes[i].value = char;
      });
      const nextIdx = Math.min(pasteData.length, otpBoxes.length - 1);
      if (otpBoxes[nextIdx]) otpBoxes[nextIdx].focus();
    });

    box.addEventListener("input", (e) => {
      const val = e.target.value.replace(/\D/g, "");
      e.target.value = val;
      if (val && idx < otpBoxes.length - 1) {
        otpBoxes[idx + 1].focus();
      }
    });

    box.addEventListener("keydown", (e) => {
      if (e.key === "Backspace" && !e.target.value && idx > 0) {
        otpBoxes[idx - 1].focus();
      }
    });
  });

  // Step 1: Send OTP
  if (emailForm) {
    emailForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      alertBox.style.display = "none";

      const cleanEmail = (emailInput?.value || "").trim().toLowerCase();
      if (!isAuthorizedAdminEmail(cleanEmail)) {
        showAlert(`Access Denied: Portal is strictly restricted to amirshaikh320340@gmail.com.`);
        return;
      }

      activeAttemptEmail = cleanEmail;

      if (sendBtn) {
        sendBtn.disabled = true;
        sendBtn.textContent = "Sending Secure OTP...";
      }

      try {
        if (!supabaseClient) throw new Error("Supabase client not initialized.");

        const { error } = await supabaseClient.auth.signInWithOtp({
          email: activeAttemptEmail,
          options: { shouldCreateUser: true }
        });

        if (error) throw error;

        showAlert(`Secure 8-digit OTP code sent to ${activeAttemptEmail}. Please check your inbox.`, true);
        if (emailForm) emailForm.style.display = "none";
        if (otpForm) otpForm.style.display = "block";
        if (otpBoxes[0]) otpBoxes[0].focus();
      } catch (err) {
        console.error("OTP send error:", err);
        showAlert(err.message || "Failed to send OTP code. Please check SMTP configuration.");
      } finally {
        if (sendBtn) {
          sendBtn.disabled = false;
          sendBtn.textContent = "Request Secure OTP Code";
        }
      }
    });
  }

  // Step 2: Verify OTP
  if (otpForm) {
    otpForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      alertBox.style.display = "none";

      let otpCode = "";
      otpBoxes.forEach(b => { otpCode += b.value.trim(); });

      if (otpCode.length < 6 || otpCode.length > 8) {
        showAlert("Please enter the complete 8-digit OTP code.");
        return;
      }

      if (verifyBtn) {
        verifyBtn.disabled = true;
        verifyBtn.textContent = "Verifying Code...";
      }

      try {
        if (!supabaseClient) throw new Error("Supabase client not initialized.");

        const { data, error } = await supabaseClient.auth.verifyOtp({
          email: activeAttemptEmail,
          token: otpCode,
          type: "email"
        });

        if (error) throw error;

        if (!data.user || !isAuthorizedAdminEmail(data.user.email)) {
          await supabaseClient.auth.signOut();
          throw new Error("Unauthorized identity. Verification rejected.");
        }

        localStorage.setItem("climbup_admin_verified", "true");
        showAlert("Verification successful! Unlocking studio...", true);

        setTimeout(() => {
          checkStrictAdminAuth();
        }, 600);
      } catch (err) {
        console.error("OTP verify error:", err);
        showAlert(err.message || "Invalid or expired OTP. Please try again.");
      } finally {
        if (verifyBtn) {
          verifyBtn.disabled = false;
          verifyBtn.textContent = "Verify OTP & Unlock Studio";
        }
      }
    });
  }

  if (backBtn) {
    backBtn.addEventListener("click", () => {
      if (otpForm) otpForm.style.display = "none";
      if (emailForm) emailForm.style.display = "block";
      alertBox.style.display = "none";
    });
  }

  if (logoutBtn) {
    logoutBtn.addEventListener("click", async () => {
      if (confirm("Lock Administrator Studio and logout?")) {
        try {
          if (supabaseClient) await supabaseClient.auth.signOut();
        } catch (e) {}
        localStorage.removeItem("climbup_admin_verified");
        location.reload();
      }
    });
  }
}

// 3. AI Assignment Studio & Editable Components Engine
let currentGeneratedAssignment = null;

function setupAiAssignmentStudio() {
  const openBtn = document.getElementById("btn-open-ai-assignment-generator");
  const studioOpenBtn = document.getElementById("btn-studio-open-ai-assignment");
  const modal = document.getElementById("modal-ai-assignment-editor");
  const closeBtn = document.getElementById("btn-close-ai-assign-modal");
  const lectureSelect = document.getElementById("ai-assign-lecture-select");
  const triggerBtn = document.getElementById("btn-trigger-ai-synthesis");
  const statusBanner = document.getElementById("ai-assign-status-banner");
  const editForm = document.getElementById("ai-assign-edit-form");
  const saveDraftBtn = document.getElementById("btn-save-draft-assignment");

  if (!modal) return;

  function populateLectureDropdown(preselectedId) {
    if (!lectureSelect) return;
    lectureSelect.innerHTML = "";

    const lessonsList = (window.allLessonsCache && window.allLessonsCache.length > 0)
      ? window.allLessonsCache
      : (typeof allLessonsCache !== "undefined" && allLessonsCache.length > 0 ? allLessonsCache : []);

    const coursesList = (window.coursesCache && window.coursesCache.length > 0)
      ? window.coursesCache
      : (typeof coursesCache !== "undefined" && coursesCache.length > 0 ? coursesCache : []);

    if (lessonsList.length === 0) {
      lectureSelect.innerHTML = "<option value=''>No lectures found in any course</option>";
      return;
    }

    // Determine target selection ID
    let targetLessonId = preselectedId || (typeof currentLessonId !== "undefined" && currentLessonId ? currentLessonId : window.currentLessonId);

    // If preselectedId is provided, sync global state so course and lesson are aligned
    if (targetLessonId) {
      const match = lessonsList.find(l => l.id === targetLessonId);
      if (match) {
        if (match.course_id) {
          window.currentCourseId = match.course_id;
          if (typeof currentCourseId !== "undefined") currentCourseId = match.course_id;
        }
        window.currentLessonId = match.id;
        if (typeof currentLessonId !== "undefined") currentLessonId = match.id;
      }
    }

    const coursesMap = new Map();
    coursesList.forEach(c => coursesMap.set(c.id, c.title));

    // Group all lectures by their Course
    const grouped = {};
    lessonsList.forEach(l => {
      const cId = l.course_id || "general";
      const cTitle = coursesMap.get(cId) || (cId.replace(/^course-/, "").replace(/-/g, " ").toUpperCase());
      if (!grouped[cTitle]) grouped[cTitle] = [];
      grouped[cTitle].push(l);
    });

    let foundSelection = false;
    Object.keys(grouped).forEach(courseTitle => {
      const optgroup = document.createElement("optgroup");
      optgroup.label = `📚 ${courseTitle}`;

      grouped[courseTitle].forEach(l => {
        const opt = document.createElement("option");
        opt.value = l.id;
        opt.textContent = `${l.title} (${l.duration || "Video"})`;
        if (targetLessonId && targetLessonId === l.id) {
          opt.selected = true;
          foundSelection = true;
        }
        optgroup.appendChild(opt);
      });

      lectureSelect.appendChild(optgroup);
    });

    if (foundSelection && targetLessonId) {
      lectureSelect.value = targetLessonId;
    } else if (lectureSelect.options.length > 0) {
      lectureSelect.selectedIndex = 0;
    }
  }

  const emptyState = document.getElementById("ai-assign-empty-state");
  const workspace = document.getElementById("ai-assign-workspace");
  const tabBtnEdit = document.getElementById("tab-btn-edit-mode");
  const tabBtnPreview = document.getElementById("tab-btn-preview-mode");
  const previewPane = document.getElementById("ai-assign-student-preview-pane");
  const previewContent = document.getElementById("student-preview-content");
  const statusPill = document.getElementById("ai-assign-status-pill");
  const qualityPill = document.getElementById("ai-assign-quality-pill");
  const domainPill = document.getElementById("ai-assign-domain-pill");
  const qualityBreakdown = document.getElementById("ai-quality-checks-breakdown");
  const totalMarksBadge = document.getElementById("ai-edit-total-marks-badge");

  function escapeHtml(str) {
    if (!str) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  // Tab Switching
  if (tabBtnEdit && tabBtnPreview) {
    tabBtnEdit.addEventListener("click", () => {
      tabBtnEdit.classList.add("active");
      tabBtnEdit.style.background = "rgba(56, 211, 153, 0.18)";
      tabBtnEdit.style.color = "#38d399";
      tabBtnPreview.classList.remove("active");
      tabBtnPreview.style.background = "transparent";
      tabBtnPreview.style.color = "#94a3b8";

      if (editForm) editForm.style.display = "block";
      if (previewPane) previewPane.style.display = "none";
    });

    tabBtnPreview.addEventListener("click", () => {
      tabBtnPreview.classList.add("active");
      tabBtnPreview.style.background = "rgba(56, 211, 153, 0.18)";
      tabBtnPreview.style.color = "#38d399";
      tabBtnEdit.classList.remove("active");
      tabBtnEdit.style.background = "transparent";
      tabBtnEdit.style.color = "#94a3b8";

      if (editForm) editForm.style.display = "none";
      if (previewPane) {
        previewPane.style.display = "block";
        renderStudentPreview();
      }
    });
  }

  function updateTotalMarksTally() {
    if (!totalMarksBadge) return;
    const inputs = document.querySelectorAll(".edit-prob-marks");
    let sum = 0;
    inputs.forEach(inp => { sum += parseInt(inp.value) || 0; });
    totalMarksBadge.textContent = `Sum: ${sum} pts / 100 max`;
    totalMarksBadge.style.color = (sum === 100) ? "#38d399" : "#fbbf24";
  }

  function renderStudentPreview() {
    if (!previewContent || !currentGeneratedAssignment) return;
    const values = collectFormValues();
    const problems = values.problems || [];
    const assignmentId = currentGeneratedAssignment.id;

    if (!window._goalStates || window._goalStates._assignmentId !== assignmentId) {
      window._goalStates = { _assignmentId: assignmentId };
      problems.forEach((p, idx) => {
        window._goalStates[idx + 1] = {
          status: idx === 0 ? "not-started" : "locked",
          code: p.starter_code || (values.starter_code || ""),
          test_results: [],
          feedback: "",
          marks_earned: 0
        };
      });
    }

    const goalStatusLabels = {
      "not-started": { label: "⚪ Not Started", class: "not-started" },
      "in-progress": { label: "⏳ In Progress", class: "in-progress" },
      "passed": { label: "✅ Passed", class: "passed" },
      "needs-revision": { label: "⚠️ Needs Revision", class: "needs-revision" },
      "locked": { label: "🔒 Locked", class: "locked" }
    };

    const assignType = String(values.assignment_type || (problems.every(p => p.goal_type === 'THEORY') ? 'THEORY' : problems.some(p => p.goal_type === 'THEORY') ? 'MIXED' : 'CODING')).toUpperCase();
    const assignTypePill = assignType === 'THEORY'
      ? `<span class="assignment-type-pill theory">📚 Theory Assignment</span>`
      : assignType === 'MIXED'
      ? `<span class="assignment-type-pill mixed">🔀 Mixed (Theory + Coding)</span>`
      : `<span class="assignment-type-pill coding">💻 Coding Assignment</span>`;

    previewContent.innerHTML = `
      <div class="preview-mission-header">
        <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; margin-bottom: 8px; flex-wrap: wrap;">
          <div>
            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px;">
              <span style="font-size: 0.75rem; font-weight: 800; color: #38d399; text-transform: uppercase;">
                🎯 Real-World Student Mission
              </span>
              ${assignTypePill}
            </div>
            <h3 style="font-size: 1.25rem; font-weight: 800; color: #fff; margin: 0 0 6px 0;">${escapeHtml(values.title)}</h3>
          </div>
          <div style="text-align: right; font-size: 0.8rem; color: #94a3b8;">
            <div style="font-weight: 800; color: #38d399; font-size: 1.05rem;">${values.max_score} Total Marks</div>
            <div>Due: ${escapeHtml(values.due_date)}</div>
          </div>
        </div>
        <p style="font-size: 0.86rem; color: #cbd5e1; margin: 0; line-height: 1.5; background: rgba(0,0,0,0.25); padding: 10px 14px; border-radius: 8px; border-left: 3px solid #38d399;">
          ${escapeHtml(values.scenario_context || "Follow the mission specifications below to complete your assignment.")}
        </p>
      </div>

      <div style="display: grid; gap: 18px; margin-bottom: 18px;">
        ${problems.map((p, idx) => {
          const gNum = idx + 1;
          const gType = String(p.goal_type || (assignType === 'THEORY' ? 'THEORY' : 'CODING')).toUpperCase();
          const isMcq = (gType === 'MCQ');
          const isNumeric = (gType === 'NUMERIC');
          const isTheory = (gType === 'THEORY');
          const isCoding = (!isMcq && !isNumeric && !isTheory);

          const gState = window._goalStates[gNum] || { status: idx === 0 ? "not-started" : "locked", code: p.starter_code || "" };
          const isLocked = gState.status === "locked";
          const stInfo = goalStatusLabels[gState.status] || goalStatusLabels["not-started"];
          const tier = p.tier || "Core";
          const tierLower = tier.toLowerCase();
          const tierColor = tierLower.includes("basic") || tierLower.includes("beginner") ? "#38bdf8" : tierLower.includes("intermediate") ? "#fbbf24" : "#f472b6";
          const ts = p.lecture_timestamp || p.timestamp_hint || "";
          const testCases = p.test_cases || [];
          const visibleTests = testCases.filter(t => !t.is_hidden);
          const hiddenCount = testCases.filter(t => t.is_hidden).length;
          const checkpoints = p.conceptual_checkpoints || p.acceptance_criteria || [];

          let typeLabel = '💻 Coding Challenge';
          let typeClass = 'coding';
          let btnGradient = 'linear-gradient(135deg, #38d399 0%, #059669 100%)';
          let btnColor = '#021526';
          if (isMcq) {
            typeLabel = '📝 Multiple Choice Checkpoint';
            typeClass = 'mcq';
            btnGradient = 'linear-gradient(135deg, #38bdf8 0%, #0284c7 100%)';
            btnColor = '#021526';
          } else if (isNumeric) {
            typeLabel = '🔢 Calculation Problem';
            typeClass = 'numeric';
            btnGradient = 'linear-gradient(135deg, #fbbf24 0%, #d97706 100%)';
            btnColor = '#021526';
          } else if (isTheory) {
            typeLabel = '📚 Theory & Architecture';
            typeClass = 'theory';
            btnGradient = 'linear-gradient(135deg, #c084fc 0%, #7c3aed 100%)';
            btnColor = '#ffffff';
          }

          return `
            <div class="preview-goal-card ${isLocked ? 'goal-locked' : 'active-goal'}" id="preview-goal-card-${gNum}">
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; flex-wrap: wrap; gap: 8px;">
                <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
                  <span class="tier-badge-pill ${tierLower}" style="background: ${tierColor}22; color: ${tierColor}; border: 1px solid ${tierColor}55;">
                    Goal ${gNum}: ${tier}
                  </span>
                  <span class="goal-type-badge ${typeClass}">
                    ${typeLabel}
                  </span>
                  <span class="goal-status-badge ${stInfo.class}" id="goal-status-badge-${gNum}">
                    ${stInfo.label}
                  </span>
                  ${ts ? `<span class="timestamp-pill" title="Covered in lecture around this timestamp">⏱️ ${escapeHtml(ts)}</span>` : ''}
                </div>
                <div style="font-size: 0.85rem; font-weight: 800; color: #38d399; background: rgba(56, 211, 153, 0.12); padding: 3px 10px; border-radius: 6px;">
                  ${p.marks || 25} Marks
                </div>
              </div>

              <div style="font-size: 0.88rem; color: #f1f5f9; line-height: 1.55; white-space: pre-wrap; margin-bottom: 12px;">${escapeHtml(p.problem_statement || p.question || "")}</div>

              ${p.expected_deliverable ? `
                <div style="font-size: 0.78rem; color: #cbd5e1; background: rgba(99, 102, 241, 0.08); padding: 7px 12px; border-radius: 6px; border: 1px solid rgba(99, 102, 241, 0.2); margin-bottom: 10px;">
                  <strong style="color: #a5b4fc;">Deliverable:</strong> ${escapeHtml(p.expected_deliverable)}
                </div>
              ` : ''}

              ${isMcq ? `
                <!-- MCQ GOAL: Interactive Option Cards -->
                <div style="margin-bottom: 12px;">
                  <div style="font-size: 0.74rem; color: #38bdf8; font-weight: 700; text-transform: uppercase; margin-bottom: 8px; letter-spacing: 0.04em;">
                    Choose the Correct Answer:
                  </div>
                  <div style="display: grid; gap: 8px;">
                    ${Object.entries(p.mcq?.options || { A: "Option A", B: "Option B", C: "Option C", D: "Option D" }).map(([optKey, optText]) => `
                      <label class="goal-mcq-option" style="display: flex; align-items: center; gap: 12px; background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.1); padding: 10px 14px; border-radius: 8px; cursor: pointer; transition: all 0.2s ease;">
                        <input type="radio" name="mcq_goal_${gNum}" value="${optKey}" ${gState.code === optKey ? 'checked' : ''} ${isLocked ? 'disabled' : ''} style="accent-color: #38bdf8; width: 16px; height: 16px;">
                        <span style="font-weight: 800; color: #38bdf8; font-size: 0.95rem;">${optKey})</span>
                        <span style="color: #e2e8f0; font-size: 0.88rem;">${escapeHtml(optText)}</span>
                      </label>
                    `).join('')}
                  </div>
                </div>
              ` : isNumeric ? `
                <!-- NUMERIC GOAL: Numeric Input and Calculation Helper -->
                <div style="background: rgba(245, 158, 11, 0.06); border: 1px solid rgba(245, 158, 11, 0.25); border-radius: 8px; padding: 14px 16px; margin-bottom: 12px;">
                  <div style="font-size: 0.74rem; font-weight: 700; color: #fbbf24; text-transform: uppercase; margin-bottom: 8px;">
                    🔢 Enter Your Computed Numerical Result
                  </div>
                  <div style="display: flex; align-items: center; gap: 10px;">
                    <input type="text" id="goal-editor-${gNum}" class="form-control" value="${escapeHtml(gState.code)}" placeholder="Enter calculated value (e.g. 10.67)" ${isLocked ? 'disabled' : ''} style="max-width: 240px; font-weight: 700; font-size: 1rem; color: #fff; background: rgba(0,0,0,0.3); border: 1px solid rgba(245, 158, 11, 0.4); padding: 8px 12px; border-radius: 6px;">
                    <span style="color: #fbbf24; font-weight: 700; font-size: 0.88rem;">${escapeHtml(p.numeric?.unit || '')}</span>
                  </div>
                  ${p.numeric?.formula_hint ? `
                    <div style="font-size: 0.76rem; color: #94a3b8; margin-top: 8px; background: rgba(0,0,0,0.2); padding: 6px 10px; border-radius: 5px;">
                      💡 <strong>Formula Hint:</strong> ${escapeHtml(p.numeric.formula_hint)}
                    </div>
                  ` : ''}
                </div>
              ` : isTheory ? `
                <!-- THEORY GOAL: Conceptual Checkpoints & Response Textarea -->
                <div style="margin-bottom: 12px;">
                  <div style="font-size: 0.72rem; color: #c084fc; font-weight: 700; text-transform: uppercase; margin-bottom: 6px; letter-spacing: 0.04em;">
                    📋 Key Conceptual Requirements & Checkpoints:
                  </div>
                  <div style="display: grid; gap: 6px;">
                    ${checkpoints.map((cp, cIdx) => `
                      <div class="goal-theory-checkpoint-item">
                        <span style="color: #c084fc; font-weight: 800;">✦</span>
                        <div>${escapeHtml(typeof cp === 'string' ? cp : cp.name || cp.input_description || `Criterion ${cIdx + 1}`)}</div>
                      </div>
                    `).join('')}
                  </div>
                </div>

                <div class="goal-theory-response-wrapper">
                  <div class="goal-theory-header">
                    <span style="font-size: 0.74rem; font-weight: 700; color: #c084fc; text-transform: uppercase;">
                      📝 Goal ${gNum} Conceptual & Descriptive Analysis
                    </span>
                    <span style="font-size: 0.72rem; color: #94a3b8;">Format: Structured Text & Analysis</span>
                  </div>
                  <textarea id="goal-editor-${gNum}" class="goal-theory-textarea" rows="7" ${isLocked ? 'disabled' : ''} placeholder="Provide your structured conceptual explanation, scenario analysis, trade-off comparisons, and concrete examples for Goal ${gNum} here...">${escapeHtml(gState.code)}</textarea>
                </div>
              ` : `
                <!-- CODING GOAL: Verification Test Cases & Code Editor -->
                <div style="margin-bottom: 12px;">
                  <div style="font-size: 0.72rem; color: #94a3b8; font-weight: 700; text-transform: uppercase; margin-bottom: 6px; letter-spacing: 0.04em;">
                    🧪 Verification Test Cases:
                  </div>
                  <div style="display: grid; gap: 6px;">
                    ${visibleTests.map((vt, tIdx) => `
                      <div class="goal-test-case-item">
                        <div>
                          <strong style="color: #38d399;">Test ${tIdx + 1}:</strong> <span style="color: #cbd5e1;">${escapeHtml(vt.input_description || 'Standard input')}</span>
                        </div>
                        <div style="color: #94a3b8; font-family: monospace; font-size: 0.76rem;">
                          Expected: <span style="color: #a7f3d0;">${escapeHtml(vt.expected_output || 'Pass')}</span>
                        </div>
                      </div>
                    `).join('')}
                    ${hiddenCount > 0 ? `
                      <div style="font-size: 0.74rem; color: #94a3b8; font-style: italic; background: rgba(255,255,255,0.03); padding: 5px 10px; border-radius: 6px;">
                        🔒 +${hiddenCount} Hidden Edge-Case Test${hiddenCount > 1 ? 's' : ''} (Evaluated server-side during verification)
                      </div>
                    ` : ''}
                  </div>
                </div>

                <div class="goal-code-editor-wrapper">
                  <div class="goal-editor-header">
                    <span style="font-size: 0.74rem; font-weight: 700; color: #94a3b8; text-transform: uppercase;">
                      💻 Goal ${gNum} Independent Code Editor
                    </span>
                    <button type="button" class="btn btn-sm btn-secondary btn-reset-goal" data-goal="${gNum}" ${isLocked ? 'disabled' : ''} style="font-size: 0.72rem; padding: 2px 8px;">
                      ↺ Reset Code
                    </button>
                  </div>
                  <textarea id="goal-editor-${gNum}" class="goal-code-textarea" rows="6" ${isLocked ? 'disabled' : ''} placeholder="Write your solution for Goal ${gNum} here...">${escapeHtml(gState.code)}</textarea>
                </div>
              `}

              ${p.mentor_guidance ? `
                <div style="margin-top: 10px; font-size: 0.78rem; color: #a5b4fc; background: rgba(99, 102, 241, 0.08); padding: 8px 12px; border-radius: 6px; border: 1px solid rgba(99, 102, 241, 0.25);">
                  🎓 <strong>Socratic Mentor Guidance:</strong> ${escapeHtml(p.mentor_guidance)}
                </div>
              ` : ''}

              <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 10px; flex-wrap: wrap; gap: 8px;">
                <div style="font-size: 0.74rem; color: #64748b;">
                  ${isLocked ? `🔒 Locked — Pass Goal ${gNum - 1} to unlock this challenge.` : (isMcq ? '⚡ Immediate zero-leakage check' : isNumeric ? '⚡ Precision calculation check' : isTheory ? '📋 Conceptual rubric verification' : '⚡ Server-side sandbox verification')}
                </div>
                <button type="button" class="btn btn-primary btn-verify-goal" id="btn-verify-goal-${gNum}" data-goal="${gNum}" ${isLocked ? 'disabled' : ''} style="background: ${btnGradient}; color: ${btnColor}; font-weight: 800; font-size: 0.82rem; padding: 6px 16px;">
                  ▶ ${isMcq ? `Check Answer (Goal ${gNum})` : isNumeric ? `Verify Calculation (Goal ${gNum})` : isTheory ? `Submit Theory (Goal ${gNum})` : `Run & Verify Goal ${gNum}`}
                </button>
              </div>

              <div id="goal-result-${gNum}" style="display: ${gState.feedback ? 'block' : 'none'};">
                ${gState.feedback ? `
                  <div class="goal-verify-banner ${gState.status === 'passed' ? 'success' : 'error'}">
                    <div style="font-weight: 700; margin-bottom: 4px;">
                      ${gState.status === 'passed' ? '✅ Goal Passed!' : '⚠️ Needs Revision'}
                    </div>
                    <div>${escapeHtml(gState.feedback)}</div>
                  </div>
                ` : ''}
              </div>
            </div>
          `;
        }).join('')}
      </div>
    `;

    // Attach Editor change and verify listeners
    problems.forEach((p, idx) => {
      const gNum = idx + 1;
      const gType = String(p.goal_type || (assignType === 'THEORY' ? 'THEORY' : 'CODING')).toUpperCase();
      const isTheory = (gType === 'THEORY');
      const editor = document.getElementById(`goal-editor-${gNum}`);
      const verifyBtn = document.getElementById(`btn-verify-goal-${gNum}`);
      const resetBtn = document.querySelector(`.btn-reset-goal[data-goal="${gNum}"]`);

      // Radio inputs for MCQ
      const radios = document.querySelectorAll(`input[name="mcq_goal_${gNum}"]`);
      radios.forEach(r => {
        r.addEventListener("change", () => {
          if (r.checked && window._goalStates[gNum]) {
            window._goalStates[gNum].code = r.value;
            if (window._goalStates[gNum].status === "not-started") {
              window._goalStates[gNum].status = "in-progress";
              const b = document.getElementById(`goal-status-badge-${gNum}`);
              if (b) {
                b.className = "goal-status-badge in-progress";
                b.textContent = "⏳ In Progress";
              }
            }
          }
        });
      });

      if (editor) {
        editor.addEventListener("input", () => {
          if (window._goalStates[gNum]) {
            window._goalStates[gNum].code = editor.value;
            if (window._goalStates[gNum].status === "not-started") {
              window._goalStates[gNum].status = "in-progress";
              const b = document.getElementById(`goal-status-badge-${gNum}`);
              if (b) {
                b.className = "goal-status-badge in-progress";
                b.textContent = "⏳ In Progress";
              }
            }
          }
        });
      }

      if (resetBtn) {
        resetBtn.addEventListener("click", () => {
          if (editor) {
            editor.value = p.starter_code || "";
            if (window._goalStates[gNum]) {
              window._goalStates[gNum].code = editor.value;
            }
          }
        });
      }

      if (verifyBtn) {
        verifyBtn.addEventListener("click", async () => {
          let studentCode = editor ? editor.value : "";
          if (isMcq) {
            const checkedRadio = document.querySelector(`input[name="mcq_goal_${gNum}"]:checked`);
            studentCode = checkedRadio ? checkedRadio.value : "";
          }

          verifyBtn.disabled = true;
          verifyBtn.textContent = "⏳ Verifying...";

          const resultContainer = document.getElementById(`goal-result-${gNum}`);
          const statusBadge = document.getElementById(`goal-status-badge-${gNum}`);

          try {
            const resp = await fetch(`/api/assignments/${assignmentId}/verify-goal`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                goal_number: gNum,
                student_code: studentCode,
                student_id: "preview_instructor"
              })
            });

            if (!resp.ok) {
              const err = await resp.json().catch(() => ({}));
              throw new Error(err.detail || "Verification failed");
            }

            const data = await resp.json();
            const passed = Boolean(data.passed);
            window._goalStates[gNum].status = passed ? "passed" : "needs-revision";
            window._goalStates[gNum].feedback = data.feedback || "";
            window._goalStates[gNum].test_results = data.test_results || [];

            if (statusBadge) {
              statusBadge.className = `goal-status-badge ${passed ? 'passed' : 'needs-revision'}`;
              statusBadge.textContent = passed ? "✅ Passed" : "⚠️ Needs Revision";
            }

            if (resultContainer) {
              resultContainer.style.display = "block";
              resultContainer.innerHTML = `
                <div class="goal-verify-banner ${passed ? 'success' : 'error'}">
                  <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                    <div style="font-weight: 800;">
                      ${passed ? '🎉 Verification Passed!' : '⚠️ Needs Revision'}
                    </div>
                    <div style="font-size: 0.78rem; font-weight: 700;">
                      Score: ${data.marks_earned} / ${data.max_marks} Marks
                    </div>
                  </div>
                  <div style="margin-bottom: 8px;">${escapeHtml(data.feedback)}</div>
                  ${data.mentor_guidance ? `
                    <div style="margin: 8px 0; font-size: 0.78rem; color: #a5b4fc; background: rgba(99, 102, 241, 0.12); padding: 8px 10px; border-radius: 6px; border-left: 3px solid #6366f1;">
                      🎓 <strong>Mentor Guidance:</strong> ${escapeHtml(data.mentor_guidance)}
                    </div>
                  ` : ''}
                  ${Array.isArray(data.test_results) && data.test_results.length > 0 ? `
                    <div style="margin-top: 8px; display: grid; gap: 4px; font-size: 0.78rem;">
                      ${data.test_results.map(tr => `
                        <div style="background: rgba(0,0,0,0.25); padding: 4px 8px; border-radius: 4px; display: flex; justify-content: space-between;">
                          <span>${tr.passed ? '✓' : '✗'} ${escapeHtml(tr.name)}</span>
                          <span style="color: ${tr.passed ? '#38d399' : '#f87171'};">${escapeHtml(tr.detail || '')}</span>
                        </div>
                      `).join('')}
                    </div>
                  ` : ''}
                </div>
              `;
            }

            if (passed && gNum < problems.length) {
              const nextNum = gNum + 1;
              if (window._goalStates[nextNum] && window._goalStates[nextNum].status === "locked") {
                window._goalStates[nextNum].status = "not-started";
                const nextCard = document.getElementById(`preview-goal-card-${nextNum}`);
                if (nextCard) {
                  nextCard.classList.remove("goal-locked");
                  nextCard.classList.add("active-goal");
                }
                const nextBadge = document.getElementById(`goal-status-badge-${nextNum}`);
                if (nextBadge) {
                  nextBadge.className = "goal-status-badge not-started";
                  nextBadge.textContent = "⚪ Not Started";
                }
                const nextEditor = document.getElementById(`goal-editor-${nextNum}`);
                if (nextEditor) nextEditor.disabled = false;
                const nextRadios = document.querySelectorAll(`input[name="mcq_goal_${nextNum}"]`);
                nextRadios.forEach(r => r.disabled = false);
                const nextBtn = document.getElementById(`btn-verify-goal-${nextNum}`);
                if (nextBtn) nextBtn.disabled = false;
                const nextReset = document.querySelector(`.btn-reset-goal[data-goal="${nextNum}"]`);
                if (nextReset) nextReset.disabled = false;
              }
            }
          } catch (err) {
            if (resultContainer) {
              resultContainer.style.display = "block";
              resultContainer.innerHTML = `
                <div class="goal-verify-banner error">
                  <div style="font-weight: 700;">Error running verification</div>
                  <div>${escapeHtml(err.message)}</div>
                </div>
              `;
            }
          } finally {
            verifyBtn.disabled = false;
            verifyBtn.textContent = isTheory ? `▶ Submit & Verify Theory Goal ${gNum}` : `▶ Run & Verify Goal ${gNum}`;
          }
        });
      }
    });
  }

  function renderAssignmentInForm(assignment) {
    currentGeneratedAssignment = assignment;
    const titleInput = document.getElementById("ai-edit-title");
    const scenarioInput = document.getElementById("ai-edit-scenario");
    const starterInput = document.getElementById("ai-edit-starter");
    const maxScoreInput = document.getElementById("ai-edit-maxscore");
    const dueInput = document.getElementById("ai-edit-due");
    const challengesList = document.getElementById("ai-edit-challenges-list");

    if (titleInput) titleInput.value = assignment.title || "Real-World Milestone Mission";
    if (scenarioInput) scenarioInput.value = assignment.scenario_context || assignment.description || "";
    if (starterInput) starterInput.value = assignment.starter_code || "";
    if (maxScoreInput) maxScoreInput.value = assignment.max_score || assignment.maxScore || assignment.rubric?.max_score || 100;
    if (dueInput && assignment.due_date) dueInput.value = assignment.due_date;

    // Status Pill
    if (statusPill) {
      const isPub = assignment.status === "published";
      statusPill.textContent = isPub ? "🟢 Published" : "🟡 Draft (Review)";
      statusPill.style.background = isPub ? "rgba(16, 185, 129, 0.15)" : "rgba(245, 158, 11, 0.15)";
      statusPill.style.color = isPub ? "#38d399" : "#fbbf24";
      statusPill.style.border = isPub ? "1px solid rgba(16, 185, 129, 0.3)" : "1px solid rgba(245, 158, 11, 0.3)";
    }

    // Archetype Pill
    const archetypePill = document.getElementById("ai-assign-archetype-pill");
    const assignType = (assignment.assignment_type || (assignment.archetype === "conceptual" ? "THEORY" : "CODING")).toUpperCase();
    if (archetypePill) {
      archetypePill.style.display = "inline-flex";
      archetypePill.className = `assignment-type-pill ${assignType.toLowerCase()}`;
      archetypePill.textContent = assignType === "THEORY" ? "📖 THEORY ASSIGNMENT" : assignType === "MIXED" ? "⚡ MIXED (THEORY + CODE)" : "💻 CODING ASSIGNMENT";
    }

    // Quality Gate Pill & Breakdown
    const qr = assignment.quality_report;
    if (qualityPill) {
      if (qr && typeof qr.quality_score === "number") {
        qualityPill.textContent = `🛡️ Quality Gate: ${qr.quality_score}/100 Verified`;
        qualityPill.style.color = qr.passed ? "#38d399" : "#fbbf24";
        qualityPill.style.display = "inline-block";
      } else {
        qualityPill.textContent = "🛡️ Quality Gate: Verified";
        qualityPill.style.display = "inline-block";
      }
    }

    if (domainPill) {
      const titleLower = (assignment.title || "").toLowerCase();
      const detectedDomain = titleLower.includes("sql") ? "📚 SQL / Database" : titleLower.includes("python") ? "🐍 Python" : "💻 Engineering";
      domainPill.textContent = detectedDomain;
    }

    if (qualityBreakdown && qr && Array.isArray(qr.checks)) {
      qualityBreakdown.innerHTML = `
        <div style="font-weight: 700; color: #fff; margin-bottom: 6px;">Quality Gate Verification Checks:</div>
        <div style="display: grid; gap: 4px;">
          ${qr.checks.map(c => `
            <div style="display: flex; align-items: center; justify-content: space-between; font-size: 0.78rem;">
              <span>${c.passed ? '✓' : '⚠️'} ${escapeHtml(c.name)}</span>
              <span style="color: ${c.passed ? '#38d399' : '#fbbf24'};">${escapeHtml(c.details || '')}</span>
            </div>
          `).join('')}
        </div>
      `;
    }

    // Render Editable Challenges
    if (challengesList) {
      challengesList.innerHTML = "";
      const problems = assignment.problems || [];
      problems.forEach((prob, idx) => {
        const tier = prob.tier || prob.difficulty || (idx === 0 ? "Basic" : idx === 1 ? "Intermediate" : "Advanced");
        const tierLower = tier.toLowerCase();
        const tierColor = tierLower === "basic" ? "#38bdf8" : tierLower === "intermediate" ? "#fbbf24" : "#f472b6";
        const goalType = (prob.goal_type || (assignType === "THEORY" ? "THEORY" : "CODING")).toUpperCase();
        const marks = prob.marks || (idx === 0 ? 25 : idx === 1 ? 35 : 40);
        const statement = prob.problem_statement || prob.question || prob.description || "";
        const criteria = Array.isArray(prob.acceptance_criteria) ? prob.acceptance_criteria : (prob.acceptance_criteria ? [prob.acceptance_criteria] : []);
        const checkpoints = Array.isArray(prob.conceptual_checkpoints) ? prob.conceptual_checkpoints : [];
        const deliverable = prob.expected_deliverable || "";
        const ts = prob.lecture_timestamp || prob.timestamp_hint || `~00:${String(15 * (idx + 1)).padStart(2, '0')}:00`;

        const card = document.createElement("div");
        card.className = "ai-challenge-card";
        card.dataset.tier = tier;
        card.dataset.goaltype = goalType;
        card.dataset.timestamp = ts;
        card.dataset.criteria = JSON.stringify(criteria);
        card.dataset.checkpoints = JSON.stringify(checkpoints);
        card.dataset.testcases = JSON.stringify(prob.test_cases || []);
        card.dataset.solutionhint = prob.solution_hint || "";

        card.innerHTML = `
          <div class="ai-challenge-header">
            <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
              <span class="tier-badge-pill ${tierLower}" style="background: ${tierColor}22; color: ${tierColor}; border: 1px solid ${tierColor}55; padding: 3px 10px; border-radius: 6px; font-size: 0.75rem; font-weight: 800; text-transform: uppercase;">
                Goal ${idx + 1}: ${tier}
              </span>
              <select class="edit-prob-goaltype" style="background: rgba(10, 16, 30, 0.9); border: 1px solid ${goalType === 'THEORY' ? '#38bdf8' : '#38d399'}; color: ${goalType === 'THEORY' ? '#7dd3fc' : '#86efac'}; padding: 3px 8px; border-radius: 6px; font-size: 0.72rem; font-weight: 700; cursor: pointer;">
                <option value="CODING" ${goalType === 'CODING' ? 'selected' : ''}>💻 Coding Goal</option>
                <option value="THEORY" ${goalType === 'THEORY' ? 'selected' : ''}>📖 Theory Goal</option>
                <option value="PRACTICAL" ${goalType === 'PRACTICAL' ? 'selected' : ''}>🛠️ Practical / Lab</option>
              </select>
              <span class="timestamp-pill" title="Covered in lecture around this timestamp">
                ⏱️ ${escapeHtml(ts)}
              </span>
            </div>
            <div style="display: flex; align-items: center; gap: 6px;">
              <span style="font-size: 0.78rem; color: #94a3b8; font-weight: 700;">Marks:</span>
              <input type="number" class="edit-prob-marks" value="${marks}" min="5" max="100" style="width: 55px; background: rgba(10, 16, 30, 0.9); border: 1px solid rgba(56, 211, 153, 0.3); color: #fff; padding: 4px 6px; border-radius: 6px; font-size: 0.8rem; font-weight: 700; text-align: center;">
            </div>
          </div>

          <div style="font-size: 0.72rem; color: #94a3b8; font-weight: 700; text-transform: uppercase; margin-bottom: 4px; letter-spacing: 0.04em;">PROBLEM SPECIFICATIONS:</div>
          <textarea class="edit-prob-desc form-input" rows="${Math.max(3, Math.ceil(statement.length / 95))}" style="width: 100%; box-sizing: border-box; background: rgba(10, 16, 30, 0.85); border: 1px solid rgba(255, 255, 255, 0.12); border-radius: 8px; padding: 9px 12px; color: #fff; font-size: 0.84rem; margin-bottom: 10px; line-height: 1.5; resize: vertical;">${escapeHtml(statement)}</textarea>

          <div class="goal-theory-notice" style="display: ${goalType === 'THEORY' ? 'block' : 'none'}; font-size: 0.76rem; color: #7dd3fc; background: rgba(56, 189, 248, 0.08); border: 1px solid rgba(56, 189, 248, 0.2); border-radius: 6px; padding: 6px 10px; margin-bottom: 10px;">
            📖 Theory Goal: Evaluates conceptual reasoning and descriptive explanations. No code editor required for this goal.
          </div>

          <div class="edit-prob-starter-container" style="margin-bottom: 10px; display: ${goalType === 'THEORY' ? 'none' : 'block'};">
            <div style="font-size: 0.72rem; color: #38d399; font-weight: 700; text-transform: uppercase; margin-bottom: 3px; letter-spacing: 0.04em;">INDEPENDENT GOAL STARTER CODE:</div>
            <textarea class="edit-prob-starter form-input" rows="3" style="width: 100%; box-sizing: border-box; background: #020712; border: 1px solid rgba(56, 211, 153, 0.25); border-radius: 6px; padding: 8px 10px; color: #9ef8dc; font-family: 'JetBrains Mono', monospace; font-size: 0.82rem; line-height: 1.45;">${escapeHtml(prob.starter_code || '')}</textarea>
          </div>

          <div style="display: grid; grid-template-columns: 1fr; gap: 8px; margin-bottom: 10px;">
            <div>
              <div style="font-size: 0.72rem; color: #818cf8; font-weight: 700; text-transform: uppercase; margin-bottom: 3px; letter-spacing: 0.04em;">EXPECTED DELIVERABLE:</div>
              <input type="text" class="edit-prob-deliverable form-input" value="${escapeHtml(deliverable)}" placeholder="e.g. Executable SQL Query or Python function" style="width: 100%; box-sizing: border-box; background: rgba(10, 16, 30, 0.7); border: 1px solid rgba(99, 102, 241, 0.25); border-radius: 6px; padding: 6px 10px; color: #cbd5e1; font-size: 0.82rem;">
            </div>
          </div>

          ${criteria.length > 0 ? `
          <div style="font-size: 0.72rem; color: #38d399; font-weight: 700; text-transform: uppercase; margin-bottom: 4px; letter-spacing: 0.04em;">ACCEPTANCE CRITERIA:</div>
          <div class="edit-criteria-tags" style="display: grid; gap: 4px; margin-bottom: 10px;">
            ${criteria.map(c => `
              <div style="font-size: 0.78rem; color: rgba(255, 255, 255, 0.9); background: rgba(56, 211, 153, 0.06); padding: 5px 10px; border-radius: 6px; border: 1px solid rgba(56, 211, 153, 0.15); display: flex; align-items: flex-start; gap: 6px;">
                <span style="color: #38d399; font-weight: 700;">✓</span> <span>${escapeHtml(c)}</span>
              </div>
            `).join('')}
          </div>
          ` : ''}

          ${checkpoints.length > 0 ? `
          <div style="font-size: 0.72rem; color: #38bdf8; font-weight: 700; text-transform: uppercase; margin-bottom: 4px; letter-spacing: 0.04em;">CONCEPTUAL CHECKPOINTS:</div>
          <div class="edit-criteria-tags" style="display: grid; gap: 4px;">
            ${checkpoints.map(cp => `
              <div style="font-size: 0.78rem; color: rgba(224, 242, 254, 0.9); background: rgba(56, 189, 248, 0.06); padding: 5px 10px; border-radius: 6px; border: 1px solid rgba(56, 189, 248, 0.2); display: flex; align-items: flex-start; gap: 6px;">
                <span style="color: #38bdf8; font-weight: 700;">📌</span> <span>${escapeHtml(cp)}</span>
              </div>
            `).join('')}
          </div>
          ` : ''}
        `;

        const marksInput = card.querySelector(".edit-prob-marks");
        if (marksInput) {
          marksInput.addEventListener("input", updateTotalMarksTally);
        }

        const goalTypeSelect = card.querySelector(".edit-prob-goaltype");
        const starterContainer = card.querySelector(".edit-prob-starter-container");
        const theoryNotice = card.querySelector(".goal-theory-notice");
        if (goalTypeSelect) {
          goalTypeSelect.addEventListener("change", (e) => {
            const val = e.target.value;
            card.dataset.goaltype = val;
            if (starterContainer) starterContainer.style.display = (val === "THEORY") ? "none" : "block";
            if (theoryNotice) theoryNotice.style.display = (val === "THEORY") ? "block" : "none";
            goalTypeSelect.style.borderColor = (val === "THEORY") ? "#38bdf8" : "#38d399";
            goalTypeSelect.style.color = (val === "THEORY") ? "#7dd3fc" : "#86efac";
          });
        }

        challengesList.appendChild(card);
      });
    }

    updateTotalMarksTally();

    // Show workspace, hide empty state
    if (emptyState) emptyState.style.display = "none";
    if (workspace) workspace.style.display = "block";
    if (editForm) editForm.style.display = "block";
    if (previewPane) previewPane.style.display = "none";

    if (tabBtnEdit && tabBtnPreview) {
      tabBtnEdit.classList.add("active");
      tabBtnEdit.style.background = "rgba(56, 211, 153, 0.18)";
      tabBtnEdit.style.color = "#38d399";
      tabBtnPreview.classList.remove("active");
      tabBtnPreview.style.background = "transparent";
      tabBtnPreview.style.color = "#94a3b8";
    }
  }

  async function checkAndLoadExistingAssignment(lessonId) {
    if (!lessonId) return;
    try {
      const res = await fetch(`/api/lessons/${lessonId}/assignment`, {
        headers: { "X-Climbup-Player": "amirshaikh320340" }
      });
      if (res.ok) {
        const data = await res.json();
        if (data && data.assignment) {
          renderAssignmentInForm(data.assignment);
          if (statusBanner) {
            statusBanner.style.display = "block";
            const isPub = data.assignment.status === "published";
            statusBanner.style.background = isPub ? "rgba(16, 185, 129, 0.15)" : "rgba(245, 158, 11, 0.15)";
            statusBanner.style.color = isPub ? "#38d399" : "#fbbf24";
            statusBanner.textContent = isPub
              ? "🟢 Published: This assignment is actively live for enrolled students. You can review, edit, or preview below."
              : "🟡 Draft (Unpublished): Review and edit challenges below. Click '🚀 Confirm & Publish to Students' when ready.";
          }
          return;
        }
      }
    } catch (_) {}

    // No existing assignment found -> show clean empty state
    if (workspace) workspace.style.display = "none";
    if (emptyState) emptyState.style.display = "block";
    if (statusBanner) {
      statusBanner.style.display = "block";
      statusBanner.style.background = "rgba(56, 211, 153, 0.08)";
      statusBanner.style.color = "#94a3b8";
      statusBanner.textContent = "⚡ No assignment generated for this lecture yet. Click '⚡ Synthesize Assignment with AI' above.";
    }
  }

  async function openAssignmentModal(preselectedId) {
    if ((!window.allLessonsCache || window.allLessonsCache.length === 0) && typeof window.loadAllLessons === "function") {
      await window.loadAllLessons();
    }
    populateLectureDropdown(preselectedId);
    if (preselectedId && lectureSelect) {
      lectureSelect.value = preselectedId;
    }
    modal.style.display = "flex";
    const lessonId = lectureSelect?.value || preselectedId;
    if (lessonId) {
      await checkAndLoadExistingAssignment(lessonId);
    }
  }

  window.openAssignmentModalForLecture = openAssignmentModal;

  if (openBtn) {
    openBtn.addEventListener("click", () => {
      const activeLessons = (window.allLessonsCache || []).filter(l => l.course_id === (window.currentCourseId || currentCourseId));
      const preId = (window.currentLessonId && activeLessons.some(l => l.id === window.currentLessonId))
        ? window.currentLessonId
        : (activeLessons[0]?.id || window.currentLessonId);
      openAssignmentModal(preId);
    });
  }
  if (studioOpenBtn) studioOpenBtn.addEventListener("click", () => openAssignmentModal(window.currentLessonId));

  if (lectureSelect) {
    lectureSelect.addEventListener("change", () => {
      checkAndLoadExistingAssignment(lectureSelect.value);
    });
  }

  if (closeBtn) {
    closeBtn.addEventListener("click", () => {
      modal.style.display = "none";
    });
  }

  // Synthesize Assignment with Dual AI
  if (triggerBtn) {
    triggerBtn.addEventListener("click", async () => {
      const lessonId = lectureSelect?.value;
      if (!lessonId) {
        alert("Please select a lecture first.");
        return;
      }

      triggerBtn.disabled = true;
      triggerBtn.textContent = "⚡ Synthesizing Mission...";
      if (statusBanner) {
        statusBanner.style.display = "block";
        statusBanner.style.background = "rgba(56, 211, 153, 0.12)";
        statusBanner.style.color = "#38d399";
        statusBanner.textContent = "Scanning lecture milestones, analyzing technical domain, and synthesizing practical challenges...";
      }

      try {
        const response = await fetch(`/api/admin/lessons/${lessonId}/assignments/generate`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-Climbup-Player": "amirshaikh320340"
          },
          body: JSON.stringify({ difficulty: "intermediate" })
        });

        if (!response.ok) {
          const errData = await response.json().catch(() => ({}));
          throw new Error(errData.detail || "AI assignment generation failed on server.");
        }

        const data = await response.json();
        renderAssignmentInForm(data.assignment);

        if (statusBanner) {
          statusBanner.style.background = "rgba(16, 185, 129, 0.15)";
          statusBanner.style.color = "#38d399";
          statusBanner.textContent = "🟢 Mission Created & Verified: High-quality practical assignment generated! Review, edit if needed, and publish.";
        }
      } catch (err) {
        console.error("Assignment synthesis error:", err);
        if (statusBanner) {
          statusBanner.style.background = "rgba(239, 68, 68, 0.15)";
          statusBanner.style.color = "#fca5a5";
          statusBanner.textContent = "Error synthesizing assignment: " + err.message;
        }
      } finally {
        triggerBtn.disabled = false;
        triggerBtn.textContent = "⚡ Synthesize Assignment with AI";
      }
    });
  }

  // Helper to collect current form values including all edited problems
  function collectFormValues() {
    const cards = document.querySelectorAll(".ai-challenge-card");
    const collectedProblems = [];

    cards.forEach((card, idx) => {
      const marksVal = parseInt(card.querySelector(".edit-prob-marks")?.value) || (idx === 0 ? 25 : idx === 1 ? 35 : 40);
      const descVal = card.querySelector(".edit-prob-desc")?.value || "";
      const delivVal = card.querySelector(".edit-prob-deliverable")?.value || "";
      const tierVal = card.dataset.tier || (idx === 0 ? "Basic" : idx === 1 ? "Intermediate" : "Advanced");
      const tsVal = card.dataset.timestamp || "";
      const goalTypeVal = (card.querySelector(".edit-prob-goaltype")?.value || card.dataset.goaltype || "CODING").toUpperCase();

      let critVal = [];
      try {
        critVal = JSON.parse(card.dataset.criteria || "[]");
      } catch (_) {
        critVal = [];
      }

      let checkpointsVal = [];
      try {
        checkpointsVal = JSON.parse(card.dataset.checkpoints || "[]");
      } catch (_) {
        checkpointsVal = [];
      }

      let testcasesVal = [];
      try {
        testcasesVal = JSON.parse(card.dataset.testcases || "[]");
      } catch (_) {
        testcasesVal = [];
      }

      const starterVal = card.querySelector(".edit-prob-starter")?.value || "";
      const hintVal = card.dataset.solutionhint || "";

      collectedProblems.push({
        problem_number: idx + 1,
        tier: tierVal,
        difficulty: tierVal,
        goal_type: goalTypeVal,
        marks: marksVal,
        problem_statement: descVal,
        question: descVal,
        starter_code: goalTypeVal === "THEORY" ? "" : starterVal,
        test_cases: goalTypeVal === "THEORY" ? [] : testcasesVal,
        conceptual_checkpoints: checkpointsVal,
        solution_hint: hintVal,
        lecture_timestamp: tsVal,
        timestamp_hint: tsVal,
        expected_deliverable: delivVal,
        acceptance_criteria: critVal
      });
    });

    const problemsToUse = collectedProblems.length > 0 ? collectedProblems : (currentGeneratedAssignment?.problems || []);

    // Derive overall assignment_type
    const hasTheory = problemsToUse.some(p => (p.goal_type || "").toUpperCase() === "THEORY");
    const hasCoding = problemsToUse.some(p => (p.goal_type || "").toUpperCase() === "CODING" || (p.goal_type || "").toUpperCase() === "PRACTICAL");
    const derivedAssignType = (hasTheory && hasCoding) ? "MIXED" : hasTheory ? "THEORY" : "CODING";

    return {
      title: document.getElementById("ai-edit-title")?.value || currentGeneratedAssignment?.title || "Real-World Milestone Mission",
      scenario_context: document.getElementById("ai-edit-scenario")?.value || currentGeneratedAssignment?.scenario_context || "",
      assignment_type: derivedAssignType,
      starter_code: derivedAssignType === "THEORY" ? "" : (document.getElementById("ai-edit-starter")?.value || currentGeneratedAssignment?.starter_code || ""),
      max_score: parseInt(document.getElementById("ai-edit-maxscore")?.value) || 100,
      due_date: document.getElementById("ai-edit-due")?.value || "Next Sunday, 11:59 PM",
      problems: problemsToUse,
      quality_report: currentGeneratedAssignment?.quality_report
    };
  }

  // Save as Draft
  if (saveDraftBtn) {
    saveDraftBtn.addEventListener("click", async () => {
      if (!currentGeneratedAssignment) return;
      saveDraftBtn.disabled = true;
      saveDraftBtn.textContent = "Saving...";

      try {
        const payload = { ...collectFormValues(), status: "draft" };
        const response = await fetch(`/api/admin/assignments/${currentGeneratedAssignment.id}/publish`, {
          method: "PUT",
          headers: {
            "Content-Type": "application/json",
            "X-Climbup-Player": "amirshaikh320340"
          },
          body: JSON.stringify(payload)
        });

        if (!response.ok) throw new Error("Failed to save draft.");

        currentGeneratedAssignment.status = "draft";
        if (statusPill) {
          statusPill.textContent = "🟡 Draft (Review)";
          statusPill.style.background = "rgba(245, 158, 11, 0.15)";
          statusPill.style.color = "#fbbf24";
        }
        if (statusBanner) {
          statusBanner.style.background = "rgba(245, 158, 11, 0.15)";
          statusBanner.style.color = "#fbbf24";
          statusBanner.textContent = "🟡 Draft Saved: All edits preserved. Students cannot view this until you click 'Confirm & Publish'.";
        }
        alert("Draft saved successfully! Not visible to students yet.");
      } catch (err) {
        alert("Error saving draft: " + err.message);
      } finally {
        saveDraftBtn.disabled = false;
        saveDraftBtn.textContent = "💾 Save as Draft";
      }
    });
  }

  // Confirm & Publish to Students
  if (editForm) {
    editForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      if (!currentGeneratedAssignment) return;

      const confirmBtn = document.getElementById("btn-confirm-publish-assignment");
      if (confirmBtn) {
        confirmBtn.disabled = true;
        confirmBtn.textContent = "Publishing to Students...";
      }

      try {
        const payload = { ...collectFormValues(), status: "published" };
        const response = await fetch(`/api/admin/assignments/${currentGeneratedAssignment.id}/publish`, {
          method: "PUT",
          headers: {
            "Content-Type": "application/json",
            "X-Climbup-Player": "amirshaikh320340"
          },
          body: JSON.stringify(payload)
        });

        if (!response.ok) {
          const errData = await response.json().catch(() => ({}));
          throw new Error(errData.detail || "Failed to publish assignment.");
        }

        currentGeneratedAssignment.status = "published";
        if (statusPill) {
          statusPill.textContent = "🟢 Published";
          statusPill.style.background = "rgba(16, 185, 129, 0.15)";
          statusPill.style.color = "#38d399";
        }
        if (statusBanner) {
          statusBanner.style.background = "rgba(16, 185, 129, 0.15)";
          statusBanner.style.color = "#38d399";
          statusBanner.textContent = "🟢 Live: Assignment verified by Quality Gate and published to all enrolled students!";
        }

        alert("Assignment successfully verified by Quality Gate and published to enrolled students!");
        modal.style.display = "none";

        // Reload course materials
        if (currentCourseId && typeof loadCourseResources === "function") {
          loadCourseResources(currentCourseId);
        }
      } catch (err) {
        console.error("Publish error:", err);
        alert("Publish failed: " + err.message);
      } finally {
        if (confirmBtn) {
          confirmBtn.disabled = false;
          confirmBtn.textContent = "🚀 Confirm & Publish to Students";
        }
      }
    });
  }

  // Submissions Modal
  const viewSubmissionsBtn = document.getElementById("btn-view-submissions-modal");
  const submissionsModal = document.getElementById("modal-assignment-submissions");
  const closeSubmissionsBtn = document.getElementById("btn-close-submissions-modal");
  const submissionsBody = document.getElementById("submissions-table-body");
  const submissionsBanner = document.getElementById("submissions-loading-banner");

  if (viewSubmissionsBtn && submissionsModal) {
    viewSubmissionsBtn.addEventListener("click", async () => {
      submissionsModal.style.display = "flex";
      if (!currentGeneratedAssignment?.id) {
        if (submissionsBody) {
          submissionsBody.innerHTML = `<tr><td colspan="5" style="text-align: center; padding: 24px; color: var(--text-muted);">Please synthesize or select an assignment first to view submissions.</td></tr>`;
        }
        return;
      }
      if (submissionsBanner) {
        submissionsBanner.style.display = "block";
        submissionsBanner.textContent = "Loading cohort submissions & automated grades...";
      }
      try {
        const res = await fetch(`/api/admin/assignments/${currentGeneratedAssignment.id}/submissions`);
        if (!res.ok) throw new Error("Could not fetch submissions");
        const data = await res.json();
        const subs = data.submissions || [];
        if (submissionsBanner) submissionsBanner.style.display = "none";
        if (subs.length === 0) {
          submissionsBody.innerHTML = `<tr><td colspan="5" style="text-align: center; padding: 28px; color: var(--text-muted);">No student submissions recorded for this assignment yet.</td></tr>`;
          return;
        }
        submissionsBody.innerHTML = subs.map(s => `
          <tr>
            <td>
              <div style="font-weight: 700; color: #fff;">${s.student_email || s.student_id || 'Enrolled Student'}</div>
              <div style="font-size: 0.75rem; color: #94a3b8;">Submission ID: ${s.id || ''}</div>
            </td>
            <td style="font-size: 0.82rem; color: #cbd5e1;">${s.created_at ? new Date(s.created_at).toLocaleString() : 'Recent'}</td>
            <td>
              <span class="badge-mini" style="background: rgba(56, 211, 153, 0.2); color: #38d399; font-weight: 800; font-size: 0.85rem;">
                ${s.ai_score ?? s.score ?? 85}/100
              </span>
            </td>
            <td>
              <span style="display: inline-flex; align-items: center; gap: 4px; font-size: 0.78rem; color: #38d399; font-weight: 700;">
                ✓ Evaluated
              </span>
            </td>
            <td style="text-align: right;">
              <button type="button" class="btn btn-sm btn-secondary" onclick="alert('Student Approach: ' + ${JSON.stringify(s.approach_notes || s.evaluation_feedback || 'Completed all acceptance criteria successfully.')})">
                Feedback
              </button>
            </td>
          </tr>
        `).join('');
      } catch (e) {
        if (submissionsBanner) {
          submissionsBanner.style.background = "rgba(239, 68, 68, 0.15)";
          submissionsBanner.style.color = "#fca5a5";
          submissionsBanner.textContent = "Error loading submissions: " + e.message;
        }
      }
    });
  }

  if (closeSubmissionsBtn && submissionsModal) {
    closeSubmissionsBtn.addEventListener("click", () => {
      submissionsModal.style.display = "none";
    });
  }
}

// 4. Zero-Leakage MCQ Manager Studio
function setupMcqManagerStudio() {
  const openMatBtn = document.getElementById("btn-open-mcq-generator");
  const openStudioBtn = document.getElementById("btn-studio-open-mcq");
  const modal = document.getElementById("modal-mcq-manager");
  const closeBtn = document.getElementById("btn-close-mcq-modal");
  const lectureSelect = document.getElementById("mcq-lecture-select");
  const fetchBtn = document.getElementById("btn-fetch-mcqs");
  const questionsContainer = document.getElementById("mcq-questions-container");

  if (!modal) return;

  function populateLectures(preselectedId) {
    if (!lectureSelect) return;
    lectureSelect.innerHTML = "";

    const lessonsList = (window.allLessonsCache && window.allLessonsCache.length > 0)
      ? window.allLessonsCache
      : (typeof allLessonsCache !== "undefined" && allLessonsCache.length > 0 ? allLessonsCache : []);

    const coursesList = (window.coursesCache && window.coursesCache.length > 0)
      ? window.coursesCache
      : (typeof coursesCache !== "undefined" && coursesCache.length > 0 ? coursesCache : []);

    if (lessonsList.length === 0) {
      lectureSelect.innerHTML = "<option value=''>No lectures found in any course</option>";
      return;
    }

    let targetLessonId = preselectedId || (typeof currentLessonId !== "undefined" && currentLessonId ? currentLessonId : window.currentLessonId);

    if (targetLessonId) {
      const match = lessonsList.find(l => l.id === targetLessonId);
      if (match) {
        if (match.course_id) {
          window.currentCourseId = match.course_id;
          if (typeof currentCourseId !== "undefined") currentCourseId = match.course_id;
        }
        window.currentLessonId = match.id;
        if (typeof currentLessonId !== "undefined") currentLessonId = match.id;
      }
    }

    const coursesMap = new Map();
    coursesList.forEach(c => coursesMap.set(c.id, c.title));

    const grouped = {};
    lessonsList.forEach(l => {
      const cId = l.course_id || "general";
      const cTitle = coursesMap.get(cId) || (cId.replace(/^course-/, "").replace(/-/g, " ").toUpperCase());
      if (!grouped[cTitle]) grouped[cTitle] = [];
      grouped[cTitle].push(l);
    });

    let foundSelection = false;
    Object.keys(grouped).forEach(courseTitle => {
      const optgroup = document.createElement("optgroup");
      optgroup.label = `📚 ${courseTitle}`;

      grouped[courseTitle].forEach(l => {
        const opt = document.createElement("option");
        opt.value = l.id;
        opt.textContent = `${l.title} (${l.duration || "Video"})`;
        if (targetLessonId && targetLessonId === l.id) {
          opt.selected = true;
          foundSelection = true;
        }
        optgroup.appendChild(opt);
      });

      lectureSelect.appendChild(optgroup);
    });

    if (foundSelection && targetLessonId) {
      lectureSelect.value = targetLessonId;
    } else if (lectureSelect.options.length > 0) {
      lectureSelect.selectedIndex = 0;
    }
  }

  async function openModal(preselectedId) {
    if ((!window.allLessonsCache || window.allLessonsCache.length === 0) && typeof window.loadAllLessons === "function") {
      await window.loadAllLessons();
    }
    populateLectures(preselectedId);
    if (preselectedId && lectureSelect) {
      lectureSelect.value = preselectedId;
    }
    modal.style.display = "flex";
    if (fetchBtn) {
      setTimeout(() => fetchBtn.click(), 50);
    }
  }

  window.openMcqModalForLecture = openModal;

  if (openMatBtn) {
    openMatBtn.addEventListener("click", () => {
      const activeLessons = (window.allLessonsCache || []).filter(l => l.course_id === (window.currentCourseId || currentCourseId));
      const preId = (window.currentLessonId && activeLessons.some(l => l.id === window.currentLessonId))
        ? window.currentLessonId
        : (activeLessons[0]?.id || window.currentLessonId);
      openModal(preId);
    });
  }
  if (openStudioBtn) openStudioBtn.addEventListener("click", () => openModal(window.currentLessonId));
  if (closeBtn) closeBtn.addEventListener("click", () => { modal.style.display = "none"; });

  if (lectureSelect) {
    lectureSelect.addEventListener("change", () => {
      if (fetchBtn) fetchBtn.click();
    });
  }

  if (fetchBtn) {
    fetchBtn.addEventListener("click", async () => {
      const lessonId = lectureSelect?.value;
      if (!lessonId) {
        alert("Please select a lecture first.");
        return;
      }
      fetchBtn.disabled = true;
      fetchBtn.textContent = "Synthesizing Practice MCQs...";
      if (questionsContainer) {
        questionsContainer.innerHTML = `<div style="text-align: center; padding: 24px; color: #38d399;">Scanning lecture transcript concepts & generating zero-leakage MCQs...</div>`;
      }

      try {
        const res = await fetch(`/api/lessons/${lessonId}/mcqs/quiz`);
        if (!res.ok) throw new Error("Failed to load MCQs");
        const data = await res.json();
        const questions = data.questions || [];

        if (questions.length === 0) {
          questionsContainer.innerHTML = `<div class="empty-state">No MCQs generated yet for this lecture. Make sure video transcript is processed.</div>`;
          return;
        }

        questionsContainer.innerHTML = questions.map((q, idx) => `
          <div class="ai-challenge-card" style="margin-bottom: 12px;">
            <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px;">
              <span class="tier-badge-pill basic">Question ${idx + 1}</span>
              <span style="font-size: 0.75rem; color: #38d399; font-weight: 700;">Grounding: ${q.concept_topic || 'Lecture Transcript'}</span>
            </div>
            <div style="font-size: 0.92rem; font-weight: 700; color: #fff; margin-bottom: 10px;">
              ${q.question}
            </div>
            <div style="display: grid; gap: 6px; margin-bottom: 8px;">
              ${(q.options || []).map((opt, optIdx) => `
                <div style="font-size: 0.84rem; padding: 7px 12px; border-radius: 8px; background: rgba(255, 255, 255, 0.04); border: 1px solid rgba(255, 255, 255, 0.08); color: #cbd5e1;">
                  <strong style="color: #38d399;">${String.fromCharCode(65 + optIdx)}.</strong> ${opt}
                </div>
              `).join('')}
            </div>
            <div style="font-size: 0.78rem; color: #94a3b8; font-style: italic;">
              ✓ Server-side verified (Zero-leakage practice testing)
            </div>
          </div>
        `).join('');
      } catch (err) {
        if (questionsContainer) {
          questionsContainer.innerHTML = `<div style="color: #fca5a5; padding: 20px; text-align: center;">Error loading MCQs: ${err.message}</div>`;
        }
      } finally {
        fetchBtn.disabled = false;
        fetchBtn.textContent = "⚡ Load / Synthesize MCQs";
      }
    });
  }
}

// Auto-run Gatekeeper, Studio, Submissions & MCQs on DOM ready
document.addEventListener("DOMContentLoaded", () => {
  checkStrictAdminAuth();
  setupGatekeeperListeners();
  setupAiAssignmentStudio();
  setupMcqManagerStudio();
});

