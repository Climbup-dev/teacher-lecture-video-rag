import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")

headers = {
    "apikey": key,
    "Authorization": f"Bearer {key}",
    "Content-Type": "application/json"
}

# 1. Fetch courses
res_courses = requests.get(f"{url}/rest/v1/courses?select=*", headers=headers)
courses = res_courses.json() if res_courses.ok else []

# 2. Fetch course_lessons
res_lessons = requests.get(f"{url}/rest/v1/course_lessons?select=*", headers=headers)
lessons = res_lessons.json() if res_lessons.ok else []

# 3. Read current local_store.json
store_file = "data/chunks/local_store.json"
try:
    with open(store_file, "r", encoding="utf-8") as f:
        store = json.load(f)
except Exception:
    store = {"courses": {}, "lessons": {}, "chunks": [], "jobs": {}}

if "courses" not in store:
    store["courses"] = {}
if "lessons" not in store:
    store["lessons"] = {}

for c in courses:
    cid = c.get("id")
    if cid:
        store["courses"][cid] = c

for l in lessons:
    lid = l.get("id")
    if lid:
        store["lessons"][lid] = l

with open(store_file, "w", encoding="utf-8") as f:
    json.dump(store, f, indent=2)

print(f"Successfully synced {len(courses)} courses and {len(lessons)} lessons into {store_file}!")
