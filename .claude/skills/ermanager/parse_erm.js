#!/usr/bin/env node
/**
 * parse_erm.js — .erm (XML) 파일을 .erm.json으로 변환
 *
 * 사용법:
 *   node .claude/skills/ermanager/parse_erm.js <input.erm> [output.erm.json]
 *
 * output을 생략하면 input과 같은 경로에 <name>.erm.json으로 저장
 */
'use strict';

const fs = require('fs');
const path = require('path');

const [, , inputArg, outputArg] = process.argv;
if (!inputArg) {
  console.error('사용법: node parse_erm.js <input.erm> [output.erm.json]');
  process.exit(1);
}

const inputPath = path.resolve(inputArg);
if (!fs.existsSync(inputPath)) {
  console.error(`파일 없음: ${inputPath}`);
  process.exit(1);
}

const outputPath = outputArg
  ? path.resolve(outputArg)
  : inputPath.replace(/\.erm$/, '.erm.json');

// ── 최소 XML 파서 ─────────────────────────────────────────────────────────────

function decodeEntities(s) {
  return s
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&apos;/g, "'")
    .replace(/&#x([0-9a-fA-F]+);/g, (_, h) => String.fromCharCode(parseInt(h, 16)))
    .replace(/&#(\d+);/g, (_, d) => String.fromCharCode(parseInt(d, 10)));
}

function parseXml(xml) {
  const root = { tag: '__root__', children: [], text: '' };
  const stack = [root];
  const re = /<!\[CDATA\[[\s\S]*?\]\]>|<!--[\s\S]*?-->|<\?[\s\S]*?\?>|<([^>]*)>|([^<]+)/g;
  let m;
  while ((m = re.exec(xml)) !== null) {
    if (!m[1] && !m[2]) continue;
    if (m[1] !== undefined) {
      const inner = m[1].trim();
      if (inner.startsWith('/')) {
        const el = stack.pop();
        if (stack.length > 0) stack[stack.length - 1].children.push(el);
      } else if (inner.endsWith('/')) {
        const tagName = inner.slice(0, -1).trim().split(/\s/)[0];
        stack[stack.length - 1].children.push({ tag: tagName, children: [], text: '' });
      } else {
        const tagName = inner.split(/\s/)[0];
        stack.push({ tag: tagName, children: [], text: '' });
      }
    } else if (m[2]) {
      const text = decodeEntities(m[2]);
      if (text.trim()) stack[stack.length - 1].text += text.trim();
    }
  }
  while (stack.length > 1) {
    const el = stack.pop();
    stack[stack.length - 1].children.push(el);
  }
  return root.children[0] || root;
}

function childEl(el, tag) {
  return el.children.find(c => c.tag === tag) || null;
}
function childText(el, tag) {
  const c = childEl(el, tag);
  return c ? c.text : '';
}
function childInt(el, tag) {
  return parseInt(childText(el, tag), 10) || 0;
}
function childBool(el, tag) {
  return childText(el, tag) === 'true';
}
function childNullableInt(el, tag) {
  const t = childText(el, tag);
  if (!t || t === 'null') return null;
  const n = parseInt(t, 10);
  return isNaN(n) ? null : n;
}
function childrenByTag(el, tag) {
  return el.children.filter(c => c.tag === tag);
}
function childrenIntByTag(el, tag) {
  return childrenByTag(el, tag).map(c => parseInt(c.text, 10)).filter(n => !isNaN(n));
}
function deepChild(el, ...tags) {
  let cur = el;
  for (const tag of tags) {
    cur = childEl(cur, tag);
    if (!cur) return null;
  }
  return cur;
}

// ── .erm 파싱 (ermParser.ts와 동일 로직) ─────────────────────────────────────

function parseErm(xmlString) {
  const diagramEl = parseXml(xmlString);

  const dbEl = deepChild(diagramEl, 'settings', 'database');
  const database = dbEl ? dbEl.text : 'PostgreSQL';

  // Dictionary
  const wordMap = new Map();
  const dictEl = childEl(diagramEl, 'dictionary');
  if (dictEl) {
    for (const wordEl of childrenByTag(dictEl, 'word')) {
      const id = childInt(wordEl, 'id');
      wordMap.set(id, {
        physicalName: childText(wordEl, 'physical_name'),
        logicalName: childText(wordEl, 'logical_name'),
        type: childText(wordEl, 'type'),
        description: childText(wordEl, 'description'),
      });
    }
  }

  const tables = [];
  const relations = [];
  const seenRelations = new Set();

  const contentsEl = childEl(diagramEl, 'contents');
  if (!contentsEl) return { database, tables, relations, categories: [] };

  for (const tableEl of childrenByTag(contentsEl, 'table')) {
    const tableId = childInt(tableEl, 'id');

    // Relations (connections > relation)
    const connectionsEl = childEl(tableEl, 'connections');
    if (connectionsEl) {
      for (const relEl of childrenByTag(connectionsEl, 'relation')) {
        const relId = childInt(relEl, 'id');
        if (!seenRelations.has(relId)) {
          seenRelations.add(relId);
          relations.push({
            id: relId,
            sourceTableId: childInt(relEl, 'source'),
            targetTableId: childInt(relEl, 'target'),
            parentCardinality: childText(relEl, 'parent_cardinality'),
            childCardinality: childText(relEl, 'child_cardinality'),
          });
        }
      }
    }

    // Columns (columns > normal_column)
    const columns = [];
    const columnsEl = childEl(tableEl, 'columns');
    if (columnsEl) {
      for (const colEl of childrenByTag(columnsEl, 'normal_column')) {
        const wordId = childInt(colEl, 'word_id');
        const word = wordMap.get(wordId) || { physicalName: '', logicalName: '', type: '', description: '' };
        columns.push({
          id: childInt(colEl, 'id'),
          wordId,
          physicalName: childText(colEl, 'physical_name') || word.physicalName,
          logicalName: childText(colEl, 'logical_name') || word.logicalName,
          type: childText(colEl, 'type') || word.type,
          description: childText(colEl, 'description') || word.description,
          isPrimaryKey: childBool(colEl, 'primary_key'),
          isForeignKey: childBool(colEl, 'foreign_key'),
          isNotNull: childBool(colEl, 'not_null'),
          isUniqueKey: childBool(colEl, 'unique_key'),
          referencedColumn: childNullableInt(colEl, 'referenced_column'),
          relationId: childNullableInt(colEl, 'relation'),
        });
      }
    }

    tables.push({
      id: tableId,
      physicalName: childText(tableEl, 'physical_name'),
      logicalName: childText(tableEl, 'logical_name'),
      description: childText(tableEl, 'description'),
      x: childInt(tableEl, 'x'),
      y: childInt(tableEl, 'y'),
      width: childInt(tableEl, 'width') || 120,
      height: childInt(tableEl, 'height') || 75,
      columns,
    });
  }

  // Categories
  const categories = [];
  const catParent = deepChild(diagramEl, 'settings', 'category_settings', 'categories');
  if (catParent) {
    for (const catEl of childrenByTag(catParent, 'category')) {
      categories.push({
        id: childInt(catEl, 'id'),
        name: childText(catEl, 'name'),
        tableIds: childrenIntByTag(catEl, 'node_element'),
      });
    }
  }

  return { database, tables, relations, categories };
}

// ── 실행 ──────────────────────────────────────────────────────────────────────

const xmlStr = fs.readFileSync(inputPath, 'utf8');
const diagram = parseErm(xmlStr);

// .erm.json (schema)
const schema = {
  database: diagram.database,
  tables: diagram.tables.map(({ id, physicalName, logicalName, description, columns }) => ({
    id, physicalName, logicalName, description, columns,
  })),
  relations: diagram.relations,
  categories: diagram.categories,
};

// .erm.layout.json (위치 정보)
const layout = {
  tables: Object.fromEntries(
    diagram.tables.map(({ id, x, y, width, height }) => [
      String(id),
      { x, y, width, height },
    ])
  ),
};

const layoutPath = outputPath.replace(/\.erm\.json$/, '.erm.layout.json');

fs.writeFileSync(outputPath, JSON.stringify(schema, null, 2), 'utf8');
fs.writeFileSync(layoutPath, JSON.stringify(layout, null, 2), 'utf8');

const totalCols = schema.tables.reduce((s, t) => s + t.columns.length, 0);
console.log(`✅ 변환 완료`);
console.log(`   ${outputPath}`);
console.log(`   ${layoutPath}`);
console.log(`   테이블 ${schema.tables.length}개 / 컬럼 ${totalCols}개 / 관계 ${schema.relations.length}개`);
