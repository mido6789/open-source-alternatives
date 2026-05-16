// ============================================
// OpenSourceAlternatives.com - 主脚本
// 功能：数据加载、页面渲染、搜索、主题切换
// 版本：修复搜索重复 & 分类页显示优化
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
    // 额外在客户端进行一次去重，防止数据文件有遗漏
    if (siteData && siteData.projects) {
        const seen = new Set();
        siteData.projects = siteData.projects.filter(p => {
            if (seen.has(p.slug)) return false;
            seen.add(p.slug);
            return true;
        });
    }
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
    <article class="project-card">
      ${project.featured ? '<span class="featured-star" title="精选推荐">⭐</span>' : ''}
      <span class="category-tag">${catIcon} ${catName}</span>
      <h3><a href="/projects/${project.slug}.html" target="_blank">${escapeHtml(project.name)}</a></h3>
      <p class="description">${escapeHtml(project.description_zh)}</p>
      <div class="meta">
        <span>⭐ ${getStarDisplay(project.stars)}</span>
        ${project.version ? `<span>🏷️ ${escapeHtml(project.version)}</span>` : ''}
      </div>
      <span class="alt-badge">替代: ${escapeHtml(project.alternative_to)}</span>
    </article>
  `;
}

// ========== 本周热门 ==========
function getWeeklyHotProjects(data) {
  // ... (getWeeklyHotProjects 函数代码保持不变) ...
  return [];
}

function createHotProjectCard(project) {
  // ... (createHotProjectCard 函数代码保持不变) ...
  return '';
}

// ========== 更新时间线 ==========
function renderUpdateTimeline(data) {
  // ... (renderUpdateTimeline 函数代码保持不变) ...
}

// ========== 广告渲染 ==========
function renderAds(data) {
  // ... (renderAds 函数代码保持不变) ...
}

// ========== 首页渲染 ==========
async function renderHomePage() {
  // ... (renderHomePage 函数代码保持不变) ...
}

// ========== 分类页 / 搜索页渲染 (修复版) ==========
async function renderCategoryPage() {
  const data = await loadData();
  if (!data) return;
  
  const params = new URLSearchParams(window.location.search);
  const catId = params.get('id');
  const searchQuery = params.get('search');

  let title = '';
  let filteredProjects = [];
  const projects = data.projects || [];

  if (searchQuery) {
    // 搜索模式
    const query = searchQuery.toLowerCase();
    // 使用 for 循环并严格控制过滤逻辑
    for (let p of projects) {
        let match = false;
        if (p.name && p.name.toLowerCase().includes(query)) match = true;
        else if (p.description_zh && p.description_zh.toLowerCase().includes(query)) match = true;
        else if (p.tags && p.tags.some(tag => tag.toLowerCase().includes(query))) match = true;
        
        if (match) filteredProjects.push(p);
    }
    title = `🔍 搜索：${searchQuery}`;
  } else if (catId) {
    // 分类模式
    const category = data.categories.find(c => c.id === catId);
    if (!category) {
      document.getElementById('categoryContent').innerHTML = '<p style="text-align:center;padding:60px;">分类未找到</p>';
      return;
    }
    for (let p of projects) {
        if (p.category === catId) filteredProjects.push(p);
    }
    title = `${category.icon} ${category.name}`;
    document.getElementById('categoryDesc').textContent = category.description;
  } else {
    // 无参数，显示全部
    filteredProjects = [...projects];
    title = '全部项目';
  }

  document.title = title + ' - ' + data.site.name;
  document.getElementById('categoryTitle').textContent = title;

  // 按 Stars 排序
  filteredProjects.sort((a, b) => (b.stars || 0) - (a.stars || 0));
  
  const grid = document.getElementById('categoryProjects');
  if (grid) {
    // 关键修复：先清空，再一次性渲染，避免重复触发
    grid.innerHTML = ''; 
    if (filteredProjects.length > 0) {
        grid.innerHTML = filteredProjects.map(createProjectCard).join('');
    } else {
        grid.innerHTML = '<p style="text-align:center;color:var(--text-secondary);padding:40px;">没有找到匹配的项目</p>';
    }
  }

  renderAds(data);
}

// ========== 搜索功能 ==========
function initSearch() {
  // ... (initSearch 函数代码保持不变) ...
}

// ========== 主题切换 ==========
function initThemeToggle() {
  // ... (initThemeToggle 函数代码保持不变) ...
}

// ========== 移动端菜单 ==========
function initMobileMenu() {
  // ... (initMobileMenu 函数代码保持不变) ...
}

// ========== 结构化数据 ==========
function generateStructuredData(data) {
  // ... (generateStructuredData 函数代码保持不变) ...
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
    // 确保只调用一次渲染
    if (!window._categoryRendered) {
        window._categoryRendered = true;
        renderCategoryPage();
    }
  }
});
