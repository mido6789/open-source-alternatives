// ============================================
// OpenSourceAlternatives.com - 主脚本
// 功能：数据加载、页面渲染、搜索、主题切换
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

// ========== 创建项目卡片（指向静态页面）==========
function createProjectCard(project) {
  const category = siteData.categories.find(c => c.id === project.category);
  const catName = category ? category.name : project.category;
  const catIcon = category ? category.icon : '';
  
  return `
    <div class="project-card">
      ${project.featured ? '<span class="featured-star" title="精选推荐">⭐</span>' : ''}
      <span class="category-tag">${catIcon} ${catName}</span>
      <h3><a href="/projects/${project.slug}.html" target="_blank">${escapeHtml(project.name)}</a></h3>
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
      <h3><a href="/projects/${project.slug}.html" target="_blank">${escapeHtml(project.name)}</a></h3>
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

  const catGrid = document.getElementById('categoriesGrid');
  if (catGrid) {
    catGrid.innerHTML = data.categories.map(cat => `
      <a href="/category.html?id=${cat.id}" class="category-card">
        <span class="icon">${cat.icon}</span>
        <span class="name">${cat.name}</span>
      </a>
    `).join('');
  }

  const hotGrid = document.getElementById('weeklyHot');
  if (hotGrid) {
    const hotProjects = getWeeklyHotProjects(data);
    if (hotProjects.length > 0) {
      hotGrid.innerHTML = hotProjects.map(createHotProjectCard).join('');
    } else {
      hotGrid.innerHTML = '<p style="color:var(--text-secondary);text-align:center;padding:20px;">📊 数据收集中，明天再来看看...</p>';
    }
  }

  const featuredGrid = document.getElementById('featuredProjects');
  if (featuredGrid) {
    const featured = data.projects.filter(p => p.featured);
    featuredGrid.innerHTML = featured.length > 0
      ? featured.map(createProjectCard).join('')
      : '<p style="color:var(--text-secondary);text-align:center;padding:20px;">精选项目即将上线...</p>';
  }

  renderUpdateTimeline(data);

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

// ========== 分类页 / 搜索页渲染 ==========
async function renderCategoryPage() {
  const data = await loadData();
  if (!data) return;
  
  const params = new URLSearchParams(window.location.search);
  const catId = params.get('id');
  const searchQuery = params.get('search');

  let title = '';
  let filteredProjects = [];

  if (searchQuery) {
    // 搜索模式
    const query = searchQuery.toLowerCase();
    filteredProjects = data.projects.filter(p => {
      return p.name.toLowerCase().includes(query) ||
             p.description_zh.toLowerCase().includes(query) ||
             (p.tags && p.tags.some(tag => tag.toLowerCase().includes(query)));
    });
    title = `🔍 搜索：${searchQuery}`;
  } else if (catId) {
    // 分类模式
    const category = data.categories.find(c => c.id === catId);
    if (!category) {
      document.getElementById('categoryContent').innerHTML = '<p style="text-align:center;padding:60px;">分类未找到</p>';
      return;
    }
    filteredProjects = data.projects.filter(p => p.category === catId);
    title = `${category.icon} ${category.name}`;
    document.getElementById('categoryDesc').textContent = category.description;
  } else {
    // 无参数，显示全部
    filteredProjects = data.projects;
    title = '全部项目';
  }

  document.title = title + ' - ' + data.site.name;
  document.getElementById('categoryTitle').textContent = title;

  // 按 Stars 排序
  filteredProjects.sort((a, b) => b.stars - a.stars);
  
  const grid = document.getElementById('categoryProjects');
  if (grid) {
    grid.innerHTML = filteredProjects.length > 0 
      ? filteredProjects.map(createProjectCard).join('')
      : '<p style="text-align:center;color:var(--text-secondary);padding:40px;">没有找到匹配的项目</p>';
  }

  renderAds(data);
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
  }
});
