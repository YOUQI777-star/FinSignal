'use strict';

/* ============================================================
   FinSignal i18n — ZH / EN toggle
   Usage:  applyLang('zh') | applyLang('en')
           getLang()  → current lang string
   ============================================================ */

const I18N = {
  en: {
    // Nav / Sidebar
    nav_dashboard:      'Dashboard',
    nav_home:           'Home',
    nav_discover:       'Discover',
    nav_deep_dive:      'Deep Dive',
    nav_signal_ranking: 'Signal Ranking',
    nav_company_search: 'Company Search',
    nav_compare:        'Compare',
    nav_reports:        'AI Report',
    nav_candidates:     'Candidates',
    nav_system:         'System',
    nav_settings:       'Settings',
    health_connecting:  'Connecting…',
    health_connected:   'API Connected',
    health_offline:     'API Offline',

    // Page titles / crumbs
    page_title_fsm:   'Financial Signal Monitor',
    page_dashboard:   'Dashboard',
    page_home_crumb:  'Home',
    page_ranking:     'Signal Ranking',
    page_search:      'Company Search',
    page_compare:     'Compare',
    page_reports:     'Reports',
    page_candidates:  'Turnover Candidates',
    page_settings:    'Settings',
    rank_crumb:       'Full List',
    search_crumb:     'Search by name or code',

    // Buttons
    btn_refresh:  'Refresh',
    btn_apply:    'Apply',
    btn_reset:    'Reset',
    btn_search:   'Search',
    btn_generate: 'Generate Report',
    btn_add:      'Add',
    btn_clear:    'Clear',
    btn_export:   'Export',
    btn_compare:  'Compare',
    btn_copy:     'Copy',
    btn_recheck:  'Re-check',

    // Loading / status
    loading_text:    'Loading',
    searching_text:  'Searching',
    generating_text: 'Generating…',

    // Dropdown options
    opt_all_markets:  'All Markets',
    opt_all_rules:    'All Rules',
    opt_select_market:'Select market…',

    // Dashboard page
    dash_title:             'Dashboard',
    dash_panel_overview:    'Overview',
    dash_panel_recent:      'Recent Signals',
    dash_cn_companies:      'CN Companies',
    dash_tw_companies:      'TW Companies',
    dash_triggered_companies: 'Triggered Companies',
    dash_rules_covered:     'Rules Covered',
    dash_rule_distribution: 'Rule Distribution',
    dash_recently_viewed:   'Recently Viewed',
    dash_quick_actions:     'Quick Actions',
    dash_compare_companies: 'Compare Companies',
    dash_no_recent:         'No recent history',
    dash_deep_dive_title:   'Deep Dive',
    home_candidates_count:  'Today Candidates',
    home_candidates_cta:    'Go to Candidates →',
    home_high_risk_count:   'High-Risk Companies',
    home_high_risk_cta:     'View Rankings →',
    home_cn_coverage:       'A-Share Coverage',
    home_rules_covered:     'Rules Covered',
    home_candidate_preview: 'Candidate Snapshot',
    home_candidate_preview_hint: 'Today’s active preview. Click to open company details.',

    // Portal cards (Homepage)
    portal_discover_label:   'Discover',
    portal_risk_label:       'Risk Check',
    portal_candidates_title: 'Candidate Discovery',
    portal_candidates_desc:  'Discover active stocks from market turnover data, then screen with financial signals',
    portal_candidates_cta:   'Go to Candidates →',
    portal_ranking_title:    'Risk Rankings',
    portal_ranking_desc:     'Companies flagged by 6 financial and governance rules, sorted by signal count',
    portal_ranking_cta:      'View Rankings →',

    // Ranking page
    rank_title:             'Signal Ranking',
    rank_filter_placeholder:'Filter by name or code…',
    rank_col_rank:          '#',
    rank_col_code:          'Code',
    rank_col_name:          'Name',
    rank_col_market:        'Market',
    rank_col_signals:       'Signals',
    rank_col_score:         'Score',
    rank_filter_market:     'Market',
    rank_filter_all:        'All',
    rank_empty:             'No signals found',

    // Search page
    search_placeholder:    'Search by name or code…',
    search_results_title:  'Results',
    search_initial_title:  'Search for a company',
    search_initial_hint:   'Enter a name or stock code above. Supports CN A-shares and TW stocks.',
    search_col_code:       'Code',
    search_col_name:       'Name',
    search_col_market:     'Market',
    search_empty:          'No results',

    // Compare page
    compare_title:            'Compare',
    compare_hint:             'Add companies to compare',
    compare_add_placeholder:  'Enter code e.g. CN:000001',
    cmp_select_title:         'Select Companies',
    cmp_select_hint:          'Enter 2–5 company IDs separated by commas',
    cmp_preset_moutai:        'Moutai · TSMC · Vanke',
    cmp_preset_cn:            '3 CN stocks',
    cmp_preset_tw:            '3 TW stocks',
    cmp_empty_title:          'No comparison yet',
    cmp_empty_hint:           'Enter company IDs above and click Compare',
    label_quick_examples:     'Quick examples:',

    // Reports page
    reports_title:       'Reports',
    reports_hint:        'Select a company to generate a report',
    page_crumb_ai_report:'AI Risk Analysis',
    rpt_generate_title:  'Generate Report',
    rpt_generate_hint:   'Select a company to run an AI risk analysis',
    label_market:        'Market',
    label_code:          'Code',
    label_company:       'Company',
    opt_select_market:   'Select market…',
    rpt_ai_report_title: 'AI Risk Report',
    rpt_empty_title:     'No report generated yet',
    rpt_empty_hint:      'Select a company and click Generate Report',

    // Settings page
    settings_title:        'Settings',
    settings_api_label:    'API Base URL',
    settings_save:         'Save',
    settings_saved:        'Saved',
    stg_api_title:         'API Connection',
    stg_api_hint:          'Backend server configuration',
    stg_base_url:          'Base URL',
    stg_base_url_hint:     'All API calls are sent to this address',
    stg_conn_status:       'Connection Status',
    stg_conn_status_hint:  'Live health check result',
    stg_display_title:     'Display',
    stg_display_hint:      'Table and list preferences',
    stg_row_limit_label:   'Default Row Limit',
    stg_row_limit_hint:    'Number of rows loaded on the ranking and dashboard pages',
    stg_rows_20:           '20 rows',
    stg_rows_50:           '50 rows',
    stg_rows_100:          '100 rows',
    stg_rows_200:          '200 rows',
    stg_market_label:      'Default Market',
    stg_market_hint:       'Pre-selected market filter when pages load',
    stg_save_display:      'Save Display Settings',
    stg_local_data_title:  'Local Data',
    stg_local_data_hint:   'Browser storage management',
    stg_recent_label:      'Recently Viewed',
    stg_recent_hint:       'Stored in localStorage',
    stg_clear_history:     'Clear History',
    stg_about_title:       'About',
    stg_about_version:     'Version',
    stg_about_markets:     'Markets',
    stg_about_markets_val: 'CN A-Share · TW Stock Exchange',
    stg_about_rules:       'Signal Rules',
    stg_about_cn_cov:      'CN Coverage',
    stg_about_cn_cov_val:  '5,502 companies',
    stg_about_tw_cov:      'TW Coverage',
    stg_about_tw_cov_val:  '1,081 companies',
    stg_about_backend:     'Backend',

    // Candidates page
    cand_filter_title:   'Filters',
    cand_table_title:    'Candidate Stocks',
    cand_turnover_range_label: '< Today Turnover% <',
    cand_price_label:    'Price <',
    cand_circmv_label:   'Circ. MktCap <',
    cand_circmv_hint:    'Circ. MktCap = tradable listed shares only',
    cand_pct_label:      'Today Change <',
    cand_exclude_st:     'Exclude ST',
    cand_unit_pct:       '%',
    cand_unit_yuan:      '¥',
    cand_unit_yi:        'bn',
    cand_col_code:       'Code',
    cand_col_name:       'Name',
    cand_col_price:      'Current Price (¥)',
    cand_col_turnover:   'Today Turnover%',
    cand_col_pct:        'Today Change%',
    cand_col_circmv:     'Circ. MktCap (bn)',
    cand_col_reason:     'Notes',
    cand_empty_title:    'No candidates found',
    cand_empty_hint:     'Try relaxing the filters',
    cand_loading_error:  'Load failed',
    cand_trading_date_label: 'Trading Date:',
    cand_akshare_label:  'AKShare fetch:',
    cand_request_label:  'This request:',

    // Footer
    footer_data_source: 'Data source: backend API',
    footer_base_url:    'Base URL:',
    footer_markets:     'CN + TW Markets',

    // Company page
    company_back:               '← Back',
    company_signals:            'Signals',
    company_overview:           'Overview',
    company_graph:              'Supply Chain Graph',
    company_no_graph:           'No graph data available',
    company_financial_signals:  'Financial Signals',
    company_governance_signals: 'Governance Signals',
    company_ai_report:          'AI Risk Report',
    company_report_empty:       'No report generated yet',
    company_report_hint:        'Click "Generate Report" to create an AI risk analysis for this company.',
    company_turnover_history:   'Turnover History',
    company_turnover_history_hint: 'View turnover-rate changes for a single stock over time.',

    // Auth
    auth_login:          'Login',
    auth_register:       'Register',
    auth_login_register: 'Login / Register',
    auth_logout:         'Logout',
    auth_email:          'Email',
    auth_password:       'Password',
    auth_favorites:      'Saved Stocks',
    auth_no_favorites:   'No favorites yet',
    auth_add_favorite:   'Click the favorite button on any company page',
    auth_save:           'Save',
    auth_saved:          'Saved',
  },

  zh: {
    // Nav / Sidebar
    nav_dashboard:      '仪表盘',
    nav_home:           '首页',
    nav_discover:       '发现',
    nav_deep_dive:      '深入分析',
    nav_signal_ranking: '信号排名',
    nav_company_search: '公司搜索',
    nav_compare:        '多股对比',
    nav_reports:        'AI 报告',
    nav_candidates:     '候选池',
    nav_system:         '系统',
    nav_settings:       '设置',
    health_connecting:  '连接中…',
    health_connected:   'API 已连接',
    health_offline:     'API 离线',

    // Page titles / crumbs
    page_title_fsm:   '财务信号监控平台',
    page_dashboard:   '仪表盘',
    page_home_crumb:  '首页',
    page_ranking:     '信号排名',
    page_search:      '公司搜索',
    page_compare:     '对比',
    page_reports:     '报告',
    page_candidates:  '持续换手候选池',
    page_settings:    '设置',
    rank_crumb:       '完整列表',
    search_crumb:     '按名称或代码搜索',

    // Buttons
    btn_refresh:  '刷新',
    btn_apply:    '应用',
    btn_reset:    '重置',
    btn_search:   '搜索',
    btn_generate: '生成报告',
    btn_add:      '添加',
    btn_clear:    '清除',
    btn_export:   '导出',
    btn_compare:  '对比',
    btn_copy:     '复制',
    btn_recheck:  '重新检测',

    // Loading / status
    loading_text:    '加载中',
    searching_text:  '搜索中',
    generating_text: '生成中…',

    // Dropdown options
    opt_all_markets:  '全部市场',
    opt_all_rules:    '全部规则',
    opt_select_market:'选择市场…',

    // Dashboard page
    dash_title:             '仪表盘',
    dash_panel_overview:    '概览',
    dash_panel_recent:      '最新信号',
    dash_cn_companies:      'A股公司',
    dash_tw_companies:      '台股公司',
    dash_triggered_companies: '触发信号公司',
    dash_rules_covered:     '覆盖规则数',
    dash_rule_distribution: '规则分布',
    dash_recently_viewed:   '最近浏览',
    dash_quick_actions:     '快捷操作',
    dash_compare_companies: '对比公司',
    dash_no_recent:         '暂无浏览记录',
    dash_deep_dive_title:   '深入分析',
    home_candidates_count:  '今日候选池',
    home_candidates_cta:    '进入候选池 →',
    home_high_risk_count:   '高风险公司',
    home_high_risk_cta:     '查看排名 →',
    home_cn_coverage:       'A 股覆盖',
    home_rules_covered:     '覆盖规则',
    home_candidate_preview: '候选池摘要',
    home_candidate_preview_hint: '今日活跃预览，点击进入公司详情',

    // Portal cards (Homepage)
    portal_discover_label:   '发现',
    portal_risk_label:       '排雷',
    portal_candidates_title: '候选发现',
    portal_candidates_desc:  '从市场换手行为发现活跃标的，叠加财务与治理信号做排雷',
    portal_candidates_cta:   '进入候选池 →',
    portal_ranking_title:    '风险排行',
    portal_ranking_desc:     '被 6 条财务与治理规则标记的公司，按触发信号数量排序',
    portal_ranking_cta:      '查看排名 →',

    // Ranking page
    rank_title:             '信号排名',
    rank_filter_placeholder:'按名称或代码筛选…',
    rank_col_rank:          '#',
    rank_col_code:          '代码',
    rank_col_name:          '名称',
    rank_col_market:        '市场',
    rank_col_signals:       '信号数',
    rank_col_score:         '得分',
    rank_filter_market:     '市场',
    rank_filter_all:        '全部',
    rank_empty:             '暂无信号',

    // Search page
    search_placeholder:    '按名称或代码搜索…',
    search_results_title:  '搜索结果',
    search_initial_title:  '搜索公司',
    search_initial_hint:   '在上方输入名称或股票代码，支持 A 股和台股。',
    search_col_code:       '代码',
    search_col_name:       '名称',
    search_col_market:     '市场',
    search_empty:          '暂无结果',

    // Compare page
    compare_title:            '对比',
    compare_hint:             '添加公司进行对比',
    compare_add_placeholder:  '输入代码如 CN:000001',
    cmp_select_title:         '选择公司',
    cmp_select_hint:          '输入 2–5 个公司 ID，用逗号分隔',
    cmp_preset_moutai:        '茅台 · 台积电 · 万科',
    cmp_preset_cn:            '3支A股',
    cmp_preset_tw:            '3支台股',
    cmp_empty_title:          '尚未对比',
    cmp_empty_hint:           '在上方输入公司 ID 并点击对比',
    label_quick_examples:     '快速示例：',

    // Reports page
    reports_title:       '报告',
    reports_hint:        '选择公司生成报告',
    page_crumb_ai_report:'AI 风险分析',
    rpt_generate_title:  '生成报告',
    rpt_generate_hint:   '选择公司进行 AI 风险分析',
    label_market:        '市场',
    label_code:          '代码',
    label_company:       '公司',
    opt_select_market:   '选择市场…',
    rpt_ai_report_title: 'AI 风险报告',
    rpt_empty_title:     '尚未生成报告',
    rpt_empty_hint:      '选择公司后点击「生成报告」',

    // Settings page
    settings_title:        '设置',
    settings_api_label:    'API 基础地址',
    settings_save:         '保存',
    settings_saved:        '已保存',
    stg_api_title:         'API 连接',
    stg_api_hint:          '后端服务器配置',
    stg_base_url:          '基础地址',
    stg_base_url_hint:     '所有 API 请求均发送至此地址',
    stg_conn_status:       '连接状态',
    stg_conn_status_hint:  '实时健康检测结果',
    stg_display_title:     '显示设置',
    stg_display_hint:      '表格与列表偏好',
    stg_row_limit_label:   '默认行数限制',
    stg_row_limit_hint:    '排名页和仪表盘页默认加载的行数',
    stg_rows_20:           '20 行',
    stg_rows_50:           '50 行',
    stg_rows_100:          '100 行',
    stg_rows_200:          '200 行',
    stg_market_label:      '默认市场',
    stg_market_hint:       '页面加载时预选的市场筛选',
    stg_save_display:      '保存显示设置',
    stg_local_data_title:  '本地数据',
    stg_local_data_hint:   '浏览器存储管理',
    stg_recent_label:      '最近浏览',
    stg_recent_hint:       '存储于 localStorage',
    stg_clear_history:     '清除历史',
    stg_about_title:       '关于',
    stg_about_version:     '版本',
    stg_about_markets:     '市场',
    stg_about_markets_val: 'A 股 · 台湾交易所',
    stg_about_rules:       '信号规则',
    stg_about_cn_cov:      'A 股覆盖',
    stg_about_cn_cov_val:  '5,502 家公司',
    stg_about_tw_cov:      '台股覆盖',
    stg_about_tw_cov_val:  '1,081 家公司',
    stg_about_backend:     '后端',

    // Candidates page
    cand_filter_title:   '筛选条件',
    cand_table_title:    '候选股票',
    cand_turnover_range_label: '< 今日换手% <',
    cand_price_label:    '现价 <',
    cand_circmv_label:   '流通市值 <',
    cand_circmv_hint:    '流通市值 = 可上市流通部分对应市值',
    cand_pct_label:      '今日涨幅 <',
    cand_exclude_st:     '排除 ST',
    cand_unit_pct:       '%',
    cand_unit_yuan:      '元',
    cand_unit_yi:        '亿',
    cand_col_code:       '代码',
    cand_col_name:       '名称',
    cand_col_price:      '现价 (元)',
    cand_col_turnover:   '今日换手%',
    cand_col_pct:        '今日涨幅%',
    cand_col_circmv:     '流通市值 (亿)',
    cand_col_reason:     '要点',
    cand_empty_title:    '没有符合条件的候选股',
    cand_empty_hint:     '尝试放宽筛选条件',
    cand_loading_error:  '加载失败',
    cand_trading_date_label: '对应交易日：',
    cand_akshare_label:  'AKShare 抓取：',
    cand_request_label:  '本次请求：',

    // Footer
    footer_data_source: '数据来源：后端 API',
    footer_base_url:    '基础地址：',
    footer_markets:     'CN + TW 市场',

    // Company page
    company_back:               '← 返回',
    company_signals:            '信号',
    company_overview:           '概览',
    company_graph:              '供应链图谱',
    company_no_graph:           '暂无图谱数据',
    company_financial_signals:  '财务信号',
    company_governance_signals: '治理信号',
    company_ai_report:          'AI 风险报告',
    company_report_empty:       '尚未生成报告',
    company_report_hint:        '点击「生成报告」为该公司创建 AI 风险分析。',
    company_turnover_history:   '历史换手率',
    company_turnover_history_hint: '查看单只股票最近一段时间的换手率变化。',

    // Auth
    auth_login:          '登录',
    auth_register:       '注册',
    auth_login_register: '登录 / 注册',
    auth_logout:         '退出登录',
    auth_email:          '邮箱',
    auth_password:       '密码',
    auth_favorites:      '收藏的股票',
    auth_no_favorites:   '还没有收藏',
    auth_add_favorite:   '在公司详情页点击收藏按钮',
    auth_save:           '收藏',
    auth_saved:          '已收藏',
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
