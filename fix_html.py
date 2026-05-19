import json, re

with open('assets/js/data.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

def strip_html(text):
    if not text: return text
    clean = re.sub(r'<[^>]+>', ' ', text)
    clean = re.sub(r'\[!\[.*?\]\(.*?\)\]\(.*?\)', ' ', clean)
    clean = re.sub(r'!\[.*?\]\(.*?\)', ' ', clean)
    clean = re.sub(r'\[([^\]]*)\]\([^)]+\)', r'\1', clean)
    clean = re.sub(r'^#{1,6}\s*', '', clean, flags=re.MULTILINE)
    clean = re.sub(r'[-=*]{3,}', ' ', clean)
    clean = re.sub(r'[`*_~>|]', ' ', clean)
    clean = re.sub(r'\s+', ' ', clean).strip()
    return clean

fixed = 0
for proj in data['projects']:
    old_zh = proj.get('description_zh', '')
    old_en = proj.get('description_en', '')
    new_zh = strip_html(old_zh)
    new_en = strip_html(old_en)
    if new_zh != old_zh or new_en != old_en:
        proj['description_zh'] = new_zh
        proj['description_en'] = new_en
        fixed += 1
        print(f'修复: {proj["name"]}')

with open('assets/js/data.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(f'\n共修复 {fixed} 个项目')
