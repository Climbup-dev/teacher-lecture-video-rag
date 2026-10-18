// Central State Manager with Pub/Sub Event Bus
class StateStore {
  constructor() {
    this.state = {
      currentCourseId: "course-applied-ai-rag",
      currentLessonId: "masterclass_os_3hours",
      courses: [],
      lessons: [],
      materials: [],
      driveFiles: []
    };
    this.listeners = {};
  }

  get(key) {
    return this.state[key];
  }

  set(key, value) {
    const prev = this.state[key];
    this.state[key] = value;
    if (this.listeners[key]) {
      this.listeners[key].forEach(fn => fn(value, prev));
    }
  }

  subscribe(key, callback) {
    if (!this.listeners[key]) {
      this.listeners[key] = [];
    }
    this.listeners[key].push(callback);
    return () => {
      this.listeners[key] = this.listeners[key].filter(fn => fn !== callback);
    };
  }

  setActiveCourse(courseId) {
    this.set("currentCourseId", courseId);
  }

  setActiveLesson(lessonId) {
    this.set("currentLessonId", lessonId);
  }
}

export const appState = new StateStore();
