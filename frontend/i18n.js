'use strict';

/* ============================================================
   FinSignal i18n — ZH / EN toggle
   Usage:  applyLang('zh') | applyLang('en')
           getLang()  → current lang string
   ============================================================ */

const I18N = {
  en: {
    // Nav / Sidebar
    nav_monitor:        'Monitor',
    nav_dashboard:      'Dashboard',
    nav_signal_ranking: 'Signal Ranking',
    nav_company_search: 'Company Search',
    nav_analysis:       'Analysis',
    nav_compare:        'Compare',
    nav_reports:        'Reports',
    nav_candidates:     'Candidates',
    nav_system:         'System',
    nav_settings:       'Settings',
    health_connecting:  'Connecting…',
    health_connected:   'API Connected',
    health_offline:     'API Offline',

    // Page titles
    page_dashboard:  'Dashboard',
    page_ranking:    'Signal Ranking',
    page_search:     'Company Search',
    page_compare:    'Compare',
    page_reports:    'Reports',
    page_candidates: '持续换手候选池',
    page_settings:   'Settings',

    // Buttons
    btn_refresh:  'Refresh',
    btn_apply:    '应用',
    btn_reset:    '重置',
    btn_search:   'Search',
    btn_generate: 'Generate Report',
    btn_add:      'Add',
    btn_clear:    'Clear All',
    btn_export:   'Export',

    // Candidates page
    cand_filter_title:  '筛选条件',
    cand_table_title:   '候选股票',
    cand_turnover_label:'今日换手 >',
    cand_price_label:   '现价 <',
    cand_circmv_label:  '流通市值 <',
    cand_pct_label:     '今日涨幅 <',
    cand_exclude_st:    '排除 ST',
    cand_unit_pct:      '%',
    cand_unit_yuan:     '元',
    cand_unit_yi:       '亿',
    cand_col_code:      '代码',
    cand_col_name:      '名称',
    cand_col_price:     'Current Price (¥)',
    cand_col_turnover:  'Today Turnover%',
    cand_col_pct:       'Today Change%',
    cand_col_circmv:    'Circ. MktCap (bn)',
    cand_col_reason:    'Notes',
    cand_empty_title:   'No candidates found',
    cand_empty_hint:    'Try relaxing the filters',
    cand_loading_error: 'Load failed',
    cand_akshare_label: 'AKShare fetch:',
    cand_request_label: 'This request:',

    // Ranking page
    rank_title:         'Signal Ranking',
    rank_col_rank:      '#',
    rank_col_code:      'Code',
    rank_col_name:      'Name',
    rank_col_market:    'Market',
    rank_col_signals:   'Signals',
    rank_col_score:     'Score',
    rank_filter_market: 'Market',
    rank_filter_all:    'All',
    rank_empty:         'No signals found',

    // Search page
    search_placeholder: 'Search by name or code…',
    search_col_code:    'Code',
    search_col_name:    'Name',
    search_col_market:  'Market',
    search_empty:       'No results',

    // Dashboard page
    dash_title:          'Dashboard',
    dash_panel_overview: 'Overview',
    dash_panel_recent:   'Recent Signals',

    // Compare page
    compare_title:           'Compare',
    compare_hint:            'Add companies to compare',
    compare_add_placeholder: 'Enter code e.g. CN:000001',

    // Reports page
    reports_title: 'Reports',
    reports_hint:  'Select a company to generate a report',

    // Settings page
    settings_title:     'Settings',
    settings_api_label: 'API Base URL',
    settings_save:      'Save',
    settings_saved:     'Saved',

    // Footer
    footer_data_source: 'Data source: backend API',
    footer_base_url:    'Base URL:',

    // Company page
    company_back:               '← Back',
    company_signals:            'Signals',
    company_overview:           'Overview',
    company_graph:              'Supply Chain Graph',
    company_no_graph:           'No graph data available',
    company_financial_signals:  'Financial Signals',
    company_governance_signals: 'Governance Signals',
    company_ai_report:          'AI Risk Report',
    btn_copy:                   'Copy',
    company_report_empty:       'No report generated yet',
    company_report_hint:        'Click "Generate Report" to create an AI risk analysis for this company.',
  },

  zh: {
    // Nav / Sidebar
    nav_monitor:        '监控',
    nav_dashboard:      '仪表盘',
    nav_signal_ranking: '信号排名',
    nav_company_search: '公司搜索',
    nav_analysis:       '分析',
    nav_compare:        '对比',
    nav_reports:        '报告',
    nav_candidates:     '候选池',
    nav_system:         '系统',
    nav_settings:       '设置',
    health_connecting:  '连接中…',
    health_connected:   'API 已连接',
    health_offline:     'API 离线',

    // Page titles
    page_dashboard:  '仪表盘',
    page_ranking:    '信号排名',
    page_search:     '公司搜索',
    page_compare:    '对比',
    page_reports:    '报告',
    page_candidates: '持续换手候选池',
    page_settings:   '设置',

    // Buttons
    btn_refresh:  '刷新',
    btn_apply:    '应用',
    btn_reset:    '重置',
    btn_search:   '搜索',
    btn_generate: '生成报告',
    btn_add:      '添加',
    btn_clear:    '清除全部',
    btn_export:   '导出',

    // Candidates page
    cand_filter_title:  '筛选条件',
    cand_table_title:   '候选股票',
    cand_turnover_label:'今日换手 >',
    cand_price_label:   '现价 <',
    cand_circmv_label:  '流通市值 <',
    cand_pct_label:     '今日涨幅 <',
    cand_exclude_st:    '排除 ST',
    cand_unit_pct:      '%',
    cand_unit_yuan:     '元',
    cand_unit_yi:       '亿',
    cand_col_code:      '代码',
    cand_col_name:      '名称',
    cand_col_price:     '现价 (元)',
    cand_col_turnover:  '今日换手%',
    cand_col_pct:       '今日涨幅%',
    cand_col_circmv:    '流通市值 (亿)',
    cand_col_reason:    '要点',
    cand_empty_title:   '没有符合条件的候选股',
    cand_empty_hint:    '尝试放宽筛选条件',
    cand_loading_error: '加载失败',
    cand_akshare_label: 'AKShare 抓取：',
    cand_request_label: '本次请求：',

    // Ranking page
    rank_title:         '信号排名',
    rank_col_rank:      '#',
    rank_col_code:      '代码',
    rank_col_name:      '名称',
    rank_col_market:    '市场',
    rank_col_signals:   '信号数',
    rank_col_score:     '得分',
    rank_filter_market: '市场',
    rank_filter_all:    '全部',
    rank_empty:         '暂无信号',

    // Search page
    search_placeholder: '按名称或代码搜索…',
    search_col_code:    '代码',
    search_col_name:    '名称',
    search_col_market:  '市场',
    search_empty:       '暂无结果',

    // Dashboard page
    dash_title:          '仪表盘',
    dash_panel_overview: '概览',
    dash_panel_recent:   '最新信号',

    // Compare page
    compare_title:           '对比',
    compare_hint:            '添加公司进行对比',
    compare_add_placeholder: '输入代码如 CN:000001',

    // Reports page
    reports_title: '报告',
    reports_hint:  '选择公司生成报告',

    // Settings page
    settings_title:     '设置',
    settings_api_label: 'API 基础地址',
    settings_save:      '保存',
    settings_saved:     '已保存',

    // Footer
    footer_data_source: '数据来源：后端 API',
    footer_base_url:    '基础地址：',

    // Company page
    company_back:               '← 返回',
    company_signals:            '信号',
    company_overview:           '概览',
    company_graph:              '供应链图谱',
    company_no_graph:           '暂无图谱数据',
    company_financial_signals:  '财务信号',
    company_governance_signals: '治理信号',
    company_ai_report:          'AI 风险报告',
    btn_copy:                   '复制',
    company_report_empty:       '尚未生成报告',
    company_report_hint:        '点击「生成报告」为该公司创建 AI 风险分析。',
  },
};

/* ── Core helpers ─────────────────────────────────────────────── */

function getLang() {
  return localStorage.getItem('fsm_lang') || 'en';
}

function applyLang(lang) {
  document.documentElement.lang = lang === 'zh' ? 'zh-CN' : 'en';

  // Replace textContent for data-i18n elements
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.getAttribute('data-i18n');
    const val = I18N[lang]?.[key];
    if (val !== undefined) el.textContent = val;
  });

  // Replace placeholder for data-i18n-placeholder elements
  document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
    const key = el.getAttribute('data-i18n-placeholder');
    const val = I18N[lang]?.[key];
    if (val !== undefined) el.placeholder = val;
  });

  // Update toggle button label
  const btn = document.getElementById('langToggleBtn');
  if (btn) btn.textContent = lang === 'zh' ? 'EN' : '中文';

  localStorage.setItem('fsm_lang', lang);
  window._currentLang = lang;
}

/* ── Bootstrap on DOMContentLoaded ──────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  applyLang(getLang());
  const btn = document.getElementById('langToggleBtn');
  if (btn) {
    btn.addEventListener('click', () => {
      applyLang(getLang() === 'zh' ? 'en' : 'zh');
    });
  }
});
