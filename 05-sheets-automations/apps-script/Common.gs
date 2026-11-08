/**
 * Two small-business automations in Google Apps Script (no server, free to run):
 *   1) Website form → Google Sheet → Telegram alert          (Leads.gs)
 *   2) Daily price monitor → Google Sheet + Telegram alert    (Prices.gs)
 *
 * Settings: Project Settings → Script properties
 *   TELEGRAM_BOT_TOKEN  token from @BotFather (keep it out of the code)
 *   TELEGRAM_CHAT_ID    where alerts go: @PublicChannel or a numeric chat id
 * The spreadsheet ids are saved there automatically by setup().
 *
 * First run: choose `setup` in the toolbar and press Run (creates both sheets and the daily triggers).
 */

const PROPS = PropertiesService.getScriptProperties();

function prop_(key) {
  return PROPS.getProperty(key) || '';
}

/** One-time setup: creates both spreadsheets (view-only for anyone with the link) and the daily triggers. */
function setup() {
  setupLeads_();
  setupPrices_();
  installTriggers();
  Logger.log('Leads sheet:  ' + leadsBook_().getUrl());
  Logger.log('Prices sheet: ' + pricesBook_().getUrl());
}

/** Daily price check at about 9:00 and a leads summary a few minutes later (script time zone). */
function installTriggers() {
  ScriptApp.getProjectTriggers().forEach(function (t) { ScriptApp.deleteTrigger(t); });
  ScriptApp.newTrigger('checkPrices').timeBased().everyDays(1).atHour(9).create();
  ScriptApp.newTrigger('dailyLeadsSummary').timeBased().everyDays(1).atHour(9).nearMinute(15).create();
}

/** Sends an HTML message to Telegram. Returns true when Telegram accepted it. */
function telegram_(html) {
  const token = prop_('TELEGRAM_BOT_TOKEN');
  const chat = prop_('TELEGRAM_CHAT_ID');
  if (!token || !chat) {
    Logger.log('Telegram is not set up yet. Message: ' + html);
    return false;
  }
  const res = UrlFetchApp.fetch('https://api.telegram.org/bot' + token + '/sendMessage', {
    method: 'post',
    contentType: 'application/json',
    muteHttpExceptions: true,
    payload: JSON.stringify({
      chat_id: chat,
      text: html,
      parse_mode: 'HTML',
      link_preview_options: { is_disabled: true },
    }),
  });
  const ok = res.getResponseCode() === 200;
  if (!ok) Logger.log('Telegram error ' + res.getResponseCode() + ': ' + res.getContentText().slice(0, 200));
  return ok;
}

function esc_(s) {
  return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

/** Opens the spreadsheet saved under `key`, or creates it (view-only for anyone with the link). */
function book_(key, title) {
  const id = prop_(key);
  if (id) {
    try {
      return SpreadsheetApp.openById(id);
    } catch (e) {
      Logger.log('Saved sheet not found, creating a new one: ' + e);
    }
  }
  const ss = SpreadsheetApp.create(title);
  PROPS.setProperty(key, ss.getId());
  try {
    DriveApp.getFileById(ss.getId()).setSharing(DriveApp.Access.ANYONE_WITH_LINK, DriveApp.Permission.VIEW);
  } catch (e) {
    Logger.log('Could not share the sheet: ' + e);
  }
  return ss;
}

/** Returns the sheet `name` with a styled header row, creating it when missing. */
function sheetOr_(ss, name, headers) {
  let sh = ss.getSheetByName(name);
  if (!sh) {
    const first = ss.getSheets()[0];
    sh = first.getLastRow() === 0 && /^(Sheet|Лист|Аркуш)\d*$/.test(first.getName()) ? first.setName(name) : ss.insertSheet(name);
  }
  sh.getRange(1, 1, 1, headers.length)
    .setValues([headers])
    .setFontWeight('bold')
    .setBackground('#0f5132')
    .setFontColor('#ffffff');
  sh.setFrozenRows(1);
  return sh;
}

function json_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}
