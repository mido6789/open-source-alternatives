// ============================================
// OpenSourceAlternatives.com - 主脚本
// 功能：数据加载、页面渲染、搜索、主题切换
// ============================================

const SITE_CONFIG = {
  dataUrl: '/open-source-alternatives/assets/js/data.json',
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

// ========== 创建项目卡片 ==========
function createProjectCard(project) {
  const category = siteData.categories.find(c => c.id === project.category);
  const catName = category ? category.name : project.category;
  const catIcon = category ? category.icon : '';
  
  return `
    <div class="project-card">
      ${project.featured ? '<span class="featured-star" title="精选推荐">⭐</span>' : ''}
      <span class="category-tag">${catIcon} ${catName}</span>
      <h3><a href="/open-source-alternatives/detail.html?id=${project.slug}">${escapeHtml(project.name)}</a></h3>
      <p class="description">${escapeHtml(project.description_zh)}</p>
      <div class="meta">
        <span>⭐ ${getStarDisplay(project.stars)}</span>
        ${project.version ? `<span>🏷️ ${escapeHtml(project.version)}</span>` : ''}
      </div>
      <span class="alt-badge">替代: ${escapeHtml(project.alternative_to)}</span>
    </div>
  `;
}

// ========== 本周热门 ==========
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
      <h3><a href="/open-source-alternatives/detail.html?id=${project.slug}">${escapeHtml(project.name)}</a></h3>
      <p class="description">${escapeHtml(project.description_zh)}</p>
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
    return `<div class="timeline-item">${formatted}</div>`;
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
      <a href="/open-source-alternatives/category.html?id=${cat.id}" class="category-card">
        <span class="icon">${cat.icon}</span>
        <span class="name">${cat.name}</span>
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
      <p>${escapeHtml(project.description_zh)}</p>
      
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

      <div class="disclaimer-box">
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
      window.location.href = '/open-source-alternatives/category.html?search=' + encodeURIComponent(query);
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
  if (path === '/' || path.endsWith('index.html') || path.endsWith('open-source-alternatives/')) {
    renderHomePage();
  } else if (path.includes('category.html')) {
    renderCategoryPage();
  } else if (path.includes('detail.html')) {
    renderDetailPage();
  }
});
