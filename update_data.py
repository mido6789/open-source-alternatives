#!/usr/bin/env python3
"""
每日自动更新脚本
功能：
1. 更新 Stars/版本 + 自动翻译 + 时间线带简介
2. 自动新增 3-5 个候选项目
3. 🆕 自动生成静态HTML项目页面，提升SEO
"""
import json, os, random, re, time, base64
from datetime import datetime, timedelta
import urllib.request
import urllib.error
import urllib.parse

DATA_PATH = 'assets/js/data.json'
SITEMAP_PATH = 'sitemap.xml'
PROJECTS_DIR = 'projects'
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN', '')

# ========== 工具函数 ==========
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

def translate(text):
    if not text or len(text) < 10: return text
    try:
        url = "https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=zh-CN&dt=t&q=" + urllib.parse.quote(text[:500])
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read().decode())
            return ''.join([s[0] for s in result[0] if s[0]])
    except:
        return text

def get_repo_info(github_url):
    match = re.search(r'github\.com/([^/]+)/([^/]+?)(?:\.git)?$', github_url)
    if not match: return None, None, None, None
    owner, repo = match.groups()
    url = f'https://api.github.com/repos/{owner}/{repo}'
    headers = {'Accept': 'application/vnd.github.v3+json', 'User-Agent': 'Python'}
    if GITHUB_TOKEN:
        headers['Authorization'] = f'token {GITHUB_TOKEN}'
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            d = json.loads(resp.read().decode())
        version = (d.get('latest_release') or {}).get('tag_name', '')
        lic = (d.get('license') or {}).get('spdx_id', '')
        desc = d.get('description', '')
        if not desc or len(desc) < 80:
            try:
                readme_url = f'https://api.github.com/repos/{owner}/{repo}/readme'
                readme_req = urllib.request.Request(readme_url, headers=headers)
                with urllib.request.urlopen(readme_req, timeout=10) as rr:
                    readme_content = base64.b64decode(json.loads(rr.read().decode())['content']).decode('utf-8', errors='ignore')
                    desc = strip_html(readme_content)[:500]
            except:
                pass
        desc = strip_html(desc) if desc else desc
        return d.get('stargazers_count', 0), version, lic, desc
    except urllib.error.HTTPError as e:
        if e.code == 403: time.sleep(2)
        return None, None, None, None
    except:
        return None, None, None, None

def load_data():
    with open(DATA_PATH, 'r', encoding='utf-8') as f: return json.load(f)

def save_data(data):
    with open(DATA_PATH, 'w', encoding='utf-8') as f: json.dump(data, f, ensure_ascii=False, indent=2)

# ========== 核心更新逻辑 ==========
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
        desc_en = item.get('description_en', '') or github_desc or ''
        desc_en = strip_html(desc_en)
        desc_zh = item.get('description_zh', '')
        if (not desc_zh or len(desc_zh) < 30) and desc_en:
            desc_zh = translate(desc_en)
        if not desc_zh:
            desc_zh = f'{name} 是一个优秀的开源项目。'
        short_desc = desc_zh[:80] + '...' if len(desc_zh) > 80 else desc_zh
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
        log_entries.append(f"{today_str} 🆕 新增：{name}（⭐ {stars:,}）| {short_desc}")
        added += 1
        print(f'  ➕ 新增: {name} (⭐ {stars})')
        time.sleep(1)
    data['pending_projects'] = pending
    for proj in data['projects']:
        if proj.get('last_updated') == today_str and proj.get('date_added') != today_str and proj.get('version'):
            desc = proj.get('description_zh', '')
            short = desc[:80] + '...' if len(desc) > 80 else desc
            log_entries.append(f"{today_str} 📦 {proj['name']} 更新至 {proj['version']}（⭐ {proj['stars']:,}）| {short}")
    if 'update_log' not in data['site']: data['site']['update_log'] = []
    data['site']['update_log'] = (log_entries + data['site']['update_log'])[:30]
    return data, added

# ========== Sitemap 生成 ==========
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
        urls.append({'loc': f'{base_url}/projects/{proj["slug"]}.html', 'priority': '0.6', 'changefreq': 'weekly', 'lastmod': proj.get('last_updated', today)})
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

# ========== 🆕 静态HTML生成 ==========
def generate_static_project_pages(data):
    print("⏳ 正在生成项目静态页面...")
    if not os.path.exists(PROJECTS_DIR):
        os.makedirs(PROJECTS_DIR)
    
    base_url = data['site']['url'].rstrip('/')
    generated = 0
    for proj in data['projects']:
        slug = proj['slug']
        category = next((c for c in data['categories'] if c['id'] == proj['category']), None)
        cat_name = category['name'] if category else proj['category']
        cat_icon = category['icon'] if category else ''
        
        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{proj['name']} - 开源替代 {proj.get('alternative_to', '')} | 开源替代</title>
  <meta name="description" content="{proj.get('description_zh', '')[:150]}">
  <link rel="canonical" href="{base_url}/projects/{slug}.html">
  <meta property="og:title" content="{proj['name']} - 开源替代 {proj.get('alternative_to', '')}">
  <meta property="og:description" content="{proj.get('description_zh', '')[:150]}">
  <meta property="og:type" content="article">
  <meta property="og:url" content="{base_url}/projects/{slug}.html">
  <link rel="stylesheet" href="/assets/css/style.css">
  <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>🔄</text></svg>">
</head>
<body>
  <nav class="navbar">
    <div class="navbar-inner">
      <a href="/" class="logo">🔄 开源替代</a>
      <ul class="nav-links">
        <li><a href="/">首页</a></li>
        <li><a href="/category.html?id=ai-agent">AI & Agent</a></li>
        <li><a href="/category.html?id=design-tools">设计工具</a></li>
        <li><a href="/category.html?id=dev-tools">开发工具</a></li>
        <li><a href="/about.html">关于我们</a></li>
      </ul>
    </div>
  </nav>
  <main class="container">
    <div class="detail-header">
      <span class="category-tag">{cat_icon} {cat_name}</span>
      <h1>{proj['name']}</h1>
      <div class="detail-meta">
        <span>⭐ {proj['stars']:,} Stars</span>
        <span>📜 {proj.get('license', 'N/A')}</span>
        <span class="alt-badge">替代: {proj.get('alternative_to', '')}</span>
      </div>
    </div>
    <div class="detail-content">
      <h2>📖 项目简介</h2>
      <p>{proj.get('description_zh', '暂无介绍')}</p>
      
      <h2>🔗 GitHub 项目地址</h2>
      <p><a href="{proj['github_url']}" target="_blank">{proj['github_url']}</a></p>
      
      <h2>🔄 可替代的商用软件</h2>
      <p>{proj.get('alternative_to', '')}</p>
      
      <h2>📝 项目原文介绍（英文）</h2>
      <p>{proj.get('description_en', 'No description available.')}</p>
      
      <div class="disclaimer-box">
        ⚠️ <strong>免责声明：</strong>本文内容整理自 GitHub 开源社区，旨在分享和介绍优秀的开源替代方案。
      </div>
    </div>
  </main>
  <footer class="footer">
    <div class="footer-bottom">
      <p>© {datetime.now().year} 开源替代 - 尊重开源，分享价值</p>
    </div>
  </footer>
</body>
</html>"""
        
        with open(f'{PROJECTS_DIR}/{slug}.html', 'w', encoding='utf-8') as f:
            f.write(html)
        generated += 1
    
    print(f"✅ 已生成 {generated} 个项目静态页面")

def generate_static_homepage(data):
    """生成简化版静态首页，供搜索引擎抓取"""
    print("⏳ 正在生成静态首页...")
    base_url = data['site']['url'].rstrip('/')
    
    # 按 Stars 排序取前 30 个项目
    top_projects = sorted(data['projects'], key=lambda p: p['stars'], reverse=True)[:30]
    
    projects_html = ''
    for proj in top_projects:
        category = next((c for c in data['categories'] if c['id'] == proj['category']), None)
        cat_name = category['name'] if category else proj['category']
        projects_html += f"""
      <div class="project-card">
        <span class="category-tag">{cat_name}</span>
        <h3><a href="/projects/{proj['slug']}.html">{proj['name']}</a></h3>
        <p class="description">{proj.get('description_zh', '')[:120]}</p>
        <div class="meta">
          <span>⭐ {proj['stars']:,}</span>
          <span class="alt-badge">替代: {proj.get('alternative_to', '')}</span>
        </div>
      </div>"""
    
    categories_html = ''
    for cat in data['categories']:
        count = len([p for p in data['projects'] if p['category'] == cat['id']])
        categories_html += f'<a href="/category.html?id={cat["id"]}" class="category-card"><span class="icon">{cat["icon"]}</span><span class="name">{cat["name"]}</span><span class="count">{count}个项目</span></a>\n'
    
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>开源替代 - 发现优秀的开源替代方案</title>
  <meta name="description" content="发现优秀的开源替代方案，告别高价付费软件。收录AI、设计工具、办公效率、开发工具等7大类{len(data['projects'])}个开源替代品。每日更新。">
  <link rel="canonical" href="{base_url}/">
  <link rel="stylesheet" href="/assets/css/style.css">
  <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>🔄</text></svg>">
</head>
<body>
  <nav class="navbar">
    <div class="navbar-inner">
      <a href="/" class="logo">🔄 开源替代</a>
      <ul class="nav-links">
        <li><a href="/">首页</a></li>
        <li><a href="/category.html?id=ai-agent">AI & Agent</a></li>
        <li><a href="/category.html?id=design-tools">设计工具</a></li>
        <li><a href="/category.html?id=dev-tools">开发工具</a></li>
        <li><a href="/about.html">关于我们</a></li>
      </ul>
    </div>
  </nav>
  <main class="container">
    <section class="hero">
      <h1>发现优秀的开源替代方案</h1>
      <p>告别高价付费软件，探索自由开源的无限可能。我们每日追踪 GitHub 上最受欢迎的开源项目，帮你找到最合适的替代品。目前已收录 <strong>{len(data['projects'])}</strong> 个开源项目。</p>
    </section>

    <section>
      <h2 class="section-title">📂 浏览分类</h2>
      <div class="categories-grid">
        {categories_html}
      </div>
    </section>

    <section>
      <h2 class="section-title">⭐ 热门开源项目</h2>
      <div class="projects-grid">
        {projects_html}
      </div>
    </section>
  </main>
  <footer class="footer">
    <div class="footer-bottom">
      <p>© {datetime.now().year} 开源替代 - 尊重开源，分享价值</p>
    </div>
  </footer>
</body>
</html>"""
    
    with open('index.html', 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"✅ 静态首页已生成（包含 {len(top_projects)} 个热门项目）")

# ========== 主流程 ==========
def main():
    print(f'🚀 开始每日更新 - {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    data = load_data()
    data = update_existing_projects(data)
    new_count = random.randint(3, 5)
    data, added = add_new_projects(data, new_count)
    save_data(data)
    generate_sitemap(data)
    generate_static_project_pages(data)
    generate_static_homepage(data)
    print(f'✅ 完成：新增 {added} 个，总计 {len(data["projects"])} 个项目')

if __name__ == '__main__':
    main()
