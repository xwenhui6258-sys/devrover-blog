(function (root, factory) {
  const api = factory();
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = api;
  }
  root.JsonUtils = api;
})(typeof window !== 'undefined' ? window : globalThis, function () {
  'use strict';

  const MAX_SAFE_INTEGER_TEXT = String(Number.MAX_SAFE_INTEGER);
  const DELETE = { deleted: true };

  function isPlainObject(value) {
    return Object.prototype.toString.call(value) === '[object Object]';
  }

  function getIndentValue(indent) {
    if (indent === 'tab' || indent === '\t' || indent === 'Tab') return '\t';
    const size = Number(indent);
    return size === 4 ? 4 : 2;
  }

  function getIndentString(indent) {
    const value = getIndentValue(indent);
    return value === '\t' ? '\t' : ' '.repeat(value);
  }

  function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, function (char) {
      return {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;'
      }[char];
    });
  }

  function unicodeEscape(text) {
    return String(text).replace(/[^\x00-\x7f]/g, function (char) {
      const code = char.charCodeAt(0).toString(16).padStart(4, '0');
      return '\\u' + code;
    });
  }

  function stringifyJson(value, indent, preserveChinese) {
    const output = JSON.stringify(value, null, getIndentValue(indent));
    return preserveChinese === false ? unicodeEscape(output) : output;
  }

  function minifyStringified(value, preserveChinese) {
    const output = JSON.stringify(value);
    return preserveChinese === false ? unicodeEscape(output) : output;
  }

  function positionToLineColumn(text, index) {
    const safeIndex = Math.max(0, Math.min(Number(index) || 0, text.length));
    let line = 1;
    let column = 1;
    for (let i = 0; i < safeIndex; i += 1) {
      if (text[i] === '\n') {
        line += 1;
        column = 1;
      } else {
        column += 1;
      }
    }
    return { line: line, column: column, index: safeIndex };
  }

  function getLineText(text, line) {
    return String(text).split(/\r\n|\r|\n/)[Math.max(0, line - 1)] || '';
  }

  function findLikelyErrorPosition(text) {
    const trailingComma = /,\s*[}\]]/.exec(text);
    if (trailingComma) return trailingComma.index;
    const singleQuotedKey = /[{,]\s*'[^']+'\s*:/.exec(text);
    if (singleQuotedKey) return singleQuotedKey.index + singleQuotedKey[0].indexOf("'");
    const bareKey = /[{,]\s*[A-Za-z_$][\w$-]*\s*:/.exec(text);
    if (bareKey) return bareKey.index + bareKey[0].search(/[A-Za-z_$]/);
    return Math.max(0, text.length - 1);
  }

  function parseErrorLocation(text, message) {
    const lineColumn = /line\s+(\d+)\s+column\s+(\d+)/i.exec(message);
    if (lineColumn) {
      const line = Number(lineColumn[1]);
      const column = Number(lineColumn[2]);
      const lines = String(text).split(/\r\n|\r|\n/);
      let index = 0;
      for (let i = 0; i < line - 1; i += 1) index += (lines[i] || '').length + 1;
      index += Math.max(0, column - 1);
      return { line: line, column: column, index: index };
    }
    const position = /position\s+(\d+)/i.exec(message) || /at\s+(\d+)/i.exec(message);
    if (position) return positionToLineColumn(text, Number(position[1]));
    return positionToLineColumn(text, findLikelyErrorPosition(text));
  }

  function countUnclosed(text, openChar, closeChar) {
    let count = 0;
    let inString = false;
    let escaped = false;
    for (let i = 0; i < text.length; i += 1) {
      const char = text[i];
      if (inString) {
        if (escaped) {
          escaped = false;
        } else if (char === '\\') {
          escaped = true;
        } else if (char === '"') {
          inString = false;
        }
        continue;
      }
      if (char === '"') inString = true;
      if (char === openChar) count += 1;
      if (char === closeChar) count -= 1;
    }
    return count;
  }

  function friendlyJsonError(text, message, location) {
    const lower = String(message).toLowerCase();
    const lineText = getLineText(text, location.line);
    if (/,\s*[}\]]/.test(text)) {
      return /,\s*}/.test(text) ? '对象末尾存在多余逗号' : '数组末尾存在多余逗号';
    }
    if (/[{,]\s*'[^']+'\s*:/.test(text) || /[{,]\s*[A-Za-z_$][\w$-]*\s*:/.test(text) || /property name|double-quoted|unexpected token/.test(lower) && /[{,]\s*[^"\s]/.test(lineText)) {
      return '属性名称必须使用双引号';
    }
    if (/unterminated|string literal|bad control character|unexpected end/.test(lower) && /"/.test(lineText)) {
      return '字符串没有正确闭合';
    }
    if (/bad escape|invalid escape|escape character/.test(lower)) {
      return '非法转义字符';
    }
    if (countUnclosed(text, '{', '}') > 0) return '缺少右花括号';
    if (countUnclosed(text, '[', ']') > 0) return '缺少右方括号';
    return message || '输入内容不是有效 JSON';
  }

  function validateJson(text) {
    const raw = String(text == null ? '' : text);
    if (!raw.trim()) {
      return {
        valid: false,
        value: null,
        error: {
          message: '请输入 JSON 内容',
          line: 0,
          column: 0,
          index: 0
        }
      };
    }
    try {
      return {
        valid: true,
        value: JSON.parse(raw),
        error: null
      };
    } catch (error) {
      const message = error && error.message ? error.message : '输入内容不是有效 JSON';
      const location = parseErrorLocation(raw, message);
      return {
        valid: false,
        value: null,
        error: {
          message: friendlyJsonError(raw, message, location),
          rawMessage: message,
          line: location.line,
          column: location.column,
          index: location.index
        }
      };
    }
  }

  function countFields(value) {
    if (Array.isArray(value)) {
      return value.reduce(function (total, item) {
        return total + countFields(item);
      }, 0);
    }
    if (isPlainObject(value)) {
      return Object.keys(value).reduce(function (total, key) {
        return total + 1 + countFields(value[key]);
      }, 0);
    }
    return 0;
  }

  function calculateJsonDepth(value) {
    if (Array.isArray(value)) {
      if (!value.length) return 1;
      return 1 + Math.max.apply(null, value.map(calculateJsonDepth));
    }
    if (isPlainObject(value)) {
      const keys = Object.keys(value);
      if (!keys.length) return 1;
      return 1 + Math.max.apply(null, keys.map(function (key) {
        return calculateJsonDepth(value[key]);
      }));
    }
    return 1;
  }

  function formatBytes(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(bytes >= 10240 ? 1 : 2).replace(/\.0$/, '') + ' KB';
    return (bytes / 1024 / 1024).toFixed(2).replace(/\.00$/, '') + ' MB';
  }

  function byteLength(text) {
    const value = String(text == null ? '' : text);
    if (typeof TextEncoder !== 'undefined') {
      return new TextEncoder().encode(value).length;
    }
    return unescape(encodeURIComponent(value)).length;
  }

  function calculateJsonStats(text, value) {
    const raw = String(text == null ? '' : text);
    const hasValue = arguments.length > 1;
    const chars = raw.length;
    const lines = raw.length ? raw.split(/\r\n|\r|\n/).length : 0;
    return {
      chars: chars,
      lines: lines,
      fields: hasValue ? countFields(value) : 0,
      depth: hasValue ? calculateJsonDepth(value) : 0,
      bytes: byteLength(raw),
      size: formatBytes(byteLength(raw))
    };
  }

  function compareUnsafeIntegerText(digits) {
    const normalized = digits.replace(/^0+/, '') || '0';
    if (normalized.length !== MAX_SAFE_INTEGER_TEXT.length) {
      return normalized.length > MAX_SAFE_INTEGER_TEXT.length;
    }
    return normalized > MAX_SAFE_INTEGER_TEXT;
  }

  function readJsonNumber(text, start) {
    let i = start;
    let number = '';
    if (text[i] === '-') {
      number += text[i];
      i += 1;
    }
    if (text[i] === '0') {
      number += text[i];
      i += 1;
    } else {
      while (/\d/.test(text[i] || '')) {
        number += text[i];
        i += 1;
      }
    }
    let integerOnly = true;
    if (text[i] === '.') {
      integerOnly = false;
      number += text[i];
      i += 1;
      while (/\d/.test(text[i] || '')) {
        number += text[i];
        i += 1;
      }
    }
    if (text[i] === 'e' || text[i] === 'E') {
      integerOnly = false;
      number += text[i];
      i += 1;
      if (text[i] === '+' || text[i] === '-') {
        number += text[i];
        i += 1;
      }
      while (/\d/.test(text[i] || '')) {
        number += text[i];
        i += 1;
      }
    }
    return { text: number, end: i, integerOnly: integerOnly };
  }

  function detectUnsafeIntegers(text) {
    const raw = String(text == null ? '' : text);
    const risks = [];
    let inString = false;
    let escaped = false;
    for (let i = 0; i < raw.length; i += 1) {
      const char = raw[i];
      if (inString) {
        if (escaped) {
          escaped = false;
        } else if (char === '\\') {
          escaped = true;
        } else if (char === '"') {
          inString = false;
        }
        continue;
      }
      if (char === '"') {
        inString = true;
        continue;
      }
      if (char === '-' || /\d/.test(char)) {
        const prev = raw[i - 1] || '';
        if (prev && /[\w.]/.test(prev)) continue;
        const token = readJsonNumber(raw, i);
        const next = raw[token.end] || '';
        if (token.text && !/[\w.]/.test(next)) {
          const unsigned = token.text[0] === '-' ? token.text.slice(1) : token.text;
          if (token.integerOnly && compareUnsafeIntegerText(unsigned)) {
            const location = positionToLineColumn(raw, i);
            risks.push({
              value: token.text,
              line: location.line,
              column: location.column,
              index: location.index
            });
          } else if (!token.integerOnly) {
            const numeric = Number(token.text);
            if (Number.isFinite(numeric) && Number.isInteger(numeric) && Math.abs(numeric) > Number.MAX_SAFE_INTEGER) {
              const location = positionToLineColumn(raw, i);
              risks.push({
                value: token.text,
                line: location.line,
                column: location.column,
                index: location.index
              });
            }
          }
        }
        i = Math.max(i, token.end - 1);
      }
    }
    return risks;
  }

  function sortObjectKeys(value, order) {
    if (Array.isArray(value)) {
      return value.map(function (item) {
        return sortObjectKeys(item, order);
      });
    }
    if (!isPlainObject(value)) return value;
    const keys = Object.keys(value);
    if (order === 'asc') keys.sort();
    if (order === 'desc') keys.sort().reverse();
    return keys.reduce(function (next, key) {
      next[key] = sortObjectKeys(value[key], order);
      return next;
    }, {});
  }

  function shouldDeleteCleaned(value, options) {
    if (value === null) return !!options.deleteNull;
    if (value === '') return !!options.deleteEmptyString;
    if (Array.isArray(value) && value.length === 0) return !!options.deleteEmptyArray;
    if (isPlainObject(value) && Object.keys(value).length === 0) return !!options.deleteEmptyObject;
    return false;
  }

  function cleanJsonValueInternal(value, options) {
    if (Array.isArray(value)) {
      const cleanedArray = [];
      value.forEach(function (item) {
        const cleaned = cleanJsonValueInternal(item, options);
        if (cleaned !== DELETE) cleanedArray.push(cleaned);
      });
      return shouldDeleteCleaned(cleanedArray, options) ? DELETE : cleanedArray;
    }
    if (isPlainObject(value)) {
      const cleanedObject = {};
      Object.keys(value).forEach(function (key) {
        const cleaned = cleanJsonValueInternal(value[key], options);
        if (cleaned !== DELETE) cleanedObject[key] = cleaned;
      });
      return shouldDeleteCleaned(cleanedObject, options) ? DELETE : cleanedObject;
    }
    return shouldDeleteCleaned(value, options) ? DELETE : value;
  }

  function cleanJsonValue(value, options) {
    const cleaned = cleanJsonValueInternal(value, options || {});
    return cleaned === DELETE ? null : cleaned;
  }

  function hasTransformOptions(options) {
    const clean = options && options.clean ? options.clean : {};
    return !!(options && options.sortOrder && options.sortOrder !== 'none') ||
      !!clean.deleteNull ||
      !!clean.deleteEmptyString ||
      !!clean.deleteEmptyArray ||
      !!clean.deleteEmptyObject;
  }

  function applyTransforms(value, options) {
    let next = value;
    if (options && options.clean) next = cleanJsonValue(next, options.clean);
    if (options && options.sortOrder && options.sortOrder !== 'none') next = sortObjectKeys(next, options.sortOrder);
    return next;
  }

  function nextNonWhitespace(text, start) {
    for (let i = start; i < text.length; i += 1) {
      if (!/\s/.test(text[i])) return { char: text[i], index: i };
    }
    return { char: '', index: text.length };
  }

  function formatJsonPreservingNumbers(text, indent) {
    const raw = String(text == null ? '' : text).trim();
    const unit = getIndentString(indent);
    let output = '';
    let level = 0;
    let inString = false;
    let escaped = false;
    for (let i = 0; i < raw.length; i += 1) {
      const char = raw[i];
      if (inString) {
        output += char;
        if (escaped) {
          escaped = false;
        } else if (char === '\\') {
          escaped = true;
        } else if (char === '"') {
          inString = false;
        }
        continue;
      }
      if (/\s/.test(char)) continue;
      if (char === '"') {
        inString = true;
        output += char;
      } else if (char === '{' || char === '[') {
        const next = nextNonWhitespace(raw, i + 1);
        output += char;
        if ((char === '{' && next.char === '}') || (char === '[' && next.char === ']')) {
          output += next.char;
          i = next.index;
        } else {
          level += 1;
          output += '\n' + unit.repeat(level);
        }
      } else if (char === '}' || char === ']') {
        level = Math.max(0, level - 1);
        output += '\n' + unit.repeat(level) + char;
      } else if (char === ',') {
        output += ',\n' + unit.repeat(level);
      } else if (char === ':') {
        output += ': ';
      } else {
        output += char;
      }
    }
    return output;
  }

  function minifyJsonPreservingNumbers(text) {
    const raw = String(text == null ? '' : text).trim();
    let output = '';
    let inString = false;
    let escaped = false;
    for (let i = 0; i < raw.length; i += 1) {
      const char = raw[i];
      if (inString) {
        output += char;
        if (escaped) {
          escaped = false;
        } else if (char === '\\') {
          escaped = true;
        } else if (char === '"') {
          inString = false;
        }
        continue;
      }
      if (/\s/.test(char)) continue;
      if (char === '"') inString = true;
      output += char;
    }
    return output;
  }

  function formatJson(text, indent, options) {
    const raw = String(text == null ? '' : text);
    const validation = validateJson(raw);
    if (!validation.valid) throw new Error(validation.error.message);
    const safeOptions = options || {};
    if (detectUnsafeIntegers(raw).length && !hasTransformOptions(safeOptions)) {
      return formatJsonPreservingNumbers(raw, indent);
    }
    const transformed = applyTransforms(validation.value, safeOptions);
    return stringifyJson(transformed, indent, safeOptions.preserveChinese !== false);
  }

  function minifyJson(text, options) {
    const raw = String(text == null ? '' : text);
    const validation = validateJson(raw);
    if (!validation.valid) throw new Error(validation.error.message);
    const safeOptions = options || {};
    if (detectUnsafeIntegers(raw).length && !hasTransformOptions(safeOptions)) {
      return minifyJsonPreservingNumbers(raw);
    }
    const transformed = applyTransforms(validation.value, safeOptions);
    return minifyStringified(transformed, safeOptions.preserveChinese !== false);
  }

  function escapeJson(text, includeOuterQuotes) {
    const escaped = String(text == null ? '' : text)
      .replace(/\\/g, '\\\\')
      .replace(/"/g, '\\"')
      .replace(/\n/g, '\\n')
      .replace(/\r/g, '\\r')
      .replace(/\t/g, '\\t');
    return includeOuterQuotes ? '"' + escaped + '"' : escaped;
  }

  function decodeSimpleEscapes(text) {
    let output = '';
    let changed = false;
    for (let i = 0; i < text.length; i += 1) {
      const char = text[i];
      if (char !== '\\') {
        output += char;
        continue;
      }
      const next = text[i + 1];
      if (next == null) {
        output += char;
        continue;
      }
      changed = true;
      if (next === '"') output += '"';
      else if (next === '\\') output += '\\';
      else if (next === 'n') output += '\n';
      else if (next === 'r') output += '\r';
      else if (next === 't') output += '\t';
      else if (next === 'b') output += '\b';
      else if (next === 'f') output += '\f';
      else if (next === 'u' && /^[0-9a-fA-F]{4}$/.test(text.slice(i + 2, i + 6))) {
        output += String.fromCharCode(parseInt(text.slice(i + 2, i + 6), 16));
        i += 4;
      } else {
        output += next;
      }
      i += 1;
    }
    return { value: output, changed: changed };
  }

  function decodeEscapedString(text) {
    const raw = String(text == null ? '' : text);
    const trimmed = raw.trim();
    if (!trimmed) return { success: false, value: raw, error: '请输入要去转义的内容' };
    if (trimmed[0] === '"' && trimmed[trimmed.length - 1] === '"') {
      try {
        const parsed = JSON.parse(trimmed);
        if (typeof parsed === 'string') return { success: true, value: parsed };
      } catch (error) {
        return { success: false, value: raw, error: error.message };
      }
    }
    try {
      const wrapped = '"' + raw.replace(/\r/g, '\\r').replace(/\n/g, '\\n').replace(/\t/g, '\\t') + '"';
      const parsed = JSON.parse(wrapped);
      if (parsed !== raw) return { success: true, value: parsed };
    } catch (error) {
      const decoded = decodeSimpleEscapes(raw);
      if (decoded.changed) return { success: true, value: decoded.value };
    }
    const fallback = decodeSimpleEscapes(raw);
    if (fallback.changed) return { success: true, value: fallback.value };
    return { success: false, value: raw, error: '输入内容不是有效的转义字符串' };
  }

  function unescapeJson(text) {
    const decoded = decodeEscapedString(text);
    if (!decoded.success) {
      return {
        success: false,
        value: String(text == null ? '' : text),
        changed: false,
        error: decoded.error
      };
    }
    return {
      success: true,
      value: decoded.value,
      changed: decoded.value !== String(text == null ? '' : text),
      error: null
    };
  }



  function splitLooseTopLevel(text, separator) {
    const parts = [];
    let start = 0;
    let depth = 0;
    let inString = false;
    let escaped = false;
    for (let i = 0; i < text.length; i += 1) {
      const char = text[i];
      if (inString) {
        if (escaped) escaped = false;
        else if (char === '\\') escaped = true;
        else if (char === '"' || char === "'") inString = false;
        continue;
      }
      if (char === '"' || char === "'") {
        inString = true;
        continue;
      }
      if (char === '{' || char === '[') depth += 1;
      else if (char === '}' || char === ']') depth -= 1;
      else if (char === separator && depth === 0) {
        parts.push(text.slice(start, i));
        start = i + 1;
      }
    }
    parts.push(text.slice(start));
    return parts;
  }

  function findLooseTopLevelColon(text) {
    let depth = 0;
    let inString = false;
    let escaped = false;
    for (let i = 0; i < text.length; i += 1) {
      const char = text[i];
      if (inString) {
        if (escaped) escaped = false;
        else if (char === '\\') escaped = true;
        else if (char === '"' || char === "'") inString = false;
        continue;
      }
      if (char === '"' || char === "'") {
        inString = true;
        continue;
      }
      if (char === '{' || char === '[') depth += 1;
      else if (char === '}' || char === ']') depth -= 1;
      else if (char === ':' && depth === 0) return i;
    }
    return -1;
  }

  function stripLooseQuotes(text) {
    const trimmed = String(text == null ? '' : text).trim();
    if ((trimmed[0] === '"' && trimmed[trimmed.length - 1] === '"') ||
        (trimmed[0] === "'" && trimmed[trimmed.length - 1] === "'")) {
      return trimmed.slice(1, -1);
    }
    return trimmed;
  }

  function parseLooseJsonLike(text) {
    const raw = String(text == null ? '' : text).trim();
    if (!raw) return { success: false, value: raw };
    if (raw[0] === '{' && raw[raw.length - 1] === '}') return parseLooseObject(raw);
    if (raw[0] === '[' && raw[raw.length - 1] === ']') return parseLooseArray(raw);
    return { success: false, value: raw };
  }

  function parseLooseObject(text) {
    const body = text.trim().slice(1, -1).trim();
    if (!body) return { success: true, value: {} };
    const object = {};
    const fields = splitLooseTopLevel(body, ',');
    for (let i = 0; i < fields.length; i += 1) {
      const field = fields[i].trim();
      if (!field) continue;
      const colon = findLooseTopLevelColon(field);
      if (colon < 0) return { success: false, value: text };
      const key = stripLooseQuotes(field.slice(0, colon));
      if (!key) return { success: false, value: text };
      object[key] = parseLooseValue(field.slice(colon + 1));
    }
    return { success: true, value: object };
  }

  function parseLooseArray(text) {
    const body = text.trim().slice(1, -1).trim();
    if (!body) return { success: true, value: [] };
    return {
      success: true,
      value: splitLooseTopLevel(body, ',').map(function (item) {
        return parseLooseValue(item);
      })
    };
  }

  function parseLooseValue(text) {
    const raw = String(text == null ? '' : text).trim();
    if (!raw) return '';
    const strict = validateJson(raw);
    if (strict.valid) return strict.value;
    const loose = parseLooseJsonLike(raw);
    if (loose.success) return loose.value;
    if (raw === 'true') return true;
    if (raw === 'false') return false;
    if (raw === 'null') return null;
    if (/^-?\d+(?:\.\d+)?$/.test(raw) && !/^\d{4}-\d{1,2}-\d{1,2}$/.test(raw)) return Number(raw);
    return stripLooseQuotes(raw);
  }

  function deepUnescapeJsonValue(value, maxLayers) {
    if (maxLayers <= 0) return { value: value, changed: false, layers: 0, maxReached: true };
    if (Array.isArray(value)) {
      let changedArray = false;
      let layersArray = 0;
      let maxArray = false;
      const arrayValue = value.map(function (item) {
        const next = deepUnescapeJsonValue(item, maxLayers);
        changedArray = changedArray || next.changed;
        layersArray += next.layers;
        maxArray = maxArray || next.maxReached;
        return next.value;
      });
      return { value: arrayValue, changed: changedArray, layers: layersArray, maxReached: maxArray };
    }
    if (isPlainObject(value)) {
      let changedObject = false;
      let layersObject = 0;
      let maxObject = false;
      const objectValue = {};
      Object.keys(value).forEach(function (key) {
        const next = deepUnescapeJsonValue(value[key], maxLayers);
        changedObject = changedObject || next.changed;
        layersObject += next.layers;
        maxObject = maxObject || next.maxReached;
        objectValue[key] = next.value;
      });
      return { value: objectValue, changed: changedObject, layers: layersObject, maxReached: maxObject };
    }
    if (typeof value !== 'string') return { value: value, changed: false, layers: 0, maxReached: false };
    let current = value;
    let layers = 0;
    for (let i = 0; i < maxLayers; i += 1) {
      const direct = validateJson(current);
      if (direct.valid) {
        if (isPlainObject(direct.value) || Array.isArray(direct.value)) {
          const nested = deepUnescapeJsonValue(direct.value, maxLayers - layers - 1);
          return {
            value: nested.value,
            changed: true,
            layers: layers + 1 + nested.layers,
            maxReached: nested.maxReached
          };
        }
        if (typeof direct.value === 'string' && direct.value !== current) {
          current = direct.value;
          layers += 1;
          continue;
        }
      }
      const loose = parseLooseJsonLike(current);
      if (loose.success) {
        const nestedLoose = deepUnescapeJsonValue(loose.value, maxLayers - layers - 1);
        return {
          value: nestedLoose.value,
          changed: true,
          layers: layers + 1 + nestedLoose.layers,
          maxReached: nestedLoose.maxReached
        };
      }
      const decoded = unescapeJson(current);
      if (decoded.success && decoded.value !== current) {
        current = decoded.value;
        layers += 1;
        continue;
      }
      break;
    }
    return {
      value: current,
      changed: current !== value,
      layers: layers,
      maxReached: layers >= maxLayers
    };
  }

  function recursivelyUnescapeJson(text, maxLayers) {
    const limit = Math.max(1, Number(maxLayers) || 10);
    let current = String(text == null ? '' : text);
    let layers = 0;
    let maxReached = false;

    const initial = validateJson(current);
    if (initial.valid) {
      const nested = deepUnescapeJsonValue(initial.value, limit);
      if (nested.changed) {
        return {
          success: true,
          value: JSON.stringify(nested.value),
          layers: nested.layers,
          nestedChanged: true,
          maxReached: nested.maxReached || nested.layers >= limit,
          error: null
        };
      }
      return {
        success: false,
        value: current,
        layers: 0,
        nestedChanged: false,
        maxReached: false,
        error: '输入内容不是有效的转义 JSON'
      };
    }

    for (let i = 0; i < limit; i += 1) {
      const decoded = unescapeJson(current);
      if (!decoded.success || decoded.value === current) break;
      current = decoded.value;
      layers += 1;
      const parsed = validateJson(current);
      if (parsed.valid) {
        const nested = deepUnescapeJsonValue(parsed.value, limit - layers);
        if (nested.changed) {
          current = JSON.stringify(nested.value);
          layers += nested.layers;
          maxReached = nested.maxReached || layers >= limit;
        }
        return {
          success: true,
          value: current,
          layers: layers,
          nestedChanged: true,
          maxReached: maxReached,
          error: null
        };
      }
    }
    if (layers >= limit) maxReached = true;
    return {
      success: layers > 0,
      value: current,
      layers: layers,
      nestedChanged: false,
      maxReached: maxReached,
      error: layers > 0 ? null : '输入内容不是有效的转义 JSON'
    };
  }

  function rootKind(value) {
    if (Array.isArray(value)) return '数组';
    if (isPlainObject(value)) return '对象';
    if (value === null) return 'null';
    return typeof value;
  }

  function isCompressedJsonText(text, value) {
    const trimmed = String(text).trim();
    if (!trimmed || /\r|\n/.test(trimmed)) return false;
    if (!(Array.isArray(value) || isPlainObject(value))) return false;
    return trimmed === JSON.stringify(value);
  }

  function detectJsonType(text) {
    const raw = String(text == null ? '' : text);
    const trimmed = raw.trim();
    const stats = calculateJsonStats(raw);
    const unsafeIntegers = detectUnsafeIntegers(raw);
    if (!trimmed) {
      return {
        kind: 'empty',
        title: '等待输入',
        detail: '请输入或粘贴 JSON 内容',
        rootType: '',
        recommendation: 'format',
        validation: null,
        stats: stats,
        unsafeIntegers: unsafeIntegers
      };
    }
    const direct = validateJson(raw);
    if (direct.valid) {
      const validStats = calculateJsonStats(raw, direct.value);
      const kind = rootKind(direct.value);
      if (typeof direct.value === 'string') {
        const recursive = recursivelyUnescapeJson(direct.value, 4);
        const parsedInner = validateJson(recursive.value);
        if (recursive.success && parsedInner.valid) {
          const multi = recursive.layers > 1 || recursive.nestedChanged;
          return {
            kind: multi ? 'multi-escaped-json' : 'escaped-json',
            title: multi ? '检测到多层转义' : '检测到转义内容',
            detail: multi ? '已识别：多层转义 JSON 字符串' : '已识别：转义 JSON 字符串',
            suggestion: multi ? '建议使用“递归去转义”' : '建议使用“去转义”',
            rootType: rootKind(parsedInner.value),
            recommendation: 'unescape',
            recursive: multi,
            validation: direct,
            stats: validStats,
            unsafeIntegers: unsafeIntegers
          };
        }
        return {
          kind: 'json-string',
          title: '格式正确',
          detail: '已识别：JSON 字符串',
          rootType: 'string',
          recommendation: 'escape',
          validation: direct,
          stats: validStats,
          unsafeIntegers: unsafeIntegers
        };
      }
      if (isPlainObject(direct.value) || Array.isArray(direct.value)) {
        const nested = deepUnescapeJsonValue(direct.value, 10);
        if (nested.changed) {
          return {
            kind: nested.layers > 1 ? 'multi-escaped-json' : 'escaped-json',
            title: nested.layers > 1 ? '检测到多层转义' : '检测到转义内容',
            detail: '已识别：标准 JSON 内含转义 JSON 字段',
            suggestion: '建议使用“递归去转义”',
            rootType: kind,
            recommendation: 'unescape',
            recursive: true,
            validation: direct,
            stats: validStats,
            unsafeIntegers: unsafeIntegers
          };
        }
        const compressed = isCompressedJsonText(raw, direct.value);
        return {
          kind: compressed ? 'compressed-json' : 'standard-json',
          title: '格式正确',
          detail: '已识别：' + (compressed ? '压缩 JSON' : '标准 JSON') + ' · ' + kind,
          rootType: kind,
          recommendation: compressed ? 'format' : 'minify',
          validation: direct,
          stats: validStats,
          unsafeIntegers: unsafeIntegers
        };
      }
      return {
        kind: 'json-primitive',
        title: '格式正确',
        detail: '已识别：JSON ' + kind,
        rootType: kind,
        recommendation: 'format',
        validation: direct,
        stats: validStats,
        unsafeIntegers: unsafeIntegers
      };
    }
    const recursive = recursivelyUnescapeJson(raw, 10);
    if (recursive.success) {
      const parsed = validateJson(recursive.value);
      if (parsed.valid) {
        const multi = recursive.layers > 1 || recursive.nestedChanged;
        return {
          kind: multi ? 'multi-escaped-json' : 'escaped-json',
          title: multi ? '检测到多层转义' : '检测到转义内容',
          detail: multi ? '已识别：多层转义 JSON 字符串' : '已识别：转义 JSON 字符串',
          suggestion: multi ? '建议使用“递归去转义”' : '建议使用“去转义”',
          rootType: rootKind(parsed.value),
          recommendation: 'unescape',
          recursive: multi,
          validation: parsed,
          stats: calculateJsonStats(raw, parsed.value),
          unsafeIntegers: unsafeIntegers
        };
      }
    }
    if (/^[{[]/.test(trimmed)) {
      return {
        kind: 'invalid-json',
        title: '格式错误',
        detail: direct.error.message,
        recommendation: 'format',
        validation: direct,
        stats: stats,
        unsafeIntegers: unsafeIntegers
      };
    }
    return {
      kind: 'plain-text',
      title: '普通文本',
      detail: '输入内容不是有效 JSON',
      recommendation: 'escape',
      validation: direct,
      stats: stats,
      unsafeIntegers: unsafeIntegers
    };
  }

  return {
    applyTransforms: applyTransforms,
    calculateJsonDepth: calculateJsonDepth,
    calculateJsonStats: calculateJsonStats,
    cleanJsonValue: cleanJsonValue,
    detectJsonType: detectJsonType,
    detectUnsafeIntegers: detectUnsafeIntegers,
    escapeHtml: escapeHtml,
    escapeJson: escapeJson,
    formatBytes: formatBytes,
    formatJson: formatJson,
    formatJsonPreservingNumbers: formatJsonPreservingNumbers,
    getIndentString: getIndentString,
    getIndentValue: getIndentValue,
    minifyJson: minifyJson,
    minifyJsonPreservingNumbers: minifyJsonPreservingNumbers,
    recursivelyUnescapeJson: recursivelyUnescapeJson,
    sortObjectKeys: sortObjectKeys,
    stringifyJson: stringifyJson,
    unescapeJson: unescapeJson,
    validateJson: validateJson
  };
});
