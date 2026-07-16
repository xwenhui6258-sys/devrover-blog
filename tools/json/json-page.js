(function () {
  'use strict';

  const utils = window.JsonUtils;
  const sampleJson = {
    name: 'DevRover',
    version: '1.0.0',
    tools: [
      'Jsonify',
      'Chrono',
      'Base64'
    ],
    enabled: true,
    metadata: {
      author: 'DevRover',
      createdAt: '2026-07-14T15:23:45+08:00'
    },
    nullableField: null,
    emptyString: '',
    emptyArray: [],
    emptyObject: {}
  };

  const icons = {
    copy: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect width="14" height="14" x="8" y="8" rx="2"></rect><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"></path></svg>',
    trash: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 6h18"></path><path d="M8 6V4h8v2"></path><path d="M19 6l-1 14H6L5 6"></path><path d="M10 11v5"></path><path d="M14 11v5"></path></svg>',
    code: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m16 18 6-6-6-6"></path><path d="m8 6-6 6 6 6"></path></svg>',
    moon: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12.2 2.2a6.4 6.4 0 0 0 8.6 8.6 8.7 8.7 0 1 1-8.6-8.6Z"></path></svg>',
    sun: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="4"></circle><path d="M12 2v2"></path><path d="M12 20v2"></path><path d="m4.93 4.93 1.41 1.41"></path><path d="m17.66 17.66 1.41 1.41"></path><path d="M2 12h2"></path><path d="M20 12h2"></path><path d="m6.34 17.66-1.41 1.41"></path><path d="m19.07 4.93-1.41 1.41"></path></svg>',
    chevronRight: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m9 18 6-6-6-6"></path></svg>',
    chevronDown: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m6 9 6 6 6-6"></path></svg>'
  };

  const state = {
    indent: localStorage.getItem('jsonify-indent') || '2',
    operation: 'format',
    operationTouched: false,
    view: 'edit',
    activeTab: 'single',
    autoDetect: true,
    preserveChinese: true,
    sortOrder: 'none',
    clean: {
      deleteNull: false,
      deleteEmptyString: false,
      deleteEmptyArray: false,
      deleteEmptyObject: false
    },
    includeOuterQuotes: false,
    unescapeMode: 'single',
    unescapeDepth: 10,
    output: '',
    detect: null,
    parsedValue: null,
    expanded: new Set(),
    treeValues: {},
    treeInputSignature: '',
    toastTimer: 0,
    debounceTimer: 0,
    checkingTimer: 0
  };

  const el = function (id) {
    return document.getElementById(id);
  };

  function queryAll(selector) {
    return Array.prototype.slice.call(document.querySelectorAll(selector));
  }

  function setButtonIcon(id, iconName, label) {
    const node = el(id);
    if (!node) return;
    node.innerHTML = icons[iconName] + (label ? '<span>' + utils.escapeHtml(label) + '</span>' : '');
  }

  function showToast(message) {
    const toast = el('jsonToast');
    clearTimeout(state.toastTimer);
    toast.textContent = message;
    toast.classList.add('show');
    state.toastTimer = setTimeout(function () {
      toast.classList.remove('show');
    }, 2200);
  }

  function fallbackCopy(text) {
    const area = document.createElement('textarea');
    area.value = text;
    area.setAttribute('readonly', '');
    area.style.position = 'fixed';
    area.style.opacity = '0';
    document.body.appendChild(area);
    area.select();
    let ok = false;
    try {
      ok = document.execCommand('copy');
    } catch (error) {
      ok = false;
    }
    document.body.removeChild(area);
    if (ok) showToast('已复制到剪贴板');
    else showToast('复制失败，请手动选择内容复制');
  }

  function copyText(text) {
    const value = String(text == null ? '' : text);
    if (!value) {
      showToast('没有可复制的内容');
      return;
    }
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(value)
        .then(function () {
          showToast('已复制到剪贴板');
        })
        .catch(function () {
          fallbackCopy(value);
        });
      return;
    }
    fallbackCopy(value);
  }

  function lineCount(text) {
    return text ? String(text).split(/\r\n|\r|\n/).length : 1;
  }

  function renderLineNumbers(container, text, errorLine) {
    const count = lineCount(text);
    let html = '';
    for (let i = 1; i <= count; i += 1) {
      html += '<span' + (errorLine === i ? ' class="error"' : '') + '>' + i + '</span>';
    }
    container.innerHTML = html;
  }

  function highlightJson(text) {
    const source = String(text == null ? '' : text);
    if (!source) return '';
    const tokenPattern = /("(?:\\u[a-fA-F0-9]{4}|\\[^u]|[^\\"])*"\s*:?)|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?|\btrue\b|\bfalse\b|\bnull\b/g;
    let cursor = 0;
    let html = '';
    source.replace(tokenPattern, function (match, stringToken, offset) {
      html += utils.escapeHtml(source.slice(cursor, offset));
      let tokenClass = '';
      if (stringToken) tokenClass = /:\s*$/.test(match) ? 'json-token-key' : 'json-token-string';
      else if (/true|false/.test(match)) tokenClass = 'json-token-boolean';
      else if (/null/.test(match)) tokenClass = 'json-token-null';
      else tokenClass = 'json-token-number';
      html += '<span class="' + tokenClass + '">' + utils.escapeHtml(match) + '</span>';
      cursor = offset + match.length;
      return match;
    });
    html += utils.escapeHtml(source.slice(cursor));
    return html;
  }

  function syncInputScroll() {
    const input = el('jsonInput');
    const highlight = el('inputHighlight');
    const lines = el('inputLines');
    highlight.style.transform = 'translate(' + (-input.scrollLeft) + 'px,' + (-input.scrollTop) + 'px)';
    lines.scrollTop = input.scrollTop;
  }

  function syncOutputScroll() {
    /* Output scrolling is handled by the outer codebox. */
  }

  function renderInputMirror(errorLine) {
    const input = el('jsonInput');
    el('inputHighlight').innerHTML = highlightJson(input.value) || '&nbsp;';
    renderLineNumbers(el('inputLines'), input.value, errorLine || 0);
    syncInputScroll();
  }

  function renderOutput() {
    const output = state.output || '';
    const hasOutput = !!output;
    const outputBox = document.querySelector('.json-codebox.output');
    el('outputPre').innerHTML = hasOutput ? highlightJson(output) : '';
    renderLineNumbers(el('outputLines'), hasOutput ? output : '', 0);
    el('outputEmpty').classList.toggle('hidden', hasOutput);
    if (outputBox) outputBox.classList.toggle('is-empty', !hasOutput);
    syncOutputScroll();
  }

  function statsText(stats) {
    return stats.chars + ' 字符 · ' + stats.lines + ' 行 · ' + stats.fields + ' 字段 · ' + stats.depth + ' 层 · ' + stats.size;
  }

  function renderStatus(info) {
    const detectInfo = info || utils.detectJsonType('');
    const badge = el('statusBadge');
    const badgeText = el('statusBadgeText');
    badge.classList.toggle('off', !state.autoDetect);
    badgeText.textContent = state.autoDetect ? '自动识别中' : '手动识别';

    let title = detectInfo.title;
    let detail = detectInfo.detail;
    if (detectInfo.kind === 'invalid-json' && detectInfo.validation && detectInfo.validation.error) {
      const error = detectInfo.validation.error;
      detail = '第 ' + error.line + ' 行，第 ' + error.column + ' 列，' + error.message;
    }
    el('statusTitle').textContent = title;
    el('statusDetail').textContent = detail || '';
    el('statusSuggestion').textContent = detectInfo.suggestion || '';
    el('statsLine').textContent = statsText(detectInfo.stats || utils.calculateJsonStats(''));

    const warnings = [];
    if (detectInfo.unsafeIntegers && detectInfo.unsafeIntegers.length) {
      warnings.push('检测到超出 JavaScript 安全范围的整数，格式化可能造成精度变化。');
    }
    if (detectInfo.stats && detectInfo.stats.bytes > 5 * 1024 * 1024) {
      warnings.push('内容较大，处理可能需要一些时间。');
    }
    const warningNode = el('statusWarning');
    warningNode.textContent = warnings.join(' ');
    warningNode.classList.toggle('show', warnings.length > 0);

    const errorLine = detectInfo.validation && detectInfo.validation.error ? detectInfo.validation.error.line : 0;
    renderInputMirror(errorLine);
  }

  function setChecking() {
    clearTimeout(state.checkingTimer);
    el('statusTitle').textContent = '校验中';
    el('statusDetail').textContent = '正在识别 JSON 内容类型';
    el('statusSuggestion').textContent = '';
  }

  function updateRecommendedOperation(info) {
    if (state.operationTouched || !info) return;
    if (info.kind === 'escaped-json' || info.kind === 'multi-escaped-json') {
      state.operation = 'unescape';
      if (info.recursive) state.unescapeMode = 'recursive';
      renderOperationControls();
      return;
    }
    if (info.kind === 'compressed-json' || info.kind === 'standard-json' || info.kind === 'json-primitive') {
      state.operation = 'format';
      renderOperationControls();
    }
  }

  function canAutoProcess(info) {
    const raw = el('jsonInput').value;
    if (!raw.trim() || !info || info.kind === 'empty') return false;
    if (state.operation === 'escape') return true;
    if (state.operation === 'unescape') return info.kind === 'escaped-json' || info.kind === 'multi-escaped-json';
    return !!(info.validation && info.validation.valid);
  }

  function runDetection() {
    const info = utils.detectJsonType(el('jsonInput').value);
    state.detect = info;
    state.parsedValue = info.validation && info.validation.valid ? info.validation.value : null;
    updateRecommendedOperation(info);
    renderStatus(info);
    refreshTreeForCurrentInput();
    renderPanels();
    if (canAutoProcess(info)) processInput(true);
  }

  function scheduleDetection() {
    setChecking();
    clearTimeout(state.debounceTimer);
    state.debounceTimer = setTimeout(runDetection, 260);
  }

  function getOptions() {
    return {
      preserveChinese: state.preserveChinese,
      sortOrder: state.sortOrder,
      clean: {
        deleteNull: state.clean.deleteNull,
        deleteEmptyString: state.clean.deleteEmptyString,
        deleteEmptyArray: state.clean.deleteEmptyArray,
        deleteEmptyObject: state.clean.deleteEmptyObject
      }
    };
  }

  function hasAdvancedTransforms() {
    const clean = state.clean;
    return state.sortOrder !== 'none' ||
      clean.deleteNull ||
      clean.deleteEmptyString ||
      clean.deleteEmptyArray ||
      clean.deleteEmptyObject;
  }

  function setResult(message, isError) {
    const bar = el('resultBar');
    el('resultText').textContent = message;
    bar.classList.toggle('error', !!isError);
  }

  function operationLabel(operation) {
    return {
      format: '格式化',
      minify: '压缩',
      escape: '转义',
      unescape: '去转义'
    }[operation] || operation;
  }

  function processInput(silent) {
    const raw = el('jsonInput').value;
    if (!raw.trim()) {
      setResult('处理失败 · 输入内容为空', true);
      if (!silent) showToast('请输入或粘贴 JSON 内容');
      return;
    }
    const options = getOptions();
    let output = '';
    try {
      if (state.operation === 'format') {
        const validation = utils.validateJson(raw);
        if (!validation.valid) throw validation.error;
        output = utils.formatJson(raw, state.indent, options);
      } else if (state.operation === 'minify') {
        const validation = utils.validateJson(raw);
        if (!validation.valid) throw validation.error;
        output = utils.minifyJson(raw, options);
      } else if (state.operation === 'escape') {
        let source = raw;
        const validation = utils.validateJson(raw);
        if (validation.valid && hasAdvancedTransforms()) {
          const transformed = utils.applyTransforms(validation.value, options);
          source = utils.stringifyJson(transformed, state.indent, state.preserveChinese);
        }
        output = utils.escapeJson(source, state.includeOuterQuotes);
      } else if (state.operation === 'unescape') {
        const result = state.unescapeMode === 'recursive'
          ? utils.recursivelyUnescapeJson(raw, state.unescapeDepth)
          : utils.unescapeJson(raw);
        if (!result.success) throw new Error(result.error || '去转义失败');
        output = result.value;
        const validation = utils.validateJson(output);
        if (validation.valid) {
          const transformed = utils.applyTransforms(validation.value, options);
          output = utils.stringifyJson(transformed, state.indent, state.preserveChinese);
        }
        if (result.maxReached && !silent) {
          showToast('已达到最大去转义层级');
        }
      }
      state.output = output;
      renderOutput();
      setResult('JSON 格式正确 · 已完成' + operationLabel(state.operation), false);
      if (!silent) showToast('处理完成');
    } catch (error) {
      const line = error && error.line ? '第 ' + error.line + ' 行，第 ' + error.column + ' 列存在错误' : (error.message || '处理失败');
      setResult('处理失败 · ' + line, true);
      if (!silent) showToast('处理失败');
    }
  }

  function clearAll() {
    const hasContent = el('jsonInput').value || state.output;
    if (hasContent && !window.confirm('确认清空当前内容吗？')) return;
    el('jsonInput').value = '';
    state.output = '';
    state.parsedValue = null;
    state.detect = utils.detectJsonType('');
    state.expanded = new Set();
    state.treeInputSignature = '';
    renderOutput();
    renderStatus(state.detect);
    setResult('处理结果将在这里显示', false);
    renderTree();
    el('jsonInput').focus();
  }

  function loadExample() {
    el('jsonInput').value = JSON.stringify(sampleJson, null, 2);
    state.operationTouched = false;
    renderInputMirror(0);
    scheduleDetection();
    showToast('示例已填充');
  }

  function copyPrimary() {
    copyText(state.output || el('jsonInput').value);
  }

  function setTheme(theme) {
    const dark = theme === 'dark';
    document.body.classList.toggle('json-dark', dark);
    el('themeToggle').innerHTML = dark ? icons.sun : icons.moon;
    localStorage.setItem('devrover-theme', theme);
    localStorage.setItem('chrono-theme', theme);
  }

  function renderOperationControls() {
    queryAll('[data-operation]').forEach(function (button) {
      button.classList.toggle('active', button.dataset.operation === state.operation);
    });
    el('escapeOptions').classList.toggle('hidden', state.operation !== 'escape');
    el('unescapeOptions').classList.toggle('hidden', state.operation !== 'unescape');
    queryAll('[data-unescape-mode]').forEach(function (button) {
      button.classList.toggle('active', button.dataset.unescapeMode === state.unescapeMode);
    });
    renderOptionControls();
  }

  function renderOptionControls() {
    queryAll('[data-option="autoDetect"]').forEach(function (input) {
      input.checked = state.autoDetect;
    });
    queryAll('[data-option="preserveChinese"]').forEach(function (input) {
      input.checked = state.preserveChinese;
    });
    queryAll('[data-option="includeOuterQuotes"]').forEach(function (input) {
      input.checked = state.includeOuterQuotes;
    });
    queryAll('[data-option="sortOrder"]').forEach(function (select) {
      select.value = state.sortOrder;
    });
    queryAll('[data-clean]').forEach(function (input) {
      input.checked = !!state.clean[input.dataset.clean];
    });
    queryAll('[data-option="unescapeDepth"]').forEach(function (input) {
      input.value = state.unescapeDepth;
    });
    el('indentSelect').value = state.indent;
  }

  function renderPanels() {
    const editing = state.view === 'edit';
    queryAll('[data-view]').forEach(function (button) {
      button.classList.toggle('active', button.dataset.view === state.view);
    });
    el('singlePanel').classList.toggle('hidden', !editing || state.activeTab !== 'single');
    el('advancedPanel').classList.toggle('hidden', !editing || state.activeTab !== 'advanced');
    el('treePanel').classList.toggle('hidden', editing);
    queryAll('[data-main-tab]').forEach(function (button) {
      button.classList.toggle('active', button.dataset.mainTab === state.activeTab);
    });
    if (!editing) renderTree();
  }

  function valueType(value) {
    if (value === null) return 'null';
    if (Array.isArray(value)) return 'array';
    return typeof value === 'object' ? 'object' : typeof value;
  }

  function valuePreview(value) {
    const type = valueType(value);
    if (type === 'object') return Object.keys(value).length + ' 字段';
    if (type === 'array') return value.length + ' 项';
    if (type === 'string') return '"' + (value.length > 70 ? value.slice(0, 70) + '...' : value) + '"';
    if (type === 'null') return 'null';
    return String(value);
  }

  function pathFor(parent, key) {
    return parent + '/' + encodeURIComponent(String(key));
  }

  function collectDefaultExpanded(value, path, depth, set) {
    const type = valueType(value);
    if (type !== 'object' && type !== 'array') return;
    if (depth < 2) set.add(path);
    if (depth >= 1) return;
    const keys = type === 'array' ? value.map(function (_, index) { return index; }) : Object.keys(value);
    keys.forEach(function (key) {
      collectDefaultExpanded(value[key], pathFor(path, key), depth + 1, set);
    });
  }

  function collectAllExpanded(value, path, set) {
    const type = valueType(value);
    if (type !== 'object' && type !== 'array') return;
    set.add(path);
    const keys = type === 'array' ? value.map(function (_, index) { return index; }) : Object.keys(value);
    keys.forEach(function (key) {
      collectAllExpanded(value[key], pathFor(path, key), set);
    });
  }

  function refreshTreeForCurrentInput() {
    const signature = el('jsonInput').value;
    if (state.treeInputSignature === signature) return;
    state.treeInputSignature = signature;
    state.expanded = new Set();
    if (state.parsedValue != null) {
      collectDefaultExpanded(state.parsedValue, '$', 0, state.expanded);
    }
    if (state.view === 'tree') renderTree();
  }

  function renderTreeNode(value, key, path, depth, isIndex) {
    const type = valueType(value);
    const expandable = type === 'object' || type === 'array';
    const expanded = state.expanded.has(path);
    state.treeValues[path] = value;
    const keyHtml = key == null
      ? '<span class="json-node-key">root</span>'
      : '<span class="' + (isIndex ? 'json-node-index' : 'json-node-key') + '">' + utils.escapeHtml(String(key)) + '</span>';
    const toggle = expandable
      ? '<button class="json-node-toggle" type="button" data-tree-toggle="' + utils.escapeHtml(path) + '" aria-label="' + (expanded ? '折叠节点' : '展开节点') + '">' + (expanded ? icons.chevronDown : icons.chevronRight) + '</button>'
      : '<span class="json-node-toggle" aria-hidden="true"></span>';
    const row = '<div class="json-node-row">' +
      toggle +
      keyHtml +
      '<span class="json-node-type ' + type + '">' + type + '</span>' +
      '<span class="json-node-preview">' + utils.escapeHtml(valuePreview(value)) + '</span>' +
      '<button class="json-node-copy" type="button" data-tree-copy-value="' + utils.escapeHtml(path) + '" aria-label="复制当前值" title="复制当前值">' + icons.copy + '</button>' +
      '<button class="json-node-copy" type="button" data-tree-copy-json="' + utils.escapeHtml(path) + '" aria-label="复制当前节点 JSON" title="复制当前节点 JSON">' + icons.code + '</button>' +
      '</div>';
    if (!expandable || !expanded) return '<div class="json-node">' + row + '</div>';
    const keys = type === 'array' ? value.map(function (_, index) { return index; }) : Object.keys(value);
    const children = keys.map(function (childKey) {
      return renderTreeNode(value[childKey], childKey, pathFor(path, childKey), depth + 1, type === 'array');
    }).join('');
    return '<div class="json-node">' + row + '<div class="json-node-children">' + children + '</div></div>';
  }

  function renderTree() {
    const treeRoot = el('treeRoot');
    state.treeValues = {};
    if (!state.parsedValue || (valueType(state.parsedValue) !== 'object' && valueType(state.parsedValue) !== 'array')) {
      treeRoot.innerHTML = '<div class="json-tree-empty">当前内容不是有效的 JSON 对象或数组，无法进入树形视图。</div>';
      return;
    }
    treeRoot.innerHTML = renderTreeNode(state.parsedValue, null, '$', 0, false);
  }

  function treeCopyValue(path) {
    const value = state.treeValues[path];
    if (valueType(value) === 'object' || valueType(value) === 'array') {
      copyText(utils.stringifyJson(value, state.indent, state.preserveChinese));
      return;
    }
    copyText(value === null ? 'null' : String(value));
  }

  function treeCopyJson(path) {
    copyText(utils.stringifyJson(state.treeValues[path], state.indent, state.preserveChinese));
  }

  function bindOptionControls() {
    queryAll('[data-option]').forEach(function (control) {
      control.addEventListener('change', function () {
        const option = control.dataset.option;
        if (option === 'autoDetect') state.autoDetect = control.checked;
        if (option === 'preserveChinese') state.preserveChinese = control.checked;
        if (option === 'includeOuterQuotes') state.includeOuterQuotes = control.checked;
        if (option === 'sortOrder') state.sortOrder = control.value;
        if (option === 'unescapeDepth') {
          state.unescapeDepth = Math.max(1, Math.min(10, Number(control.value) || 10));
        }
        renderOptionControls();
        runDetection();
      });
    });
    queryAll('[data-clean]').forEach(function (control) {
      control.addEventListener('change', function () {
        state.clean[control.dataset.clean] = control.checked;
        renderOptionControls();
        runDetection();
      });
    });
  }

  function bindEvents() {
    const input = el('jsonInput');
    input.addEventListener('input', function () {
      state.operationTouched = false;
      renderInputMirror(0);
      if (state.autoDetect) scheduleDetection();
    });
    input.addEventListener('scroll', syncInputScroll);
    document.querySelector('.json-codebox.output').addEventListener('scroll', syncOutputScroll);
    el('indentSelect').addEventListener('change', function () {
      state.indent = el('indentSelect').value;
      localStorage.setItem('jsonify-indent', state.indent);
      renderOptionControls();
    });
    el('themeToggle').addEventListener('click', function () {
      setTheme(document.body.classList.contains('json-dark') ? 'light' : 'dark');
    });
    queryAll('[data-view]').forEach(function (button) {
      button.addEventListener('click', function () {
        state.view = button.dataset.view;
        if (state.view === 'tree' && (!state.parsedValue || (valueType(state.parsedValue) !== 'object' && valueType(state.parsedValue) !== 'array'))) {
          showToast('当前 JSON 不合法或不是对象/数组');
        }
        renderPanels();
      });
    });
    queryAll('[data-main-tab]').forEach(function (button) {
      button.addEventListener('click', function () {
        state.activeTab = button.dataset.mainTab;
        renderPanels();
      });
    });
    queryAll('[data-operation]').forEach(function (button) {
      button.addEventListener('click', function () {
        state.operation = button.dataset.operation;
        state.operationTouched = true;
        renderOperationControls();
        if (el('jsonInput').value.trim()) processInput();
      });
    });
    queryAll('[data-unescape-mode]').forEach(function (button) {
      button.addEventListener('click', function () {
        state.unescapeMode = button.dataset.unescapeMode;
        renderOperationControls();
      });
    });
    bindOptionControls();
    el('processButton').addEventListener('click', processInput);
    el('advancedProcessButton').addEventListener('click', function () {
      state.activeTab = 'single';
      renderPanels();
      processInput();
    });
    el('quickCopy').addEventListener('click', copyPrimary);
    el('quickClear').addEventListener('click', clearAll);
    el('loadExample').addEventListener('click', loadExample);
    el('outputCopy').addEventListener('click', function () {
      copyText(state.output);
    });
    el('expandTree').addEventListener('click', function () {
      if (state.parsedValue != null) {
        state.expanded = new Set();
        collectAllExpanded(state.parsedValue, '$', state.expanded);
        renderTree();
      }
    });
    el('collapseTree').addEventListener('click', function () {
      state.expanded = new Set();
      renderTree();
    });
    document.body.addEventListener('click', function (event) {
      const toggle = event.target.closest('[data-tree-toggle]');
      if (toggle) {
        const path = toggle.dataset.treeToggle;
        if (state.expanded.has(path)) state.expanded.delete(path);
        else state.expanded.add(path);
        renderTree();
      }
      const copyValue = event.target.closest('[data-tree-copy-value]');
      if (copyValue) treeCopyValue(copyValue.dataset.treeCopyValue);
      const copyJson = event.target.closest('[data-tree-copy-json]');
      if (copyJson) treeCopyJson(copyJson.dataset.treeCopyJson);
    });
  }

  function init() {
    if (!utils) return;
    setButtonIcon('quickCopy', 'copy', '复制');
    setButtonIcon('quickClear', 'trash', '清空');
    setButtonIcon('loadExample', 'code', '示例');
    setButtonIcon('outputCopy', 'copy', '复制');
    el('indentSelect').value = state.indent;
    renderOptionControls();
    renderOperationControls();
    renderPanels();
    renderOutput();
    renderStatus(utils.detectJsonType(''));
    bindEvents();
    setTheme(localStorage.getItem('devrover-theme') || localStorage.getItem('chrono-theme') || 'light');
  }

  document.addEventListener('DOMContentLoaded', init);
})();
