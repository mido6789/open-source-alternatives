// ============================================
// OpenSourceAlternatives.com - 主脚本
// 功能：数据加载、页面渲染、搜索、主题切换、中英翻译
// ============================================

const SITE_CONFIG = {
  dataUrl: '/assets/js/data.json',
  perPage: 12,
};

let siteData = null;

// ========== 加载数据 ==========
async function loadData() {
  if (siteData) return siteData;
  try {
    const res = await fetch(SITE_CONFIG.dataUrl);
    siteData = await res.json();
    return siteData;
  } catch (e) {
    console.error('数据加载失败:', e);
    return null;
  }
}

// ========== 工具函数 ==========
function getStarDisplay(stars) {
  if (stars >= 100000) return (stars / 1000).toFixed(1) + 'k';
  if (stars >= 10000) return (stars / 1000).toFixed(1) + 'k';
  if (stars >= 1000) return (stars / 1000).toFixed(1) + 'k';
  return stars.toString();
}

function escapeHtml(str) {
  if (!str) return '';
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

// ========== 创建项目卡片（新窗口打开）==========
function createProjectCard(project) {
  const category = siteData.categories.find(c => c.id === project.category);
  const catName = category ? category.name : project.category;
  const catIcon = category ? category.icon : '';
  
  return `
    <div class="project-card">
      ${project.featured ? '<span class="featured-star" title="精选推荐">⭐</span>' : ''}
      <span class="category-tag">${catIcon} ${catName}</span>
      <h3><a href="/detail.html?id=${project.slug}" target="_blank">${escapeHtml(project.name)}</a></h3>
      <p class="description" data-translate>${escapeHtml(project.description_zh)}</p>
      <div class="meta">
        <span>⭐ ${getStarDisplay(project.stars)}</span>
        ${project.version ? `<span>🏷️ ${escapeHtml(project.version)}</span>` : ''}
      </div>
      <span class="alt-badge">替代: ${escapeHtml(project.alternative_to)}</span>
    </div>
  `;
}

// ========== 本周热门（新窗口打开）==========
function getWeeklyHotProjects(data) {
  const today = new Date();
  const sevenDaysAgo = new Date(today - 7 * 24 * 60 * 60 * 1000);
  const cutoffStr = sevenDaysAgo.toISOString().split('T')[0];
  
  return data.projects
    .map(proj => {
      const history = proj.stars_history || {};
      let oldestInRange = proj.stars;
      let newestInRange = proj.stars;
      
      Object.entries(history).forEach(([date, stars]) => {
        if (date >= cutoffStr) {
          oldestInRange = Math.min(oldestInRange, stars);
          newestInRange = Math.max(newestInRange, stars);
        }
      });
      
      const growth = newestInRange - oldestInRange;
      return { ...proj, weekly_growth: growth };
    })
    .filter(p => p.weekly_growth > 0)
    .sort((a, b) => b.weekly_growth - a.weekly_growth)
    .slice(0, 8);
}

function createHotProjectCard(project) {
  const category = siteData.categories.find(c => c.id === project.category);
  const catName = category ? category.name : project.category;
  const catIcon = category ? category.icon : '';
  
  return `
    <div class="project-card hot-card">
      ${project.weekly_growth > 500 ? '<span class="hot-badge">🔥 热门</span>' : ''}
      <span class="category-tag">${catIcon} ${catName}</span>
      <h3><a href="/detail.html?id=${project.slug}" target="_blank">${escapeHtml(project.name)}</a></h3>
      <p class="description" data-translate>${escapeHtml(project.description_zh)}</p>
      <div class="meta">
        <span>⭐ ${getStarDisplay(project.stars)}</span>
        <span class="growth-positive">📈 +${project.weekly_growth.toLocaleString()}</span>
      </div>
      <span class="alt-badge">替代: ${escapeHtml(project.alternative_to)}</span>
    </div>
  `;
}

// ========== 更新时间线 ==========
function renderUpdateTimeline(data) {
  const container = document.getElementById('updateTimeline');
  if (!container) return;
  
  const logs = data.site.update_log || [];
  if (logs.length === 0) {
    container.innerHTML = '<p style="color:var(--text-secondary);text-align:center;padding:20px;">⏳ 自动更新后会显示最近动态...</p>';
    return;
  }
  
  const recent = logs.slice(0, 10);
  container.innerHTML = recent.map(log => {
    const formatted = log.replace(/^(\d{4}-\d{2}-\d{2})/, '<span class="timeline-date">$1</span>');
    return `<div class="timeline-item" data-translate>${formatted}</div>`;
  }).join('');
}

// ========== 广告渲染 ==========
function renderAds(data) {
  const ads = data.site.ads;
  const adSlots = document.querySelectorAll('[data-ad-slot]');
  adSlots.forEach(slot => {
    const slotName = slot.dataset.adSlot;
    if (ads[slotName] && ads[slotName].trim() !== '') {
      slot.innerHTML = ads[slotName];
      slot.style.display = 'flex';
    }
  });
}

// ========== 首页渲染 ==========
async function renderHomePage() {
  const data = await loadData();
  if (!data) return;

  document.querySelectorAll('[data-site-name]').forEach(el => {
    el.textContent = data.site.name;
  });
  document.title = data.site.name + ' - ' + data.site.description;

  // 渲染分类
  const catGrid = document.getElementById('categoriesGrid');
  if (catGrid) {
    catGrid.innerHTML = data.categories.map(cat => `
      <a href="/category.html?id=${cat.id}" class="category-card">
        <span class="icon">${cat.icon}</span>
        <span class="name" data-translate>${cat.name}</span>
      </a>
    `).join('');
  }

  // 渲染本周热门
  const hotGrid = document.getElementById('weeklyHot');
  if (hotGrid) {
    const hotProjects = getWeeklyHotProjects(data);
    if (hotProjects.length > 0) {
      hotGrid.innerHTML = hotProjects.map(createHotProjectCard).join('');
    } else {
      hotGrid.innerHTML = '<p style="color:var(--text-secondary);text-align:center;padding:20px;">📊 数据收集中，明天再来看看...</p>';
    }
  }

  // 渲染精选推荐
  const featuredGrid = document.getElementById('featuredProjects');
  if (featuredGrid) {
    const featured = data.projects.filter(p => p.featured);
    featuredGrid.innerHTML = featured.length > 0
      ? featured.map(createProjectCard).join('')
      : '<p style="color:var(--text-secondary);text-align:center;padding:20px;">精选项目即将上线...</p>';
  }

  // 渲染更新时间线
  renderUpdateTimeline(data);

  // 渲染最新收录
  const latestGrid = document.getElementById('latestProjects');
  if (latestGrid) {
    const latest = [...data.projects].sort((a, b) => new Date(b.date_added) - new Date(a.date_added)).slice(0, 6);
    latestGrid.innerHTML = latest.length > 0
      ? latest.map(createProjectCard).join('')
      : '<p style="color:var(--text-secondary);text-align:center;padding:20px;">项目即将上线...</p>';
  }

  renderAds(data);
  generateStructuredData(data);
}

// ========== 分类页渲染 ==========
async function renderCategoryPage() {
  const data = await loadData();
  if (!data) return;
  
  const params = new URLSearchParams(window.location.search);
  const catId = params.get('id');
  const category = data.categories.find(c => c.id === catId);
  
  if (!category) {
    document.getElementById('categoryContent').innerHTML = '<p style="text-align:center;padding:60px;">分类未找到</p>';
    return;
  }

  document.title = category.icon + ' ' + category.name + ' - ' + data.site.name;
  document.getElementById('categoryTitle').textContent = category.icon + ' ' + category.name;
  document.getElementById('categoryDesc').textContent = category.description;

  const projects = data.projects
    .filter(p => p.category === catId)
    .sort((a, b) => b.stars - a.stars);
  
  const grid = document.getElementById('categoryProjects');
  if (grid) {
    grid.innerHTML = projects.length > 0 
      ? projects.map(createProjectCard).join('')
      : '<p style="text-align:center;color:var(--text-secondary);padding:40px;">该分类下暂无项目，敬请期待~</p>';
  }

  renderAds(data);
}

// ========== 详情页渲染 ==========
async function renderDetailPage() {
  const data = await loadData();
  if (!data) return;

  const params = new URLSearchParams(window.location.search);
  const slug = params.get('id');
  const project = data.projects.find(p => p.slug === slug);

  if (!project) {
    document.getElementById('detailContent').innerHTML = '<p style="text-align:center;padding:60px;">项目未找到</p>';
    return;
  }

  document.title = project.name + ' - 开源替代 ' + project.alternative_to + ' - ' + data.site.name;
  
  const category = data.categories.find(c => c.id === project.category);
  
  document.getElementById('detailContent').innerHTML = `
    <div class="detail-header">
      <span class="category-tag">${category ? category.icon + ' ' + category.name : project.category}</span>
      <h1>${escapeHtml(project.name)}</h1>
      <div class="detail-meta">
        <span class="stat">⭐ ${project.stars.toLocaleString()} Stars</span>
        ${project.version ? `<span class="stat">🏷️ ${escapeHtml(project.version)}</span>` : ''}
        ${project.license ? `<span class="stat">📜 ${escapeHtml(project.license)}</span>` : ''}
        <span class="alt-badge">替代: ${escapeHtml(project.alternative_to)}</span>
      </div>
    </div>

    <div class="detail-content">
      <h2>📖 项目简介</h2>
      <p data-translate>${escapeHtml(project.description_zh)}</p>
      
      <h2>🔗 GitHub 项目地址</h2>
      <p><a href="${escapeHtml(project.github_url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(project.github_url)}</a></p>
      
      <h2>🔄 可替代的商用软件</h2>
      <p>${escapeHtml(project.alternative_to)}</p>
      
      <h2>📝 项目原文介绍（英文）</h2>
      <p>${escapeHtml(project.description_en)}</p>

      ${project.download_url ? `
      <h2>💾 网盘下载</h2>
      <p><a href="${escapeHtml(project.download_url)}" target="_blank" rel="noopener">点击下载（网盘）</a></p>
      ` : ''}

      <div id="articleAd" class="ad-slot"></div>

      <div class="disclaimer-box" data-translate>
        ⚠️ <strong>免责声明：</strong>本文内容整理自 GitHub 开源社区，旨在分享和介绍优秀的开源替代方案。所有项目版权归原作者所有，我们尊重并注明原始出处。如有侵权请联系我们删除。感谢开源社区的每一位贡献者！
      </div>
    </div>
  `;

  renderAds(data);
  if (data.site.ads.article_bottom && data.site.ads.article_bottom.trim() !== '') {
    const articleAd = document.getElementById('articleAd');
    articleAd.innerHTML = data.site.ads.article_bottom;
    articleAd.style.display = 'flex';
  }
}

// ========== 搜索功能 ==========
function initSearch() {
  const searchInputs = document.querySelectorAll('#globalSearch, #globalSearch2');
  const searchBtns = document.querySelectorAll('#searchBtn, #searchBtn2');
  
  function doSearch(input) {
    const query = input?.value.trim();
    if (query) {
      window.location.href = '/category.html?search=' + encodeURIComponent(query);
    }
  }
  
  searchInputs.forEach(input => {
    input?.addEventListener('keypress', (e) => {
      if (e.key === 'Enter') doSearch(input);
    });
  });
  
  searchBtns.forEach(btn => {
    btn?.addEventListener('click', () => {
      const input = document.querySelector('#globalSearch, #globalSearch2');
      doSearch(input);
    });
  });
}

// ========== 主题切换 ==========
function initThemeToggle() {
  const toggles = document.querySelectorAll('#themeToggle');
  const saved = localStorage.getItem('theme');
  if (saved === 'dark' || (!saved && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
    document.documentElement.setAttribute('data-theme', 'dark');
  }
  
  toggles.forEach(toggle => {
    toggle?.addEventListener('click', () => {
      const current = document.documentElement.getAttribute('data-theme');
      const next = current === 'dark' ? 'light' : 'dark';
      document.documentElement.setAttribute('data-theme', next);
      localStorage.setItem('theme', next);
    });
  });
}

// ========== 移动端菜单 ==========
function initMobileMenu() {
  const hamburger = document.getElementById('hamburgerBtn');
  const navLinks = document.getElementById('navLinks');
  hamburger?.addEventListener('click', () => {
    navLinks?.classList.toggle('open');
  });
}

// ========== 结构化数据 ==========
function generateStructuredData(data) {
  const structured = {
    "@context": "https://schema.org",
    "@type": "WebSite",
    "name": data.site.name,
    "description": data.site.description,
    "url": data.site.url,
  };
  const script = document.createElement('script');
  script.type = 'application/ld+json';
  script.textContent = JSON.stringify(structured);
  document.head.appendChild(script);
}

// ========== 初始化 ==========
document.addEventListener('DOMContentLoaded', () => {
  initThemeToggle();
  initMobileMenu();
  initSearch();

  const path = window.location.pathname;
  if (path === '/' || path.endsWith('index.html') || path.endsWith('/')) {
    renderHomePage();
  } else if (path.includes('category.html')) {
    renderCategoryPage();
  } else if (path.includes('detail.html')) {
    renderDetailPage();
  }

  // ========== 中英翻译功能 (绕过CORS) ==========
  const BAIDU_APPID = '20211019000977416';
  const BAIDU_KEY = '30k4V59TqG49dEsXK98f';
  let currentLang = 'zh';
  let translatedCache = {};

  async function switchLang() {
    const langBtn = document.getElementById('langBtn');
    if (!langBtn) return;
    
    if (currentLang === 'zh') {
      langBtn.innerText = '⏳ ...';
      const textsToTranslate = [];
      const elements = document.querySelectorAll('[data-translate]');

      elements.forEach(el => {
        const text = el.innerText.trim();
        if (text && !translatedCache[text]) {
          textsToTranslate.push({ el, text });
        }
      });

      if (textsToTranslate.length > 0) {
        try {
          const query = textsToTranslate.map(t => t.text).join('\n');
          const salt = Date.now();
          const sign = md5(BAIDU_APPID + query + salt + BAIDU_KEY);
          const resp = await fetch(`https://fanyi-api.baidu.com/api/trans/vip/translate?q=${encodeURIComponent(query)}&from=zh&to=en&appid=${BAIDU_APPID}&salt=${salt}&sign=${sign}`);
          const data = await resp.json();
          
          if (data.trans_result) {
            data.trans_result.forEach((item, index) => {
              const originalText = textsToTranslate[index]?.text;
              if (originalText) {
                translatedCache[originalText] = item.dst;
              }
            });
          }
        } catch(e) {
          console.error('Translation fetch failed:', e);
        }
      }

      document.querySelectorAll('[data-translate]').forEach(el => {
        const text = el.innerText.trim();
        if (translatedCache[text]) {
          el.setAttribute('data-original', text);
          el.innerText = translatedCache[text];
        } else {
          el.setAttribute('data-original', text);
        }
      });
      
      currentLang = 'en';
      langBtn.innerText = '🇨🇳 中';
    } else {
      document.querySelectorAll('[data-translate]').forEach(el => {
        const original = el.getAttribute('data-original');
        if (original) {
          el.innerText = original;
        }
      });
      currentLang = 'zh';
      langBtn.innerText = '🇺🇸 EN';
    }
  }

  // Attach switchLang to the global scope if the button exists
  const langButton = document.getElementById('langBtn');
  if (langButton) {
    langButton.onclick = switchLang;
  }

  function md5(string) {
    function md5cycle(x, k) { var a = x[0], b = x[1], c = x[2], d = x[3]; a = ff(a, b, c, d, k[0], 7, -680876936); d = ff(d, a, b, c, k[1], 12, -389564586); c = ff(c, d, a, b, k[2], 17, 606105819); b = ff(b, c, d, a, k[3], 22, -1044525330); a = ff(a, b, c, d, k[4], 7, -176418897); d = ff(d, a, b, c, k[5], 12, 1200080426); c = ff(c, d, a, b, k[6], 17, -1473231341); b = ff(b, c, d, a, k[7], 22, -45705983); a = ff(a, b, c, d, k[8], 7, 1770035416); d = ff(d, a, b, c, k[9], 12, -1958414417); c = ff(c, d, a, b, k[10], 17, -42063); b = ff(b, c, d, a, k[11], 22, -1990404162); a = ff(a, b, c, d, k[12], 7, 1804603682); d = ff(d, a, b, c, k[13], 12, -40341101); c = ff(c, d, a, b, k[14], 17, -1502002290); b = ff(b, c, d, a, k[15], 22, 1236535329); a = gg(a, b, c, d, k[1], 5, -165796510); d = gg(d, a, b, c, k[6], 9, -1069501632); c = gg(c, d, a, b, k[11], 14, 643717713); b = gg(b, c, d, a, k[0], 20, -373897302); a = gg(a, b, c, d, k[5], 5, -701558691); d = gg(d, a, b, c, k[10], 9, 38016083); c = gg(c, d, a, b, k[15], 14, -660478335); b = gg(b, c, d, a, k[4], 20, -405537848); a = gg(a, b, c, d, k[9], 5, 568446438); d = gg(d, a, b, c, k[14], 9, -1019803690); c = gg(c, d, a, b, k[3], 14, -187363961); b = gg(b, c, d, a, k[8], 20, 1163531501); a = gg(a, b, c, d, k[13], 5, -1444681467); d = gg(d, a, b, c, k[2], 9, -51403784); c = gg(c, d, a, b, k[7], 14, 1735328473); b = gg(b, c, d, a, k[12], 20, -1926607734); a = hh(a, b, c, d, k[5], 4, -378558); d = hh(d, a, b, c, k[8], 11, -2022574463); c = hh(c, d, a, b, k[11], 16, 1839030562); b = hh(b, c, d, a, k[14], 23, -35309556); a = hh(a, b, c, d, k[1], 4, -1530992060); d = hh(d, a, b, c, k[4], 11, 1272893353); c = hh(c, d, a, b, k[7], 16, -155497632); b = hh(b, c, d, a, k[10], 23, -1094730640); a = hh(a, b, c, d, k[13], 4, 681279174); d = hh(d, a, b, c, k[0], 11, -358537222); c = hh(c, d, a, b, k[3], 16, -722521979); b = hh(b, c, d, a, k[6], 23, 76029189); a = hh(a, b, c, d, k[9], 4, -640364487); d = hh(d, a, b, c, k[12], 11, -421815835); c = hh(c, d, a, b, k[15], 16, 530742520); b = hh(b, c, d, a, k[2], 23, -995338651); a = ii(a, b, c, d, k[0], 6, -198630844); d = ii(d, a, b, c, k[7], 10, 1126891415); c = ii(c, d, a, b, k[14], 15, -1416354905); b = ii(b, c, d, a, k[5], 21, -57434055); a = ii(a, b, c, d, k[12], 6, 1700485571); d = ii(d, a, b, c, k[3], 10, -1894986606); c = ii(c, d, a, b, k[10], 15, -1051523); b = ii(b, c, d, a, k[1], 21, -2054922799); a = ii(a, b, c, d, k[8], 6, 1873313359); d = ii(d, a, b, c, k[15], 10, -30611744); c = ii(c, d, a, b, k[6], 15, -1560198380); b = ii(b, c, d, a, k[13], 21, 1309151649); a = ii(a, b, c, d, k[4], 6, -145523070); d = ii(d, a, b, c, k[11], 10, -1120210379); c = ii(c, d, a, b, k[2], 15, 718787259); b = ii(b, c, d, a, k[9], 21, -343485551); x[0] = add32(a, x[0]); x[1] = add32(b, x[1]); x[2] = add32(c, x[2]); x[3] = add32(d, x[3]); } function cmn(q, a, b, x, s, t) { a = add32(add32(a, q), add32(x, t)); return add32((a << s) | (a >>> (32 - s)), b); } function ff(a, b, c, d, x, s, t) { return cmn((b & c) | ((~b) & d), a, b, x, s, t); } function gg(a, b, c, d, x, s, t) { return cmn((b & d) | (c & (~d)), a, b, x, s, t); } function hh(a, b, c, d, x, s, t) { return cmn(b ^ c ^ d, a, b, x, s, t); } function ii(a, b, c, d, x, s, t) { return cmn(c ^ (b | (~d)), a, b, x, s, t); } function md51(s) { var n = s.length, state = [1732584193, -271733879, -1732584194, 271733878], i; for (i = 64; i <= s.length; i += 64) { md5cycle(state, md5blk(s.substring(i - 64, i))); } s = s.substring(i - 64); var tail = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]; for (i = 0; i < s.length; i++) tail[i >> 2] |= s.charCodeAt(i) << ((i % 4) << 3); tail[i >> 2] |= 0x80 << ((i % 4) << 3); if (i > 55) { md5cycle(state, tail); for (i = 0; i < 16; i++) tail[i] = 0; } tail[14] = n * 8; md5cycle(state, tail); return state; } function md5blk(s) { var md5blks = [], i; for (i = 0; i < 64; i += 4) { md5blks[i >> 2] = s.charCodeAt(i) + (s.charCodeAt(i + 1) << 8) + (s.charCodeAt(i + 2) << 16) + (s.charCodeAt(i + 3) << 24); } return md5blks; } var hex_chr = '0123456789abcdef'.split(''); function rhex(n) { var s = '', j = 0; for (; j < 4; j++) s += hex_chr[(n >> (j * 8 + 4)) & 0x0F] + hex_chr[(n >> (j * 8)) & 0x0F]; return s; } function hex(x) { for (var i = 0; i < x.length; i++) x[i] = rhex(x[i]); return x.join(''); } function add32(a, b) { return (a + b) & 0xFFFFFFFF; } return hex(md51(string)); }
});
