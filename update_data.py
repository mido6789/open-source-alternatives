#!/usr/bin/env python3
"""
每日自动更新脚本 (增强版)
功能：
1. 更新 Stars/版本 + 自动翻译 + 时间线带简介
2. 自动新增 3-5 个候选项目
3. 增量生成语义化、SEO友好的静态HTML项目页面 + 静态首页
4. 抓取社区讨论 (Discussions) 丰富内容，段落式展示
5. 候选池自动补给 (低于20个时一次性追加20个新候选)
6. 🆕 向百度主动推送新增URL，加速收录
"""
import json, os, random, re, time, base64, hashlib
from datetime import datetime, timedelta
import urllib.request
import urllib.error
import urllib.parse

DATA_PATH = 'assets/js/data.json'
SITEMAP_PATH = 'sitemap.xml'
PROJECTS_DIR = 'projects'
PAGE_STATES_PATH = 'assets/js/page_states.json'
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN', '')
BAIDU_TOKEN = os.environ.get('BAIDU_PUSH_TOKEN', '')

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

def auto_refill_pending(data):
    pending = data.get('pending_projects', [])
    if len(pending) >= 20:
        return data
    
    print("⏳ 候选池不足20个，自动搜索补充...")
    headers = {'Accept': 'application/vnd.github.v3+json', 'User-Agent': 'Python'}
    if GITHUB_TOKEN:
        headers['Authorization'] = f'token {GITHUB_TOKEN}'
    
    queries = [
        "open source alternative to",
        "free self-hosted tool",
        "open source replacement for"
    ]
    
    new_candidates = []
    for query in queries:
        try:
            url = f"https://api.github.com/search/repositories?q={urllib.parse.quote(query)}&sort=stars&order=desc&per_page=10"
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                result = json.loads(resp.read().decode())
                for item in result.get('items', []):
                    repo_url = item['html_url']
                    if any(c['github_url'] == repo_url for c in pending) or \
                       any(c['github_url'] == repo_url for c in new_candidates):
                        continue
                    
                    if item['stargazers_count'] < 50:
                        continue
                    
                    description = item.get('description', '') or ''
                    category = 'dev-tools'
                    if any(kw in description.lower() for kw in ['ai', 'machine learning', 'llm']):
                        category = 'ai-agent'
                    elif any(kw in description.lower() for kw in ['design', 'draw', 'image']):
                        category = 'design-tools'
                    elif any(kw in description.lower() for kw in ['video', 'audio', 'music']):
                        category = 'media-video'
                    elif any(kw in description.lower() for kw in ['password', 'security', 'privacy']):
                        category = 'security-privacy'
                    elif any(kw in description.lower() for kw in ['office', 'document', 'note']):
                        category = 'office-productivity'
                    elif any(kw in description.lower() for kw in ['system', 'utility', 'file']):
                        category = 'system-utils'
                    
                    new_candidates.append({
                        "github_url": repo_url,
                        "category": category,
                        "alternative_to": "商业软件",
                        "description_zh": description[:100] if description else "开源项目",
                        "description_en": description,
                        "tags": [],
                        "license": item.get('license', {}).get('spdx_id', '')
                    })
                    
                    if len(new_candidates) >= 20:
                        break
            time.sleep(2)
        except Exception as e:
            print(f"搜索出错: {e}")
            continue
    
    if new_candidates:
        pending.extend(new_candidates)
        data['pending_projects'] = pending
        print(f"✅ 一次性追加了 {len(new_candidates)} 个候选项目")
    
    return data

def add_new_projects(data, count=3):
    # 🆕 最终去重：确保数据源没有重复 slug
    seen = set()
    original_count = len(data['projects'])
    data['projects'] = [p for p in data['projects'] if p.get('slug') not in seen and not seen.add(p.get('slug'))]
    if len(data['projects']) < original_count:
        print(f"⚠️ 自动清理了 {original_count - len(data['projects'])} 个后台重复项目")

    data = auto_refill_pending(data)
    
    pending = data.get('pending_projects', [])
    if not pending: print('📭 候选池已空'); return data, []
    actual = min(count, len(pending))
    selected = random.sample(pending, actual)
    added, log_entries = 0, []
    today_str = datetime.now().strftime('%Y-%m-%d')
    new_project_slugs = []
    
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
        new_project_slugs.append(slug)
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
    
    # 🆕 主动向百度推送新增URL
    if new_project_slugs and BAIDU_TOKEN:
        push_to_baidu(data, new_project_slugs)
    
    return data, added

def push_to_baidu(data, new_slugs):
    """向百度普通收录API推送新增URL"""
    base_url = data['site']['url'].rstrip('/')
    new_urls = [f"{base_url}/projects/{slug}.html" for slug in new_slugs]
    
    try:
        api_url = f"http://data.zz.baidu.com/urls?site={base_url}&token={BAIDU_TOKEN}"
        payload = "\n".join(new_urls).encode('utf-8')
        req = urllib.request.Request(api_url, data=payload, headers={'Content-Type': 'text/plain'})
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode('utf-8'))
            print(f"✅ 已向百度推送 {len(new_urls)} 个新URL，成功: {result.get('success', 0)} 条")
    except Exception as e:
        print(f"⚠️ 百度推送失败: {e}")

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
        urls.append({'loc': f'{base_url}/projects/{proj["slug"]}.html', 'priority': '0.6', 'changefreq': 'daily', 'lastmod': proj.get('last_updated', today)})
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

def get_project_fingerprint(proj):
    key_content = f"{proj['name']}|{proj['description_zh']}|{proj['description_en']}|{proj['stars']}|{proj.get('version','')}"
    if 'discussions' in proj:
        key_content += '|' + '|'.join([d['title'] for d in proj['discussions'][:5]])
    return hashlib.md5(key_content.encode('utf-8')).hexdigest()

def load_page_states():
    if os.path.exists(PAGE_STATES_PATH):
        with open(PAGE_STATES_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_page_states(states):
    with open(PAGE_STATES_PATH, 'w', encoding='utf-8') as f:
        json.dump(states, f, ensure_ascii=False, indent=2)

def generate_static_project_pages(data):
    print("⏳ 正在生成项目静态页面 (增量模式)...")
    if not os.path.exists(PROJECTS_DIR):
        os.makedirs(PROJECTS_DIR)
    base_url = data['site']['url'].rstrip('/')
    generated, skipped, new_states = 0, 0, {}
    old_states = load_page_states()
    
    for proj in data['projects']:
        slug = proj['slug']
        fingerprint = get_project_fingerprint(proj)
        if old_states.get(slug) == fingerprint:
            skipped += 1
            new_states[slug] = fingerprint
            continue

        category = next((c for c in data['categories'] if c['id'] == proj['category']), None)
        cat_name = category['name'] if category else proj['category']
        cat_icon = category['icon'] if category else ''
        
        discussions_html = ''
        if 'discussions' in proj and proj['discussions']:
            disc_items = []
            for d in proj['discussions'][:5]:
                title = d.get('title', '讨论')
                author = d.get('author', '社区用户')
                url = d.get('url', '#')
                time_str = d.get('created_at', '')[:10]
                disc_items.append(f'<p>📌 <a href="{url}" target="_blank">{title}</a> — 由 {author} 发布于 {time_str}</p>')
            discussions_html = f"""
      <h2>💬 社区讨论</h2>
      <div class="discussions-list">
        {''.join(disc_items)}
      </div>"""

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
  <link rel="icon" href="/logo.png" type="image/png">
  <link rel="manifest" href="/manifest.json">
  <meta name="theme-color" content="#6366f1">
  <script>
  function translatePage() {{
    var currentUrl = window.location.href;
    window.open('https://translate.google.com/translate?sl=zh-CN&tl=en&u=' + encodeURIComponent(currentUrl), '_blank');
  }}
  </script>
  <script defer src="https://cloud.umami.is/script.js" data-website-id="f80d17db-cf1a-4532-88ce-6cbefe2a77ee"></script>
</head>
<body>
  <nav class="navbar">
    <div class="navbar-inner">
      <a href="/" class="logo"><img src="/logo.png" alt="开源替代" style="height:24px;width:24px;vertical-align:middle;margin-right:6px;"> <span data-site-name>开源替代</span></a>
      <button class="hamburger" id="hamburgerBtn" aria-label="菜单">☰</button>
      <ul class="nav-links" id="navLinks">
        <li><a href="/category.html?id=ai-agent">AI & Agent</a></li>
        <li><a href="/category.html?id=design-tools">设计工具</a></li>
        <li><a href="/category.html?id=office-productivity">办公效率</a></li>
        <li><a href="/category.html?id=dev-tools">开发工具</a></li>
        <li><a href="/category.html?id=media-video">影音图像</a></li>
        <li><a href="/category.html?id=security-privacy">安全隐私</a></li>
        <li><a href="/category.html?id=system-utils">系统工具</a></li>
        <li><a href="/about.html">关于我们</a></li>
        <li><button class="theme-toggle" id="themeToggle" aria-label="切换主题">🌓</button></li>
        <li><button onclick="translatePage()" style="background:none;border:1px solid var(--border);border-radius:20px;padding:6px 10px;cursor:pointer;font-size:0.85rem;color:var(--text-secondary);margin-left:8px;" title="Translate to English">🇺🇸 EN</button></li>
      </ul>
    </div>
  </nav>
  <main class="container">
    <header class="detail-header">
      <span class="category-tag">{cat_icon} {cat_name}</span>
      <h1>{proj['name']}</h1>
      <div class="detail-meta">
        <span>⭐ {proj['stars']:,} Stars</span>
        <span>📜 {proj.get('license', 'N/A')}</span>
        <span class="alt-badge">替代: {proj.get('alternative_to', '')}</span>
      </div>
    </header>
    <article class="detail-content">
      <h2>📖 项目简介</h2>
      <p>{proj.get('description_zh', '暂无介绍')}</p>
      <h2>🔗 GitHub 项目地址</h2>
      <p><a href="{proj['github_url']}" target="_blank">{proj['github_url']}</a></p>
      <h2>🔄 可替代的商用软件</h2>
      <p>{proj.get('alternative_to', '')}</p>
      <h2>📝 项目原文介绍（英文）</h2>
      <p>{proj.get('description_en', 'No description available.')}</p>
      {discussions_html}
      <section class="disclaimer-box">
        ⚠️ <strong>免责声明：</strong>本文内容整理自 GitHub 开源社区，旨在分享和介绍优秀的开源替代方案。
      </section>
    </article>
  </main>
  <footer class="footer">
    <div class="footer-inner">
      <div class="footer-col"><h4>关于本站</h4><p style="font-size:0.85rem;color:var(--text-secondary);">发现并分享优秀的开源替代方案。</p></div>
      <div class="footer-col"><h4>快速链接</h4><a href="/">首页</a><a href="/about.html">关于我们</a><a href="/privacy.html">隐私政策</a></div>
      <div class="footer-col"><h4>联系我们</h4><a href="mailto:mailtomidoo@gmail.com">📧 mailtomidoo@gmail.com</a></div>
    </div>
    <div class="footer-bottom"><p>© <span id="currentYear"></span> 开源替代 - 尊重开源，分享价值</p></div>
  </footer>
  <script>document.getElementById('currentYear').textContent = new Date().getFullYear();</script>
  <script src="/assets/js/main.js"></script>
</body>
</html>"""
        with open(f'{PROJECTS_DIR}/{slug}.html', 'w', encoding='utf-8') as f:
            f.write(html)
        generated += 1
        new_states[slug] = fingerprint

    save_page_states(new_states)
    print(f"✅ 已生成 {generated} 个页面，跳过 {skipped} 个未变化的页面")
