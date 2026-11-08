// Offline tests for the Apps Script code: Google services are replaced by small in-memory fakes.
// Run: node 05-sheets-automations/tests/run.js
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const assert = require('assert');

function colNum(letters) {
  return letters.split('').reduce((n, c) => n * 26 + c.charCodeAt(0) - 64, 0);
}

class Range {
  constructor(sheet, row, col, nr, nc) { Object.assign(this, { sheet, row, col, nr, nc }); }
  setValues(v) {
    assert.strictEqual(v.length, this.nr, 'rows mismatch');
    v.forEach((r, i) => { assert.strictEqual(r.length, this.nc, 'cols mismatch'); r.forEach((x, j) => this.sheet.set(this.row + i, this.col + j, x)); });
    return this;
  }
  getValues() {
    const out = [];
    for (let i = 0; i < this.nr; i++) { const r = []; for (let j = 0; j < this.nc; j++) r.push(this.sheet.get(this.row + i, this.col + j)); out.push(r); }
    return out;
  }
  setFormulas(f) { f.forEach((r, i) => r.forEach((x, j) => this.sheet.formulas[(this.row + i) + ':' + (this.col + j)] = x)); return this; }
  insertCheckboxes() { return this; }
  setFontWeight() { return this; }
  setBackground() { return this; }
  setFontColor() { return this; }
  setNumberFormat() { return this; }
  setDataValidation() { return this; }
}

class Sheet {
  constructor(book, name) { this.book = book; this.name = name; this.cells = {}; this.formulas = {}; this.maxRow = 0; this.rules = []; }
  set(r, c, v) { this.cells[r + ':' + c] = v; if (v !== '' && v != null && r > this.maxRow) this.maxRow = r; }
  get(r, c) { const v = this.cells[r + ':' + c]; return v === undefined ? '' : v; }
  getName() { return this.name; }
  setName(n) { this.name = n; return this; }
  getLastRow() { return this.maxRow; }
  getRange(a, b, c, d) {
    if (typeof a === 'string') {
      const m = a.match(/^([A-Z]+)(\d+):([A-Z]+)(\d*)$/);
      const c1 = colNum(m[1]), c2 = colNum(m[3]);
      return new Range(this, Number(m[2]), c1, Math.max(this.maxRow - Number(m[2]) + 1, 1), c2 - c1 + 1);
    }
    return new Range(this, a, b, c || 1, d || 1);
  }
  appendRow(values) { const r = this.maxRow + 1; values.forEach((v, j) => this.set(r, j + 1, v)); this.maxRow = r; return this; }
  setFrozenRows() { return this; }
  setColumnWidth() { return this; }
  setColumnWidths() { return this; }
  setConditionalFormatRules(r) { this.rules = r; return this; }
  rowsOf(n) { const out = []; for (let r = 2; r <= this.maxRow; r++) out.push(this.getRange(r, 1, 1, n).getValues()[0]); return out; }
}

class Book {
  constructor(id, title) { this.id = id; this.title = title; this.sheets = [new Sheet(this, 'Sheet1')]; this.shared = false; }
  getId() { return this.id; }
  getUrl() { return 'https://docs.google.com/spreadsheets/d/' + this.id + '/edit'; }
  getSheets() { return this.sheets; }
  getSheetByName(n) { return this.sheets.find((s) => s.name === n) || null; }
  insertSheet(n) { const s = new Sheet(this, n); this.sheets.push(s); return s; }
  setActiveSheet(s) { this.active = s; return s; }
  moveActiveSheet(pos) { this.sheets = [this.active].concat(this.sheets.filter((s) => s !== this.active)); return this; }
}

function makeEnv() {
  const props = {};
  const books = {};
  const cache = {};
  const sent = [];
  const triggers = [];
  let fetchAllImpl = () => [];
  let nextId = 1;
  const chain = () => new Proxy({}, { get: (t, k) => (k === 'build' ? () => ({ built: true }) : () => chain()) });
  const ctx = {
    console,
    PropertiesService: { getScriptProperties: () => ({ getProperty: (k) => (k in props ? props[k] : null), setProperty: (k, v) => { props[k] = String(v); } }) },
    SpreadsheetApp: {
      openById: (id) => { if (!books[id]) throw new Error('not found'); return books[id]; },
      create: (title) => { const id = 'ss' + nextId++; books[id] = new Book(id, title); return books[id]; },
      newDataValidation: chain,
      newConditionalFormatRule: chain,
    },
    DriveApp: { getFileById: (id) => ({ setSharing: () => { books[id].shared = true; } }), Access: { ANYONE_WITH_LINK: 1 }, Permission: { VIEW: 1 } },
    UrlFetchApp: {
      fetch: (url, opts) => { sent.push({ url, body: JSON.parse(opts.payload) }); return { getResponseCode: () => 200, getContentText: () => '{"ok":true}' }; },
      fetchAll: (reqs) => fetchAllImpl(reqs),
    },
    CacheService: { getScriptCache: () => ({ get: (k) => (k in cache ? cache[k] : null), put: (k, v) => { cache[k] = v; } }) },
    LockService: { getScriptLock: () => ({ waitLock: () => {}, releaseLock: () => {} }) },
    ContentService: { createTextOutput: (s) => ({ text: s, setMimeType() { return this; } }), MimeType: { JSON: 'json' } },
    Utilities: { formatDate: (d) => d.toISOString().slice(0, 13) },
    Logger: { log: () => {} },
    ScriptApp: {
      getProjectTriggers: () => triggers.slice(),
      deleteTrigger: (t) => triggers.splice(triggers.indexOf(t), 1),
      newTrigger: (fn) => { const b = { timeBased: () => b, everyDays: () => b, atHour: () => b, nearMinute: () => b, create: () => { triggers.push(fn); return fn; } }; return b; },
    },
  };
  vm.createContext(ctx);
  const dir = path.join(__dirname, '..', 'apps-script');
  for (const f of ['Common.gs', 'Leads.gs', 'Prices.gs']) vm.runInContext(fs.readFileSync(path.join(dir, f), 'utf8'), ctx, { filename: f });
  return { ctx, props, books, sent, triggers, cache, setFetchAll: (fn) => { fetchAllImpl = fn; } };
}

const page = (title, price, stock = 'In stock (22 available)', pound = '£') =>
  `<html><h1>${title}</h1><p class="price_color">${pound}${price}</p>
   <p class="instock availability">
      <i class="icon-ok"></i>
      ${stock}
   </p></html>`;
const res = (code, text) => ({ getResponseCode: () => code, getContentText: () => text });
const out = (r) => JSON.parse(r.text);
let passed = 0;
function test(name, fn) { fn(); passed++; console.log('ok  ' + name); }

// ---------- setup ----------
const env = makeEnv();
const C = env.ctx;
test('setup creates both shared sheets and two daily triggers', () => {
  C.setup();
  const leads = env.books[env.props.LEADS_SHEET_ID];
  const prices = env.books[env.props.PRICES_SHEET_ID];
  assert.ok(leads.shared && prices.shared);
  assert.deepStrictEqual(leads.getSheetByName('Leads').getRange(1, 1, 1, 8).getValues()[0][0], 'Received');
  assert.strictEqual(prices.getSheetByName('Products').getLastRow(), 9);
  assert.strictEqual(prices.sheets[0].name, 'Latest');
  assert.deepStrictEqual(env.triggers.sort(), ['checkPrices', 'dailyLeadsSummary']);
  C.setup(); // running again does not duplicate anything
  assert.strictEqual(env.triggers.length, 2);
  assert.strictEqual(env.books[env.props.PRICES_SHEET_ID].getSheetByName('Products').getLastRow(), 9);
});

// ---------- leads ----------
test('honeypot request is accepted silently and not saved', () => {
  const r = out(C.doPost({ parameter: { name: 'Bot', contact: 'a@b.co', company_website: 'spam' } }));
  assert.deepStrictEqual(r, { ok: true, id: 0 });
  assert.strictEqual(env.books[env.props.LEADS_SHEET_ID].getSheetByName('Leads').getLastRow(), 1);
});

test('without Telegram settings the lead is still saved', () => {
  const r = out(C.doPost({ parameter: { name: 'Anna Smith', contact: '+44 7700 900123', service: 'Deep cleaning', date: '2026-11-20', message: 'Two bedrooms, see www.spam.com' } }));
  assert.deepStrictEqual(r, { ok: true, id: 1 });
  const row = env.books[env.props.LEADS_SHEET_ID].getSheetByName('Leads').rowsOf(8)[0];
  assert.strictEqual(row[1], 'Anna');
  assert.strictEqual(row[2], "'+44******123"); // leading ' keeps it as text, Sheets does not show it
  assert.strictEqual(row[3], 'Deep cleaning');
  assert.strictEqual(row[4], '2026-11-20');
  assert.ok(row[5].includes('[link removed]') && !row[5].includes('spam.com'));
  assert.strictEqual(row[7], 'New');
  assert.strictEqual(env.sent.length, 0);
});

env.props.TELEGRAM_BOT_TOKEN = '123:abc';
env.props.TELEGRAM_CHAT_ID = '@demo_channel';

test('JSON body works and sends a Telegram alert without free text', () => {
  const r = out(C.doPost({ parameter: {}, postData: { contents: JSON.stringify({ name: 'Tom <b>', contact: 'tom@example.com', service: 'Office cleaning', message: 'call me' }) } }));
  assert.deepStrictEqual(r, { ok: true, id: 2 });
  assert.strictEqual(env.sent.length, 1);
  const msg = env.sent[0].body;
  assert.strictEqual(msg.chat_id, '@demo_channel');
  assert.strictEqual(msg.parse_mode, 'HTML');
  assert.ok(msg.text.includes('New request #2'));
  assert.ok(msg.text.includes('t***@example.com'));
  assert.ok(msg.text.includes('has a message'));
  assert.ok(!msg.text.includes('call me'));
  assert.ok(env.sent[0].url.endsWith('/sendMessage'));
});

test('bad contact and missing name are rejected with a clear message', () => {
  assert.strictEqual(out(C.doPost({ parameter: { name: 'Al', contact: 'hello' } })).error, 'Please enter a phone number or an email.');
  assert.strictEqual(out(C.doPost({ parameter: { name: ' ', contact: '+44 7700 900123' } })).error, 'Please enter your name.');
  assert.strictEqual(out(C.doPost({ parameter: { name: 'Al', contact: '123' } })).ok, false);
});

test('unknown service becomes "Other", bad date is dropped', () => {
  out(C.doPost({ parameter: { name: 'Kate', contact: '07700 900456', service: 'Car wash', date: 'tomorrow' } }));
  const rows = env.books[env.props.LEADS_SHEET_ID].getSheetByName('Leads').rowsOf(8);
  const last = rows[rows.length - 1];
  assert.strictEqual(last[3], 'Other');
  assert.strictEqual(last[4], '');
  assert.strictEqual(last[2], '07******456');
});

test('formula-like text is saved as plain text, not as a formula', () => {
  out(C.doPost({ parameter: { name: '=HYPERLINK("x")', contact: 'eve@example.com', message: '=IMAGE("y") hi', source: '@ads' } }));
  const rows = env.books[env.props.LEADS_SHEET_ID].getSheetByName('Leads').rowsOf(8);
  const last = rows[rows.length - 1];
  assert.strictEqual(last[1], '\'=HYPERLINK("x")');
  assert.strictEqual(last[5], '\'=IMAGE("y") hi');
  assert.strictEqual(last[6], "'@ads");
  assert.strictEqual(last[2], 'e***@example.com');
});

test('spam guard stops after 40 requests in an hour', () => {
  const key = Object.keys(env.cache)[0];
  env.cache[key] = '40';
  const r = out(C.doPost({ parameter: { name: 'Late', contact: 'late@example.com' } }));
  assert.strictEqual(r.ok, false);
  assert.ok(/Too many requests/.test(r.error));
  env.cache[key] = '0';
});

test('morning summary counts new requests by service', () => {
  env.sent.length = 0;
  C.dailyLeadsSummary();
  assert.strictEqual(env.sent.length, 1);
  const t = env.sent[0].body.text;
  assert.ok(t.includes('Requests in the last 24 hours: 4'), t);
  assert.ok(t.includes('Deep cleaning: 1') && t.includes('Office cleaning: 1') && t.includes('Other: 2'));
  assert.ok(t.includes('Still waiting for a reply: 4'));
});

// ---------- prices ----------
test('product page parser: title, price, stock, entities and broken £ encoding', () => {
  assert.deepStrictEqual(JSON.parse(JSON.stringify(C.parseProduct_(page('It&#39;s Only the Himalayas', '45.17')))), { title: "It's Only the Himalayas", price: 45.17, stock: 'In stock (22 available)' });
  assert.strictEqual(C.parseProduct_(page('A', '1,045.50', 'In stock', 'Â£')).price, 1045.5);
  assert.strictEqual(C.parseProduct_('<html>no price</html>'), null);
});

const titles = {};
let prices = {};
env.setFetchAll((reqs) => reqs.map((r, i) => {
  titles[r.url] = titles[r.url] || 'Book ' + (i + 1);
  return res(200, page(titles[r.url], prices[r.url].toFixed(2), prices[r.url] < 0 ? 'Out of stock' : (prices[r.url].stock || 'In stock (5 available)')));
}));

test('first price check fills Latest and History and sends no alert', () => {
  const urls = env.books[env.props.PRICES_SHEET_ID].getSheetByName('Products').rowsOf(3).map((r) => r[0]);
  urls.forEach((u, i) => { prices[u] = 20 + i; });
  env.sent.length = 0;
  const r = C.checkPrices();
  assert.deepStrictEqual(JSON.parse(JSON.stringify(r)), { checked: 8, alerts: 0 });
  const book = env.books[env.props.PRICES_SHEET_ID];
  assert.strictEqual(book.getSheetByName('Latest').getLastRow(), 9);
  assert.strictEqual(book.getSheetByName('History').getLastRow(), 9);
  assert.strictEqual(env.sent.length, 0);
  assert.ok(book.getSheetByName('Latest').formulas['2:9'].startsWith('=IFERROR(SPARKLINE('));
});

test('second check alerts on a price drop and a target price; Latest keeps previous price', () => {
  const book = env.books[env.props.PRICES_SHEET_ID];
  const prod = book.getSheetByName('Products');
  const urls = prod.rowsOf(3).map((r) => r[0]);
  prod.set(3, 2, 19); // alert below £19 for the 2nd product
  prices[urls[0]] = 18; // 20 → 18
  prices[urls[1]] = 18.5; // 21 → 18.5, also below 19
  env.sent.length = 0;
  const r = C.checkPrices();
  assert.strictEqual(r.checked, 8);
  assert.strictEqual(env.sent.length, 1);
  const t = env.sent[0].body.text;
  assert.ok(t.includes('📉 <b>Book 1</b>: £20.00 → £18.00 (-10.0%)'), t);
  assert.ok(t.includes('🎯 <b>Book 2</b> is £18.50, below your £19.00'), t);
  const latest = book.getSheetByName('Latest').rowsOf(9);
  assert.strictEqual(latest[0][1], 18);
  assert.strictEqual(latest[0][2], 20);
  assert.ok(Math.abs(latest[0][3] + 0.1) < 1e-9);
  assert.strictEqual(latest[0][4], 18);
  assert.strictEqual(book.getSheetByName('History').getLastRow(), 17);
});

test('same prices next day: no repeated target alert, nothing sent', () => {
  env.sent.length = 0;
  const r = C.checkPrices();
  assert.deepStrictEqual(JSON.parse(JSON.stringify(r)), { checked: 8, alerts: 0 });
  assert.strictEqual(env.sent.length, 0);
});

test('broken page and missing price are reported, others still saved', () => {
  const urls = env.books[env.props.PRICES_SHEET_ID].getSheetByName('Products').rowsOf(3).map((r) => r[0]);
  env.setFetchAll((reqs) => reqs.map((r, i) => (i === 0 ? res(503, '') : i === 1 ? res(200, '<html></html>') : res(200, page('Book ' + (i + 1), prices[r.url].toFixed(2))))));
  env.sent.length = 0;
  const r = C.checkPrices();
  assert.strictEqual(r.checked, 6);
  const t = env.sent[0].body.text;
  assert.ok(t.includes('did not open (503)') && t.includes('Price not found'), t);
  assert.ok(urls.length === 8);
});

console.log(`\n${passed} tests passed`);
