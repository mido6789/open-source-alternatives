#!/usr/bin/env python3
"""
每日自动更新脚本 (增强版)
功能：
1. 更新 Stars/版本 + 自动翻译（增强清洗）+ 自然语气点评 + 时间线带简介
2. 自动新增 3-5 个候选项目
3. 为缺少标签的项目自动补全标签
4. 增量生成语义化、SEO友好的静态HTML项目页面（含面包屑导航、彩色标签）+ 静态首页
5. 抓取社区讨论 (Discussions) 丰富内容，段落式展示
6. 候选池自动补给 (低于20个时一次性追加20个新候选)
7. 向百度主动推送新增URL，加速收录
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
    clean = re.sub(r'https?://\S+', '', clean)
    clean = re.sub(r'\s+', ' ', clean).strip()
    return clean

def clean_for_translation(text):
    """翻译前清洗：去emoji、去特殊符号"""
    if not text: return text
    # 去掉emoji
    clean = re.sub(r'[🚀🔥🎨⚡🦊💻🌟✅⭐📌📋🔗🔄📖📝💬⚠️☰🌓🇺🇸🇨🇳]', '', text)
    # 去掉连续的符号
    clean = re.sub(r'[•·]{1,}', '', clean)
    clean = re.sub(r'\s+', ' ', clean).strip()
    return clean

def add_comment(zh_text, stars):
    """根据Stars数添加自然语气点评"""
    if stars > 50000:
        return zh_text + " 该项目在开源社区中拥有极高的知名度和活跃度，是同类替代方案中的领军者。"
    elif stars > 10000:
        return zh_text + " 该项目在社区中拥有极高的人气，是同类替代方案中的佼佼者。"
    elif stars > 1000:
        return zh_text + " 该项目在社区中已获得一定认可，功能完善，值得关注和尝试。"
    elif stars > 100:
        return zh_text + " 该项目虽然目前关注度不高，但功能独特，未来发展值得期待。"
    else:
        return zh_text + " 该项目是一个新兴的开源替代方案，具有独特的功能定位，值得一试。"

def translate(text):
    if not text or len(text) < 10: return text
    for attempt in range(3):
        try:
            url = "https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=zh-CN&dt=t&q=" + urllib.parse.quote(text[:500])
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=15) as resp:
                result = json.loads(resp.read().decode())
                translated = ''.join([s[0] for s in result[0] if s[0]])
                if translated and translated != text:
                    return translated
        except:
            time.sleep(2)
    return text

def needs_translation(zh, en):
    if not zh or len(zh) < 20:
        return True
    if zh == en:
        return True
    ascii_letters = sum(1 for c in zh if c.isascii() and c.isalpha())
    if len(zh) > 0 and ascii_letters / len(zh) > 0.5:
        return True
    return False

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
        if not desc or len(desc) < 50:
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
    translated = 0
    tags_filled = 0
    for project in data['projects']:
        stars, version, lic, desc = get_repo_info(project['github_url'])
        if stars is not None:
            if 'stars_history' not in project: project['stars_history'] = {}
            project['stars_history'][today_str] = stars
            project['stars_history'] = {k: v for k, v in project['stars_history'].items() if k >= cutoff}
            project['stars'] = stars; project['last_updated'] = today_str; updated += 1
        if version: project['version'] = version
        if lic and not project.get('license'): project['license'] = lic

        zh = project.get('description_zh', '')
        en = project.get('description_en', '') or desc or ''
        if desc:
            project['description_en'] = desc
        if en:
            en = strip_html(en)
        if needs_translation(zh, en) and en:
            clean_en = clean_for_translation(en)
            new_zh = translate(clean_en)
            if new_zh and new_zh != zh:
                new_zh = add_comment(new_zh, project['stars'])
                project['description_zh'] = new_zh
                translated += 1

        if not project.get('tags'):
            default_tags = []
            cat = next((c for c in data['categories'] if c['id'] == project['category']), None)
            if cat:
                default_tags.append(cat['name'])
            alt = project.get('alternative_to', '')
            if alt and alt != '商业软件':
                first_alt = alt.split('/')[0].strip().rstrip('等').strip()
                if first_alt:
                    default_tags.append(first_alt)
            fillers = ['开源', '免费', '替代', '工具', '自建']
            for tag in fillers:
                if len(default_tags) >= 4:
                    break
                if tag not in default_tags:
                    default_tags.append(tag)
            project['tags'] = default_tags[:5]
            tags_filled += 1

        time.sleep(1)

    if translated > 0:
        print(f'🌐 重新翻译了 {translated} 个项目的中文简介（含点评）')
    if tags_filled > 0:
        print(f'🏷️ 为 {tags_filled} 个项目补全了标签')
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
        
        # 🆕 增强翻译检查：只要中文简介包含太多英文，就重新翻译
        if (not desc_zh or len(desc_zh) < 20 or needs_translation(desc_zh, desc_en)) and desc_en:
            clean_en = clean_for_translation(desc_en)
            desc_zh = translate(clean_en)
            if desc_zh and desc_zh != desc_en:
                desc_zh = add_comment(desc_zh, stars)
        
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
    
    if new_project_slugs and BAIDU_TOKEN:
        push_to_baidu(data, new_project_slugs)
    
    return data, added

def push_to_baidu(data, new_slugs):
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
    if 'tags' in proj:
        key_content += '|' + '|'.join(proj['tags'])
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
    
    tag_colors = [
        "#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#ec4899", "#06b6d4", "#f97316"
    ]
    
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
        
        breadcrumb_html = f'<nav class="breadcrumb"><a href="/">首页</a> &raquo; <a href="/category.html?id={proj["category"]}">{cat_name}</a> &raquo; {proj["name"]}</nav>'
        
        tags_html = ''
        if proj.get('tags'):
            max_tags = min(5, len(proj['tags']))
            num_tags = random.randint(3, max_tags) if max_tags >= 3 else max_tags
            selected_tags = random.sample(proj['tags'], num_tags)
            
            tag_links = []
            for tag in selected_tags:
                color = random.choice(tag_colors)
                tag_links.append(f'<a href="/category.html?search={tag.strip()}" class="tag-link" style="background-color: {color}; color: white; padding: 4px 10px; border-radius: 12px; font-size: 0.8rem; text-decoration: none; margin-right: 6px;">{tag.strip()}</a>')
            tags_html = f'<div class="tags-list" style="margin: 20px 0;">{" ".join(tag_links)}</div>'
        
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
        <li><a href="/">首页</a></li>
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
    {breadcrumb_html}
    
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
      {tags_html}
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
      <div class="footer-col"><h4>联系我们</h4><a href="mailto:info@kyal.cn">📧 info@kyal.cn</a></div>
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

def fetch_discussions(data):
    if not GITHUB_TOKEN:
        print("⚠️ 未配置 GITHUB_TOKEN，跳过 Discussions 抓取")
        return data
    print("⏳ 正在抓取社区讨论...")
    headers = {'Authorization': f'Bearer {GITHUB_TOKEN}', 'Content-Type': 'application/json'}
    updated_count = 0
    
    for i, proj in enumerate(data['projects']):
        match = re.search(r'github\.com/([^/]+)/([^/]+?)(?:\.git)?$', proj['github_url'])
        if not match: continue
        owner, repo = match.groups()
        
        query = """
        {
          repository(owner: "%s", name: "%s") {
            discussions(first: 5, orderBy: {field: CREATED_AT, direction: DESC}) {
              nodes {
                title
                url
                createdAt
                author { login }
              }
            }
          }
        }
        """ % (owner, repo)
        
        try:
            req = urllib.request.Request(
                'https://api.github.com/graphql',
                data=json.dumps({'query': query}).encode('utf-8'),
                headers=headers,
                method='POST'
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                res = json.loads(resp.read().decode())
                nodes = res.get('data', {}).get('repository', {}).get('discussions', {}).get('nodes', [])
                
                if nodes:
                    proj['discussions'] = [
                        {'title': n['title'], 'url': n['url'], 'created_at': n['createdAt'], 'author': n['author']['login']}
                        for n in nodes if n
                    ]
                    updated_count += 1
        except Exception as e:
            pass
        
        if (i + 1) % 10 == 0:
            time.sleep(1)
    
    print(f"✅ 已抓取 {updated_count} 个项目的讨论内容")
    return data

def generate_static_homepage(data):
    print("⏳ 正在生成静态首页...")
    base_url = data['site']['url'].rstrip('/')
    
    top_projects = sorted(data['projects'], key=lambda p: p['stars'], reverse=True)[:6]
    projects_html = ''
    for proj in top_projects:
        category = next((c for c in data['categories'] if c['id'] == proj['category']), None)
        cat_name = category['name'] if category else proj['category']
        projects_html += f"""
      <article class="project-card">
        <span class="category-tag">{cat_name}</span>
        <h3><a href="/projects/{proj['slug']}.html" target="_blank">{proj['name']}</a></h3>
        <p class="description">{proj.get('description_zh', '')[:120]}</p>
        <div class="meta">
          <span>⭐ {proj['stars']:,}</span>
          <span class="alt-badge">替代: {proj.get('alternative_to', '')}</span>
        </div>
      </article>"""
    
    categories_html = ''
    for cat in data['categories']:
        count = len([p for p in data['projects'] if p['category'] == cat['id']])
        categories_html += f'<a href="/category.html?id={cat["id"]}" class="category-card"><span class="icon">{cat["icon"]}</span><span class="name">{cat["name"]}</span><span class="count">{count}个项目</span></a>\n'
    
    update_logs = data['site'].get('update_log', [])[:10]
    timeline_html = ''
    for log in update_logs:
        date_str = log[:10]
        rest = log[11:]
        timeline_html += f'        <div class="timeline-item"><span class="timeline-date">{date_str}</span>{rest}</div>\n'
    if not update_logs:
        timeline_html = '        <p style="color:var(--text-secondary);padding:20px;">即将更新...</p>'
    
    today = datetime.now()
    seven_days_ago = today - timedelta(days=7)
    cutoff_str = seven_days_ago.strftime('%Y-%m-%d')
    
    hot_projects = []
    for proj in data['projects']:
        history = proj.get('stars_history', {})
        oldest_in_range = proj['stars']
        newest_in_range = proj['stars']
        for date_str, stars in history.items():
            if date_str >= cutoff_str:
                oldest_in_range = min(oldest_in_range, stars)
                newest_in_range = max(newest_in_range, stars)
        growth = newest_in_range - oldest_in_range
        if growth > 0:
            hot_projects.append({**proj, 'weekly_growth': growth})
    
    hot_projects.sort(key=lambda p: p['weekly_growth'], reverse=True)
    hot_projects = hot_projects[:8]
    
    weekly_hot_html = ''
    if hot_projects:
        for proj in hot_projects:
            category = next((c for c in data['categories'] if c['id'] == proj['category']), None)
            cat_name = category['name'] if category else proj['category']
            weekly_hot_html += f"""
      <article class="project-card hot-card">
        {f'<span class="hot-badge">🔥 热门</span>' if proj['weekly_growth'] > 500 else ''}
        <span class="category-tag">{cat_name}</span>
        <h3><a href="/projects/{proj['slug']}.html" target="_blank">{proj['name']}</a></h3>
        <p class="description">{proj.get('description_zh', '')[:120]}</p>
        <div class="meta">
          <span>⭐ {proj['stars']:,}</span>
          <span class="growth-positive">📈 +{proj['weekly_growth']:,}</span>
        </div>
        <span class="alt-badge">替代: {proj.get('alternative_to', '')}</span>
      </article>"""
    else:
        weekly_hot_html = '<p style="color:var(--text-secondary);padding:20px;">数据收集中，明天再来看看...</p>'
    
    latest_projects = sorted(data['projects'], key=lambda p: p.get('date_added', ''), reverse=True)[:6]
    latest_html = ''
    for proj in latest_projects:
        category = next((c for c in data['categories'] if c['id'] == proj['category']), None)
        cat_name = category['name'] if category else proj['category']
        latest_html += f"""
      <article class="project-card">
        <span class="category-tag">{cat_name}</span>
        <h3><a href="/projects/{proj['slug']}.html" target="_blank">{proj['name']}</a></h3>
        <p class="description">{proj.get('description_zh', '')[:120]}</p>
        <div class="meta">
          <span>⭐ {proj['stars']:,}</span>
          <span class="alt-badge">替代: {proj.get('alternative_to', '')}</span>
        </div>
      </article>"""
    
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>开源替代 - 发现优秀的开源替代方案</title>
  <meta name="description" content="发现优秀的开源替代方案，告别高价付费软件。收录AI、设计工具、办公效率、开发工具等7大类{len(data['projects'])}个开源替代品。每日更新。">
  <link rel="canonical" href="{base_url}/">
  <meta property="og:title" content="开源替代 - 发现优秀的开源替代方案">
  <meta property="og:description" content="收录最全的开源替代方案，涵盖AI、设计、办公、开发等7大领域，每日更新Stars和版本号。">
  <meta property="og:type" content="website">
  <meta property="og:url" content="{base_url}/">
  <link rel="stylesheet" href="/assets/css/style.css">
  <link rel="icon" href="/logo.png" type="image/png">
  <link rel="manifest" href="/manifest.json">
  <meta name="theme-color" content="#6366f1">
  <script type="application/ld+json">
  {{
    "@context": "https://schema.org",
    "@type": "WebSite",
    "name": "开源替代",
    "description": "发现优秀的开源替代方案，告别高价付费软件",
    "url": "{base_url}"
  }}
  </script>
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
        <li><a href="/">首页</a></li>
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
    <section class="hero">
      <h1>发现优秀的开源替代方案</h1>
      <p>告别高价付费软件，探索自由开源的无限可能。我们每日追踪 GitHub 上最受欢迎的开源项目，帮你找到最合适的替代品。目前已收录 <strong>{len(data['projects'])}</strong> 个开源项目。</p>
      <div class="hero-search">
        <input type="text" id="globalSearch2" placeholder="搜索你想要的替代方案...">
        <button id="searchBtn2">🔍 探索</button>
      </div>
    </section>

    <section>
      <h2 class="section-title">📂 浏览分类</h2>
      <nav class="categories-grid">
        {categories_html}
      </nav>
    </section>

    <div class="ad-slot" data-ad-slot="sidebar_top"></div>

    <section>
      <h2 class="section-title"><span class="hot-icon">🔥</span> 本周热门</h2>
      <p style="color:var(--text-secondary);margin-bottom:20px;font-size:0.9rem;">Star 增长最快的开源项目（7日内涨幅）</p>
      <div class="projects-grid" id="weeklyHot">
        {weekly_hot_html}
      </div>
    </section>

    <div class="ad-slot" data-ad-slot="list_item"></div>

    <section>
      <h2 class="section-title">⭐ 精选推荐</h2>
      <div class="projects-grid">
        {projects_html}
      </div>
    </section>

    <div class="ad-slot" data-ad-slot="list_item"></div>

    <section>
      <h2 class="section-title">📋 最近更新</h2>
      <div class="timeline-container">
{timeline_html}
      </div>
    </section>

    <div class="ad-slot" data-ad-slot="sidebar_bottom"></div>

    <section>
      <h2 class="section-title">🆕 最新收录</h2>
      <div class="projects-grid">
        {latest_html}
      </div>
    </section>
  </main>

  <div id="footerAd" class="ad-slot" data-ad-slot="footer"></div>
  <footer class="footer">
    <div class="footer-inner">
      <div class="footer-col">
        <h4>关于本站</h4>
        <p style="font-size:0.85rem;color:var(--text-secondary);">发现并分享优秀的开源替代方案，让更多人用上自由软件。</p>
      </div>
      <div class="footer-col">
        <h4>快速链接</h4>
        <a href="/">首页</a>
        <a href="/about.html">关于我们</a>
        <a href="/privacy.html">隐私政策</a>
      </div>
      <div class="footer-col">
        <h4>联系我们</h4>
        <a href="mailto:info@kyal.cn">📧 info@kyal.cn</a>
      </div>
    </div>
    <div class="footer-bottom">
      <p>© <span id="currentYear"></span> 开源替代 - 尊重开源，分享价值</p>
      <p style="margin-top:4px;">本站内容整理自 GitHub 开源社区。如有侵权请联系删除。</p>
    </div>
  </footer>
  <script>document.getElementById('currentYear').textContent = new Date().getFullYear();</script>
  <script src="/assets/js/main.js"></script>
</body>
</html>"""
    
    with open('index.html', 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"✅ 静态首页已生成（精选{len(top_projects)}个 | 最新{len(latest_projects)}个 | 更新{len(update_logs)}条）")

def main():
    print(f'🚀 开始每日更新 - {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    data = load_data()
    data = update_existing_projects(data)
    new_count = random.randint(3, 5)
    data, added = add_new_projects(data, new_count)
    data = fetch_discussions(data)
    save_data(data)
    generate_sitemap(data)
    generate_static_project_pages(data)
    generate_static_homepage(data)
    print(f'✅ 完成：新增 {added} 个，总计 {len(data["projects"])} 个项目')

if __name__ == '__main__':
    main()
