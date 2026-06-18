/** AI Company OS i18n — Chinese/English toggle */
window.__i18n = (function(){
  var lang = localStorage.getItem('aios_lang') || 'zh';
  var dict = {
    zh: {
      dashboard: '总览面板', commander: '指挥官', chat: 'AI 对话',
      cto: '技术审查', image: '图片生成', marketing: '营销内容',
      openclaw: 'OpenClaw 研究', skills: '技能库', templates: '场景模板',
      history: '运行记录', settings: '系统设置', ai_registry: '资源中心',
      agent_health: 'Agent 健康', api_calls: 'API 调用', total_tokens: '总Tokens',
      cost: '费用', cache_hit: '缓存命中', db_sessions: 'DB会话',
      memories: '记忆数', payments: '支付笔数', refresh: '刷新',
      execute: '执行', send: '发送', clear: '清空', new_chat: '新对话',
      loading: '加载中...', no_data: '暂无数据', confirm: '确定',
      cancel: '取消', save: '保存', delete: '删除',
      search: '搜索', deploy: '部署',
      onboarding_title: '欢迎来到 AI Company OS',
      onboarding_sub: '多智能体协作操作系统 — 告诉它做什么，自动拆解执行',
      onboarding_start: '开始使用',
      onboarding_skip: '跳过引导',
    },
    en: {
      dashboard: 'Dashboard', commander: 'Commander', chat: 'AI Chat',
      cto: 'CTO Review', image: 'Image Gen', marketing: 'Marketing',
      openclaw: 'OpenClaw Research', skills: 'Skills', templates: 'Templates',
      history: 'History', settings: 'Settings', ai_registry: 'AI Registry',
      agent_health: 'Agent Health', api_calls: 'API Calls', total_tokens: 'Tokens',
      cost: 'Cost', cache_hit: 'Cache Hit', db_sessions: 'DB Sessions',
      memories: 'Memories', payments: 'Transactions', refresh: 'Refresh',
      execute: 'Execute', send: 'Send', clear: 'Clear', new_chat: 'New Chat',
      loading: 'Loading...', no_data: 'No Data', confirm: 'Confirm',
      cancel: 'Cancel', save: 'Save', delete: 'Delete',
      search: 'Search', deploy: 'Deploy',
      onboarding_title: 'Welcome to AI Company OS',
      onboarding_sub: 'Multi-Agent OS — tell it what to do, it decomposes and executes',
      onboarding_start: 'Get Started',
      onboarding_skip: 'Skip',
    }
  };
  return {
    t: function(key) { return (dict[lang]||dict.zh)[key] || key; },
    setLang: function(l) { lang = l; localStorage.setItem('aios_lang', l); location.reload(); },
    getLang: function() { return lang; }
  };
})();
var t = window.__i18n.t;
