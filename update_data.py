#!/usr/bin/env python3
"""每日自动更新：更新 Stars/版本 + 随机新增 3-5 个候选项目 + 自动翻译中文简介 + 记录日志 + 生成 sitemap"""
import json, os, random, re, time, requests
from datetime import datetime, timedelta

DATA_PATH = 'assets/js/data.json'
SITEMAP_PATH = 'sitemap.xml'
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN', '')
HEADERS = {'Accept': 'application/vnd.github.v3+json'}
if GITHUB_TOKEN:
    HEADERS['Authorization'] = f'token {GITHUB_TOKEN}'

# 自动翻译
try:
    from deep_translator import GoogleTranslator
    TRANSLATOR_AVAILABLE = True
except ImportError:
    TRANSLATOR_AVAILABLE = False

def load_data():
    with open(DATA_PATH, 'r', encoding='utf-8') as f: return json.load(f)

def save_data(data):
    with open(DATA_PATH, 'w', encoding='utf-8') as f: json.dump(data, f, ensure_ascii=False, indent=2)

def translate(text):
    """自动翻译英文到中文，失败时返回原文"""
    if not text or len(text) < 10: return text
    try:
        if TRANSLATOR_AVAILABLE:
            return GoogleTranslator(source='en', target='zh-CN').translate(text[:500])
    except:
        pass
    return text

def get_repo_info(github_url):
    match = re.search(r'github\.com/([^/]+)/([^/]+?)(?:\.git)?$', github_url)
    if not match: return None, None, None, None
    owner, repo = match.groups()
    try:
        resp = requests.get(f'https://api.github.com/repos/{owner}/{repo}', headers=HEADERS, timeout=15)
        if resp.status_code == 403: time.sleep(2); return None, None, None, None
        if resp.status_code != 200: return None, None, None, None
        d = resp.json()
        return d.get('stargazers_count', 0), (d.get('latest_release') or {}).get('tag_name', ''), (d.get('license') or {}).get('spdx_id', ''), d.get('description', '')
    except:
        return None, None, None, None

def update_existing_projects(data):
    today_str = datetime.now().strftime('%Y-%m-%d')
    cutoff = (datetime.now() - timedelta(days=14)).strftime('%Y-%m-%d')
    updated = 0
    for project in data['projects']:
        stars, version, lic, desc = get_repo_info(project['github_url'])
        if stars is not None:
            if 'stars_history' not in project: project['stars_history'] = {}
            project['stars_history'][today_str] = stars
            project['stars_history'] = {k: v for k, v in project['stars_history'].items() if k >= cutoff}
            project['stars'] = stars; project['last_updated'] = today_str; updated += 1
        if version: project['version'] = version
        if lic and not project.get('license'): project['license'] = lic
        # 如果中文简介太短，尝试用 GitHub 最新描述翻译补充
        if desc and (not project.get('description_zh') or len(project['description_zh']) < 30):
            project['description_en'] = desc
            project['description_zh'] = translate(desc)
        time.sleep(1)
    print(f'✅ 已更新 {updated}/{len(data["projects"])} 个项目')
    return data

def add_new_projects(data, count=3):
    pending = data.get('pending_projects', [])
    if not pending: print('📭 候选池已空'); return data, []
    actual = min(count, len(pending))
    selected = random.sample(pending, actual)
    added, log_entries = 0, []
    today_str = datetime.now().strftime('%Y-%m-%d')
    for item in selected:
        stars, version, lic, github_desc = get_repo_info(item['github_url'])
        if stars is None: continue
        name = item['github_url'].rstrip('/').split('/')[-1]
        slug = re.sub(r'[^a-z0-9-]', '-', name.lower()).strip('-')
        # 英文简介：优先候选池预设，其次 GitHub API 返回的描述
        desc_en = item.get('description_en', '') or github_desc or ''
        # 中文简介：优先候选池预设，其次自动翻译英文
        desc_zh = item.get('description_zh', '')
        if (not desc_zh or len(desc_zh) < 30) and desc_en:
            desc_zh = translate(desc_en)
        if not desc_zh:
            desc_zh = f'{name} 是一个优秀的开源项目。'
        project = {
            'id': f'auto-{int(time.time())}-{random.randint(100,999)}',
            'name': name, 'slug': slug, 'category': item['category'], 'github_url': item['github_url'],
            'stars': stars, 'version': version or '', 'last_updated': today_str, 'stars_history': {today_str: stars},
            'description_zh': desc_zh, 'description_en': desc_en,
            'alternative_to': item['alternative_to'], 'tags': item.get('tags', []),
            'license': lic or item.get('license', ''), 'download_url': '', 'featured': False, 'date_added': today_str
        }
        data['projects'].append(project)
        pending.remove(item)
        log_entries.append(f"{today_str} 🆕 新增收录：{name}（⭐ {stars:,}）")
        added += 1
        print(f'  ➕ 新增: {name} (⭐ {stars})')
        time.sleep(1)
    data['pending_projects'] = pending
    # 版本更新日志
    for proj in data['projects']:
        if proj.get('last_updated') == today_str and proj.get('date_added') != today_str and proj.get('version'):
            log_entries.append(f"{today_str} 📦 {proj['name']} 更新至 {proj['version']}（⭐ {proj['stars']:,}）")
    if 'update_log' not in data['site']: data['site']['update_log'] = []
    data['site']['update_log'] = (log_entries + data['site']['update_log'])[:30]
    return data, added

def generate_sitemap(data):
    base_url = data['site']['url'].rstrip('/')
    today = datetime.now().strftime('%Y-%m-%d')
    urls = [
        {'loc': f'{base_url}/', 'priority': '1.0', 'changefreq': 'daily'},
        {'loc': f'{base_url}/about.html', 'priority': '0.6', 'changefreq': 'monthly'},
        {'loc': f'{base_url}/privacy.html', 'priority': '0.4', 'changefreq': 'monthly'},
        {'loc': f'{base_url}/category.html', 'priority': '0.8', 'changefreq': 'daily'},
    ]
    for cat in data.get('categories', []):
        urls.append({'loc': f'{base_url}/category.html?id={cat["id"]}', 'priority': '0.7', 'changefreq': 'daily'})
    for proj in data.get('projects', []):
        urls.append({'loc': f'{base_url}/detail.html?id={proj["slug"]}', 'priority': '0.6', 'changefreq': 'weekly', 'lastmod': proj.get('last_updated', today)})
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    for u in urls:
        xml += '  <url>\n'
        xml += f'    <loc>{u["loc"]}</loc>\n'
        if 'lastmod' in u: xml += f'    <lastmod>{u["lastmod"]}</lastmod>\n'
        xml += f'    <changefreq>{u["changefreq"]}</changefreq>\n'
        xml += f'    <priority>{u["priority"]}</priority>\n'
        xml += '  </url>\n'
    xml += '</urlset>'
    with open(SITEMAP_PATH, 'w', encoding='utf-8') as f: f.write(xml)
    print(f'✅ sitemap.xml 已生成，{len(urls)} 个页面')

def main():
    print(f'🚀 开始每日更新 - {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    data = load_data()
    data = update_existing_projects(data)
    new_count = random.randint(3, 5)
    data, added = add_new_projects(data, new_count)
    save_data(data)
    generate_sitemap(data)
    print(f'✅ 完成：新增 {added} 个，总计 {len(data["projects"])} 个项目')

if __name__ == '__main__':
    main()
