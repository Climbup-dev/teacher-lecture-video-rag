// Students Tab Controller - Simple Student Enrollment & Progress Roster
import { api } from "../api.js";
import { appState } from "../state.js";

export function initStudentsTab() {
  const studentsTableBody = document.getElementById("students-roster-body");
  const courseFilterSelect = document.getElementById("filter-student-course");
  const studentSearchInput = document.getElementById("search-student");
  const badgeStudentsCount = document.getElementById("tab-students-count");
  const kpiStudentsCount = document.getElementById("kpi-total-students");
  const kpiActiveLearners = document.getElementById("kpi-active-learners");
  
  // Modal Elements
  const modalEnroll = document.getElementById("modal-enroll-student");
  const btnShowEnroll = document.getElementById("btn-show-enroll-student");
  const btnCloseEnroll = document.getElementById("btn-close-enroll");
  const btnCancelEnroll = document.getElementById("btn-cancel-enroll");
  const enrollForm = document.getElementById("enroll-student-form");
  const enrollCourseSelect = document.getElementById("enroll-student-course");

  let allStudents = [];

  async function loadStudents() {
    try {
      const selectedCourse = courseFilterSelect ? courseFilterSelect.value : "";
      const students = await api.getStudents(selectedCourse || null);
      allStudents = students || [];

      // Update counters
      const count = allStudents.length;
      if (badgeStudentsCount) badgeStudentsCount.textContent = count;
      if (kpiStudentsCount) kpiStudentsCount.textContent = count;
      if (kpiActiveLearners) kpiActiveLearners.textContent = Math.max(1, Math.round(count * 0.8));

      renderStudents();
    } catch (err) {
      console.warn("Could not load students:", err);
      if (studentsTableBody) {
        studentsTableBody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--text-muted); padding: 32px;">Could not load students roster.</td></tr>`;
      }
    }
  }

  function renderStudents() {
    if (!studentsTableBody) return;
    const query = (studentSearchInput?.value || "").toLowerCase().trim();

    const filtered = allStudents.filter(s => {
      const name = (s.name || "").toLowerCase();
      const email = (s.email || "").toLowerCase();
      const course = (s.course_id || "").toLowerCase();
      return name.includes(query) || email.includes(query) || course.includes(query);
    });

    if (filtered.length === 0) {
      studentsTableBody.innerHTML = `
        <tr>
          <td colspan="6" style="text-align: center; color: var(--text-muted); padding: 36px;">
            No students found. Click <strong>+ Enroll Student</strong> to add one.
          </td>
        </tr>
      `;
      return;
    }

    studentsTableBody.innerHTML = filtered.map(s => {
      const progress = s.progress !== undefined ? s.progress : 45;
      const doubts = s.doubts_count !== undefined ? s.doubts_count : 3;
      const enrolledDate = s.enrolled_date || "2026-10-18";
      const initial = (s.name || "S").charAt(0).toUpperCase();

      return `
        <tr data-student-id="${s.id}">
          <td>
            <div style="display: flex; align-items: center; gap: 10px;">
              <div style="width: 34px; height: 34px; border-radius: 8px; background: linear-gradient(135deg, #6366f1, #a855f7); color: white; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 14px;">
                ${initial}
              </div>
              <div>
                <div style="font-weight: 600; color: var(--text-main); font-size: 0.9rem;">${escapeHtml(s.name)}</div>
                <div style="font-size: 0.78rem; color: var(--text-muted);">${escapeHtml(s.email)}</div>
              </div>
            </div>
          </td>
          <td>
            <span class="badge-mini" style="background: rgba(99, 102, 241, 0.15); color: #818cf8;">
              ${escapeHtml(s.course_id || "General")}
            </span>
          </td>
          <td style="color: var(--text-muted); font-size: 0.85rem;">${enrolledDate}</td>
          <td style="min-width: 140px;">
            <div style="display: flex; align-items: center; gap: 8px;">
              <div style="flex: 1; height: 6px; background: rgba(255,255,255,0.08); border-radius: 4px; overflow: hidden;">
                <div style="width: ${progress}%; height: 100%; background: linear-gradient(90deg, #6366f1, #10b981); border-radius: 4px;"></div>
              </div>
              <span style="font-size: 0.78rem; font-weight: 600; color: #10b981;">${progress}%</span>
            </div>
          </td>
          <td>
            <span style="display: inline-flex; align-items: center; gap: 4px; font-size: 0.82rem; font-weight: 600; color: #a855f7;">
              💬 ${doubts} doubts
            </span>
          </td>
          <td style="text-align: right;">
            <button class="btn btn-sm btn-icon btn-delete-student" data-id="${s.id}" title="Remove Student" style="color: #f43f5e;">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
            </button>
          </td>
        </tr>
      `;
    }).join("");

    // Attach delete listeners
    studentsTableBody.querySelectorAll(".btn-delete-student").forEach(btn => {
      btn.addEventListener("click", async () => {
        const studentId = btn.dataset.id;
        if (!confirm("Are you sure you want to remove this student?")) return;
        try {
          await api.deleteStudent(studentId);
          await loadStudents();
        } catch (err) {
          alert("Failed to remove student: " + err.message);
        }
      });
    });
  }

  function syncCourseDropdowns(courses) {
    if (courseFilterSelect) {
      const current = courseFilterSelect.value;
      courseFilterSelect.innerHTML = `<option value="">All Courses</option>`;
      courses.forEach(c => {
        const opt = document.createElement("option");
        opt.value = c.id;
        opt.textContent = c.title;
        courseFilterSelect.appendChild(opt);
      });
      courseFilterSelect.value = current;
    }

    if (enrollCourseSelect) {
      enrollCourseSelect.innerHTML = "";
      courses.forEach(c => {
        const opt = document.createElement("option");
        opt.value = c.id;
        opt.textContent = c.title;
        enrollCourseSelect.appendChild(opt);
      });
    }
  }

  function escapeHtml(str) {
    if (!str) return "";
    return String(str).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  // Event Listeners
  if (courseFilterSelect) {
    courseFilterSelect.addEventListener("change", loadStudents);
  }

  if (studentSearchInput) {
    studentSearchInput.addEventListener("input", renderStudents);
  }

  if (btnShowEnroll && modalEnroll) {
    btnShowEnroll.addEventListener("click", () => {
      modalEnroll.style.display = "flex";
    });
  }
  if (btnCloseEnroll && modalEnroll) {
    btnCloseEnroll.addEventListener("click", () => {
      modalEnroll.style.display = "none";
    });
  }
  if (btnCancelEnroll && modalEnroll) {
    btnCancelEnroll.addEventListener("click", () => {
      modalEnroll.style.display = "none";
    });
  }

  if (enrollForm) {
    enrollForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const name = document.getElementById("enroll-name")?.value?.trim();
      const email = document.getElementById("enroll-email")?.value?.trim();
      const courseId = enrollCourseSelect?.value || "course-applied-ai-rag";

      if (!name || !email) {
        alert("Please provide both name and email.");
        return;
      }

      try {
        await api.enrollStudent({ name, email, course_id: courseId });
        if (modalEnroll) modalEnroll.style.display = "none";
        enrollForm.reset();
        await loadStudents();
      } catch (err) {
        alert("Enrollment failed: " + err.message);
      }
    });
  }

  appState.subscribe("courses", syncCourseDropdowns);

  // Initial load
  loadStudents();
}
