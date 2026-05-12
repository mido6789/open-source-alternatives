#!/usr/bin/env python3
"""
每日自动更新脚本
功能：
1. 更新 Stars/版本 + 自动翻译 + 时间线带简介
2. 自动新增 3-5 个候选项目
3. **🆕 自动生成静态HTML页面，提升SEO**
"""
import json, os, random, re, time, base64, shutil
from datetime import datetime, timedelta
import urllib.request
import urllib.error
import urllib.parse

DATA_PATH = 'assets/js/data.json'
SITEMAP_PATH = 'sitemap.xml'
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN', '')

# ========== 工具函数 (保持不变) ==========
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

# ========== 模板函数 (复用原网站样式) ==========
def get_header(title, description, canonical_url):
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <meta name="description" content="{description}">
  <link rel="canonical" href="{canonical_url}">
  <meta property="og:title" content="{title}">
  <meta property="og:description" content="{description}">
  <meta property="og:type" content="website">
  <meta property="og:url" content="{canonical_url}">
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
"""

def get_footer():
    return """
  </main>
  <footer class="footer">
    <div class="footer-bottom">
      <p>© """ + str(datetime.now().year) + """ 开源替代 - 尊重开源，分享价值</p>
    </div>
  </footer>
</body>
</html>"""

def generate_static_project_pages(data):
    """为每个项目生成静态详情页"""
    print("⏳ 正在生成项目静态页面...")
    
    # 创建目录
    if not os.path.exists('projects'):
        os.makedirs('projects')
    
    for proj in data['projects']:
        slug = proj['slug']
        title = f"{proj['name']} - 开源替代 {proj.get('alternative_to', '')} | 开源替代"
        description = proj.get('description_zh', '')[:150]
        canonical_url = f"{data['site']['url']}/detail.html?id={slug}"
        
        # 构建HTML
        html = get_header(title, description, canonical_url)
        
        # 面包屑和标题
        category = next((c for c in data['categories'] if c['id'] == proj['category']), None)
        cat_name = category['name'] if category else proj['category']
        cat_icon = category['icon'] if category else ''
        
        html += f"""
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
    </div>"""
        
        html += get_footer()
        
        # 写入文件
        with open(f'projects/{slug}.html', 'w', encoding='utf-8') as f:
            f.write(html)
    
    print(f"✅ 已生成 {len(data['projects'])} 个项目静态页面")

# ========== 修改主流程，加入生成静态页面的步骤 ==========
def main():
    print(f'🚀 开始每日更新 - {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    data = load_data()
    data = update_existing_projects(data)
    new_count = random.randint(3, 5)
    data, added = add_new_projects(data, new_count)
    save_data(data)
    
    # 生成sitemap
    generate_sitemap(data)
    
    # 🆕 生成静态HTML
    generate_static_project_pages(data)
    
    print(f'✅ 完成：新增 {added} 个，总计 {len(data["projects"])} 个项目')

if __name__ == '__main__':
    main()
