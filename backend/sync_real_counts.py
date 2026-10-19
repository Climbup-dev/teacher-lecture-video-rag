import requests, json
from backend.config import Config

url = Config.SUPABASE_URL
key = Config.SUPABASE_KEY
headers = {
    'apikey': key,
    'Authorization': f'Bearer {key}',
    'Content-Type': 'application/json'
}

# Fetch all real lessons from course_lessons
res_lessons = requests.get(f'{url}/rest/v1/course_lessons?select=id,course_id', headers=headers)
lessons = res_lessons.json() if res_lessons.ok else []
counts = {}
for l in lessons:
    cid = l.get('course_id')
    if cid:
        counts[cid] = counts.get(cid, 0) + 1

print('Real lesson counts per course:', counts)

# Fetch all courses
res_courses = requests.get(f'{url}/rest/v1/courses?select=id,title,total_lessons', headers=headers)
courses = res_courses.json() if res_courses.ok else []

for c in courses:
    cid = c['id']
    real_count = counts.get(cid, 0)
    title = c.get('title', '')
    prev = c.get('total_lessons', 0)
    print(f'Updating course {cid} ({title}): {prev} -> {real_count}')
    requests.patch(
        f'{url}/rest/v1/courses?id=eq.{cid}',
        headers=headers,
        json={'total_lessons': real_count}
    )

# Also update local_store.json
store_path = 'data/chunks/local_store.json'
with open(store_path, 'r', encoding='utf-8') as f:
    store = json.load(f)

for cid, c in store.get('courses', {}).items():
    real_count = counts.get(cid, 0)
    c['total_lessons'] = real_count

with open(store_path, 'w', encoding='utf-8') as f:
    json.dump(store, f, indent=2)

print('Successfully updated all courses to real lecture counts!')
