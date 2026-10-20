// EduRAG API Client
const API_BASE = (typeof window !== "undefined" && (window.location.port === "8000" || window.location.port === "8080"))
  ? ""
  : (typeof window !== "undefined" && (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1"))
    ? "http://127.0.0.1:8000"
    : "https://teacher-lecture-video-rag-28929614461.asia-south1.run.app";

async function parseResponse(res, defaultError = "Request failed") {
  if (!res.ok) {
    let msg = `${defaultError} (${res.status})`;
    try {
      const raw = await res.text();
      try {
        const json = JSON.parse(raw);
        msg = json.detail || json.message || json.error || msg;
      } catch {
        const titleMatch = raw.match(/<title>(.*?)<\/title>/i);
        if (titleMatch && titleMatch[1]) {
          msg = `${titleMatch[1].trim()} (HTTP ${res.status})`;
        } else {
          const text = raw.replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim();
          msg = text.slice(0, 200) || `HTTP ${res.status}`;
        }
      }
    } catch {}
    throw new Error(msg);
  }
  return res.json();
}

export const api = {
  // System Status
  async getStatus() {
    const res = await fetch(`${API_BASE}/api/status`);
    return parseResponse(res, "Failed to get system status");
  },

  // Courses
  async getCourses() {
    const res = await fetch(`${API_BASE}/api/courses`);
    return parseResponse(res, "Failed to load courses");
  },

  async createCourse(courseData) {
    const res = await fetch(`${API_BASE}/api/courses`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(courseData)
    });
    return parseResponse(res, "Failed to create course");
  },

  async deleteCourse(courseId) {
    const res = await fetch(`${API_BASE}/api/courses/${courseId}`, { method: "DELETE" });
    return parseResponse(res, "Failed to delete course");
  },

  // Lessons / Video Lectures
  async getLessons() {
    const res = await fetch(`${API_BASE}/api/lessons`);
    return parseResponse(res, "Failed to load lectures");
  },

  async getLesson(lessonId) {
    const res = await fetch(`${API_BASE}/api/lessons/${lessonId}`);
    return parseResponse(res, "Failed to load lecture details");
  },

  async deleteLesson(lessonId) {
    const res = await fetch(`${API_BASE}/api/lessons/${lessonId}`, { method: "DELETE" });
    return parseResponse(res, "Failed to delete lecture");
  },

  async processVideo(formData) {
    const res = await fetch(`${API_BASE}/api/process-video`, {
      method: "POST",
      body: formData
    });
    return parseResponse(res, "Video ingestion failed");
  },

  async getJob(jobId) {
    const res = await fetch(`${API_BASE}/api/jobs/${jobId}`);
    return parseResponse(res, "Failed to fetch job status");
  },

  async retryJob(jobId) {
    const res = await fetch(`${API_BASE}/api/jobs/${jobId}/retry`, { method: "POST" });
    return parseResponse(res, "Failed to retry job");
  },

  async cancelJob(jobId) {
    const res = await fetch(`${API_BASE}/api/jobs/${jobId}/cancel`, { method: "POST" });
    return parseResponse(res, "Failed to cancel job");
  },

  // Notes & Assignments
  async getCourseResources(courseId) {
    const res = await fetch(`${API_BASE}/api/courses/${courseId}/resources`);
    return parseResponse(res, "Failed to load course materials");
  },

  async uploadResource(formData) {
    const res = await fetch(`${API_BASE}/api/resources/upload`, {
      method: "POST",
      body: formData
    });
    return parseResponse(res, "Resource upload failed");
  },

  async deleteResource(resourceId) {
    const res = await fetch(`${API_BASE}/api/resources/${resourceId}`, { method: "DELETE" });
    return parseResponse(res, "Failed to delete resource");
  },

  // RAG Chat
  async sendChat(query, lessonId, sessionId = null) {
    const res = await fetch(`${API_BASE}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, lesson_id: lessonId, session_id: sessionId })
    });
    return parseResponse(res, "Chat request failed");
  },

  async clearChat(sessionId) {
    if (!sessionId) return;
    try {
      await fetch(`${API_BASE}/api/chat/clear`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId })
      });
    } catch {}
  },

  // Google Drive
  async getDriveFiles() {
    try {
      const res = await fetch(`${API_BASE}/api/drive/files`);
      if (!res.ok) return { configured: false, files: [] };
      return res.json();
    } catch {
      return { configured: false, files: [] };
    }
  },

  // Students
  async getStudents(courseId = null) {
    const url = courseId ? `${API_BASE}/api/students?course_id=${encodeURIComponent(courseId)}` : `${API_BASE}/api/students`;
    const res = await fetch(url);
    return parseResponse(res, "Failed to load students");
  },

  async enrollStudent(studentData) {
    const res = await fetch(`${API_BASE}/api/students`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(studentData)
    });
    return parseResponse(res, "Failed to enroll student");
  },

  async deleteStudent(studentId) {
    const res = await fetch(`${API_BASE}/api/students/${studentId}`, { method: "DELETE" });
    return parseResponse(res, "Failed to remove student");
  },

  // Settings
  async updateConfig(payload) {
    const res = await fetch(`${API_BASE}/api/update-config`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    return parseResponse(res, "Failed to update config");
  }
};
