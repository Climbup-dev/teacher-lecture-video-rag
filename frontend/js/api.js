// EduRAG API Client
const API_BASE = (typeof window !== "undefined" && (window.location.port === "8000" || window.location.port === "8080"))
  ? ""
  : (typeof window !== "undefined" && (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1"))
    ? "http://127.0.0.1:8000"
    : "https://teacher-lecture-video-rag-28929614461.asia-south1.run.app";

export const api = {
  // System Status
  async getStatus() {
    const res = await fetch(`${API_BASE}/api/status`);
    return res.json();
  },

  // Courses
  async getCourses() {
    const res = await fetch(`${API_BASE}/api/courses`);
    if (!res.ok) throw new Error("Failed to load courses");
    return res.json();
  },

  async createCourse(courseData) {
    const res = await fetch(`${API_BASE}/api/courses`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(courseData)
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Failed to create course");
    }
    return res.json();
  },

  async deleteCourse(courseId) {
    const res = await fetch(`${API_BASE}/api/courses/${courseId}`, { method: "DELETE" });
    if (!res.ok) throw new Error("Failed to delete course");
    return res.json();
  },

  // Lessons / Video Lectures
  async getLessons() {
    const res = await fetch(`${API_BASE}/api/lessons`);
    if (!res.ok) throw new Error("Failed to load lectures");
    return res.json();
  },

  async getLesson(lessonId) {
    const res = await fetch(`${API_BASE}/api/lessons/${lessonId}`);
    if (!res.ok) throw new Error("Failed to load lecture details");
    return res.json();
  },

  async deleteLesson(lessonId) {
    const res = await fetch(`${API_BASE}/api/lessons/${lessonId}`, { method: "DELETE" });
    if (!res.ok) throw new Error("Failed to delete lecture");
    return res.json();
  },

  async processVideo(formData) {
    const res = await fetch(`${API_BASE}/api/process-video`, {
      method: "POST",
      body: formData
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Video ingestion failed");
    }
    return res.json();
  },

  // Notes & Assignments
  async getCourseResources(courseId) {
    const res = await fetch(`${API_BASE}/api/courses/${courseId}/resources`);
    if (!res.ok) throw new Error("Failed to load course materials");
    return res.json();
  },

  async uploadResource(formData) {
    const res = await fetch(`${API_BASE}/api/resources/upload`, {
      method: "POST",
      body: formData
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Resource upload failed");
    }
    return res.json();
  },

  async deleteResource(resourceId) {
    const res = await fetch(`${API_BASE}/api/resources/${resourceId}`, { method: "DELETE" });
    if (!res.ok) throw new Error("Failed to delete resource");
    return res.json();
  },

  // RAG Chat
  async sendChat(query, lessonId) {
    const res = await fetch(`${API_BASE}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, lesson_id: lessonId })
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Chat request failed");
    }
    return res.json();
  },

  // Google Drive
  async getDriveFiles() {
    const res = await fetch(`${API_BASE}/api/drive/files`);
    if (!res.ok) return { configured: false, files: [] };
    return res.json();
  },

  // Students
  async getStudents(courseId = null) {
    const url = courseId ? `${API_BASE}/api/students?course_id=${encodeURIComponent(courseId)}` : `${API_BASE}/api/students`;
    const res = await fetch(url);
    if (!res.ok) throw new Error("Failed to load students");
    return res.json();
  },

  async enrollStudent(studentData) {
    const res = await fetch(`${API_BASE}/api/students`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(studentData)
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Failed to enroll student");
    }
    return res.json();
  },

  async deleteStudent(studentId) {
    const res = await fetch(`${API_BASE}/api/students/${studentId}`, { method: "DELETE" });
    if (!res.ok) throw new Error("Failed to remove student");
    return res.json();
  },

  // Settings
  async updateConfig(payload) {
    const res = await fetch(`${API_BASE}/api/update-config`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    if (!res.ok) throw new Error("Failed to update config");
    return res.json();
  }
};
