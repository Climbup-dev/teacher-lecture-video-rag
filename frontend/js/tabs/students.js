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

  function getUniqueStudents(list) {
    const map = new Map();
    (list || []).forEach(s => {
      const email = (s.email || "").toLowerCase().trim();
      const key = email || (s.user_id ? String(s.user_id) : (s.name ? s.name.toLowerCase().trim() : s.id));
      if (!map.has(key)) {
        map.set(key, {
          key: key,
          user_id: s.user_id,
          name: s.name || "Student",
          email: s.email || "student@university.edu",
          avatar_url: s.avatar_url || null,
          enrollments: []
        });
      }
      map.get(key).enrollments.push(s);
    });

    return Array.from(map.values()).map(student => {
      const count = student.enrollments.length;
      const totalProg = student.enrollments.reduce((sum, e) => sum + (parseInt(e.progress) || 0), 0);
      const avgProg = count > 0 ? Math.round(totalProg / count) : 0;
      const totalDoubts = student.enrollments.reduce((sum, e) => sum + (parseInt(e.doubts_count || e.doubts_asked) || 0), 0);
      const dates = student.enrollments.map(e => e.enrolled_date).filter(Boolean).sort();
      return {
        ...student,
        coursesCount: count,
        avgProgress: avgProg,
        totalDoubts: totalDoubts,
        enrolledDate: dates.length > 0 ? dates[0] : "2026-10-18",
        enrollmentIds: student.enrollments.map(e => e.id)
      };
    });
  }

  async function loadStudents() {
    try {
      const selectedCourse = courseFilterSelect ? courseFilterSelect.value : "";
      const students = await api.getStudents(selectedCourse || null);
      allStudents = students || [];

      // Update counters based on UNIQUE students
      const unique = getUniqueStudents(allStudents);
      const count = unique.length;
      if (badgeStudentsCount) badgeStudentsCount.textContent = count;
      if (kpiStudentsCount) kpiStudentsCount.textContent = count;
      if (kpiActiveLearners) kpiActiveLearners.textContent = Math.max(1, count);

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

    const uniqueStudents = getUniqueStudents(allStudents);

    const filtered = uniqueStudents.filter(s => {
      const name = (s.name || "").toLowerCase();
      const email = (s.email || "").toLowerCase();
      const matchesSearch = !query || name.includes(query) || email.includes(query) ||
        s.enrollments.some(e => (e.course_id || e.course_title || "").toLowerCase().includes(query));
      return matchesSearch;
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
      const initial = (s.name || "S").charAt(0).toUpperCase();

      return `
        <tr data-student-key="${s.key}">
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
            <div style="display: flex; flex-direction: column; gap: 6px; align-items: flex-start;">
              <span class="badge-mini" style="background: rgba(99, 102, 241, 0.2); color: #a5b4fc; font-weight: 700; border: 1px solid rgba(99, 102, 241, 0.4);">
                📚 ${s.coursesCount} ${s.coursesCount === 1 ? 'Course' : 'Courses'}
              </span>
              <div style="display: flex; flex-wrap: wrap; gap: 4px;">
                ${s.enrollments.map(e => `
                  <span class="badge-mini" style="background: rgba(99, 102, 241, 0.12); color: #c7d2fe;">
                    🎓 ${escapeHtml(e.course_title || e.course_id || "General")}
                  </span>
                `).join("")}
              </div>
            </div>
          </td>
          <td style="color: var(--text-muted); font-size: 0.85rem;">${s.enrolledDate}</td>
          <td style="min-width: 140px;">
            <div style="display: flex; align-items: center; gap: 8px;">
              <div style="flex: 1; height: 6px; background: rgba(255,255,255,0.08); border-radius: 4px; overflow: hidden;">
                <div style="width: ${s.avgProgress}%; height: 100%; background: linear-gradient(90deg, #6366f1, #10b981); border-radius: 4px;"></div>
              </div>
              <span style="font-size: 0.78rem; font-weight: 600; color: #10b981;">${s.avgProgress}%</span>
            </div>
          </td>
          <td>
            <span style="display: inline-flex; align-items: center; gap: 4px; font-size: 0.82rem; font-weight: 600; color: #a855f7;">
              💬 ${s.totalDoubts} doubts
            </span>
          </td>
          <td style="text-align: right;">
            <button class="btn btn-sm btn-icon btn-delete-student" data-student-key="${s.key}" title="Remove Student" style="color: #f43f5e;">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
            </button>
          </td>
        </tr>
      `;
    }).join("");

    // Attach delete listeners
    studentsTableBody.querySelectorAll(".btn-delete-student").forEach(btn => {
      btn.addEventListener("click", async () => {
        const studentKey = btn.dataset.studentKey;
        const targetStd = getUniqueStudents(allStudents).find(s => s.key === studentKey);
        const stdName = targetStd ? targetStd.name : "this student";
        if (!confirm(`Are you sure you want to remove ${stdName}?`)) return;
        try {
          if (targetStd && targetStd.enrollmentIds) {
            await Promise.all(targetStd.enrollmentIds.map(id => api.deleteStudent(id)));
          }
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
