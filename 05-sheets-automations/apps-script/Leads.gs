/**
 * Website form → Google Sheet → Telegram alert.
 * Deploy → New deployment → Web app (Execute as: Me, Who has access: Anyone).
 * The website form sends a POST to the web app URL; each request becomes a row and an instant alert.
 */

const LEADS = {
  TITLE: 'Brightway Cleaning: leads (demo)',
  SHEET: 'Leads',
  HEADERS: ['Received', 'Name', 'Contact', 'Service', 'Preferred date', 'Message', 'Source', 'Status'],
  SERVICES: ['Regular cleaning', 'Deep cleaning', 'End of tenancy', 'Office cleaning'],
  STATUSES: ['New', 'Contacted', 'Booked', 'Lost'],
  DEMO_MODE: true, // the demo sheet is public: contacts are masked, links removed, alerts show no free text
  MAX_PER_HOUR: 40, // simple spam guard
};

function leadsBook_() {
  return book_('LEADS_SHEET_ID', LEADS.TITLE);
}

function setupLeads_() {
  const sh = sheetOr_(leadsBook_(), LEADS.SHEET, LEADS.HEADERS);
  sh.setColumnWidths(1, LEADS.HEADERS.length, 150);
  sh.setColumnWidth(6, 320);
  sh.getRange('A2:A').setNumberFormat('dd mmm yyyy, hh:mm');
  sh.getRange('H2:H').setDataValidation(
    SpreadsheetApp.newDataValidation().requireValueInList(LEADS.STATUSES, true).build()
  );
  const colors = { New: '#fff3cd', Contacted: '#cfe2ff', Booked: '#d1e7dd', Lost: '#f8d7da' };
  sh.setConditionalFormatRules(
    Object.keys(colors).map(function (v) {
      return SpreadsheetApp.newConditionalFormatRule()
        .whenTextEqualTo(v)
        .setBackground(colors[v])
        .setRanges([sh.getRange('H2:H')])
        .build();
    })
  );
}

/** Health check for the web app URL. */
function doGet() {
  return json_({ ok: true, demo: 'website form → Google Sheet → Telegram' });
}

/** Receives one request from the website form. */
function doPost(e) {
  try {
    const p = params_(e);
    if (p.company_website) return json_({ ok: true, id: 0 }); // honeypot: people never fill this hidden field
    const lead = cleanLead_(p);
    if (!underLimit_()) return json_({ ok: false, error: 'Too many requests right now. Please try again in an hour.' });
    const lock = LockService.getScriptLock();
    lock.waitLock(15000);
    let row;
    try {
      const sh = leadsBook_().getSheetByName(LEADS.SHEET);
      sh.appendRow([new Date(), cell_(lead.nameShown), cell_(lead.contactShown), lead.service, lead.date, cell_(lead.messageShown), cell_(lead.source), 'New']);
      row = sh.getLastRow();
    } finally {
      lock.releaseLock();
    }
    telegram_(leadAlert_(lead, row - 1));
    return json_({ ok: true, id: row - 1 });
  } catch (err) {
    return json_({ ok: false, error: String((err && err.message) || err) });
  }
}

/** Form fields (urlencoded) or a JSON body. */
function params_(e) {
  const p = Object.assign({}, (e && e.parameter) || {});
  const body = e && e.postData && e.postData.contents;
  if (body && /^\s*\{/.test(body)) {
    try {
      Object.assign(p, JSON.parse(body));
    } catch (x) {
      // not JSON: keep the form fields
    }
  }
  return p;
}

function cleanLead_(p) {
  const str = function (v, n) {
    return String(v == null ? '' : v).replace(/\s+/g, ' ').trim().slice(0, n);
  };
  const name = str(p.name, 60);
  const contact = str(p.contact, 80);
  const service = LEADS.SERVICES.indexOf(p.service) >= 0 ? p.service : 'Other';
  const date = /^\d{4}-\d{2}-\d{2}$/.test(p.date || '') ? p.date : '';
  const message = str(p.message, 500).replace(/https?:\/\/\S+|www\.\S+/gi, '[link removed]');
  if (name.length < 2) throw new Error('Please enter your name.');
  if (!isContact_(contact)) throw new Error('Please enter a phone number or an email.');
  return {
    name: name,
    contact: contact,
    service: service,
    date: date,
    message: message,
    source: str(p.source, 40) || 'Website',
    nameShown: LEADS.DEMO_MODE ? name.split(' ')[0] : name,
    contactShown: LEADS.DEMO_MODE ? maskContact_(contact) : contact,
    messageShown: LEADS.DEMO_MODE ? message.slice(0, 200) : message,
  };
}

/** Text starting with = + - @ would turn into a formula in Sheets (a phone like +44… too): keep it as plain text. */
function cell_(v) {
  return typeof v === 'string' && /^[=+\-@]/.test(v) ? "'" + v : v;
}

function isContact_(s) {
  const email = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(s);
  const phone = /^\+?[\d\s()-]+$/.test(s) && s.replace(/\D/g, '').length >= 7;
  return email || phone;
}

function maskContact_(s) {
  if (s.indexOf('@') > 0) {
    const parts = s.split('@');
    return parts[0].slice(0, 1) + '***@' + parts[1];
  }
  const digits = s.replace(/\D/g, '');
  return (s.trim().charAt(0) === '+' ? '+' : '') + digits.slice(0, 2) + '******' + digits.slice(-3);
}

function underLimit_() {
  const cache = CacheService.getScriptCache();
  const key = 'leads_' + Utilities.formatDate(new Date(), 'UTC', 'yyyyMMddHH');
  const n = Number(cache.get(key) || 0) + 1;
  cache.put(key, String(n), 3600);
  return n <= LEADS.MAX_PER_HOUR;
}

function leadAlert_(lead, id) {
  const lines = [
    '🆕 <b>New request #' + id + '</b>',
    '👤 ' + esc_(lead.nameShown),
    '🧽 ' + esc_(lead.service) + (lead.date ? '  ·  📅 ' + esc_(lead.date) : ''),
    '📞 ' + esc_(lead.contactShown),
  ];
  if (lead.message) lines.push('💬 ' + (LEADS.DEMO_MODE ? 'has a message (see the sheet)' : esc_(lead.message.slice(0, 300))));
  lines.push('<a href="' + leadsBook_().getUrl() + '">Open the sheet</a>');
  return lines.join('\n');
}

/** Morning summary: new requests in the last 24 hours and how many still wait for a reply. */
function dailyLeadsSummary() {
  const sh = leadsBook_().getSheetByName(LEADS.SHEET);
  const n = sh.getLastRow() - 1;
  const rows = n > 0 ? sh.getRange(2, 1, n, LEADS.HEADERS.length).getValues() : [];
  const since = Date.now() - 24 * 3600 * 1000;
  const fresh = rows.filter(function (r) { return r[0] instanceof Date && r[0].getTime() >= since; });
  const waiting = rows.filter(function (r) { return r[7] === 'New'; }).length;
  if (!fresh.length && !waiting) return;
  const byService = {};
  fresh.forEach(function (r) { byService[r[3]] = (byService[r[3]] || 0) + 1; });
  const lines = ['☀️ <b>Requests in the last 24 hours: ' + fresh.length + '</b>'];
  Object.keys(byService).forEach(function (k) { lines.push('• ' + esc_(k) + ': ' + byService[k]); });
  lines.push('Still waiting for a reply: ' + waiting);
  lines.push('<a href="' + leadsBook_().getUrl() + '">Open the sheet</a>');
  telegram_(lines.join('\n'));
}
