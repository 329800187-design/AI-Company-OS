// ========== 路由 ==========
function switchPage(page) {
  document.querySelectorAll('.page').forEach(p => {p.classList.remove('active');p.classList.remove('active-flex')});
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  var el = document.getElementById('page-' + page);
  if (!el) return;
  el.classList.add('active');
  if (page === 'chat') el.classList.add('active-flex');
  var nav = document.querySelector('.nav-item[data-page="' + page + '"]');
  if (nav) nav.classList.add('active');
}

// ========== 工具函数 ==========
const BASE = location.origin || 'http://localhost:8000';
function escapeHtml(text) {
  if (!text) return '';
  const d = document.createElement('div');
  d.textContent = text;
  return d.innerHTML;
}
function showToast(msg, type='info') {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.className = 'toast toast-' + type + ' show';
  setTimeout(() => t.classList.remove('show'), 3000);
}
function copyText(t) {
  navigator.clipboard.writeText(t).then(() => showToast('已复制: ' + t, 'success')).catch(() => {});
}

// ========== Dashboard 状态 ==========
async function checkStatus() {
  try {
    const r = await fetch(BASE + '/');
    const d = await r.json();
    document.getElementById('dash-status').textContent = '✅ ' + (d.status || '运行中');
  } catch(e) {
    document.getElementById('dash-status').textContent = '❌ 无法连接';
  }
  try {
    const r = await fetch(BASE + '/commander/sessions');
    const d = await r.json();
    document.getElementById('dash-sessions').textContent = d.count || 0;
  } catch(e) {}
  try {
    const r = await fetch(BASE + '/tasks/');
    const d = await r.json();
    document.getElementById('dash-tasks').textContent = Array.isArray(d) ? d.length : 0;
  } catch(e) {}
}
checkStatus();

// ========== 格式化 JSON ==========
function formatJSON(obj) {
  return JSON.stringify(obj, null, 2)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
    .replace(/"([^"]+)":/g, '<span class="key">"$1"</span>:')
    .replace(/"([^"]*?)"/g, (m, g) => {
      if (m.startsWith('<span')) return m;
      return '<span class="string">"' + g + '"</span>';
    })
    .replace(/\b(\d+)\b/g, '<span class="number">$1</span>');
}

function showResult(elementId, data) {
  const el = document.getElementById(elementId);
  el.innerHTML = formatJSON(data);
  el.classList.add('show');
}

// ========== Global Event Bus (模块 → 指挥官) ==========
var _commanderEvents = [];
function postToCommander(event) {
  event.time = new Date().toLocaleTimeString();
  _commanderEvents.unshift(event);
  if (_commanderEvents.length > 50) _commanderEvents.length = 50;
  renderActivityFeed();
}
function renderActivityFeed() {
  var feed = document.getElementById('cmd-activity-feed');
  if (!feed) return;
  if (!_commanderEvents.length) {
    feed.innerHTML = '<div class="empty" style="padding:20px"><p>等待执行任务...</p></div>';
    return;
  }
  var html = '';
  _commanderEvents.forEach(function(e) {
    var icon = e.module === 'commander' ? '🧠' : e.module === 'codex' ? '💻' : e.module === 'openclaw' ? '🌐' : e.module === 'system' ? '🖥️' : e.module === 'template' ? '📋' : e.module === 'ai-registry' ? '🧩' : '🤖';
    var cls = e.status === 'ok' ? 'done' : e.status === 'error' ? 'fail' : 'active';
    html += '<div style="display:flex;align-items:center;gap:8px;padding:6px 8px;margin:2px 0;background:var(--bg);border-radius:6px;font-size:12px">';
    html += '<span>' + icon + '</span>';
    html += '<span style="width:8px;height:8px;border-radius:50%;background:var(--'+ (cls==='done'?'green':cls==='fail'?'red':'yellow') +');flex-shrink:0"></span>';
    html += '<span style="flex:1">' + escapeHtml(e.desc || '') + '</span>';
    html += '<span style="color:var(--text2);font-size:10px">' + escapeHtml(e.module) + '</span>';
    html += '<span style="color:var(--text2);font-size:10px">' + (e.time||'') + '</span>';
    html += '</div>';
  });
  feed.innerHTML = html;
}

// ========== Commander Pipeline ==========

function resetPipeline() {
  document.getElementById('cmd-pipeline').style.display = 'none';
  document.getElementById('cmd-error').style.display = 'none';
  document.getElementById('cmd-input-card').style.display = 'block';
  ['phase-decompose','phase-execute','phase-result'].forEach(function(id) {
    var el = document.getElementById(id);
    el.classList.remove('active-phase','done-phase','error-phase');
  });
  document.getElementById('phase1-status').textContent = '...';
  document.getElementById('phase2-status').textContent = '...';
  document.getElementById('phase3-status').textContent = '...';
  document.getElementById('cmd-progress-bar').style.width = '0%';
  document.getElementById('cmd-steps-live').innerHTML = '';
  document.getElementById('cmd-final-result').innerHTML = '';
  document.getElementById('cmd-run-btn').disabled = false;
}

function setPhase(phaseId, status) {
  // status: 'active' | 'done' | 'error'
  const el = document.getElementById(phaseId);
  el.classList.remove('active-phase','done-phase','error-phase');
  if (status === 'active') el.classList.add('active-phase');
  else if (status === 'done') el.classList.add('done-phase');
  else if (status === 'error') el.classList.add('error-phase');
}

function addLiveStep(stepNum, description, agent, status) {
  const container = document.getElementById('cmd-steps-live');
  // Check if step already exists
  let el = container.querySelector(`[data-step-num="${stepNum}"]`);
  if (!el) {
    el = document.createElement('div');
    el.className = 'step-live-item';
    el.setAttribute('data-step-num', stepNum);
    container.appendChild(el);
  }
  const icon = agent === 'codex' ? '💻' : agent === 'openclaw' ? '🌐' :
               agent === 'system' ? '🖥️' : agent === 'qa' ? '✅' :
               agent === 'ceo' ? '🧩' : '🤖';
  const dotClass = status === 'running' ? 'running' : status === 'ok' ? 'done' : 'fail';
  const statusText = status === 'running' ? '执行中...' : status === 'ok' ? '✓' : '✗';
  el.innerHTML = `<span class="step-dot ${dotClass}"></span>
    <span>${icon}</span>
    <span style="flex:1"><strong>步骤${stepNum}:</strong> ${escapeHtml(description || '')}</span>
    <span style="font-size:11px;color:var(--text2)">${agent||''}</span>
    <span style="font-size:12px">${statusText}</span>`;
}

async function runCommanderPipeline() {
  var goal = document.getElementById('cmd-goal').value.trim();
  if (!goal) { showToast('请输入目标', 'error'); return; }

  resetPipeline();
  document.getElementById('cmd-input-card').style.display = 'none';
  document.getElementById('cmd-pipeline').style.display = 'block';
  document.getElementById('cmd-run-btn').disabled = true;

  postToCommander({module:'commander',status:'running',desc:goal});

  // Phase 1
  setPhase('phase-decompose', 'active');
  document.getElementById('phase1-status').textContent = '正在分析目标...';

  try {
    var r = await fetch(BASE + '/commander/run-async', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({"目标": goal})
    });
    var data = await r.json();

    if (data.status === '失败') { throw new Error(data.message || '拆解失败'); }

    var taskId = data.task_id;
    var sessionId = data.session_id;
    window._exportSessionId = sessionId;

    setPhase('phase-decompose', 'done');
    document.getElementById('phase1-status').textContent = '已拆解';

    setPhase('phase-execute', 'active');
    document.getElementById('phase2-status').textContent = '执行中...';

    var wsDone = false, finalResult = null, totalSteps = 0;
    var wsUrl = 'ws://' + location.host + '/ws/task/' + taskId;
    var authToken = document.getElementById('cfg-auth-token').value;
    if (authToken) { wsUrl += '?token=' + encodeURIComponent(authToken); }
    var ws = new WebSocket(wsUrl);

    ws.onopen = function() { document.getElementById('phase2-status').textContent = 'Agent 工作中...'; };
    ws.onmessage = function(event) {
      var msg = JSON.parse(event.data);
      if (msg.type === 'step_start') {
        totalSteps = msg.total_steps || totalSteps;
        addLiveStep(msg.step, msg.description, msg.agent, 'running');
        document.getElementById('phase2-status').textContent = '步骤 ' + msg.step + '/' + (totalSteps||'?');
      } else if (msg.type === 'step_done') {
        totalSteps = msg.total_steps || totalSteps;
        var ok = msg.status === '已完成';
        addLiveStep(msg.step, msg.description, msg.agent, ok ? 'ok' : 'fail');
        document.getElementById('cmd-progress-bar').style.width = (totalSteps ? Math.round(msg.step/totalSteps*100) : 50) + '%';
        document.getElementById('phase2-status').textContent = '步骤 ' + msg.step + '/' + totalSteps + (ok ? ' OK' : ' FAIL');
      } else if (msg.type === 'summary') {
        // summary 先缓存，不关 WebSocket，等 task_completed
        finalResult = msg;
        // 提前展示摘要
        var s = msg.summary || '';
        if (s) { document.getElementById('cmd-final-result').innerHTML = '<div class="result-md"><pre style="white-space:pre-wrap;font-size:13px">' + escapeHtml(s) + '</pre></div>'; }
      } else if (msg.type === 'task_completed') {
        // 如果 summary 事件先到了，合并到 task_completed 的 result 里
        if (finalResult && finalResult.type === 'summary' && msg.result) {
          if (!msg.result.summary) msg.result.summary = finalResult.summary;
          if (!msg.result.results || msg.result.results.length===0) msg.result.results = finalResult.results || [];
        }
        wsDone = true; finalResult = msg; ws.close();
      } else if (msg.type === 'task_failed') {
        wsDone = true; finalResult = msg; ws.close();
      } else if (msg.type === 'task_status') {
        document.getElementById('phase2-status').textContent = msg.status || '排队中...';
      }
    };
    ws.onerror = function() { document.getElementById('phase2-status').textContent = 'WebSocket 中断，尝试轮询...'; };
    ws.onclose = function() {
      if (wsDone && finalResult) { finishPipeline(finalResult); }
      else if (finalResult && finalResult.type === 'summary') {
        // WebSocket 断了但有 summary 缓存，等轮询补齐 task_completed
        document.getElementById('phase2-status').textContent = 'WS断开，轮询最终结果...';
        pollForResult(taskId, 0);
      }
      else if (!wsDone) { pollForResult(taskId, 0); }
    };
    // 8秒兜底：WS 连上但没有任何消息过来 → 强制轮询
    setTimeout(function() {
      if (!wsDone && !finalResult) {
        document.getElementById('phase2-status').textContent = '等候超时，轮询任务状态...';
        pollForResult(taskId, 0);
      }
    }, 8000);
  } catch(e) { showPipelineError(e.message); }
}

function pollForResult(taskId, attempt) {
  if (attempt > 60) { showPipelineError('轮询超时（60次），任务可能仍在执行'); return; }
  fetch(BASE + '/commander/tasks/' + taskId).then(function(r) { return r.json(); }).then(function(task) {
    // 轮询结果格式：{task_id, status:'queued|running|completed|failed', result:{status,summary,results}, error}
    if (task.status === 'completed' && task.result) {
      finishPipeline({type:'task_completed', result: task.result});
    } else if (task.status === 'failed') {
      showPipelineError(task.error || task.result?.error || '执行失败');
    } else if (task.status === 'queued' || task.status === 'running') {
      document.getElementById('phase2-status').textContent = '轮询 ' + (attempt+1) + ' (' + task.status + ')';
      setTimeout(function() { pollForResult(taskId, attempt+1); }, 1500);
    } else {
      // 未知状态，继续等
      document.getElementById('phase2-status').textContent = '轮询 ' + (attempt+1) + ' (' + (task.status||'?') + ')';
      setTimeout(function() { pollForResult(taskId, attempt+1); }, 1500);
    }
  }).catch(function() { setTimeout(function() { pollForResult(taskId, attempt+1); }, 2000); });
}

function finishPipeline(finalResult) {
  // 兼容三种数据来源：
  //   1. WebSocket task_completed: {type:'task_completed', status, result:{status,summary,results}}
  //   2. WebSocket summary: {type:'summary', summary, results}
  //   3. 轮询 pollForResult: {type:'task_completed', result:{status,summary,results}}
  //   4. WebSocket task_failed: {type:'task_failed', error}

  if (finalResult.type === 'task_failed') {
    setPhase('phase-execute', 'error');
    setPhase('phase-result', 'error');
    document.getElementById('phase2-status').textContent = '执行失败';
    document.getElementById('phase3-status').textContent = '失败';
    showPipelineError(finalResult.error || '未知错误');
    return;
  }

  setPhase('phase-execute', 'done');
  document.getElementById('cmd-progress-bar').style.width = '100%';
  document.getElementById('phase2-status').textContent = '全部完成';

  setPhase('phase-result', 'active');
  document.getElementById('phase3-status').textContent = '生成报告...';

  // 提取内层数据：task_completed 事件有嵌套 result，summary 事件是平铺
  var inner = finalResult.result || finalResult;
  var finalStatus = inner.status || finalResult.status || 'completed';
  var summary = inner.summary || finalResult.summary || '';
  var results = inner.results || finalResult.results || [];
  var goal = document.getElementById('cmd-goal').value.trim();

  if (summary) {
    var html = '<div class="result-md">';
    var lines = summary.split('\n');
    for (var i = 0; i < lines.length; i++) {
      var t = lines[i].trim();
      if (!t) { html += '<br>'; continue; }
      if (t.indexOf('✅')===0 || t.indexOf('❌')===0) html += '<h3>' + escapeHtml(t) + '</h3>';
      else if (t.indexOf('- ')==0 || t.indexOf('• ')==0) html += '<div style="padding:3px 8px;margin:2px 0;background:rgba(59,130,246,.06);border-radius:6px;font-size:13px">' + escapeHtml(t) + '</div>';
      else html += '<p style="margin:2px 0;color:var(--text2);font-size:13px">' + escapeHtml(t) + '</p>';
    }
    html += '</div>';
    document.getElementById('cmd-final-result').innerHTML = html;
  } else if (results.length > 0) {
    var h = '<div class="result-md"><h3>完成</h3><ul>';
    for (var j = 0; j < results.length; j++) {
      var r = results[j];
      var txt = typeof r.result === 'string' ? r.result.slice(0,100) : (r.result && r.result.result ? String(r.result.result).slice(0,100) : '完成');
      h += '<li>步骤'+(r.step||'')+': '+escapeHtml(txt)+'</li>';
    }
    h += '</ul></div>';
    document.getElementById('cmd-final-result').innerHTML = h;
  } else {
    document.getElementById('cmd-final-result').innerHTML = '<p style="color:var(--green);font-size:14px">完成</p>';
  }

  setPhase('phase-result', 'done');
  document.getElementById('phase3-status').textContent = '完成';
  document.getElementById('cmd-run-btn').disabled = false;

  // Post to activity feed
  postToCommander({module:'commander',status:'ok',desc:goal + ' → 完成'});
}

function showPipelineError(msg) {
  setPhase('phase-execute', 'error');
  setPhase('phase-result', 'error');
  document.getElementById('cmd-pipeline').style.display = 'none';
  document.getElementById('cmd-error').style.display = 'block';
  document.getElementById('cmd-error-msg').textContent = msg || '未知错误';
  document.getElementById('cmd-run-btn').disabled = false;
  showToast('执行失败: ' + msg, 'error');
  // 3秒后隐藏错误区域，恢复输入框
  setTimeout(function() {
    document.getElementById('cmd-error').style.display = 'none';
  }, 10000);
}

// Session history is on the History page (/page-history), loaded via loadHistory()

// ========== 2. Codex ==========
async function runCodex() {
  const goal = document.getElementById('codex-goal').value;
  const code = document.getElementById('codex-code').value;
  const timeout = parseInt(document.getElementById('codex-timeout').value) || 15;

  if (!code) { showToast('请输入代码', 'error'); return; }

  document.getElementById('codex-loading').classList.add('show');
  document.getElementById('codex-result').style.display = 'none';

  try {
    const r = await fetch(BASE + '/agents/codex/run', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({type: goal ? 'code' : 'execute', goal: goal, code: code, language: 'python', timeout: timeout})
    });
    const data = await r.json();
    document.getElementById('codex-loading').classList.remove('show');
    document.getElementById('codex-result').style.display = 'block';

    const badge = document.getElementById('codex-status-badge');
    if (data.success) {
      badge.innerHTML = '<span class="badge badge-success">✅ 执行成功</span>';
    } else {
      badge.innerHTML = '<span class="badge badge-error">❌ 执行失败</span>';
    }

    const out = document.getElementById('codex-output');
    let html = '';
    if (data.stdout) html += '📤 标准输出:\n' + data.stdout + '\n\n';
    if (data.stderr) html += '⚠️ 错误输出:\n' + data.stderr + '\n\n';
    if (data.result && data.result !== data.stdout) html += '📋 结果:\n' + data.result + '\n';
    if (data.files_created && data.files_created.length > 0) html += '\n📁 创建的文件: ' + data.files_created.join(', ');
    out.textContent = html || JSON.stringify(data, null, 2);
    postToCommander({module:'codex',status:data.success!==false?'ok':'error',desc:'Codex: '+(goal||code).slice(0,60)});
  } catch(e) {
    document.getElementById('codex-loading').classList.remove('show');
    showToast('请求失败: ' + e.message, 'error');
    postToCommander({module:'codex',status:'error',desc:'Codex 执行失败'});
  }
}

// ========== 3. OpenClaw ==========
function switchOCTab(tab, btn) {
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
  btn.classList.add('active');
  document.getElementById('oc-' + tab).classList.add('active');
}

async function runOpenClaw(mode) {
  let url, taskType, payload;
  if (mode === 'scrape') {
    url = document.getElementById('oc-url-scrape').value.trim();
    taskType = 'browser_scrape';
    payload = {"目标URL": url, "任务类型": taskType, "提取类型": document.getElementById('oc-extract').value, "选择器": document.getElementById('oc-selector').value};
  } else if (mode === 'screenshot') {
    url = document.getElementById('oc-url-shot').value.trim();
    taskType = 'browser_screenshot';
    payload = {"目标URL": url, "任务类型": taskType, "选择器": document.getElementById('oc-shot-selector').value, "full_page": document.getElementById('oc-fullpage').value === 'true'};
  } else {
    url = document.getElementById('oc-url-test').value.trim();
    taskType = 'browser_test';
    const checks = [];
    if (document.getElementById('oc-chk-loaded').checked) checks.push({"type":"page_loaded"});
    if (document.getElementById('oc-chk-title').checked) checks.push({"type":"has_title"});
    if (document.getElementById('oc-chk-js').checked) checks.push({"type":"no_js_error"});
    payload = {"目标URL": url, "任务类型": taskType, "checks": checks};
  }

  if (!url) { showToast('请输入网址', 'error'); return; }

  document.getElementById('oc-loading').classList.add('show');
  document.getElementById('oc-result').style.display = 'none';

  try {
    const r = await fetch(BASE + '/agents/openclaw/run', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify(payload)
    });
    const data = await r.json();
    document.getElementById('oc-loading').classList.remove('show');
    document.getElementById('oc-result').style.display = 'block';
    document.getElementById('oc-status').innerHTML = `<span class="badge ${data.success ? 'badge-success' : 'badge-error'}">${data.status}</span>`;

    const out = document.getElementById('oc-output');
    if (mode === 'screenshot' && data.screenshot_path) {
      out.textContent = '截图已保存到: ' + data.screenshot_path + '\n页面标题: ' + (data.page_title || '无');
    } else if (mode === 'test') {
      let html = '';
      if (data.checks) {
        data.checks.forEach(c => {
          html += (c.passed ? '✅ ' : '❌ ') + c.check + ': ' + c.detail + '\n';
        });
      }
      html += `\n通过: ${data.passed_count}/${data.total_count}`;
      out.textContent = html;
    } else {
      if (data.data) {
        out.textContent = typeof data.data === 'string' ? data.data : JSON.stringify(data.data, null, 2).slice(0, 3000);
      } else {
        out.textContent = JSON.stringify(data, null, 2).slice(0, 3000);
      }
    }
    postToCommander({module:'openclaw',status:data.success!==false?'ok':'error',desc:'OpenClaw: '+url.slice(0,60)});
  } catch(e) {
    document.getElementById('oc-loading').classList.remove('show');
    showToast('请求失败: ' + e.message, 'error');
    postToCommander({module:'openclaw',status:'error',desc:'浏览器操作失败'});
  }
}

// ========== 4. CEO ==========
async function runCEO() {
  const goal = document.getElementById('ceo-goal').value.trim();
  if (!goal) { showToast('请输入目标', 'error'); return; }

  document.getElementById('ceo-loading').classList.add('show');
  document.getElementById('ceo-result').style.display = 'none';

  try {
    const r = await fetch(BASE + '/agents/ceo/run', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({"目标": goal})
    });
    const data = await r.json();
    document.getElementById('ceo-loading').classList.remove('show');
    document.getElementById('ceo-result').style.display = 'block';

    const mode = data.summary || '';
    document.getElementById('ceo-mode').innerHTML = mode.includes('AI') ? '<span class="badge badge-info">🤖 AI 智能拆解</span>' : '<span class="badge badge-warn">⚙️ 规则模式拆解</span>';

    const tasks = data.output?.created_tasks || [];
    const el = document.getElementById('ceo-tasks');
    if (tasks.length === 0) {
      el.innerHTML = '<div class="empty"><p>未生成任务</p></div>';
    } else {
      let html = `<p style="margin-bottom:8px">共生成 <b>${tasks.length}</b> 个子任务：</p>`;
      tasks.forEach((t, i) => {
        const agentEmoji = {codex_agent:'💻', openclaw_agent:'🌐', qa_agent:'✅', ceo_agent:'📋'};
        html += `<div class="step-item"><div class="step-num done">${i+1}</div>
          <div><div>${agentEmoji[t.assigned_to]||'📦'} [${t.task_type}] ${t.goal}</div>
          <div class="sub">分配给: ${t.assigned_to}</div></div></div>`;
      });
      el.innerHTML = html;
    }

    document.getElementById('ceo-raw').textContent = formatJSON(data);
  } catch(e) {
    document.getElementById('ceo-loading').classList.remove('show');
    showToast('请求失败: ' + e.message, 'error');
  }
}

// ========== 5. QA ==========
async function runQA() {
  const goal = document.getElementById('qa-goal').value.trim();
  const result = document.getElementById('qa-result').value.trim();
  let expected = {};
  try { expected = JSON.parse(document.getElementById('qa-expected').value); } catch(e) {}

  if (!goal) { showToast('请输入任务目标', 'error'); return; }

  document.getElementById('qa-loading').classList.add('show');
  document.getElementById('qa-result-box').style.display = 'none';

  try {
    const r = await fetch(BASE + '/agents/qa/run', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({"目标": goal, "结果": result, "期望产出": expected})
    });
    const data = await r.json();
    document.getElementById('qa-loading').classList.remove('show');
    document.getElementById('qa-result-box').style.display = 'block';

    const score = data.score || 0;
    const badge = document.getElementById('qa-score-badge');
    if (score >= 90) badge.innerHTML = '<span class="badge badge-success">✅ ' + score + '分 · 通过</span>';
    else if (score >= 70) badge.innerHTML = '<span class="badge badge-warn">⚠️ ' + score + '分 · 需复查</span>';
    else badge.innerHTML = '<span class="badge badge-error">❌ ' + score + '分 · 未通过</span>';

    let html = `<p><b>状态：</b>${data.status}</p>`;
    html += `<p><b>总结：</b>${data.summary}</p>`;
    if (data.problems && data.problems.length > 0) {
      html += '<p><b>发现的问题：</b></p><ul>';
      data.problems.forEach(p => html += `<li style="color:var(--red)">${p}</li>`);
      html += '</ul>';
    }
    document.getElementById('qa-detail').innerHTML = html;
    document.getElementById('qa-raw').textContent = formatJSON(data);
  } catch(e) {
    document.getElementById('qa-loading').classList.remove('show');
    showToast('请求失败: ' + e.message, 'error');
  }
}

// ========== 6. Tasks ==========
async function listTasks() {
  try {
    const r = await fetch(BASE + '/tasks/');
    const d = await r.json();
    const list = document.getElementById('tasks-list');
    document.getElementById('task-count').textContent = '共 ' + (Array.isArray(d) ? d.length : 0) + ' 个任务';

    if (!Array.isArray(d) || d.length === 0) {
      list.innerHTML = '<div class="empty"><div class="big">📭</div><p>暂无任务</p></div>';
      return;
    }
    let html = '';
    d.slice().reverse().forEach(t => {
      const s = t.status || t.状态 || '?';
      const badgeCls = s === '已完成' ? 'badge-success' : (s === '失败' ? 'badge-error' : 'badge-info');
      html += `<div class="step-item"><div class="step-num ${s === '已完成' ? 'done' : (s === '失败' ? 'fail' : 'active')}"></div>
        <div><div>${t.goal || t.目标 || '(无描述)'} <span class="badge ${badgeCls}" style="margin-left:8px">${s}</span></div>
        <div class="sub">${t.task_id || t.任务ID || ''} · ${t.assigned_to || t.分配给 || '?'}</div></div></div>`;
    });
    list.innerHTML = html;
  } catch(e) {}
}

// ========== 运行记录 ==========
async function loadHistory() {
  try {
    const r = await fetch(BASE + '/commander/sessions');
    const d = await r.json();
    const list = document.getElementById('history-list');
    const count = document.getElementById('history-count');
    if (count) count.textContent = '共 ' + (d.sessions ? d.sessions.length : 0) + ' 条';
    if (!d.sessions || d.sessions.length === 0) {
      if (list) list.innerHTML = '<div class="empty"><p>暂无运行记录</p></div>';
      return;
    }
    let html = '';
    d.sessions.slice(0, 50).forEach(function(s) {
      var sid = s.id || s.session_id || '';
      var title = s.goal || s.title || '无标题';
      var time = (s.created_at || '').slice(0, 16);
      var status = s.status || 'unknown';
      var sc = status === 'completed' ? 'var(--green)' : status === 'failed' ? 'var(--red)' : 'var(--yellow)';
      html += `<div style="display:flex;align-items:center;gap:10px;padding:10px 12px;margin:4px 0;background:var(--bg);border-radius:8px">
        <span class="dot" style="background:${sc};flex-shrink:0"></span>
        <span style="flex:1;font-size:13px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${escapeHtml(title.substring(0, 60))}</span>
        <span style="font-size:11px;color:var(--text2);flex-shrink:0">${escapeHtml(status)}</span>
        <span style="font-size:11px;color:var(--text2);flex-shrink:0">${time}</span>
        <button class="btn btn-sm btn-outline" onclick="deleteSession('${sid}')" style="flex-shrink:0;color:var(--red);border-color:var(--red);padding:2px 8px;font-size:11px">✕</button>
      </div>`;
    });
    if (list) list.innerHTML = html || '<div class="empty"><p>暂无记录</p></div>';
  } catch(e) {
    var list = document.getElementById('history-list');
    if (list) list.innerHTML = '<div class="empty"><p>加载失败</p></div>';
  }
}

async function deleteSession(sid) {
  if (!confirm('删除这条运行记录？')) return;
  try {
    await fetch(BASE + '/commander/sessions/' + sid, {method: 'DELETE'});
    showToast('已删除', 'success');
    loadHistory();
  } catch(e) {
    showToast('删除失败: ' + e.message, 'error');
  }
}

async function clearHistory() {
  if (!confirm('确定要清空所有运行记录吗？此操作不可撤销。')) return;
  try {
    // Delete each session
    const r = await fetch(BASE + '/commander/sessions');
    const d = await r.json();
    if (d.sessions) {
      for (const s of d.sessions) {
        const sid = s.id || s.session_id || '';
        if (sid) {
          try { await fetch(BASE + '/commander/sessions/' + sid, {method: 'DELETE'}); } catch(e) {}
        }
      }
    }
    showToast('已清空全部记录', 'success');
    loadHistory();
  } catch(e) {
    showToast('清空失败: ' + e.message, 'error');
  }
}

function showHistoryDetail(sessionId) {
  showToast('查看记录: ' + sessionId, 'info');
  switchPage('chat');
}

// ========== CTO 技术审查 ==========
async function runCTO() {
  var type = document.getElementById('cto-task-type').value;
  var input = document.getElementById('cto-input').value.trim();
  if (!input) { showToast('请输入内容', 'error'); return; }
  var status = document.getElementById('cto-status');
  status.textContent = '执行中...';
  var endpoints = {
    code_review: '/cto/review', tech_choice: '/cto/tech-choice',
    architecture_review: '/cto/architect', task_decompose: '/cto/decompose',
    effort_estimate: '/cto/estimate'
  };
  try {
    var r = await fetch(BASE + (endpoints[type] || '/cto/review'), {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({code: input, goal: input, language: '', context: '', architecture_desc: input})
    });
    var d = await r.json();
    status.textContent = d.status || '';
    document.getElementById('cto-result').style.display = 'block';
    var card = document.getElementById('cto-result-card');
    var findings = d.findings || d.data?.findings || [];
    var html = '<h3>' + (d.summary || '结果') + '</h3>';
    if (d.score !== undefined) { html += '<p>评分: <b>' + d.score + '/100</b></p>'; }
    if (d.data) {
      var dd = d.data;
      if (dd.recommendation) html += '<p>推荐: <b>' + escapeHtml(dd.recommendation) + '</b></p>';
      if (dd.total_hours) html += '<p>预估工时: <b>' + dd.total_hours + 'h</b></p>';
      if (dd.subtasks && dd.subtasks.length) { html += '<p>子任务 (' + dd.subtasks.length + '): ' + dd.subtasks.map(function(s){return s.title||s}).join(', ') + '</p>'; }
    }
    if (findings.length) {
      html += '<div style="margin-top:8px"><b>发现问题:</b>';
      findings.forEach(function(f) { html += '<div style="padding:4px 0;border-bottom:1px solid #222">[' + (f.severity||'?').toUpperCase() + '] ' + escapeHtml(f.description||'') + (f.suggestion ? '<br><span style="color:var(--accent)">→ ' + escapeHtml(f.suggestion) + '</span>' : '') + '</div>'; });
      html += '</div>';
    }
    if (d.suggestions && d.suggestions.length) { html += '<p>建议: ' + d.suggestions.map(escapeHtml).join('; ') + '</p>'; }
    card.innerHTML = html;
  } catch(e) { status.textContent = '错误'; showToast('执行失败: ' + e.message, 'error'); }
}

// ========== 技能库 ==========
async function loadSkills() {
  try {
    var r = await fetch(BASE + '/skills/list');
    var d = await r.json();
    var skills = d.skills || [];
    var html = '<table style="width:100%;font-size:13px;border-collapse:collapse"><tr style="border-bottom:1px solid #333"><th style="text-align:left;padding:8px">名称</th><th style="text-align:left;padding:8px">类别</th><th style="text-align:left;padding:8px">能力</th></tr>';
    skills.forEach(function(s) {
      html += '<tr style="border-bottom:1px solid #222"><td style="padding:8px"><b>' + escapeHtml(s.title||s.name) + '</b><br><span style="color:var(--text2);font-size:11px">' + escapeHtml(s.description||'') + '</span></td><td style="padding:8px"><span class="badge">' + escapeHtml(s.category||'') + '</span></td><td style="padding:8px">' + (s.capabilities||[]).map(function(c){return '<span style="background:#333;padding:1px 6px;border-radius:4px;margin:2px;font-size:11px;display:inline-block">'+escapeHtml(c)+'</span>'}).join(' ') + '</td></tr>';
    });
    html += '</table>';
    document.getElementById('skills-list').innerHTML = html || '<div class="empty"><p>无技能</p></div>';
  } catch(e) { document.getElementById('skills-list').innerHTML = '<div class="empty"><p>加载失败: ' + escapeHtml(e.message) + '</p></div>'; }
}

async function matchSkills() {
  var q = document.getElementById('skills-match-input').value.trim();
  if (!q) { showToast('请输入目标描述', 'error'); return; }
  try {
    var r = await fetch(BASE + '/skills/match?goal=' + encodeURIComponent(q));
    var d = await r.json();
    var matched = d.matched || d.skills || [];
    var html = '<h4>匹配到 ' + matched.length + ' 个相关技能</h4>';
    matched.forEach(function(s) { html += '<div style="padding:8px;margin:4px 0;background:#111;border-radius:4px"><b>' + escapeHtml(s.title||s.name) + '</b> <span class="badge">' + escapeHtml(s.category||'') + '</span><br><span style="color:var(--text2)">' + escapeHtml(s.description||'') + '</span></div>'; });
    document.getElementById('skills-match-result').style.display = 'block';
    document.getElementById('skills-match-card').innerHTML = html;
  } catch(e) { showToast('匹配失败: ' + e.message, 'error'); }
}

// ========== OpenClaw 1M 智能对话 ==========
var ocConversationId = 'oc_' + Date.now();

function refreshOpenClawCtxBar() {
  fetch(BASE + '/agents/openclaw/run', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({task_type:'chat',goal:'__stats__',max_tokens:1})
  }).catch(function(){});
  // Try to get stats via context summary
  updateOpenClawCtxDisplay(null);
}

function updateOpenClawCtxDisplay(stats) {
  var bar = document.getElementById('ctx-bar');
  var text = document.getElementById('ctx-stats');
  if (!stats) {
    bar.style.width = '0%'; text.textContent = '准备中...'; return;
  }
  var total = stats.total_stored_tokens || 0;
  var active = stats.active_tokens || 0;
  var ratio = stats.compression_ratio || '1x';
  var maxVirt = 1000000;
  var pct = Math.min(100, Math.round(total / maxVirt * 100));
  bar.style.width = pct + '%';
  var pctUsed = Math.min(100, Math.round(active / 96000 * 100));
  bar.style.background = pctUsed < 30 ? 'var(--green)' : pctUsed < 70 ? 'linear-gradient(90deg,var(--green),var(--yellow))' : 'linear-gradient(90deg,var(--yellow),var(--red))';
  text.textContent = '虚拟 ' + formatTokens(total) + ' → 发送 ' + formatTokens(active) + ' (' + ratio + ')';
}

function formatTokens(n) {
  if (n >= 1000000) return (n/1000000).toFixed(1) + 'M';
  if (n >= 1000) return (n/1000).toFixed(0) + 'K';
  return String(n);
}

async function sendOpenClawChat() {
  var input = document.getElementById('oc-input');
  var goal = input.value.trim();
  if (!goal) return;
  var mode = document.getElementById('oc-mode').value;
  var msgs = document.getElementById('oc-chat-messages');

  // Show user message
  var userDiv = document.createElement('div');
  userDiv.style.cssText = 'text-align:right;margin:8px 0';
  userDiv.innerHTML = '<div style="display:inline-block;background:var(--accent);color:#fff;padding:8px 14px;border-radius:12px 12px 0 12px;max-width:80%;text-align:left;font-size:13px">' + escapeHtml(goal) + '</div><div style="font-size:10px;color:var(--text2);margin-top:2px">' + (mode === 'deep_research' ? '🔍深度研究' : mode === 'reason' ? '💭思考' : mode === 'verify' ? '✅核查' : mode === 'learn' ? '📚学习' : '💬') + '</div>';
  msgs.appendChild(userDiv);

  // Show loading
  var loadDiv = document.createElement('div');
  loadDiv.id = 'oc-loading';
  loadDiv.style.cssText = 'text-align:left;margin:8px 0';
  loadDiv.innerHTML = '<div style="display:inline-block;background:#111;padding:8px 14px;border-radius:12px 12px 12px 0;max-width:80%;font-size:13px;color:var(--text2)"><span class="spinner"></span> ' + (mode === 'deep_research' ? '深度研究中... 搜索 → 抓取 → 分析 → 验证 (需30-90秒)' : '思考中...') + '</div>';
  msgs.appendChild(loadDiv);
  msgs.scrollTop = msgs.scrollHeight;
  input.value = '';
  input.disabled = true;

  try {
    var r = await fetch(BASE + '/agents/openclaw/run', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        task_type: mode,
        goal: goal,
        conversation_id: ocConversationId,
        max_tokens: 2048,
        temperature: mode === 'reason' ? 0.3 : 0.7
      })
    });
    var d = await r.json();
  } catch(e) {
    d = {success:false, result:'网络错误: ' + e.message};
  }

  // Remove loading
  var ld = document.getElementById('oc-loading'); if (ld) ld.remove();

  // Show response
  var aiDiv = document.createElement('div');
  aiDiv.style.cssText = 'text-align:left;margin:8px 0';
  var result = d.result || d.summary || '';
  var displayText = result.length > 3000 ? result.substring(0, 3000) + '\n\n... (已截断，完整内容见数据面板)' : result;
  var html = '<div style="display:inline-block;background:#111;padding:12px 16px;border-radius:12px 12px 12px 0;max-width:85%;text-align:left;font-size:13px;line-height:1.7;white-space:pre-wrap">' + escapeHtml(displayText) + '</div>';

  // Show context stats if available
  var cstats = (d.data && d.data.context_stats) ? d.data.context_stats : null;
  if (cstats && cstats.total_stored_tokens > 0) {
    html += '<div style="font-size:10px;color:var(--text2);margin-top:4px;display:flex;gap:8px;flex-wrap:wrap">';
    html += '<span>📊 虚拟: ' + formatTokens(cstats.total_stored_tokens) + 'tokens</span>';
    html += '<span>📤 发送: ' + formatTokens(cstats.active_tokens || 0) + 'tokens</span>';
    html += '<span>🗜️ 压缩: ' + (cstats.compression_ratio || '1x') + '</span>';
    html += '<span>📝 消息: ' + (cstats.total_messages || 0) + '条</span>';
    html += '</div>';
    updateOpenClawCtxDisplay(cstats);
  }

  // Show research data if available
  if (mode === 'deep_research' && d.data) {
    var dd = d.data;
    var srcs = dd.sources || [];
    if (srcs.length) {
      html += '<div style="font-size:10px;color:var(--text2);margin-top:6px;border-top:1px solid #222;padding-top:4px">📚 参考来源 (' + srcs.length + '):';
      srcs.forEach(function(s,i){ html += '<br>' + (i+1) + '. <a href="' + escapeHtml(s.url||'') + '" target="_blank" style="color:var(--accent)">' + escapeHtml((s.title||'').substring(0,50)) + '</a>'; });
      html += '</div>';
    }
    var verify = dd.verification;
    if (verify) {
      html += '<div style="font-size:10px;color:var(--accent);margin-top:4px">🔍 可信度: ' + (verify.reliability_score || '?') + '/100</div>';
    }
  }

  aiDiv.innerHTML = html;
  msgs.appendChild(aiDiv);
  msgs.scrollTop = msgs.scrollHeight;
  input.disabled = false;
  input.focus();
}

async function loadDashboard() {
  document.getElementById('dash-refresh-time').textContent = '加载中...';
  try {
    var r = await fetch(BASE + '/system/metrics');
    var d = await r.json();

    // Cards
    var cards = document.getElementById('dash-cards');
    var agents = d.agents || {};
    var healthy = Object.values(agents).filter(function(v){return v==='ok'}).length;
    var usage = d.usage || {};
    var db = d.db || {};
    var cache = d.cache || {};
    var payment = d.payment || {};

    cards.innerHTML = [
      {l:'Agent 健康',v:healthy + '/' + Object.keys(agents).length,c:'var(--green)'},
      {l:'API 调用',v:(usage.all_calls||0),c:'var(--accent)'},
      {l:'总Tokens',v:formatTokens(usage.all_tokens||0),c:'var(--yellow)'},
      {l:'费用',v:'¥' + ((usage.cost_yuan||0)/100).toFixed(2),c:'var(--red)'},
      {l:'缓存命中',v:cache.hit_rate||'0%',c:'var(--green)'},
      {l:'DB会话',v:db.sessions||0,c:'var(--accent)'},
      {l:'记忆数',v:db.memories||0,c:'var(--accent)'},
      {l:'支付笔数',v:payment.tx_count||0,c:'var(--yellow)'},
    ].map(function(c){
      return '<div style="background:#0a0a0a;padding:12px;border-radius:8px;text-align:center"><div style="font-size:22px;font-weight:700;color:'+c.c+'">'+c.v+'</div><div style="font-size:11px;color:var(--text2);margin-top:4px">'+c.l+'</div></div>';
    }).join('');

    // Agent health
    var al = document.getElementById('dash-agent-list');
    al.innerHTML = Object.entries(agents).map(function(e){
      var cls = e[1]==='ok' ? 'color:var(--green)' : 'color:var(--red)';
      return '<span style="'+cls+';display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:6px;background:currentColor"></span>'+e[0]+' ';
    }).join('');

    // Usage
    document.getElementById('dash-usage').innerHTML =
      '<div>24h调用: <b>'+(usage['24h_calls']||0)+'</b></div>'+
      '<div>24h Tokens: <b>'+formatTokens(usage['24h_tokens']||0)+'</b></div>'+
      '<div>总调用: <b>'+(usage.all_calls||0)+'</b></div>'+
      '<div>总费用: <b>¥'+((usage.cost_yuan||0)/100).toFixed(2)+'</b></div>';

    // DB
    document.getElementById('dash-db-stats').innerHTML =
      '<div>Sessions: <b>'+(db.sessions||0)+'</b></div>'+
      '<div>Steps: <b>'+(db.steps||0)+'</b></div>'+
      '<div>Memories: <b>'+(db.memories||0)+'</b></div>'+
      '<div>Audit entries: <b>'+(db.audit_logs||0)+'</b></div>';

    // Infra
    document.getElementById('dash-infra-stats').innerHTML =
      '<div>缓存命中: <b>'+(cache.hit_rate||'0%')+'</b></div>'+
      '<div>缓存条目: <b>'+(cache.size||0)+'/'+(cache.max_size||0)+'</b></div>'+
      '<div>Stripe: <b>'+(payment.active?'已配置':'未配置')+'</b></div>'+
      '<div>支付记录: <b>'+(payment.tx_count||0)+'</b></div>';

    document.getElementById('dash-refresh-time').textContent = new Date().toLocaleTimeString();
  } catch(e) {
    document.getElementById('dash-refresh-time').textContent = '加载失败';
  }
}

async function subscribeToPlan(tier) {
  var userToken = localStorage.getItem('aios_user_token') || '';
  if (!userToken) {
    showToast('请先在 Settings 页面登录或注册账号', 'error');
    return;
  }
  try {
    var r = await fetch(BASE + '/payment/subscribe', {
      method: 'POST', headers: {'Content-Type':'application/json','Authorization':'Bearer '+userToken},
      body: JSON.stringify({tier:tier, success_url: location.origin + '/ui?payment=success', cancel_url: location.origin + '/ui?payment=cancelled'})
    });
    var d = await r.json();
    if (d.ok && d.checkout_url) {
      window.open(d.checkout_url, '_blank');
      showToast('正在跳转到 Stripe 支付页面...', 'success');
    } else {
      showToast(d.error || '支付服务暂未配置，请联系管理员', 'error');
      document.getElementById('pricing-status').innerHTML = '<p style=\"color:var(--yellow)\">⚠️ Stripe 支付暂未配置。<br>请联系管理员手动升级套餐。</p>';
    }
  } catch(e) {
    showToast('订阅失败: ' + e.message, 'error');
  }
}

async function clearOpenClawContext() {
  if (!confirm('确定清空所有对话历史吗？这将重置上下文窗口。')) return;
  ocConversationId = 'oc_' + Date.now();
  document.getElementById('oc-chat-messages').innerHTML = '<div class="empty" style="text-align:left;padding:20px"><p style="color:var(--accent)">🆕 上下文已清空，开始新对话...</p></div>';
  updateOpenClawCtxDisplay({total_stored_tokens:0, active_tokens:0, compression_ratio:'1x', total_messages:0});
  showToast('上下文已清空', 'success');
}

// ========== 图片生成 ==========
async function runImageGen() {
  var prompt = document.getElementById('img-prompt').value.trim();
  if (!prompt) { showToast('请输入图片描述', 'error'); return; }
  var status = document.getElementById('img-status');
  status.textContent = '生成中 (可能需要30-90秒)...';
  try {
    var r = await fetch(BASE + '/image/generate', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({prompt: prompt, size: document.getElementById('img-size').value, style: document.getElementById('img-style').value})
    });
    var d = await r.json();
    status.textContent = d.status || '';
    document.getElementById('img-result').style.display = 'block';
    var card = document.getElementById('img-result-card');
    var html = '<h4>' + escapeHtml(d.summary||'') + '</h4>';
    var images = (d.data && d.data.images) ? d.data.images : [];
    if (images.length) {
      images.forEach(function(img) {
        var src = img.local_path ? ('file:///' + img.local_path.replace(/\\/g,'/')) : img.url;
        html += '<div style="margin:8px 0"><img src="' + escapeHtml(src) + '" style="max-width:100%;max-height:400px;border-radius:8px" onerror="this.style.display=\'none\';this.nextSibling.style.display=\'block\'"><div style="display:none;color:var(--text2)">图片 URL: ' + escapeHtml(img.url||'') + '</div></div>';
        if (img.revised_prompt) html += '<p style="color:var(--text2);font-size:12px">优化提示词: ' + escapeHtml(img.revised_prompt) + '</p>';
      });
    } else if (d.data && d.data.enhanced_prompt) {
      html += '<p><b>增强提示词:</b></p><pre style="background:#111;padding:12px;border-radius:4px;color:var(--accent)">' + escapeHtml(d.data.enhanced_prompt) + '</pre>';
      if (d.data.note) html += '<p style="color:var(--yellow)">' + escapeHtml(d.data.note) + '</p>';
    }
    if (d.data && d.data.local_path) html += '<p>📁 已保存: ' + escapeHtml(d.data.local_path) + '</p>';
    card.innerHTML = html;
  } catch(e) { status.textContent = '错误'; showToast('生成失败: ' + e.message, 'error'); }
}

// ========== 营销内容 ==========
async function runMarketing() {
  var type = document.getElementById('mkt-type').value;
  var input = document.getElementById('mkt-input').value.trim();
  if (!input) { showToast('请输入需求描述', 'error'); return; }
  var status = document.getElementById('mkt-status');
  status.textContent = '生成中...';
  var endpoints = {
    copywriting: '/marketing/copywriting', social_media: '/marketing/social',
    seo_article: '/marketing/seo', email_campaign: '/marketing/email',
    brand_strategy: '/marketing/brand-strategy', campaign_plan: '/marketing/campaign'
  };
  try {
    var r = await fetch(BASE + (endpoints[type] || '/marketing/copywriting'), {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({prompt: input, task_type: type})
    });
    var d = await r.json();
    status.textContent = d.status || '';
    document.getElementById('mkt-result').style.display = 'block';
    var card = document.getElementById('mkt-result-card');
    var dd = d.data || d.output || {};
    var html = '<h4>' + escapeHtml(d.summary||'') + '</h4>';
    // Render known fields
    if (dd.headline) html += '<h3 style="color:var(--accent)">' + escapeHtml(dd.headline) + '</h3>';
    if (dd.subheadline) html += '<p style="color:var(--text2)">' + escapeHtml(dd.subheadline) + '</p>';
    if (dd.content) html += '<div style="white-space:pre-wrap;background:#111;padding:16px;border-radius:8px;margin:8px 0;line-height:1.8">' + dd.content + '</div>';
    if (dd.body) html += '<div style="white-space:pre-wrap;background:#111;padding:16px;border-radius:8px;margin:8px 0;line-height:1.8">' + dd.body + '</div>';
    if (dd.cta) html += '<p><b>CTA:</b> <span style="color:var(--accent)">' + escapeHtml(dd.cta) + '</span></p>';
    if (dd.brand_positioning) html += '<p><b>定位:</b> ' + escapeHtml(dd.brand_positioning) + '</p>';
    if (dd.campaign_name) html += '<p><b>活动:</b> ' + escapeHtml(dd.campaign_name) + '</p>';
    var subtasks = dd.subtasks || [];
    if (subtasks.length) { html += '<p>子任务: ' + subtasks.map(function(s){return s.title||s}).join(', ') + '</p>'; }
    if (dd.mode) html += '<p style="color:var(--yellow);font-size:11px">模式: ' + escapeHtml(dd.mode) + '</p>';
    card.innerHTML = html;
  } catch(e) { status.textContent = '错误'; showToast('生成失败: ' + e.message, 'error'); }
}
// ========== 7. Settings / 配置管理 ==========
function switchProviderTab(prov, btn) {
  document.querySelectorAll('#provider-tabs .tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('[id^="prov-"]').forEach(c => c.classList.remove('active'));
  btn.classList.add('active');
  const el = document.getElementById('prov-' + prov);
  if (el) el.classList.add('active');
}

async function loadConfigStatus() {
  try {
    const [cfgResp, authResp] = await Promise.all([
      fetch(BASE + '/config/status'),
      fetch(BASE + '/auth/info').catch(function() { return null; })
    ]);
    const d = await cfgResp.json();
    var authInfo = null;
    if (authResp) { try { authInfo = await authResp.json(); } catch(e) {} }
    
    var authHtml = '<span class="badge badge-warn">未启用</span>';
    var tokenPreview = '';
    if (authInfo && authInfo.enabled) {
      authHtml = '<span class="badge badge-success">已启用</span>';
      tokenPreview = authInfo.token_full || authInfo.token_preview || '';
      if (tokenPreview) {
        document.getElementById('cfg-auth-token').value = tokenPreview;
      }
    }
    
    const el = document.getElementById('cfg-status');
    el.innerHTML = '<table style="font-size:13px;line-height:1.8">' +
      '<tr><td style="color:var(--text2);padding-right:16px">当前 Provider</td><td><b>' + d.current_provider + '</b></td></tr>' +
      '<tr><td style="color:var(--text2)">API 鉴权</td><td>' + authHtml + '</td></tr>' +
      '<tr><td style="color:var(--text2)">Codex 超时</td><td>' + d.agents.codex_timeout + 's</td></tr>' +
      '<tr><td style="color:var(--text2)">OpenClaw</td><td>' + (d.agents.openclaw_headless ? '无头模式' : '可见模式') + ' / ' + d.agents.openclaw_timeout + 's</td></tr>' +
      '</table>';
    // 更新 provider selector
    document.getElementById('cfg-provider').value = d.current_provider;
  } catch(e) {
    document.getElementById('cfg-status').innerHTML = '<span style="color:var(--red)">无法获取配置状态</span>';
  }
}

async function saveProviderConfig() {
  const provider = document.getElementById('cfg-provider').value;
  const data = {
    ai_provider: provider,
    deepseek_api_key: document.getElementById('cfg-ds-key').value,
    deepseek_base_url: document.getElementById('cfg-ds-url').value,
    deepseek_model: document.getElementById('cfg-ds-model').value,
    openai_api_key: document.getElementById('cfg-oai-key').value,
    openai_base_url: document.getElementById('cfg-oai-url').value,
    openai_model: document.getElementById('cfg-oai-model').value,
    claude_api_key: document.getElementById('cfg-cl-key').value,
    claude_base_url: document.getElementById('cfg-cl-url').value,
    claude_model: document.getElementById('cfg-cl-model').value,
  };
  try {
    const r = await fetch(BASE + '/config/save', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify(data)
    });
    const d = await r.json();
    showToast(d.message || '配置已保存', d.status === 'ok' ? 'success' : 'error');
    loadConfigStatus();
  } catch(e) {
    showToast('保存失败: ' + e.message, 'error');
  }
}

async function testConnection() {
  const provider = document.getElementById('cfg-provider').value;
  const el = document.getElementById('cfg-test-result');
  el.innerHTML = '<span style="color:var(--yellow)">⏳ 测试中...</span>';
  try {
    const r = await fetch(BASE + '/config/test', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({provider: provider})
    });
    const d = await r.json();
    el.innerHTML = '<span style="color:' + (d.status === 'ok' ? 'var(--green)' : 'var(--red)') + '">' + d.message + '</span>';
  } catch(e) {
    el.innerHTML = '<span style="color:var(--red)">测试失败: ' + e.message + '</span>';
  }
}

async function saveAuthToken() {
  const token = document.getElementById('cfg-auth-token').value.trim();
  const enabled = token.length > 0;
  try {
    const r = await fetch(BASE + '/config/save', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({auth_token: token, auth_enabled: enabled})
    });
    const d = await r.json();
    showToast(enabled ? '🔐 鉴权已启用' : '🔓 鉴权已关闭', 'success');
    loadConfigStatus();
  } catch(e) {
    showToast('保存失败: ' + e.message, 'error');
  }
}

async function saveAgentConfig() {
  try {
    showToast('Agent 参数保存功能需要后端支持', 'info');
    loadConfigStatus();
  } catch(e) {
    showToast('保存失败: ' + e.message, 'error');
  }
}

// 统一 switchPage — 切换页面时自动加载数据
const _origSwitchPage = switchPage;
var _tplData = null;
switchPage = function(page) {
  _origSwitchPage(page);
  if (page === 'settings') loadConfigStatus();
  if (page === 'ai-registry') scanAIRegistry();
  if (page === 'templates') loadTemplates();
  if (page === 'chat') renderChatHistory();
  if (page === 'history') loadHistory();
  if (page === 'skills') loadSkills();
  if (page === 'openclaw-chat') refreshOpenClawCtxBar();
  if (page === 'dashboard') loadDashboard();
};

// ═══════════════════════════════════════════════════════════
// 模板系统（场景化模板）
// ═══════════════════════════════════════════════════════════

async function loadTemplates() {
  document.getElementById('tpl-list').style.display = 'block';
  document.getElementById('tpl-list').innerHTML = '<div class="loading show"><div class="spinner"></div></div>';
  document.getElementById('tpl-form').style.display = 'none';
  document.getElementById('tpl-result').style.display = 'none';
  document.getElementById('tpl-loading').classList.remove('show');
  try {
    const r = await fetch(BASE + '/templates/list');
    const d = await r.json();
    _tplData = d.templates;
    renderTplList(d.templates);
  } catch(e) {
    document.getElementById('tpl-list').innerHTML = '<div class="card" style="text-align:center;color:var(--red);padding:30px">❌ 加载模板失败: ' + e.message + '</div>';
  }
}

function renderTplList(templates) {
  if (!templates || !templates.length) {
    document.getElementById('tpl-list').innerHTML = '<div class="card empty"><div class="big">📋</div><p>暂无可用模板</p></div>';
    return;
  }
  var html = '<div class="grid-2">';
  templates.forEach(function(t) {
    html += '<div class="card template-card" onclick="showTplForm(\'' + t.id + '\')" style="cursor:pointer;transition:.2s">';
    html += '<div style="font-size:36px;margin-bottom:8px;text-align:center">' + (t.emoji || '📋') + '</div>';
    html += '<h3 style="text-align:center;margin-bottom:8px">' + t.name + '</h3>';
    html += '<p class="sub" style="text-align:center;font-size:13px">' + t.description + '</p>';
    html += '<div style="text-align:center;margin-top:10px"><span class="badge badge-info">' + (t.steps ? t.steps.length : 0) + ' 步</span></div>';
    html += '</div>';
  });
  html += '</div>';
  document.getElementById('tpl-list').innerHTML = html;
}

var _currentTpl = null;
function showTplForm(tplId) {
  var tpl = null;
  if (_tplData) tpl = _tplData.find(function(t) { return t.id === tplId; });
  if (!tpl) { showToast('模板数据未加载', 'error'); return; }
  _currentTpl = tpl;
  document.getElementById('tpl-list').style.display = 'none';
  document.getElementById('tpl-form').style.display = 'block';
  document.getElementById('tpl-result').style.display = 'none';
  document.getElementById('tpl-loading').classList.remove('show');
  document.getElementById('tpl-form-title').textContent = (tpl.emoji || '📋') + ' ' + tpl.name;
  var html = '<p class="sub" style="margin-bottom:16px">' + tpl.description + '</p>';
  html += '<p class="sub" style="margin-bottom:12px;color:var(--accent)">📌 ' + tpl.output_hint + '</p>';
  tpl.inputs.forEach(function(inp) {
    html += '<div class="form-group">';
    html += '<label>' + inp.label + '</label>';
    if (inp.type === 'select') {
      html += '<select id="tpl-inp-' + inp.key + '">';
      (inp.options || []).forEach(function(o) {
        var sel = o === (inp.default || '') ? ' selected' : '';
        html += '<option value="' + o + '"' + sel + '>' + o + '</option>';
      });
      html += '</select>';
    } else if (inp.type === 'textarea') {
      html += '<textarea id="tpl-inp-' + inp.key + '" placeholder="' + (inp.placeholder || '') + '" rows="3"></textarea>';
    } else {
      html += '<input type="' + (inp.type || 'text') + '" id="tpl-inp-' + inp.key + '" placeholder="' + (inp.placeholder || '') + '">';
    }
    html += '</div>';
  });
  html += '<div class="card" style="background:var(--bg)"><p class="sub" style="font-size:12px">⚡ 执行步骤：' + (tpl.steps || []).map(function(s) { return s.agent; }).join(' → ') + '</p></div>';
  document.getElementById('tpl-form-card').innerHTML = html;
  document.getElementById('tpl-run-btn').disabled = false;
}

function backToTplList() {
  _currentTpl = null;
  document.getElementById('tpl-list').style.display = 'block';
  document.getElementById('tpl-form').style.display = 'none';
  document.getElementById('tpl-result').style.display = 'none';
  document.getElementById('tpl-loading').classList.remove('show');
}

async function runTemplate() {
  if (!_currentTpl) { showToast('请先选择模板', 'error'); return; }
  var inputs = {};
  var tplInputs = _currentTpl.inputs || [];
  for (var i = 0; i < tplInputs.length; i++) {
    var inp = tplInputs[i];
    var el = document.getElementById('tpl-inp-' + inp.key);
    if (el) inputs[inp.key] = el.value;
  }
  document.getElementById('tpl-run-btn').disabled = true;
  document.getElementById('tpl-loading').classList.add('show');
  document.getElementById('tpl-result').style.display = 'none';
  try {
    var body = JSON.stringify({template_id: _currentTpl.id, inputs: inputs});
    var r = await fetch(BASE + '/templates/run/' + _currentTpl.id, {
      method: 'POST', headers: {'Content-Type':'application/json'}, body: body
    });
    if (!r.ok) {
      var errText = await r.text();
      throw new Error('HTTP ' + r.status + ': ' + errText.substring(0, 100));
    }
    var d = await r.json();
    document.getElementById('tpl-loading').classList.remove('show');
    document.getElementById('tpl-run-btn').disabled = false;
    showTplResult(d);
    var ok = !d.status || d.status.indexOf('失败') < 0;
    postToCommander({module:'template',status:ok?'ok':'error',desc:'模板: ' + (_currentTpl.name||'') + ' → ' + (d.status||'完成')});
  } catch(e) {
    document.getElementById('tpl-loading').classList.remove('show');
    document.getElementById('tpl-run-btn').disabled = false;
    showToast('执行失败: ' + e.message, 'error');
    postToCommander({module:'template',status:'error',desc:'模板执行失败: '+e.message});
  }
}

function showTplResult(d) {
  document.getElementById('tpl-form').style.display = 'none';
  document.getElementById('tpl-result').style.display = 'block';
  document.getElementById('tpl-run-btn').disabled = false;

  var statusClass = 'badge-success';
  var statusIcon = '✅';
  if (d.status && d.status.indexOf('失败') >= 0) { statusClass = 'badge-error'; statusIcon = '❌'; }
  else if (d.status && d.status.indexOf('部分') >= 0) { statusClass = 'badge-warn'; statusIcon = '⚠️'; }

  var html = '<div class="flex-between"><h3>' + statusIcon + ' ' + (d.template_name || '') + '</h3>';
  html += '<span class="badge ' + statusClass + '">' + (d.status || '完成') + '</span></div>';
  html += '<p class="sub">任务ID: ' + (d.run_id || '') + ' · ' + (d.success_count || 0) + '/' + (d.total_count || 0) + ' 步成功</p>';

  if (d.final_output) {
    html += '<div class="card" style="background:var(--bg);margin-top:12px">';
    html += '<p style="font-size:13px;white-space:pre-wrap;word-break:break-all">' + escapeHtml(JSON.stringify(d.final_output, null, 2)) + '</p>';
    html += '</div>';
  }

  html += '<p class="sub" style="margin-top:12px;color:var(--accent)">📌 ' + (d.output_hint || '') + '</p>';
  document.getElementById('tpl-result-summary').innerHTML = html;

  // Steps detail
  if (d.results && d.results.length) {
    var stepHtml = '';
    d.results.forEach(function(r, i) {
      var sClass = r.status === '已完成' ? 'badge-success' : 'badge-error';
      var sIcon = r.status === '已完成' ? '✅' : '❌';
      stepHtml += '<div class="step-item">';
      stepHtml += '<div class="step-num ' + (r.status === '已完成' ? 'done' : 'fail') + '">' + (i + 1) + '</div>';
      stepHtml += '<div style="flex:1"><strong style="font-size:14px">' + r.agent + '</strong>';
      if (r.summary) stepHtml += '<div class="sub" style="font-size:12px;margin-top:2px">' + escapeHtml(r.summary.substring(0, 150)) + '</div>';
      stepHtml += '</div><span class="badge ' + sClass + '">' + sIcon + ' ' + r.status + '</span>';
      stepHtml += '</div>';
    });
    document.getElementById('tpl-result-steps').innerHTML = stepHtml;
    document.getElementById('tpl-result-detail').style.display = 'block';
  }
}

function escapeHtml(s) {
  if (!s) return '';
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// ═══════════════════════════════════════════════════════════
// System Agent 页面
// ═══════════════════════════════════════════════════════════
function switchSysTab(tab, btn) {
  document.querySelectorAll('#page-system .tab-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  document.querySelectorAll('#page-system .tab-content').forEach(c => c.classList.remove('active'));
  const el = document.getElementById('sys-' + tab);
  if (el) el.classList.add('active');
}

async function runSystemShell() {
  const cmd = document.getElementById('sys-cmd').value.trim();
  if (!cmd) { showToast('请输入命令', 'error'); return; }
  const shellType = document.getElementById('sys-shell-type').value;
  const timeout = parseInt(document.getElementById('sys-timeout').value) || 30;
  document.getElementById('sys-loading').classList.add('show');
  document.getElementById('sys-result').style.display = 'none';
  try {
    const r = await fetch(BASE + '/agents/system/run', { method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({任务类型:'shell_execute', 目标:cmd, command:cmd, shell_type:shellType, 超时:timeout}) });
    const d = await r.json();
    document.getElementById('sys-loading').classList.remove('show');
    document.getElementById('sys-result').style.display = 'block';
    document.getElementById('sys-status').innerHTML = d.success
      ? '<span class="badge badge-success">✅ 成功</span>'
      : '<span class="badge badge-error">❌ 失败</span>';
    let out = d.stdout ? '📤 输出:\n' + d.stdout + '\n' : '';
    if (d.stderr) out += '⚠️ 错误:\n' + d.stderr + '\n';
    if (d.output_files && d.output_files.length) out += '\n📁 产出文件:\n' + d.output_files.join('\n');
    document.getElementById('sys-output').textContent = out || JSON.stringify(d, null, 2);
  } catch(e) {
    document.getElementById('sys-loading').classList.remove('show');
    document.getElementById('sys-result').style.display = 'block';
    document.getElementById('sys-output').textContent = '请求失败: ' + e.message;
    postToCommander({module:'system',status:'error',desc:'系统命令失败'});
  }
  // Post success
  var sysCmdDone = document.getElementById('sys-status') && document.getElementById('sys-status').textContent.indexOf('成功') >= 0;
  if (!sysCmdDone) postToCommander({module:'system',status:'ok',desc:'系统命令完成'});
}

function toggleFileContent() {
  const action = document.getElementById('sys-file-action').value;
  document.getElementById('sys-file-content-group').style.display = action === 'write' ? 'block' : 'none';
}

async function runSystemAI() {
  document.getElementById('sys-loading').classList.add('show');
  document.getElementById('sys-result').style.display = 'none';
  try {
    const r = await fetch(BASE + '/agents/system/run', { method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({任务类型:'local_ai_list', 目标:'检测本地 AI 能力'}) });
    const d = await r.json();
    document.getElementById('sys-loading').classList.remove('show');
    document.getElementById('sys-result').style.display = 'block';
    document.getElementById('sys-status').innerHTML = '<span class="badge badge-info">🧠 检测结果</span>';
    document.getElementById('sys-output').textContent = JSON.stringify(d, null, 2);
  } catch(e) { document.getElementById('sys-loading').classList.remove('show'); showToast('失败: '+e.message, 'error'); }
}

async function runSystemProgram() {
  const prog = document.getElementById('sys-prog-path').value.trim();
  const args = document.getElementById('sys-prog-args').value.trim();
  if (!prog) { showToast('请输入程序路径', 'error'); return; }
  document.getElementById('sys-loading').classList.add('show');
  document.getElementById('sys-result').style.display = 'none';
  try {
    const r = await fetch(BASE + '/agents/system/run', { method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({任务类型:'run_program', 目标:'启动: ' + prog, program: prog, args: args ? args.split(/\s+/) : []}) });
    const d = await r.json();
    document.getElementById('sys-loading').classList.remove('show');
    document.getElementById('sys-result').style.display = 'block';
    document.getElementById('sys-status').innerHTML = d.success ? '<span class="badge badge-success">✅ 已启动</span>' : '<span class="badge badge-error">❌ 失败</span>';
    document.getElementById('sys-output').textContent = d.result || d.stdout || d.error || JSON.stringify(d, null, 2);
  } catch(e) { document.getElementById('sys-loading').classList.remove('show'); showToast('失败: '+e.message, 'error'); }
}

async function runSystemFile() {
  const action = document.getElementById('sys-file-action').value;
  const path = document.getElementById('sys-file-path').value.trim();
  const content = document.getElementById('sys-file-content').value;
  if (!path) { showToast('请输入文件路径', 'error'); return; }
  let task = { 目标: '' };
  if (action === 'write')      { task.任务类型 = 'file_write'; task.目标 = '写入: ' + path; task.file_path = path; task.file_content = content; }
  else if (action === 'read')  { task.任务类型 = 'file_read';  task.目标 = '读取: ' + path; task.file_path = path; }
  else if (action === 'list')  { task.任务类型 = 'file_list';  task.目标 = '列目录: ' + path; task.directory = path; }
  else if (action === 'delete'){ task.任务类型 = 'file_delete';task.目标 = '删除: ' + path; task.file_path = path; }
  document.getElementById('sys-loading').classList.add('show');
  document.getElementById('sys-result').style.display = 'none';
  try {
    const r = await fetch(BASE + '/agents/system/run', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(task) });
    const d = await r.json();
    document.getElementById('sys-loading').classList.remove('show');
    document.getElementById('sys-result').style.display = 'block';
    document.getElementById('sys-status').innerHTML = d.success ? '<span class="badge badge-success">✅ 成功</span>' : '<span class="badge badge-error">❌ 失败</span>';
    document.getElementById('sys-output').textContent = d.result || d.content || d.stdout || JSON.stringify(d, null, 2);
  } catch(e) { document.getElementById('sys-loading').classList.remove('show'); showToast('失败: '+e.message, 'error'); }
}

// ═══════════════════════════════════════════════════════════
// AI Registry 页面
// ═══════════════════════════════════════════════════════════
async function scanAIRegistry() {
  const el = document.getElementById('ai-scan-result');
  el.innerHTML = '<div class="loading show"><div class="spinner"></div><div>扫描中...</div></div>';
  try {
    const r = await fetch(BASE + '/ai/scan');
    const d = await r.json();
    let html = `<div class="flex-between" style="margin-bottom:12px"><span>发现 <b>${d.count}</b> 个资源，<b>${d.online}</b> 个在线</span></div>`;
    if (d.services && d.services.length) {
      d.services.forEach(s => {
        const emoji = { proxy:'🔀', agent:'🤖', cli:'⌨️', desktop_app:'🖥️' }[s.kind] || '📦';
        const statusDot = s.status === 'online' || s.status === 'running' ? 'dot-green' : (s.status === 'installed' ? 'dot-yellow' : 'dot-red');
        html += `<div class="step-item">
          <div class="step-num done">${emoji}</div>
          <div style="flex:1">
            <div><b>${s.name}</b> <span class="dot ${statusDot}"></span> <span class="sub" style="margin-left:4px">${s.status === 'online' ? '在线' : s.status === 'running' ? '运行中' : s.status === 'installed' ? '已安装' : '离线'}</span></div>
            <div class="sub">${s.base_url || ''} · 能力: ${(s.capabilities||[]).join(', ')}</div>
          </div>
        </div>`;
      });
    }
    el.innerHTML = html;
    loadAICapabilities();
    postToCommander({module:'ai-registry',status:'ok',desc:'资源扫描完成: '+(d.services||[]).length+' 个服务'});
  } catch(e) {
    el.innerHTML = '<div class="empty"><div class="big">❌</div><p>扫描失败: ' + e.message + '</p></div>';
  }
}

async function routeAIRegistry() {
  const goal = document.getElementById('ai-route-goal').value.trim();
  if (!goal) { showToast('请输入目标', 'error'); return; }
  try {
    const r = await fetch(BASE + '/ai/route', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({目标: goal}) });
    const d = await r.json();
    const el = document.getElementById('ai-route-result');
    el.style.display = 'block';
    el.innerHTML = '<div class="card"><h3>🎯 路由结果</h3>' +
      `<p><b>服务:</b> ${d.service || '?'}</p>` +
      `<p><b>任务类型:</b> ${d.task_type || '?'}</p>` +
      `<p><b>原因:</b> ${d.reason || '?'}</p></div>`;
  } catch(e) {
    showToast('路由失败: ' + e.message, 'error');
  }
}

async function loadAICapabilities() {
  try {
    const r = await fetch(BASE + '/ai/capabilities');
    const d = await r.json();
    const el = document.getElementById('ai-capabilities');
    const caps = d.capabilities || {};
    const routes = d.default_routes || {};
    let html = '';
    for (const [cap, providers] of Object.entries(caps)) {
      const defaultSvc = routes[cap] || '-';
      html += `<div class="step-item"><div class="step-num done" style="font-size:11px">🔧</div><div><b>${cap}</b><span class="sub" style="margin-left:8px">默认: ${defaultSvc}</span><div class="sub">提供者: ${providers.join(', ')}</div></div></div>`;
    }
    el.innerHTML = html || '<p class="sub">暂无能力数据</p>';
  } catch(e) {
    document.getElementById('ai-capabilities').innerHTML = '<span style="color:var(--red)">加载失败: ' + e.message + '</span>';
  }
}

// ═══════════════════════════════════════════════════════════
// 💬 AI 对话系统
// ═══════════════════════════════════════════════════════════

var _chatMessages = [];
var _chatHistory = [];
var _currentChatId = null;

// 加载对话历史（localStorage）
function loadChatHistory() {
  try {
    var raw = localStorage.getItem('aco_chat_history');
    if (raw) _chatHistory = JSON.parse(raw) || [];
  } catch(e) { _chatHistory = []; }
  if (!Array.isArray(_chatHistory)) _chatHistory = [];
  return _chatHistory;
}

// 保存对话历史
function saveChatHistory() {
  try { localStorage.setItem('aco_chat_history', JSON.stringify(_chatHistory)); } catch(e) {}
}

// 加载某次对话的消息
function loadChatMessages(chatId) {
  try {
    var raw = localStorage.getItem('aco_chat_' + chatId);
    if (raw) _chatMessages = JSON.parse(raw) || [];
    else _chatMessages = [];
  } catch(e) { _chatMessages = []; }
  if (!Array.isArray(_chatMessages)) _chatMessages = [];
  return _chatMessages;
}

// 保存当前对话的消息
function saveChatMessages() {
  if (!_currentChatId) { chatNew(); }
  try { localStorage.setItem('aco_chat_' + _currentChatId, JSON.stringify(_chatMessages)); } catch(e) {}
}

// 渲染对话历史列表（简化的新版UI不再显示侧边列表，仅保持数据同步）
function renderChatHistory() {
  loadChatHistory();
  var el = document.getElementById('chat-history-list');
  if (!el) return; // 新版 UI 没有侧边栏
  var countEl = document.getElementById('chat-count');
  if (!_chatHistory.length) {
    el.innerHTML = '<div class="empty" style="padding:20px"><p>暂无对话</p></div>';
    if (countEl) countEl.textContent = '0';
    return;
  }
  if (countEl) countEl.textContent = _chatHistory.length;
  var html = '';
  for (var i = _chatHistory.length - 1; i >= 0; i--) {
    var h = _chatHistory[i];
    var active = h.id === _currentChatId ? ' style="background:rgba(59,130,246,.12);border-left:3px solid var(--accent);border-radius:0 8px 8px 0"' : '';
    html += '<div class="step-item"' + active + ' onclick="chatSwitch(\'' + h.id + '\')" style="cursor:pointer;padding:8px 10px">';
    html += '<div style="flex:1;min-width:0"><div style="font-size:13px">' + escapeHtml(h.title || '新对话') + '</div>';
    html += '<div style="font-size:11px;color:var(--text2)">' + new Date(h.time).toLocaleString() + '</div></div>';
    html += '<div onclick="event.stopPropagation();chatDelete(\'' + h.id + '\')" style="font-size:12px;color:var(--red);cursor:pointer;padding:4px">✕</div>';
    html += '</div>';
  }
  el.innerHTML = html;
}

// 渲染消息列表
function renderMessages() {
  var el = document.getElementById('chat-messages');
  if (!_chatMessages.length) {
    el.innerHTML = '<div class="empty" style="padding:60px 20px"><div class="big" style="font-size:48px">👋</div><p style="margin-top:8px;font-size:16px">你好！有什么可以帮你的？</p><p style="color:var(--text2);font-size:14px;margin-top:8px">随便问什么都行</p><div style="margin-top:16px;display:flex;flex-wrap:wrap;gap:8px;justify-content:center"><button class="btn btn-sm btn-outline" onclick="chatQuick(\'帮我写5条小红书文案，产品是手工耳环\')">写小红书文案</button><button class="btn btn-sm btn-outline" onclick="chatQuick(\'帮我写一条朋友圈文案，推广我的手工皂\')">写朋友圈文案</button><button class="btn btn-sm btn-outline" onclick="chatQuick(\'做一个产品展示页，卖手工耳环，风格小清新\')">做一个网页</button></div></div>';
    return;
  }
  var html = '';
  _chatMessages.forEach(function(m, idx) {
    if (m.role === 'user') {
      html += '<div style="display:flex;justify-content:flex-end;margin-bottom:16px">';
      html += '<div style="max-width:75%;padding:10px 16px;background:var(--accent);color:#fff;border-radius:16px 16px 4px 16px;font-size:14px;line-height:1.5">' + escapeHtml(m.content) + '</div>';
      html += '</div>';
    } else if (m.role === 'assistant') {
      html += '<div style="display:flex;justify-content:flex-start;margin-bottom:16px">';
      html += '<div style="max-width:85%;padding:12px 16px;background:var(--card);border:1px solid var(--border);border-radius:16px 16px 16px 4px;font-size:14px;line-height:1.6">';
      if (m.is_loading) {
        html += '<div style="display:flex;gap:8px;align-items:center"><div class="spinner" style="width:20px;height:20px;margin:0"></div><span style="color:var(--text2)">正在思考...</span></div>';
      } else {
        // 主要内容
        html += '<div style="white-space:pre-wrap;word-break:break-word">' + markdownToHtml(escapeHtml(m.content)) + '</div>';
        // 操作按钮区（复制 + 下载）
        html += '<div style="margin-top:12px;display:flex;gap:8px;flex-wrap:wrap">';
        html += '<button onclick="copyMessageText(' + idx + ')" style="font-size:12px;padding:4px 12px;background:var(--bg);border:1px solid var(--border);border-radius:6px;cursor:pointer;color:var(--text)">&#128203; 复制结果</button>';
        // 如果内容包含 HTML 代码，显示下载按钮
        if (m.content && (m.content.includes('<html') || m.content.includes('<!DOCTYPE') || m.content.includes('<div'))) {
          html += '<button onclick="downloadAsHtml(' + idx + ')" style="font-size:12px;padding:4px 12px;background:var(--bg);border:1px solid var(--border);border-radius:6px;cursor:pointer;color:var(--text)">&#128190; 下载网页</button>';
        }
        html += '</div>';
        // 思考过程（折叠，默认隐藏）
        if (m.thinkingText) {
          html += '<details style="margin-top:8px;font-size:12px">';
          html += '<summary style="cursor:pointer;color:var(--text2)">&#128173; 查看思考过程</summary>';
          html += '<div style="margin-top:8px;padding:10px;background:rgba(59,130,246,.05);border:1px solid rgba(59,130,246,.15);border-radius:8px;color:var(--text2);font-size:12px;line-height:1.5;white-space:pre-wrap">' + escapeHtml(m.thinkingText) + '</div>';
          html += '</details>';
        }
        // 显示使用的模型（简化）
        if (m.modelName) {
          html += '<div style="margin-top:8px;font-size:11px;color:var(--text2)">使用: ' + escapeHtml(m.modelName) + '</div>';
        }
      }
      html += '</div></div>';
    }
  });
  el.innerHTML = html;
  // 滚动到底部
  el.scrollTop = el.scrollHeight;
}

// 复制消息文本
function copyMessageText(msgIdx) {
  var msg = _chatMessages[msgIdx];
  if (!msg || !msg.content) return;
  // 清理 markdown 格式，获取纯文本
  var text = msg.content
    .replace(/```[\s\S]*?```/g, function(m) { return m.replace(/```\w*\n?/g, '').replace(/```/g, ''); })
    .replace(/\*\*(.*?)\*\*/g, '$1')
    .replace(/\*(.*?)\*/g, '$1')
    .replace(/#{1,6}\s/g, '')
    .replace(/`(.*?)`/g, '$1');
  navigator.clipboard.writeText(text).then(function() {
    showToast('已复制到剪贴板', 'success');
  }).catch(function() {
    // 降级方案
    var ta = document.createElement('textarea');
    ta.value = text;
    document.body.appendChild(ta);
    ta.select();
    document.execCommand('copy');
    document.body.removeChild(ta);
    showToast('已复制到剪贴板', 'success');
  });
}

// 下载为 HTML 文件
function downloadAsHtml(msgIdx) {
  var msg = _chatMessages[msgIdx];
  if (!msg || !msg.content) return;
  var content = msg.content;
  // 如果内容被 markdown 代码块包裹，提取出来
  var match = content.match(/```(?:html)?\n?([\s\S]*?)```/);
  if (match) content = match[1];
  // 确保有完整的 HTML 结构
  if (!content.includes('<!DOCTYPE') && !content.includes('<html')) {
    content = '<!DOCTYPE html>\n<html lang="zh-CN">\n<head>\n<meta charset="UTF-8">\n<title>生成的页面</title>\n</head>\n<body>\n' + content + '\n</body>\n</html>';
  }
  var blob = new Blob([content], {type: 'text/html;charset=utf-8'});
  var url = URL.createObjectURL(blob);
  var a = document.createElement('a');
  a.href = url;
  a.download = '生成的网页.html';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
  showToast('文件已下载', 'success');
}

// Markdown 简易渲染（支持粗体、链接、换行、列表、代码块）
function markdownToHtml(s) {
  if (!s) return '';
  // 代码块（先处理，避免被其他规则影响）
  s = s.replace(/```(\w*)\n([\s\S]*?)```/g, function(match, lang, code) {
    return '<pre style="background:var(--bg);border:1px solid var(--border);border-radius:8px;padding:12px;overflow-x:auto;margin:8px 0;font-size:13px;line-height:1.5"><code>' + escapeHtml(code.trim()) + '</code></pre>';
  });
  // 行内代码
  s = s.replace(/`([^`]+)`/g, '<code style="background:var(--bg);padding:2px 6px;border-radius:4px;font-size:13px">$1</code>');
  // 粗体
  s = s.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  // 链接
  s = s.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" style="color:var(--accent)">$1</a>');
  // 列表
  s = s.replace(/^- (.+)/gm, '• $1');
  // 标题
  s = s.replace(/^### (.+)/gm, '<h4 style="margin:12px 0 4px;font-size:15px">$1</h4>');
  s = s.replace(/^## (.+)/gm, '<h3 style="margin:16px 0 8px;font-size:16px">$1</h3>');
  s = s.replace(/^# (.+)/gm, '<h2 style="margin:20px 0 12px;font-size:18px">$1</h2>');
  // 换行
  s = s.replace(/\n/g, '<br>');
  return s;
}

// 创建新对话
function chatNew() {
  _currentChatId = 'chat_' + Date.now() + '_' + Math.random().toString(36).substr(2, 4);
  _chatMessages = [];
  // 添加到历史
  _chatHistory.push({id: _currentChatId, title: '新对话', time: Date.now()});
  saveChatHistory();
  renderChatHistory();
  renderMessages();
}

// 切换到指定对话
function chatSwitch(chatId) {
  _currentChatId = chatId;
  _chatMessages = loadChatMessages(chatId);
  renderMessages();
  renderChatHistory();
}

// 删除对话
function chatDelete(chatId) {
  if (!confirm('删除此对话？')) return;
  _chatHistory = _chatHistory.filter(function(h) { return h.id !== chatId; });
  try { localStorage.removeItem('aco_chat_' + chatId); } catch(e) {}
  if (_currentChatId === chatId) {
    _currentChatId = null;
    _chatMessages = [];
    renderMessages();
  }
  saveChatHistory();
  renderChatHistory();
}

// 快速提问（点击预设按钮）
function chatQuick(text) {
  document.getElementById('chat-input').value = text;
  chatSend();
}

// 发送消息
async function chatSend() {
  var input = document.getElementById('chat-input');
  var text = input.value.trim();
  if (!text) return;
  input.value = '';
  input.style.height = '44px';

  // 如果没有当前对话，创建一个新对话
  if (!_currentChatId) {
    chatNew();
    _chatHistory[_chatHistory.length - 1].title = text.substring(0, 40) + (text.length > 40 ? '...' : '');
    saveChatHistory();
    renderChatHistory();
  } else {
    var hist = _chatHistory.find(function(h) { return h.id === _currentChatId; });
    if (hist && _chatMessages.length === 0) {
      hist.title = text.substring(0, 40) + (text.length > 40 ? '...' : '');
      hist.time = Date.now();
      saveChatHistory();
      renderChatHistory();
    }
  }

  // 保存用户消息
  _chatMessages.push({role: 'user', content: text});
  var msgIdx = _chatMessages.length;
  _chatMessages.push({role: 'assistant', is_loading: true, content: '...'});
  renderMessages();
  saveChatMessages();

  // 判断是否走纯对话模式 vs 指挥官任务模式
  var execPatterns = /^(帮我写|帮我创建|帮我生成|帮我搜索|帮我分析|写一个|创建|生成|搜索|分析|对比|计算|执行|运行|打开|搜索网站)/;
  var simpleChat = !execPatterns.test(text);

  try {
    var contentText = '';
    var thinkingText = '';
    var modelName = '';
    var steps = [];

    if (simpleChat) {
      // === 纯对话模式：直接调用 AI ===
      var r = await fetch(BASE + '/commander/chat/send', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          message: text,
          temperature: 0.7,
          max_tokens: 4096
        })
      });
      if (r.ok) {
        var d = await r.json();
        contentText = d.reply || '';
        modelName = d.model || 'deepseek-chat';
        thinkingText = d.thinking || '';
      } else {
        // 降级到 Commander
        simpleChat = false;
      }
    }

    if (!simpleChat) {
      // === 任务模式：走 Commander 编排 ===
      var r = await fetch(BASE + '/commander/run-async', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({目标: text})
      });
      var d = await r.json();
      var finalResult = await pollTaskResult(d.task_id);

      if (finalResult && finalResult.result) {
        var res = finalResult.result;
        contentText = res.summary || res.result_summary || '任务已完成';
        if (res.steps) steps = res.steps;
      }
      if (!contentText) contentText = '任务已完成';
    }

    // 更新消息（包含 AI 回复和思考过程）
    _chatMessages[msgIdx] = {
      role: 'assistant',
      content: contentText,
      thinkingText: thinkingText,
      modelName: modelName,
      steps: steps,
    };
    renderMessages();
    saveChatMessages();

  } catch(e) {
    // 更新为错误消息
    _chatMessages[msgIdx] = {
      role: 'assistant', 
      content: '❌ 执行失败: ' + e.message,
    };
    renderMessages();
    saveChatMessages();
  }
}

// 轮询任务结果
async function pollTaskResult(taskId, maxWaitMs) {
  maxWaitMs = maxWaitMs || 60000;
  var start = Date.now();
  var lastStatus = '';
  while (Date.now() - start < maxWaitMs) {
    try {
      var r = await fetch(BASE + '/commander/tasks/' + taskId);
      var d = await r.json();
      if (d.status === 'completed' || d.status === 'failed') {
        return d;
      }
      if (d.status !== lastStatus) {
        // Try WebSocket too
        lastStatus = d.status;
      }
    } catch(e) { /* retry */ }
    await new Promise(function(resolve) { setTimeout(resolve, 1500); });
  }
  throw new Error('任务超时（' + maxWaitMs/1000 + 's）');
}

// 首次引导逻辑
function dismissOnboarding() {
  document.getElementById('onboarding-overlay').style.display = 'none';
  try { localStorage.setItem('aco_onboarded', '1'); } catch(e) {}
}

// 页面加载时判断是否首次访问
(function() {
  var onboarded = false;
  try { onboarded = localStorage.getItem('aco_onboarded') === '1'; } catch(e) {}
  if (!onboarded) {
    document.getElementById('onboarding-overlay').style.display = 'flex';
  }
})();

// ========== 算力信息显示 ==========
var _aiProvider = 'DeepSeek V4 Pro';
var _aiProviderUrl = '';

async function loadProviderInfo() {
  try {
    var r = await fetch(BASE + '/config/status');
    var d = await r.json();
    var provider = d.provider || d.ai_provider || 'deepseek';
    var model = d.model || d.ai_model || 'deepseek-chat';
    var baseUrl = d.base_url || d.ai_base_url || '';
    _aiProvider = model.charAt(0).toUpperCase() + model.slice(1).replace(/-/g, ' ');
    _aiProviderUrl = baseUrl;
    var badge = document.getElementById('chat-provider-badge');
    if (badge) {
      var urlDisplay = (baseUrl || 'https://api.deepseek.com').replace('https://', '').replace('http://', '').split('/')[0] || '';
      badge.innerHTML = '⚡ <span style="color:var(--accent);font-weight:600">' + escapeHtml(_aiProvider) + '</span> · <span style="color:var(--text2)">' + escapeHtml(urlDisplay) + '</span>';
    }
  } catch(e) {
    var badge = document.getElementById('chat-provider-badge');
    if (badge) badge.textContent = '⚡ DeepSeek V4 Pro · api.deepseek.com';
  }
}

// 页面加载后自动获取算力信息
setTimeout(loadProviderInfo, 500);


// ========== 首页功能 ==========
function homeQuickFill(text) {
  document.getElementById('home-input').value = text;
  document.getElementById('home-input').focus();
}

function homeQuickSend() {
  var text = document.getElementById('home-input').value.trim();
  if (!text) return;
  // 跳转到对话页面并发送
  switchPage('chat');
  document.getElementById('chat-input').value = text;
  setTimeout(function() { chatSend(); }, 300);
}


// ========== 数据分析页面 ==========
function dataQuickFill(text) {
  document.getElementById('data-input').value = text;
  document.getElementById('data-input').focus();
}

function handleDataFile(input) {
  if (!input.files.length) return;
  var file = input.files[0];
  document.getElementById('data-input').value = '分析我上传的文件: ' + file.name;
}

function runDataAnalysis() {
  var text = document.getElementById('data-input').value.trim();
  if (!text) { showToast('请先描述你想分析什么', 'error'); return; }
  switchPage('chat');
  document.getElementById('chat-input').value = text;
  setTimeout(function() { chatSend(); }, 300);
}


// ========== 建网站页面 ==========
function websiteQuickFill(text) {
  document.getElementById('website-input').value = text;
  document.getElementById('website-input').focus();
}

function runWebsiteBuild() {
  var text = document.getElementById('website-input').value.trim();
  if (!text) { showToast('请先描述你想要的网站', 'error'); return; }
  switchPage('chat');
  document.getElementById('chat-input').value = '帮我做一个HTML网页：' + text;
  setTimeout(function() { chatSend(); }, 300);
}


// ========== 做调研页面 ==========
function researchQuickFill(topic, detail) {
  document.getElementById('research-topic').value = topic;
  document.getElementById('research-input').value = detail;
}

function runResearch() {
  var topic = document.getElementById('research-topic').value.trim();
  var detail = document.getElementById('research-input').value.trim();
  if (!topic && !detail) { showToast('请先填写调研内容', 'error'); return; }
  var prompt = detail || '帮我调研：' + topic;
  switchPage('chat');
  document.getElementById('chat-input').value = prompt;
  setTimeout(function() { chatSend(); }, 300);
}


// ========== 设置页面 ==========
async function loadSettings() {
  // 加载当前主脑
  try {
    var r = await fetch(BASE + '/brain/current');
    var brain = await r.json();
    var el = document.getElementById('settings-current-brain');
    el.innerHTML = '<span style="font-size:32px">' + (brain.icon || '🧠') + '</span>' +
      '<div><div style="font-weight:600;font-size:16px">' + escapeHtml(brain.name) + '</div>' +
      '<div style="font-size:13px;color:var(--text2)">' + escapeHtml(brain.description || '') + '</div></div>';
  } catch(e) {}

  // 加载主脑列表
  try {
    var r = await fetch(BASE + '/brain/list');
    var data = await r.json();
    var el = document.getElementById('settings-brain-list');
    el.innerHTML = data.brains.map(function(b) {
      var isCurrent = b.brain_id === data.current.brain_id;
      var isAvailable = data.available.some(function(a) { return a.brain_id === b.brain_id; });
      var border = isCurrent ? 'border:2px solid var(--accent)' : '';
      var status = isCurrent ? '✅ 使用中' : (isAvailable ? '可用' : '需要配置');
      var statusColor = isCurrent ? 'var(--accent)' : (isAvailable ? 'var(--green)' : 'var(--text2)');
      return '<div style="padding:12px;background:var(--bg);border-radius:8px;cursor:pointer;' + border + '" onclick="switchBrain(\'' + b.brain_id + '\')">' +
        '<div style="display:flex;align-items:center;gap:8px;margin-bottom:4px">' +
        '<span style="font-size:20px">' + (b.icon || '🧠') + '</span>' +
        '<span style="font-weight:600">' + escapeHtml(b.name) + '</span></div>' +
        '<div style="font-size:11px;color:' + statusColor + '">' + status + '</div></div>';
    }).join('');
  } catch(e) {}

  // 加载能力
  scanCapabilities();
}

async function switchBrain(brainId) {
  try {
    var r = await fetch(BASE + '/brain/switch', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({brain_id: brainId})
    });
    var d = await r.json();
    if (d.ok) {
      showToast(d.message, 'success');
      loadSettings();
    } else {
      showToast(d.error || '切换失败', 'error');
    }
  } catch(e) {
    showToast('切换失败: ' + e.message, 'error');
  }
}

async function scanCapabilities() {
  var el = document.getElementById('settings-capabilities');
  el.innerHTML = '<div style="padding:16px;text-align:center"><div class="spinner" style="width:20px;height:20px;margin:0 auto"></div><div style="margin-top:8px;font-size:12px;color:var(--text2)">正在扫描...</div></div>';

  try {
    var r = await fetch(BASE + '/brain/capabilities?force=true');
    var data = await r.json();

    var html = '';

    // AI 服务
    if (data.ai_services && data.ai_services.length) {
      html += '<div style="margin-bottom:12px"><div style="font-size:12px;color:var(--text2);margin-bottom:6px">AI 服务</div>';
      html += '<div style="display:flex;gap:6px;flex-wrap:wrap">';
      data.ai_services.forEach(function(s) {
        var color = s.status === 'available' ? 'var(--green)' : 'var(--text2)';
        html += '<span style="font-size:11px;padding:4px 8px;background:var(--bg);border:1px solid var(--border);border-radius:4px;color:' + color + '">' + s.name + ' (' + s.status + ')</span>';
      });
      html += '</div></div>';
    }

    // 浏览器
    if (data.browsers && data.browsers.length) {
      html += '<div style="margin-bottom:12px"><div style="font-size:12px;color:var(--text2);margin-bottom:6px">浏览器</div>';
      html += '<div style="display:flex;gap:6px;flex-wrap:wrap">';
      data.browsers.forEach(function(b) {
        html += '<span style="font-size:11px;padding:4px 8px;background:var(--bg);border:1px solid var(--border);border-radius:4px">' + b.name + '</span>';
      });
      html += '</div></div>';
    }

    // 工具
    if (data.tools && data.tools.length) {
      html += '<div style="margin-bottom:12px"><div style="font-size:12px;color:var(--text2);margin-bottom:6px">本地工具</div>';
      html += '<div style="display:flex;gap:6px;flex-wrap:wrap">';
      data.tools.forEach(function(t) {
        html += '<span style="font-size:11px;padding:4px 8px;background:var(--bg);border:1px solid var(--border);border-radius:4px">' + t.name + (t.version ? ' ' + t.version : '') + '</span>';
      });
      html += '</div></div>';
    }

    // Agent
    if (data.agents && data.agents.length) {
      html += '<div><div style="font-size:12px;color:var(--text2);margin-bottom:6px">Agent 工具</div>';
      html += '<div style="display:flex;gap:6px;flex-wrap:wrap">';
      data.agents.forEach(function(a) {
        html += '<span style="font-size:11px;padding:4px 8px;background:var(--bg);border:1px solid var(--border);border-radius:4px">' + a.name + '</span>';
      });
      html += '</div></div>';
    }

    if (!html) {
      html = '<div style="font-size:13px;color:var(--text2)">未检测到可用能力</div>';
    }

    el.innerHTML = html;
  } catch(e) {
    el.innerHTML = '<div style="font-size:13px;color:var(--red)">扫描失败: ' + e.message + '</div>';
  }
}

async function saveApiKeys() {
  showToast('API Key 配置功能开发中...', 'info');
}


// ========== Agent 市场 ==========
var _marketData = [];
var _marketCategories = [];

async function loadMarket() {
  try {
    var r = await fetch(BASE + '/marketplace/agents');
    var d = await r.json();
    _marketData = d.agents || [];
    renderMarketStats(d.stats);
    renderMarketCategories();
    renderMarketAgents(_marketData);
  } catch(e) {
    showToast('加载市场失败: ' + e.message, 'error');
  }
}

function renderMarketStats(stats) {
  var el = document.getElementById('market-stats');
  if (!stats) { el.innerHTML = ''; return; }
  el.innerHTML = '<div class="card" style="flex:1;padding:12px;text-align:center"><div style="font-size:24px;font-weight:700">' + (stats.builtin_count||0) + '</div><div style="font-size:11px;color:var(--text2)">内置 Agent</div></div>' +
    '<div class="card" style="flex:1;padding:12px;text-align:center"><div style="font-size:24px;font-weight:700">' + (stats.installed_count||0) + '</div><div style="font-size:11px;color:var(--text2)">已安装</div></div>' +
    '<div class="card" style="flex:1;padding:12px;text-align:center"><div style="font-size:24px;font-weight:700">' + (stats.categories||0) + '</div><div style="font-size:11px;color:var(--text2)">分类</div></div>';
}

function renderMarketCategories() {
  var cats = {};
  _marketData.forEach(function(a) { cats[a.category] = (cats[a.category]||0) + 1; });
  var el = document.getElementById('market-categories');
  var html = '<button class="btn btn-sm ' + (!_currentMarketCat ? 'btn-primary' : 'btn-outline') + '" onclick="filterMarket()">全部</button>';
  Object.keys(cats).forEach(function(c) {
    html += '<button class="btn btn-sm ' + (_currentMarketCat===c ? 'btn-primary' : 'btn-outline') + '" onclick="filterMarket(\'' + c + '\')">' + c + ' (' + cats[c] + ')</button>';
  });
  el.innerHTML = html;
}

var _currentMarketCat = '';
function filterMarket(cat) {
  _currentMarketCat = cat || '';
  var filtered = cat ? _marketData.filter(function(a) { return a.category === cat; }) : _marketData;
  renderMarketAgents(filtered);
  renderMarketCategories();
}

function renderMarketAgents(agents) {
  var el = document.getElementById('market-agents');
  if (!agents.length) { el.innerHTML = '<div class="card"><p>无结果</p></div>'; return; }
  el.innerHTML = agents.map(function(a) {
    var stars = '&#9733;'.repeat(Math.round(a.rating||0));
    return '<div class="card" style="padding:16px">' +
      '<div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">' +
      '<span style="font-size:28px">' + (a.icon||'&#129302;') + '</span>' +
      '<div><div style="font-weight:600">' + escapeHtml(a.name) + '</div>' +
      '<div style="font-size:11px;color:var(--text2)">' + escapeHtml(a.category) + ' · v' + escapeHtml(a.version) + '</div></div></div>' +
      '<div style="font-size:13px;color:var(--text2);margin-bottom:8px">' + escapeHtml(a.description) + '</div>' +
      '<div style="display:flex;gap:4px;flex-wrap:wrap;margin-bottom:8px">' +
      (a.capabilities||[]).map(function(c) { return '<span style="font-size:10px;background:var(--bg);padding:2px 6px;border-radius:4px">' + c + '</span>'; }).join('') + '</div>' +
      '<div style="display:flex;justify-content:space-between;align-items:center">' +
      '<span style="font-size:12px;color:var(--accent)">' + stars + ' ' + (a.rating||0) + '</span>' +
      '<button class="btn btn-primary btn-sm" onclick="installAgent(\'' + a.agent_id + '\')">&#128229; 安装</button></div></div>';
  }).join('');
}

async function searchMarket() {
  var q = document.getElementById('market-search').value.trim();
  if (!q) { loadMarket(); return; }
  try {
    var r = await fetch(BASE + '/marketplace/search', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({query:q})});
    var d = await r.json();
    _marketData = d.results || [];
    renderMarketAgents(_marketData);
  } catch(e) { showToast('搜索失败', 'error'); }
}

async function installAgent(agentId) {
  try {
    var r = await fetch(BASE + '/marketplace/install', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({agent_id:agentId})});
    var d = await r.json();
    if (d.ok) showToast(d.message, 'success');
    else showToast(d.error||'安装失败', 'error');
    loadMarket();
  } catch(e) { showToast('安装失败', 'error'); }
}


// ========== 指挥官管理 ==========
async function loadCommanders() {
  try {
    var r = await fetch(BASE + '/commanders/');
    var d = await r.json();
    renderCommanderCurrent(d.current);
    renderCommanderList(d.commanders);
  } catch(e) { showToast('加载失败', 'error'); }
}

function renderCommanderCurrent(cur) {
  var el = document.getElementById('cmd-mgr-current');
  if (!cur) { el.innerHTML = ''; return; }
  el.innerHTML = '<div style="display:flex;align-items:center;gap:12px">' +
    '<span style="font-size:40px">' + (cur.icon||'&#129504;') + '</span>' +
    '<div><div style="font-size:11px;color:var(--text2)">当前指挥官</div>' +
    '<div style="font-size:18px;font-weight:700">' + escapeHtml(cur.name) + '</div>' +
    '<div style="font-size:13px;color:var(--text2)">' + escapeHtml(cur.description) + '</div></div></div>';
}

function renderCommanderList(cmds) {
  var el = document.getElementById('cmd-mgr-list');
  el.innerHTML = cmds.map(function(c) {
    var border = c.is_current ? 'border:2px solid var(--accent)' : '';
    return '<div class="card" style="padding:16px;' + border + '">' +
      '<div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">' +
      '<span style="font-size:24px">' + (c.icon||'&#129504;') + '</span>' +
      '<div><div style="font-weight:600">' + escapeHtml(c.name) + '</div>' +
      '<div style="font-size:11px;color:var(--text2)">' + (c.is_current ? '&#9989; 当前使用' : c.commander_id) + '</div></div></div>' +
      '<div style="font-size:13px;color:var(--text2);margin-bottom:8px">' + escapeHtml(c.description) + '</div>' +
      '<div style="display:flex;gap:4px;flex-wrap:wrap;margin-bottom:8px">' +
      (c.capabilities||[]).map(function(cap) { return '<span style="font-size:10px;background:var(--bg);padding:2px 6px;border-radius:4px">' + cap + '</span>'; }).join('') + '</div>' +
      (!c.is_current ? '<button class="btn btn-primary btn-sm" onclick="switchCommander(\'' + c.commander_id + '\')">&#9889; 切换</button>' : '<span style="font-size:12px;color:var(--accent)">&#9989; 使用中</span>') +
      '</div>';
  }).join('');
}

async function switchCommander(cid) {
  try {
    var r = await fetch(BASE + '/commanders/switch', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({commander_id:cid})});
    var d = await r.json();
    if (d.ok) { showToast(d.message, 'success'); loadCommanders(); }
    else showToast(d.error||'切换失败', 'error');
  } catch(e) { showToast('切换失败', 'error'); }
}


// ========== 插件管理 ==========
var _plugins = [];
var _editPluginId = null;

async function loadPlugins() {
  try {
    var r = await fetch(BASE + '/plugins/');
    var d = await r.json();
    _plugins = d.plugins || [];
    renderPluginList();
  } catch(e) { showToast('加载失败', 'error'); }
}

function renderPluginList() {
  var el = document.getElementById('plugin-list');
  if (!_plugins.length) {
    el.innerHTML = '<div class="card" style="padding:24px;text-align:center"><p style="color:var(--text2)">暂无插件，点击上方「+ 创建插件」开始</p></div>';
    return;
  }
  el.innerHTML = _plugins.map(function(p) {
    return '<div class="card" style="padding:16px">' +
      '<div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">' +
      '<span style="font-size:24px">&#129302;</span>' +
      '<div><div style="font-weight:600">' + escapeHtml(p.name) + '</div>' +
      '<div style="font-size:11px;color:var(--text2)">' + escapeHtml(p.id) + '</div></div></div>' +
      '<div style="font-size:13px;color:var(--text2);margin-bottom:8px">' + escapeHtml(p.description||'无描述') + '</div>' +
      '<div style="display:flex;gap:4px;flex-wrap:wrap;margin-bottom:8px">' +
      (p.capabilities||[]).map(function(c) { return '<span style="font-size:10px;background:var(--bg);padding:2px 6px;border-radius:4px">' + c + '</span>'; }).join('') + '</div>' +
      '<div style="display:flex;gap:8px">' +
      '<button class="btn btn-outline btn-sm" onclick="editPlugin(\'' + p.id + '\')">&#9998; 编辑</button>' +
      '<button class="btn btn-outline btn-sm" onclick="testPlugin(\'' + p.id + '\')">&#9654; 测试</button>' +
      '<button class="btn btn-outline btn-sm" style="color:var(--red)" onclick="deletePlugin(\'' + p.id + '\')">&#128465; 删除</button>' +
      '</div></div>';
  }).join('');
}

function showCreatePlugin() {
  _editPluginId = null;
  document.getElementById('plugin-editor-title').textContent = '创建插件';
  document.getElementById('plugin-name').value = '';
  document.getElementById('plugin-desc').value = '';
  document.getElementById('plugin-caps').value = '';
  document.getElementById('plugin-code').value = '';
  document.getElementById('plugin-editor').style.display = 'block';
  document.getElementById('plugin-test-result').style.display = 'none';
}

function hidePluginEditor() {
  document.getElementById('plugin-editor').style.display = 'none';
  _editPluginId = null;
}

async function editPlugin(pluginId) {
  try {
    var r = await fetch(BASE + '/plugins/' + pluginId);
    var d = await r.json();
    _editPluginId = pluginId;
    document.getElementById('plugin-editor-title').textContent = '编辑插件: ' + d.name;
    document.getElementById('plugin-name').value = d.name || '';
    document.getElementById('plugin-desc').value = d.description || '';
    document.getElementById('plugin-caps').value = (d.capabilities||[]).join(', ');
    document.getElementById('plugin-code').value = d.source_code || '';
    document.getElementById('plugin-editor').style.display = 'block';
    document.getElementById('plugin-test-result').style.display = 'none';
  } catch(e) { showToast('加载失败', 'error'); }
}

async function savePlugin() {
  var name = document.getElementById('plugin-name').value.trim();
  var desc = document.getElementById('plugin-desc').value.trim();
  var caps = document.getElementById('plugin-caps').value.split(',').map(function(s) { return s.trim(); }).filter(Boolean);
  var code = document.getElementById('plugin-code').value;

  if (!name || !code) { showToast('名称和代码不能为空', 'error'); return; }

  try {
    var url, body;
    if (_editPluginId) {
      url = BASE + '/plugins/update';
      body = {plugin_id: _editPluginId, name: name, description: desc, capabilities: caps, code: code};
    } else {
      url = BASE + '/plugins/create';
      body = {name: name, description: desc, capabilities: caps, task_types: [], code: code};
    }
    var r = await fetch(url, {method: _editPluginId ? 'PUT' : 'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
    var d = await r.json();
    if (d.ok) { showToast(d.message||'保存成功', 'success'); hidePluginEditor(); loadPlugins(); }
    else showToast(d.error||d.detail||'保存失败', 'error');
  } catch(e) { showToast('保存失败', 'error'); }
}

async function testPlugin(pluginId) {
  try {
    var r = await fetch(BASE + '/plugins/' + pluginId + '/test', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({goal:'测试任务'})});
    var d = await r.json();
    showToast('测试完成: ' + (d.ok ? '成功' : '失败'), d.ok ? 'success' : 'error');
  } catch(e) { showToast('测试失败', 'error'); }
}

async function testCurrentPlugin() {
  if (!_editPluginId) { showToast('请先保存插件', 'error'); return; }
  testPlugin(_editPluginId);
}

async function deletePlugin(pluginId) {
  if (!confirm('确定删除插件 ' + pluginId + '?')) return;
  try {
    var r = await fetch(BASE + '/plugins/' + pluginId, {method:'DELETE'});
    var d = await r.json();
    if (d.ok) { showToast(d.message, 'success'); loadPlugins(); }
    else showToast(d.error||'删除失败', 'error');
  } catch(e) { showToast('删除失败', 'error'); }
}

var _pluginTemplates = {};
async function loadPluginTemplate() {
  var sel = document.getElementById('plugin-template');
  var tid = sel.value;
  sel.value = '';
  if (!tid) return;
  if (!_pluginTemplates[tid]) {
    try {
      var r = await fetch(BASE + '/plugins/templates/list');
      var d = await r.json();
      (d.templates||[]).forEach(function(t) { _pluginTemplates[t.id] = t.code; });
    } catch(e) { showToast('加载模板失败', 'error'); return; }
  }
  if (_pluginTemplates[tid]) {
    document.getElementById('plugin-code').value = _pluginTemplates[tid];
  }
}


// ========== 页面切换时自动加载 ==========
var _pageLoaders = {
  'marketplace': loadMarket,
  'commander-mgr': loadCommanders,
  'plugin-mgr': loadPlugins,
  'templates': loadTemplates,
  'settings': loadSettings,
};
var _originalSwitchPage = switchPage;
switchPage = function(page) {
  _originalSwitchPage(page);
  if (_pageLoaders[page]) _pageLoaders[page]();
};
