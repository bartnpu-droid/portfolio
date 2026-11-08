/**
 * Daily price monitor → Google Sheet + Telegram alert.
 * Products: one product page URL per row on the "Products" tab (plus an optional "alert below" price).
 * Every morning: reads each page, saves the price to "History", updates "Latest" and sends a Telegram
 * alert when a price changes, drops below your target, or the item goes out of stock.
 * Demo store: books.toscrape.com, a public sandbox made for scraping practice.
 */

const PRICES = {
  TITLE: 'Price monitor: Books to Scrape (demo)',
  PRODUCTS: [
    'https://books.toscrape.com/catalogue/its-only-the-himalayas_981/index.html',
    'https://books.toscrape.com/catalogue/full-moon-over-noahs-ark-an-odyssey-to-mount-ararat-and-beyond_811/index.html',
    'https://books.toscrape.com/catalogue/see-america-a-celebration-of-our-national-parks-treasured-sites_732/index.html',
    'https://books.toscrape.com/catalogue/vagabonding-an-uncommon-guide-to-the-art-of-long-term-world-travel_552/index.html',
    'https://books.toscrape.com/catalogue/under-the-tuscan-sun_504/index.html',
    'https://books.toscrape.com/catalogue/a-summer-in-europe_458/index.html',
    'https://books.toscrape.com/catalogue/the-great-railway-bazaar_446/index.html',
    'https://books.toscrape.com/catalogue/a-year-in-provence-provence-1_421/index.html',
  ],
  LATEST: ['Product', 'Price (£)', 'Previous (£)', 'Change', 'Lowest seen (£)', 'Stock', 'Checked', 'URL', 'Trend'],
  HISTORY: ['Checked', 'Product', 'Price (£)', 'Stock', 'URL'],
};

function pricesBook_() {
  return book_('PRICES_SHEET_ID', PRICES.TITLE);
}

function setupPrices_() {
  const ss = pricesBook_();
  const prod = sheetOr_(ss, 'Products', ['Product URL', 'Alert below (£)', 'Active']);
  if (prod.getLastRow() < 2) {
    prod.getRange(2, 1, PRICES.PRODUCTS.length, 3).setValues(PRICES.PRODUCTS.map(function (u) { return [u, '', true]; }));
  }
  prod.getRange(2, 3, Math.max(prod.getLastRow() - 1, 1), 1).insertCheckboxes();
  prod.setColumnWidth(1, 520);
  prod.setColumnWidth(2, 120);

  const latest = sheetOr_(ss, 'Latest', PRICES.LATEST);
  latest.setColumnWidth(1, 300);
  latest.setColumnWidths(2, 6, 110);
  latest.setColumnWidth(6, 170);
  latest.setColumnWidth(8, 120);
  latest.setColumnWidth(9, 140);

  const hist = sheetOr_(ss, 'History', PRICES.HISTORY);
  hist.setColumnWidth(2, 300);
  hist.getRange('A2:A').setNumberFormat('dd mmm yyyy, hh:mm');
  hist.getRange('C2:C').setNumberFormat('£0.00');

  ss.setActiveSheet(latest);
  ss.moveActiveSheet(1);
}

/** Runs every morning (see installTriggers in Common.gs); can also be run by hand. */
function checkPrices() {
  const ss = pricesBook_();
  const prod = ss.getSheetByName('Products');
  const latest = ss.getSheetByName('Latest');
  const hist = ss.getSheetByName('History');

  const items = prod.getLastRow() > 1
    ? prod.getRange(2, 1, prod.getLastRow() - 1, 3).getValues().filter(function (r) { return r[0] && r[2] !== false; })
    : [];
  const prev = {};
  if (latest.getLastRow() > 1) {
    latest.getRange(2, 1, latest.getLastRow() - 1, PRICES.LATEST.length).getValues().forEach(function (r, i) {
      prev[r[7]] = { row: i + 2, price: Number(r[1]) || 0, lowest: Number(r[4]) || Number(r[1]) || 0 };
    });
  }

  const now = new Date();
  const alerts = [];
  const historyRows = [];
  const responses = UrlFetchApp.fetchAll(items.map(function (r) {
    return { url: String(r[0]), muteHttpExceptions: true, followRedirects: true };
  }));

  responses.forEach(function (res, i) {
    const url = String(items[i][0]);
    const alertBelow = Number(items[i][1]) || 0;
    if (res.getResponseCode() !== 200) {
      alerts.push('⚠️ Page did not open (' + res.getResponseCode() + '): ' + esc_(url));
      return;
    }
    const info = parseProduct_(res.getContentText('UTF-8'));
    if (!info) {
      alerts.push('⚠️ Price not found on the page: ' + esc_(url));
      return;
    }
    historyRows.push([now, info.title, info.price, info.stock, url]);

    const p = prev[url];
    const had = p && p.price > 0;
    const change = had ? (info.price - p.price) / p.price : '';
    const lowest = had ? Math.min(p.lowest || info.price, info.price) : info.price;
    const row = [info.title, info.price, had ? p.price : '', change, lowest, info.stock, now, url, ''];
    if (p) latest.getRange(p.row, 1, 1, row.length).setValues([row]);
    else latest.appendRow(row);

    if (had && info.price !== p.price) {
      alerts.push((info.price < p.price ? '📉 ' : '📈 ') + '<b>' + esc_(info.title) + '</b>: £' + p.price.toFixed(2) +
        ' → £' + info.price.toFixed(2) + ' (' + (change > 0 ? '+' : '') + (change * 100).toFixed(1) + '%)');
    }
    // Target alert only when the price crosses the target, so it does not repeat every morning
    if (alertBelow && info.price <= alertBelow && (!had || p.price > alertBelow)) {
      alerts.push('🎯 <b>' + esc_(info.title) + '</b> is £' + info.price.toFixed(2) + ', below your £' + alertBelow.toFixed(2));
    }
    if (/out of stock/i.test(info.stock)) alerts.push('🚫 <b>' + esc_(info.title) + '</b> is out of stock');
  });

  if (historyRows.length) hist.getRange(hist.getLastRow() + 1, 1, historyRows.length, PRICES.HISTORY.length).setValues(historyRows);
  formatLatest_(latest);
  if (alerts.length) {
    telegram_('🛒 <b>Daily price check</b>\n' + alerts.join('\n') + '\n<a href="' + ss.getUrl() + '">Open the sheet</a>');
  }
  return { checked: historyRows.length, alerts: alerts.length };
}

/** Title, price and stock from a product page of the demo store. */
function parseProduct_(html) {
  const t = html.match(/<h1>([\s\S]*?)<\/h1>/);
  const p = html.match(/<p class="price_color">\s*(?:£|&pound;|Â£)?\s*([\d.,]+)\s*<\/p>/);
  const s = html.match(/<p class="(?:instock|outofstock) availability">([\s\S]*?)<\/p>/);
  if (!t || !p) return null;
  return {
    title: decodeHtml_(t[1].trim()),
    price: Number(p[1].replace(/,/g, '')),
    stock: s ? s[1].replace(/<[^>]+>/g, '').replace(/\s+/g, ' ').trim() : '',
  };
}

function decodeHtml_(s) {
  return s
    .replace(/&#39;/g, "'")
    .replace(/&quot;/g, '"')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&amp;/g, '&');
}

function formatLatest_(sh) {
  const n = sh.getLastRow() - 1;
  if (n < 1) return;
  sh.getRange(2, 2, n, 2).setNumberFormat('£0.00');
  sh.getRange(2, 4, n, 1).setNumberFormat('+0.0%;-0.0%;0.0%');
  sh.getRange(2, 5, n, 1).setNumberFormat('£0.00');
  sh.getRange(2, 7, n, 1).setNumberFormat('dd mmm, hh:mm');
  // Trend: price history of this product as a small line chart in the cell
  const formulas = [];
  for (let r = 2; r <= n + 1; r++) {
    formulas.push(['=IFERROR(SPARKLINE(FILTER(History!C:C, History!E:E=H' + r + ')), "")']);
  }
  sh.getRange(2, 9, n, 1).setFormulas(formulas);
  const changeRange = sh.getRange(2, 4, n, 1);
  sh.setConditionalFormatRules([
    SpreadsheetApp.newConditionalFormatRule().whenNumberLessThan(0).setFontColor('#0f7b3e').setBackground('#e6f4ea').setRanges([changeRange]).build(),
    SpreadsheetApp.newConditionalFormatRule().whenNumberGreaterThan(0).setFontColor('#b3261e').setBackground('#fce8e6').setRanges([changeRange]).build(),
  ]);
}
