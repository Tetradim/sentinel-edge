/* global console, document, fetch, process, URL, window */
import { chromium } from 'playwright-core';
import { existsSync } from 'node:fs';
import { readFile } from 'node:fs/promises';

const appUrl = process.env.SENTINEL_EDGE_UI_URL || 'http://127.0.0.1:5173/';
const chromeCandidates = [
  process.env.PLAYWRIGHT_CHROME_EXECUTABLE,
  process.env.CHROME_PATH,
  'C:/Program Files/Google/Chrome/Application/chrome.exe',
  'C:/Program Files (x86)/Google/Chrome/Application/chrome.exe',
].filter(Boolean);

function parsePrice(text) {
  const value = Number(String(text || '').replace(/[^0-9.-]/g, ''));
  if (!Number.isFinite(value)) throw new Error(`Unable to parse price from "${text}"`);
  return value;
}

function firstNumber(text) {
  const match = String(text || '').match(/-?\d+(?:\.\d+)?/);
  if (!match) throw new Error(`Unable to parse number from "${text}"`);
  const value = Number(match[0]);
  if (!Number.isFinite(value)) throw new Error(`Unable to parse finite number from "${text}"`);
  return value;
}

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

function isToleratedOrbEmptyResponse(response) {
  if (response.status !== 404) return false;
  try {
    const url = new URL(response.url);
    return /^\/api\/orb\/[^/]+$/.test(url.pathname);
  } catch {
    return response.url.includes('/api/orb/');
  }
}

function splitConsoleErrors(messages, { toleratedOrbEmptyCount = 0 } = {}) {
  let remainingOrbConsoleAllowance = toleratedOrbEmptyCount;
  const toleratedOrbConsoleErrors = [];
  const unexpectedConsoleErrors = [];
  for (const message of messages) {
    if (message.includes('status of 429 (Too Many Requests)')) continue;
    if (
      remainingOrbConsoleAllowance > 0
      && message.includes('Failed to load resource')
      && message.includes('status of 404')
    ) {
      toleratedOrbConsoleErrors.push(message);
      remainingOrbConsoleAllowance -= 1;
      continue;
    }
    unexpectedConsoleErrors.push(message);
  }
  return { unexpectedConsoleErrors, toleratedOrbConsoleErrors };
}

function payloadArray(value, keys = []) {
  if (Array.isArray(value)) return value;
  for (const key of keys) {
    const nested = value?.[key];
    if (Array.isArray(nested)) return nested;
    if (nested && typeof nested === 'object') {
      return Object.entries(nested).map(([key, item]) => (
        item && typeof item === 'object' ? { key, name: key, ...item } : { key, name: key, value: item }
      ));
    }
  }
  if (value && typeof value === 'object') {
    return Object.entries(value).map(([key, item]) => (
      item && typeof item === 'object' ? { key, name: key, ...item } : { key, name: key, value: item }
    ));
  }
  return [];
}

function expectedStatusLabel(row, fallbackPrefix, index) {
  return String(row?.label ?? row?.name ?? row?.provider ?? row?.key ?? `${fallbackPrefix} ${index + 1}`);
}

async function fetchJson(path, options = {}) {
  const response = await fetch(new URL(path, appUrl), options);
  if (!response.ok) throw new Error(`${path} returned ${response.status}`);
  return response.json();
}

async function expectedLevelsFor(symbol) {
  const chart = await fetchJson(`/api/chart-workspace/${encodeURIComponent(symbol)}?limit=180`);
  const currentPrice = chart.bars.at(-1).close;
  const sr = await fetchJson('/api/support-resistance/evaluate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      symbol,
      bars: chart.bars,
      current_price: currentPrice,
      settings: { opening_range_minutes: 30, swing_window: 2 },
      emit_event: false,
    }),
  });
  const support = sr.levels.items
    .filter((item) => item.role === 'support' && item.price <= currentPrice)
    .sort((a, b) => b.price - a.price)[0]
    ?? sr.levels.items.filter((item) => item.role === 'support').sort((a, b) => Math.abs(a.price - currentPrice) - Math.abs(b.price - currentPrice))[0];
  const resistance = sr.levels.items
    .filter((item) => item.role === 'resistance' && item.price >= currentPrice)
    .sort((a, b) => a.price - b.price)[0]
    ?? sr.levels.items.filter((item) => item.role === 'resistance').sort((a, b) => Math.abs(a.price - currentPrice) - Math.abs(b.price - currentPrice))[0];
  return { symbol, chart, currentPrice, sr, support, resistance };
}

async function launchChrome() {
  const executablePath = chromeCandidates.find((candidate) => existsSync(candidate));
  if (executablePath) {
    return chromium.launch({ executablePath, headless: true });
  }
  try {
    return await chromium.launch({ headless: true });
  } catch (error) {
    throw new Error(
      `Unable to launch Chromium. Install Chrome or set CHROME_PATH/PLAYWRIGHT_CHROME_EXECUTABLE. Original error: ${error.message}`,
      { cause: error },
    );
  }
}

const expectedBySymbol = {
  SPY: await expectedLevelsFor('SPY'),
  QQQ: await expectedLevelsFor('QQQ'),
  NVDA: await expectedLevelsFor('NVDA'),
};
const { currentPrice, sr, support, resistance } = expectedBySymbol.SPY;
const expectedBotNames = [
  'Sentinel Pulse',
  'Tandem Suite',
  'Sentinel Edge',
  'Consolidation',
  'APK Alerts',
  'Darkpool Mon',
  'Extension External',
  'Futures Bot',
  'Auto-Crypto',
];

const browser = await launchChrome();
const context = await browser.newContext({
  acceptDownloads: true,
  viewport: { width: 1440, height: 920 },
});
const page = await context.newPage();
const consoleErrors = [];
const apiResponses = [];
const httpFailures = [];
const interceptedControls = [];
page.on('console', (message) => {
  if (message.type() === 'error') consoleErrors.push(message.text());
});
page.on('response', (response) => {
  const url = response.url();
  if (url.includes('/api/')) apiResponses.push({ url, status: response.status() });
  if (response.status() >= 400) httpFailures.push({ url, status: response.status() });
});

try {
  await page.goto(appUrl, { waitUntil: 'domcontentloaded', timeout: 15000 });
  await page.waitForSelector('.se-shell', { timeout: 15000 });
  await page.waitForFunction(() => document.body.innerText.includes('S/R API support / resistance'), null, { timeout: 20000 });
  const expandedPopouts = [];
  const canvasStats = [];
  let heatmapTooltipText = '';
  await page.route(/\/api\/(?:control\/(?:pause|resume)|automation(?:\/tickers\/[^/?]+)?|pulse\/(?:trailing-stop|emergency-exit)\/[^/?]+|emergency\/kill-switch|tickers\/[^/?]+)(?:\?.*)?$/, async (route) => {
    const request = route.request();
    if (!['POST', 'PUT', 'DELETE'].includes(request.method())) {
      await route.continue();
      return;
    }
    const url = new URL(request.url());
    interceptedControls.push({
      method: request.method(),
      pathname: url.pathname,
      search: url.search,
      body: request.postData() ?? '',
    });
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        ok: true,
        intercepted: true,
        method: request.method(),
        path: url.pathname,
      }),
    });
  });

  async function assertCanvasDrawn(containerSelector, label) {
    await page.waitForSelector(`${containerSelector} canvas`, { timeout: 10000 });
    const stats = await page.locator(`${containerSelector} canvas`).first().evaluate((canvas) => {
      const width = canvas.width;
      const height = canvas.height;
      const ctx = canvas.getContext('2d');
      if (!ctx || width < 100 || height < 80) {
        return { width, height, sampledPixels: 0, coloredPixels: 0, uniqueBuckets: 0 };
      }
      const image = ctx.getImageData(0, 0, width, height).data;
      const step = Math.max(1, Math.floor(Math.sqrt((width * height) / 6000)));
      const buckets = new Set();
      let sampledPixels = 0;
      let coloredPixels = 0;
      for (let y = 0; y < height; y += step) {
        for (let x = 0; x < width; x += step) {
          const index = (y * width + x) * 4;
          const r = image[index];
          const g = image[index + 1];
          const b = image[index + 2];
          const a = image[index + 3];
          if (a > 0) sampledPixels += 1;
          if (a > 0 && (r > 34 || g > 34 || b > 34)) coloredPixels += 1;
          buckets.add(`${Math.floor(r / 24)}-${Math.floor(g / 24)}-${Math.floor(b / 24)}-${Math.floor(a / 64)}`);
        }
      }
      return { width, height, sampledPixels, coloredPixels, uniqueBuckets: buckets.size };
    });
    assert(stats.width >= 100 && stats.height >= 80, `${label} canvas was not sized for rendering: ${JSON.stringify(stats)}`);
    assert(stats.sampledPixels > 1000, `${label} canvas did not expose enough pixels: ${JSON.stringify(stats)}`);
    assert(stats.coloredPixels > 120, `${label} canvas looked blank or only background colored: ${JSON.stringify(stats)}`);
    assert(stats.uniqueBuckets > 8, `${label} canvas did not have enough color variation: ${JSON.stringify(stats)}`);
    const result = { label, ...stats };
    canvasStats.push(result);
    return result;
  }

  async function assertHeatmapTooltip() {
    const heatmapCanvas = page.locator('.se-heat-stage canvas').first();
    await heatmapCanvas.waitFor({ timeout: 10000 });
    await heatmapCanvas.scrollIntoViewIfNeeded();
    const box = await heatmapCanvas.boundingBox();
    assert(box, 'Heatmap canvas was not visible for tooltip verification');
    await heatmapCanvas.hover({ position: { x: box.width * 0.58, y: box.height * 0.44 } });
    await page.waitForSelector('.se-heat-stage .se-tooltip.visible', { timeout: 5000 });
    const tooltipText = (await page.locator('.se-heat-stage .se-tooltip.visible').first().innerText()).replace(/\s+/g, ' ').trim();
    assert(tooltipText.includes('SPY'), `Heatmap tooltip did not include active symbol: ${tooltipText}`);
    ['Price', 'Allow', 'Risk', 'Volume'].forEach((token) => {
      assert(tooltipText.includes(token), `Heatmap tooltip missing ${token}: ${tooltipText}`);
    });
    heatmapTooltipText = tooltipText;
    await page.mouse.move(box.x - 10, box.y - 10);
    return tooltipText;
  }

  async function assertSupportResistanceFallback() {
    const fallbackContext = await browser.newContext({
      viewport: { width: 1280, height: 860 },
    });
    const fallbackPage = await fallbackContext.newPage();
    const fallbackResponses = [];
    fallbackPage.on('response', (response) => {
      const url = response.url();
      if (url.includes('/api/')) fallbackResponses.push({ url, status: response.status() });
    });
    await fallbackPage.route(/\/api\/support-resistance\/evaluate(?:\?.*)?$/, async (route) => {
      if (route.request().method() !== 'POST') {
        await route.continue();
        return;
      }
      await route.fulfill({
        status: 503,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'probe forced S/R outage' }),
      });
    });

    try {
      await fallbackPage.goto(appUrl, { waitUntil: 'domcontentloaded', timeout: 15000 });
      await fallbackPage.waitForSelector('.se-shell', { timeout: 15000 });
      await fallbackPage.waitForFunction(() => {
        const text = document.body.innerText;
        return text.includes('Partial refresh warning') && text.includes('supportResistance') && text.toLowerCase().includes('fallback');
      }, null, { timeout: 20000 });
      const warningText = (await fallbackPage.locator('.se-warning-strip').innerText()).replace(/\s+/g, ' ').trim();
      assert(warningText.includes('supportResistance'), `Fallback warning did not name supportResistance: ${warningText}`);
      await fallbackPage.getByRole('button', { name: /Breakouts/ }).click();
      await fallbackPage.waitForSelector('.se-grid-breakouts', { timeout: 10000 });
      await fallbackPage.waitForFunction(() => {
        const cells = Array.from(document.querySelectorAll('.se-grid-breakouts .se-table tbody tr:first-child td')).map((cell) => cell.textContent?.trim() ?? '');
        return cells[0] === 'SPY'
          && cells[5]
          && cells[5] !== 'S/R API'
          && ['chart workspace', 'ORB', 'OHLCV fallback', 'price fallback'].includes(cells[5]);
      }, null, { timeout: 20000 });
      const fallbackRowCells = await fallbackPage.locator('.se-grid-breakouts .se-table tbody tr').first().locator('td').allTextContents();
      assert(fallbackRowCells[0] === 'SPY', `Fallback first key-level row was not SPY: ${JSON.stringify(fallbackRowCells)}`);
      assert(fallbackRowCells[5] !== 'S/R API', `Fallback key-level row still used S/R API: ${JSON.stringify(fallbackRowCells)}`);
      const forcedSrFailures = fallbackResponses.filter((response) => response.url.includes('/api/support-resistance/evaluate') && response.status === 503).length;
      assert(forcedSrFailures > 0, `Fallback probe did not intercept S/R evaluate as 503: ${JSON.stringify(fallbackResponses)}`);
      return { warningText, fallbackRowCells, forcedSrFailures };
    } finally {
      await fallbackContext.close();
    }
  }

  async function assertKillSwitchStatusRendering() {
    const killSwitchContext = await browser.newContext({
      viewport: { width: 1280, height: 860 },
    });
    const killSwitchPage = await killSwitchContext.newPage();
    let killSwitchStatusReads = 0;
    await killSwitchPage.route(/\/api\/emergency\/kill-switch(?:\?.*)?$/, async (route) => {
      if (route.request().method() !== 'GET') {
        await route.continue();
        return;
      }
      killSwitchStatusReads += 1;
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          kill_switch_active: true,
          mode: 'read_only_status',
        }),
      });
    });

    try {
      await killSwitchPage.goto(appUrl, { waitUntil: 'domcontentloaded', timeout: 15000 });
      await killSwitchPage.waitForSelector('.se-shell', { timeout: 15000 });
      await killSwitchPage.waitForFunction(() => {
        const cards = Array.from(document.querySelectorAll('.se-kpi'));
        const pulseGate = cards.find((card) => card.querySelector('label')?.textContent?.trim() === 'Pulse Gate');
        return pulseGate?.querySelector('.se-kpi-value')?.textContent?.trim() === 'KILL SWITCH';
      }, null, { timeout: 20000 });
      const pulseGateValue = await killSwitchPage.locator('.se-kpi').filter({ hasText: 'Pulse Gate' }).locator('.se-kpi-value').first().innerText();
      assert(killSwitchStatusReads > 0, 'Kill-switch status probe did not read /api/emergency/kill-switch');
      assert(pulseGateValue === 'KILL SWITCH', `kill_switch_active true did not render KILL SWITCH Pulse Gate: ${pulseGateValue}`);
      return { killSwitchStatusReads, pulseGateValue };
    } finally {
      await killSwitchContext.close();
    }
  }

  async function assertKpiDashboard() {
    await page.waitForSelector('.se-kpi-row .se-kpi', { timeout: 10000 });
    const kpis = await page.locator('.se-kpi-row .se-kpi').evaluateAll((cards) => cards.map((card) => ({
      label: card.querySelector('label')?.textContent?.trim() ?? '',
      value: card.querySelector('.se-kpi-value')?.textContent?.trim() ?? '',
      sub: card.querySelector('.se-kpi-sub span')?.textContent?.trim() ?? '',
      sparklineCount: card.querySelectorAll('svg.se-spark polyline').length,
    })));
    const byLabel = Object.fromEntries(kpis.map((kpi) => [kpi.label, kpi]));
    ['Risk Score', 'Portfolio Health', 'Active Alerts', 'Bots Monitored', 'Decisions Today', 'Pulse Gate'].forEach((label) => {
      assert(byLabel[label], `Missing KPI card ${label}: ${JSON.stringify(kpis)}`);
      assert(byLabel[label].sparklineCount === 1, `KPI ${label} did not render its sparkline: ${JSON.stringify(byLabel[label])}`);
    });
    const risk = firstNumber(byLabel['Risk Score'].value);
    const portfolioHealth = firstNumber(byLabel['Portfolio Health'].value);
    const activeAlerts = firstNumber(byLabel['Active Alerts'].value);
    const decisionsToday = firstNumber(byLabel['Decisions Today'].value);
    assert(risk >= 0 && risk <= 100, `Risk Score KPI out of range: ${byLabel['Risk Score'].value}`);
    assert(portfolioHealth >= 0 && portfolioHealth <= 100, `Portfolio Health KPI out of range: ${byLabel['Portfolio Health'].value}`);
    assert(activeAlerts >= 0, `Active Alerts KPI was negative: ${byLabel['Active Alerts'].value}`);
    assert(decisionsToday >= 0, `Decisions Today KPI was negative: ${byLabel['Decisions Today'].value}`);
    assert(/^\d+\s*\/\s*\d+$/.test(byLabel['Bots Monitored'].value), `Bots Monitored KPI was not a count pair: ${byLabel['Bots Monitored'].value}`);
    assert(byLabel['Pulse Gate'].value.length > 0, `Pulse Gate KPI was empty: ${JSON.stringify(byLabel['Pulse Gate'])}`);
    return kpis;
  }

  async function assertDecisionFeed() {
    await page.waitForSelector('.se-feed-list .se-decision', { timeout: 10000 });
    const rows = await page.locator('.se-feed-list .se-decision').evaluateAll((items) => items.slice(0, 6).map((item) => ({
      time: item.querySelector('.se-time')?.textContent?.trim() ?? '',
      action: item.querySelector('.se-tag')?.textContent?.trim() ?? '',
      headline: item.querySelector('b')?.textContent?.trim() ?? '',
      detail: item.querySelector('p')?.textContent?.trim() ?? '',
      severity: item.querySelector('.se-severity')?.textContent?.trim().toLowerCase() ?? '',
    })));
    assert(rows.length >= 3, `Decision feed rendered too few rows: ${JSON.stringify(rows)}`);
    assert(rows.some((row) => row.headline.includes('SPY')), `Decision feed did not include any SPY row: ${JSON.stringify(rows)}`);
    rows.forEach((row) => {
      assert(row.time.length > 0, `Decision feed row missing time: ${JSON.stringify(row)}`);
      assert(row.action.length > 0, `Decision feed row missing action tag: ${JSON.stringify(row)}`);
      assert(/^[A-Z0-9.:-]+\s+/.test(row.headline), `Decision feed row did not include a leading symbol: ${JSON.stringify(row)}`);
      assert(row.detail.length > 0, `Decision feed row missing detail: ${JSON.stringify(row)}`);
      assert(['low', 'medium', 'high'].includes(row.severity), `Decision feed row has invalid severity: ${JSON.stringify(row)}`);
    });
    return rows;
  }

  async function assertPolicyStack() {
    await page.waitForSelector('.se-grid-risk .se-policy-stack article', { timeout: 10000 });
    const policies = await page.locator('.se-grid-risk .se-policy-stack article').evaluateAll((items) => items.map((item) => ({
      name: item.querySelector('strong')?.textContent?.trim() ?? '',
      detail: item.querySelector('p')?.textContent?.trim() ?? '',
      enabled: item.querySelector('.se-switch')?.classList.contains('on') ?? false,
    })));
    ['Breakout confirmation', 'Support-loss stop', 'ATR risk sizing', 'Pulse handoff gates'].forEach((name) => {
      const policy = policies.find((item) => item.name === name);
      assert(policy, `Policy Stack missing ${name}: ${JSON.stringify(policies)}`);
      assert(policy.enabled, `Policy Stack row was not enabled: ${JSON.stringify(policy)}`);
      assert(policy.detail.length > 0, `Policy Stack row missing detail: ${JSON.stringify(policy)}`);
    });
    return policies;
  }

  async function assertBotEcosystem() {
    const providerHealthPayload = await fetchJson('/api/providers/health');
    const expectedProviderHealthRows = payloadArray(providerHealthPayload, ['providers', 'items', 'health']);
    await page.waitForSelector('.se-grid-network .se-bot-node', { timeout: 10000 });
    const meshNodes = await page.locator('.se-grid-network .se-bot-node').evaluateAll((nodes) => nodes.map((node) => ({
      name: node.querySelector('strong')?.textContent?.trim() ?? '',
      subtitle: node.querySelector('small')?.textContent?.trim() ?? '',
      state: node.querySelector('.se-bot-copy span')?.textContent?.trim().toLowerCase() ?? '',
      title: node.getAttribute('title') ?? '',
      sparklineCount: node.querySelectorAll('svg.se-spark polyline').length,
      active: node.classList.contains('active'),
    })));
    assert(meshNodes.length === expectedBotNames.length, `Bot mesh rendered ${meshNodes.length} nodes instead of ${expectedBotNames.length}: ${JSON.stringify(meshNodes)}`);
    expectedBotNames.forEach((name) => {
      const node = meshNodes.find((item) => item.name === name);
      assert(node, `Bot mesh missing ${name}: ${JSON.stringify(meshNodes)}`);
      assert(node.subtitle.length > 0, `Bot mesh node missing subtitle for ${name}: ${JSON.stringify(node)}`);
      assert(['healthy', 'watch', 'blocked', 'offline'].includes(node.state), `Bot mesh node ${name} had invalid state: ${JSON.stringify(node)}`);
      assert(node.title.includes('Tetradim/'), `Bot mesh node ${name} missing repo title metadata: ${JSON.stringify(node)}`);
      assert(node.sparklineCount === 1, `Bot mesh node ${name} missing sparkline: ${JSON.stringify(node)}`);
    });

    await page.locator('.se-grid-network .se-bot-node').filter({ hasText: 'Sentinel Pulse' }).first().click();
    await page.waitForFunction(() => document.querySelector('.se-selected-bot strong')?.textContent?.trim() === 'Sentinel Pulse', null, { timeout: 5000 });
    const selectedBotText = (await page.locator('.se-selected-bot').innerText()).replace(/\s+/g, ' ').trim();
    assert(selectedBotText.includes('Execution handoff worker'), `Selecting Sentinel Pulse did not update selected bot card: ${selectedBotText}`);
    await page.locator('.se-grid-network .se-bot-node').filter({ hasText: 'Sentinel Edge' }).first().click();

    const directiveRows = await page.evaluate(() => {
      const panels = Array.from(document.querySelectorAll('.se-grid-network .se-panel'));
      const panel = panels.find((item) => item.querySelector('h3')?.textContent?.trim() === 'Bot Directive Matrix');
      return Array.from(panel?.querySelectorAll('tbody tr') ?? []).map((row) => {
        const cells = Array.from(row.querySelectorAll('td')).map((cell) => cell.textContent?.replace(/\s+/g, ' ').trim() ?? '');
        return {
          bot: cells[0] ?? '',
          health: cells[1] ?? '',
          directive: cells[2] ?? '',
          latency: cells[3] ?? '',
        };
      });
    });
    assert(directiveRows.length === expectedBotNames.length, `Bot Directive Matrix rendered ${directiveRows.length} rows instead of ${expectedBotNames.length}: ${JSON.stringify(directiveRows)}`);
    expectedBotNames.forEach((name) => {
      const row = directiveRows.find((item) => item.bot.includes(name));
      assert(row, `Bot Directive Matrix missing ${name}: ${JSON.stringify(directiveRows)}`);
      assert(/\d+%/.test(row.health), `Bot Directive Matrix row missing health percent for ${name}: ${JSON.stringify(row)}`);
      assert(row.directive.length > 0, `Bot Directive Matrix row missing directive for ${name}: ${JSON.stringify(row)}`);
      assert(/\d+ms/.test(row.latency), `Bot Directive Matrix row missing latency for ${name}: ${JSON.stringify(row)}`);
    });
    if (expectedProviderHealthRows.length > 0) {
      const consolidationRow = directiveRows.find((item) => item.bot.includes('Consolidation'));
      assert(consolidationRow?.health === '88%', `Consolidation did not reflect provider-health context: ${JSON.stringify({ expectedProviderHealthRows: expectedProviderHealthRows.length, consolidationRow })}`);
      const consolidationNode = meshNodes.find((item) => item.name === 'Consolidation');
      assert(consolidationNode?.state === 'healthy', `Consolidation node was not healthy with provider-health context: ${JSON.stringify(consolidationNode)}`);
    }

    return { meshNodes, directiveRows, selectedBotText, expectedProviderHealthRows: expectedProviderHealthRows.length };
  }

  async function assertProviderReadinessDetails() {
    const [readyPayload, providersPayload, marketDataPayload] = await Promise.all([
      fetchJson('/api/ready'),
      fetchJson('/api/providers/health'),
      fetchJson('/api/market-data/providers'),
    ]);
    const failingReadinessRows = payloadArray(readyPayload?.failing_check_details);
    const allReadinessRows = payloadArray(readyPayload?.check_details);
    const failingReadinessNames = new Set(failingReadinessRows.map((row) => expectedStatusLabel(row, 'Check', 0)));
    const expectedReadinessRows = [
      ...failingReadinessRows,
      ...allReadinessRows.filter((row, index) => !failingReadinessNames.has(expectedStatusLabel(row, 'Check', index))),
    ];
    const expectedProviderRows = payloadArray(providersPayload, ['providers', 'items', 'health']);
    const expectedMarketDataRows = payloadArray(marketDataPayload, ['providers', 'items', 'market_data_providers']);

    await page.waitForSelector('.se-readiness-details', { timeout: 10000 });
    const sections = await page.locator('.se-readiness-details').evaluate((root) => Array.from(root.children).map((section) => ({
      heading: section.querySelector('h4')?.textContent?.trim() ?? '',
      text: section.textContent?.replace(/\s+/g, ' ').trim() ?? '',
      rows: Array.from(section.querySelectorAll('.se-status-line')).map((row) => ({
        label: row.querySelector('span')?.textContent?.trim() ?? '',
        value: row.querySelector('b')?.textContent?.trim() ?? '',
        tone: row.querySelector('b')?.className ?? '',
      })),
    })));

    const assertSection = (heading, expectedRows, emptyText, fallbackPrefix) => {
      const section = sections.find((item) => item.heading === heading);
      assert(section, `Provider / Readiness Details missing ${heading} section: ${JSON.stringify(sections)}`);
      if (expectedRows.length > 0) {
        assert(section.rows.length > 0, `${heading} had backend rows but rendered no status lines: ${JSON.stringify({ expectedRows, section })}`);
        assert(
          section.rows.length === Math.min(expectedRows.length, 8),
          `${heading} rendered unexpected row count: ${JSON.stringify({ expectedRows: expectedRows.length, renderedRows: section.rows.length, section })}`,
        );
        section.rows.forEach((row) => {
          assert(row.label.length > 0, `${heading} status line missing label: ${JSON.stringify(row)}`);
          assert(row.value.length > 0, `${heading} status line missing value: ${JSON.stringify(row)}`);
          assert(['ok', 'warn', 'bad', 'blue', 'gold'].includes(row.tone), `${heading} status line had invalid tone: ${JSON.stringify(row)}`);
        });
        expectedRows.slice(0, section.rows.length).forEach((expectedRow, index) => {
          const expectedLabel = expectedStatusLabel(expectedRow, fallbackPrefix, index);
          assert(section.rows.some((row) => row.label === expectedLabel), `${heading} did not render expected backend label ${expectedLabel}: ${JSON.stringify(section.rows)}`);
        });
      } else {
        assert(section.text.includes(emptyText), `${heading} empty state did not render expected copy "${emptyText}": ${section.text}`);
      }
      return section;
    };

    const readiness = assertSection('Readiness', expectedReadinessRows, 'No readiness checks returned.', 'Check');
    const providers = assertSection('Providers', expectedProviderRows, 'No provider rows returned.', 'Provider');
    const marketData = assertSection('Market Data', expectedMarketDataRows, 'No market-data provider rows returned.', 'Market provider');
    assert(readiness.rows.some((row) => row.value === 'Ready' || row.value === 'Blocked'), `Readiness did not render Ready/Blocked status values: ${JSON.stringify(readiness.rows)}`);
    assert(!providers.rows.some((row) => /^Provider \d+$/.test(row.label)), `Provider health rendered generic labels instead of backend provider names: ${JSON.stringify(providers.rows)}`);
    assert(!marketData.rows.some((row) => /^Market provider \d+$/.test(row.label)), `Market Data rendered generic labels instead of backend provider names: ${JSON.stringify(marketData.rows)}`);
    assert(marketData.rows.some((row) => ['Configured', 'Needs key', 'Enabled', 'Disabled'].includes(row.value)), `Market Data did not render provider configuration status: ${JSON.stringify(marketData.rows)}`);

    return {
      readinessReady: Boolean(readyPayload?.ready),
      expectedReadinessRows: expectedReadinessRows.length,
      expectedProviderRows: expectedProviderRows.length,
      expectedMarketDataRows: expectedMarketDataRows.length,
      sections: { readiness, providers, marketData },
    };
  }

  async function assertSystemHealthAndPulseContext() {
    const [queuePayload, schemaPayload] = await Promise.all([
      fetchJson('/api/pulse/queue'),
      fetchJson('/api/pulse/handoff/schema'),
    ]);
    await page.waitForSelector('.se-health-list article', { timeout: 10000 });
    await page.waitForSelector('.se-pulse-context', { timeout: 10000 });
    const systemHealthRows = await page.locator('.se-health-list article').evaluateAll((rows) => rows.map((row) => ({
      name: row.querySelector('strong')?.textContent?.trim() ?? '',
      state: row.querySelector('em')?.textContent?.trim() ?? '',
      detail: row.querySelector('small')?.textContent?.trim() ?? '',
      dotClass: row.querySelector('.se-dot')?.className ?? '',
    })));
    [
      'Backend live',
      'Readiness',
      'Provider health',
      'Market data providers',
      'Pulse status',
      'Pulse handoff schema',
      'Rate limit',
    ].forEach((name) => {
      const row = systemHealthRows.find((item) => item.name === name);
      assert(row, `System Health missing ${name}: ${JSON.stringify(systemHealthRows)}`);
      assert(['Healthy', 'Needs review'].includes(row.state), `System Health row ${name} has invalid state: ${JSON.stringify(row)}`);
      assert(row.detail.length > 0, `System Health row ${name} missing detail text: ${JSON.stringify(row)}`);
      assert(row.dotClass.includes('ok') || row.dotClass.includes('bad'), `System Health row ${name} missing status dot class: ${JSON.stringify(row)}`);
    });

    const pulseContext = await page.locator('.se-pulse-context').evaluate((root) => ({
      text: root.textContent?.replace(/\s+/g, ' ').trim() ?? '',
      headings: Array.from(root.querySelectorAll('h4')).map((heading) => heading.textContent?.trim() ?? ''),
      rows: Array.from(root.querySelectorAll('.se-status-line')).map((row) => ({
        label: row.querySelector('span')?.textContent?.trim() ?? '',
        value: row.querySelector('b')?.textContent?.trim() ?? '',
        tone: row.querySelector('b')?.className ?? '',
      })),
    }));
    assert(pulseContext.headings.includes('Positions'), `Pulse Context missing Positions heading: ${JSON.stringify(pulseContext)}`);
    assert(pulseContext.headings.includes('Queue'), `Pulse Context missing Queue heading: ${JSON.stringify(pulseContext)}`);
    assert(pulseContext.headings.includes('Handoff Contract'), `Pulse Context missing Handoff Contract heading: ${JSON.stringify(pulseContext)}`);
    const queueSize = Number(queuePayload?.queue_size ?? queuePayload?.size ?? queuePayload?.count);
    if (Number.isFinite(queueSize)) {
      const queueSizeRow = pulseContext.rows.find((row) => row.label === 'Queue size');
      assert(queueSizeRow?.value === String(queueSize), `Pulse Context did not render backend queue_size ${queueSize}: ${JSON.stringify(pulseContext.rows)}`);
      if (Number.isFinite(Number(queuePayload?.default_ttl_seconds))) {
        const defaultTtlRow = pulseContext.rows.find((row) => row.label === 'Default TTL');
        assert(defaultTtlRow?.value === `${Number(queuePayload.default_ttl_seconds)}s`, `Pulse Context did not render default TTL: ${JSON.stringify(pulseContext.rows)}`);
      }
      if (Number.isFinite(Number(queuePayload?.emergency_ttl_seconds))) {
        const emergencyTtlRow = pulseContext.rows.find((row) => row.label === 'Emergency TTL');
        assert(emergencyTtlRow?.value === `${Number(queuePayload.emergency_ttl_seconds)}s`, `Pulse Context did not render emergency TTL: ${JSON.stringify(pulseContext.rows)}`);
      }
    } else if (pulseContext.rows.length > 0) {
      pulseContext.rows.forEach((row) => {
        assert(row.label.length > 0, `Pulse Context row missing label: ${JSON.stringify(row)}`);
        assert(row.value.length > 0, `Pulse Context row missing value: ${JSON.stringify(row)}`);
      });
    } else {
      assert(
        pulseContext.text.includes('No Pulse position rows returned.') && pulseContext.text.includes('No Pulse queue rows returned.'),
        `Pulse Context empty state did not render both fallbacks: ${pulseContext.text}`,
      );
    }

    const contractVersionRow = pulseContext.rows.find((row) => row.label === 'Contract version');
    assert(
      contractVersionRow?.value === String(schemaPayload?.contract_version),
      `Pulse Context did not render backend contract_version: ${JSON.stringify({ schemaPayload, pulseContext })}`,
    );
    const endpointRow = pulseContext.rows.find((row) => row.label === 'Recommended endpoint');
    assert(
      endpointRow?.value === String(schemaPayload?.recommended_endpoint ?? '--'),
      `Pulse Context did not render backend recommended_endpoint: ${JSON.stringify({ schemaPayload, pulseContext })}`,
    );
    const idempotencyRow = pulseContext.rows.find((row) => row.label === 'Idempotency header');
    assert(
      idempotencyRow?.value === (schemaPayload?.transport_headers?.['Idempotency-Key'] ? 'Required' : 'Missing'),
      `Pulse Context did not render Idempotency-Key header state: ${JSON.stringify({ schemaPayload, pulseContext })}`,
    );

    return { systemHealthRows, pulseContext, queueMetadata: queuePayload, handoffSchema: schemaPayload };
  }

  async function assertExpandedPanel(buttonLabel, expectedTitleText) {
    await page.getByLabel(buttonLabel).click();
    await page.waitForSelector('.se-modal', { timeout: 5000 });
    const title = await page.locator('.se-modal h2').innerText();
    assert(
      title.toLowerCase().includes(expectedTitleText),
      `${buttonLabel} opened "${title}" instead of a ${expectedTitleText} popout`,
    );
    const bodySurfaceCount = await page.locator(
      '.se-modal-body canvas, .se-modal-body .se-table-wrap, .se-modal-body .se-risk-panel, .se-modal-body .se-heat-stage',
    ).count();
    assert(bodySurfaceCount > 0, `${buttonLabel} popout did not render a chart, table, heatmap, or risk panel`);
    if (await page.locator('.se-modal-body canvas').count()) {
      await assertCanvasDrawn('.se-modal-body', `${buttonLabel} popout`);
    }
    expandedPopouts.push({ buttonLabel, title });
    await page.getByRole('button', { name: 'Close expanded panel' }).click();
    await page.waitForSelector('.se-modal', { state: 'detached', timeout: 5000 });
  }

  async function assertFirstKeyLevelRow(expected) {
    const cells = await page.locator('.se-table tbody tr').first().locator('td').allTextContents();
    assert(cells[0] === expected.symbol, `Expected first key-level row to be ${expected.symbol}, got ${cells[0]}`);
    const uiSupport = parsePrice(cells[1]);
    const uiPrice = parsePrice(cells[2]);
    const uiResistance = parsePrice(cells[3]);
    assert(Math.abs(uiPrice - expected.currentPrice) < 0.02, `${expected.symbol} UI price ${uiPrice} did not match chart close ${expected.currentPrice}`);
    assert(Math.abs(uiSupport - expected.support.price) < 0.02, `${expected.symbol} support ${uiSupport} did not match S/R support ${expected.support.price}`);
    assert(Math.abs(uiResistance - expected.resistance.price) < 0.02, `${expected.symbol} resistance ${uiResistance} did not match S/R resistance ${expected.resistance.price}`);
    assert(cells[5] === 'S/R API', `Expected S/R API source for ${expected.symbol}, got ${cells[5]}`);
    return cells;
  }

  async function waitForFirstKeyLevelRow(expected) {
    await page.waitForFunction((target) => {
      const cells = Array.from(document.querySelectorAll('.se-table tbody tr:first-child td')).map((cell) => cell.textContent?.trim() ?? '');
      const parseCellPrice = (text) => Number(String(text || '').replace(/[^0-9.-]/g, ''));
      return cells[0] === target.symbol
        && Math.abs(parseCellPrice(cells[1]) - target.support) < 0.02
        && Math.abs(parseCellPrice(cells[2]) - target.currentPrice) < 0.02
        && Math.abs(parseCellPrice(cells[3]) - target.resistance) < 0.02
        && cells[5] === 'S/R API';
    }, {
      symbol: expected.symbol,
      currentPrice: expected.currentPrice,
      support: expected.support.price,
      resistance: expected.resistance.price,
    }, { timeout: 20000 });
    return assertFirstKeyLevelRow(expected);
  }

  const navText = await page.locator('.se-nav').innerText();
  const brandSubtitle = await page.locator('.se-brand p').innerText();
  assert(brandSubtitle === 'Risk Control Brain', `Unexpected brand subtitle: ${brandSubtitle}`);
  assert(!navText.includes('Legacy'), 'Legacy Console still appears in nav');
  assert(!(await page.locator('body').innerText()).includes('Legacy Asset Command Console'), 'Legacy console text still appears');
  const kpiSnapshot = await assertKpiDashboard();

  await page.evaluate(() => {
    Object.defineProperty(window.navigator, 'clipboard', {
      configurable: true,
      value: {
        writeText: async (text) => {
          window.__sentinelCopiedSnapshot = text;
        },
      },
    });
  });
  await page.getByRole('button', { name: 'Copy Status Snapshot' }).click();
  const copiedSnapshot = JSON.parse(await page.evaluate(() => window.__sentinelCopiedSnapshot ?? '{}'));
  assert(copiedSnapshot.symbol === 'SPY', `Copied snapshot symbol mismatch: ${JSON.stringify(copiedSnapshot)}`);
  assert(typeof copiedSnapshot.risk === 'number', `Copied snapshot did not include numeric risk: ${JSON.stringify(copiedSnapshot)}`);
  assert(typeof copiedSnapshot.regime === 'string' && copiedSnapshot.regime.length > 0, 'Copied snapshot did not include regime');
  assert(typeof copiedSnapshot.pulseGate === 'string' && copiedSnapshot.pulseGate.length > 0, 'Copied snapshot did not include Pulse gate');
  await page.waitForFunction(() => document.body.innerText.includes('Snapshot copied to clipboard'), null, { timeout: 5000 });

  const topActions = page.locator('.se-top-actions');
  await topActions.getByRole('button', { name: 'Live' }).click();
  assert(await topActions.getByRole('button', { name: 'Paused' }).count() === 1, 'Topbar live polling button did not switch to Paused');
  await topActions.getByRole('button', { name: 'Paused' }).click();
  assert(await topActions.getByRole('button', { name: 'Live' }).count() === 1, 'Topbar live polling button did not switch back to Live');
  const refreshStartApiCount = apiResponses.length;
  await topActions.getByRole('button', { name: 'Refresh' }).click();
  await page.waitForTimeout(1000);
  assert(apiResponses.length > refreshStartApiCount, 'Manual Refresh did not trigger additional API calls');

  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Export Audit Log' }).click();
  const download = await downloadPromise;
  assert(download.suggestedFilename().startsWith('sentinel-edge-audit-SPY-'), `Unexpected audit filename: ${download.suggestedFilename()}`);

  await page.getByRole('button', { name: /Breakouts/ }).click();
  await page.waitForSelector('.se-grid-breakouts', { timeout: 10000 });
  const firstRowCells = await waitForFirstKeyLevelRow(expectedBySymbol.SPY);
  await page.locator('select.se-select').selectOption('QQQ');
  const qqqFirstRowCells = await waitForFirstKeyLevelRow(expectedBySymbol.QQQ);
  await page.locator('select.se-select').selectOption('SPY');
  await waitForFirstKeyLevelRow(expectedBySymbol.SPY);
  await topActions.locator('input').fill('NVDA');
  await topActions.locator('input').press('Enter');
  const nvdaInputRowCells = await waitForFirstKeyLevelRow(expectedBySymbol.NVDA);
  await page.locator('select.se-select').selectOption('SPY');
  await waitForFirstKeyLevelRow(expectedBySymbol.SPY);

  await page.getByRole('button', { name: /VOL/ }).click();
  await page.waitForFunction(() => document.body.innerText.toLowerCase().includes('vol heat map'), null, { timeout: 5000 });
  await page.getByRole('button', { name: /VEX/ }).click();
  await page.waitForFunction(() => document.body.innerText.toLowerCase().includes('vex heat map'), null, { timeout: 5000 });
  await assertCanvasDrawn('.se-heat-stage', 'main VEX heatmap');
  await assertHeatmapTooltip();
  await page.getByRole('button', { name: 'Refresh Heatmap' }).click();
  await page.waitForTimeout(300);
  const heatmapDownloadPromise = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Save Heatmap' }).click();
  const heatmapDownload = await heatmapDownloadPromise;
  assert(heatmapDownload.suggestedFilename().startsWith('sentinel-edge-heatmap-SPY-VEX-'), `Unexpected heatmap filename: ${heatmapDownload.suggestedFilename()}`);
  const heatmapPath = await heatmapDownload.path();
  assert(heatmapPath, 'Heatmap export did not produce a readable download path');
  const heatmapJson = JSON.parse(await readFile(heatmapPath, 'utf8'));
  assert(heatmapJson.symbol === 'SPY', `Heatmap export symbol mismatch: ${heatmapJson.symbol}`);
  assert(heatmapJson.mode === 'VEX', `Heatmap export mode mismatch: ${heatmapJson.mode}`);
  assert(Math.abs(heatmapJson.current_price - currentPrice) < 0.02, `Heatmap export current price ${heatmapJson.current_price} did not match ${currentPrice}`);
  assert(Array.isArray(heatmapJson.series) && heatmapJson.series.length > 20, 'Heatmap export did not include plotted series data');

  await assertExpandedPanel('Expand VEX Heat Map', 'vex heat map');

  await page.getByRole('button', { name: /Bot Network/ }).click();
  await page.waitForFunction(() => document.body.innerText.toLowerCase().includes('bot ecosystem mesh'), null, { timeout: 5000 });
  const botEcosystemSnapshot = await assertBotEcosystem();
  const decisionFeedSnapshot = await assertDecisionFeed();
  await page.getByRole('button', { name: /Risk Engine/ }).click();
  await page.waitForFunction(() => document.body.innerText.toLowerCase().includes('risk exposure brain'), null, { timeout: 5000 });
  const policyStackSnapshot = await assertPolicyStack();
  await assertCanvasDrawn('.se-gamma-stage', 'main gamma by strike');
  await assertExpandedPanel('Expand Risk Exposure Brain', 'sentinel risk brain');
  await assertExpandedPanel('Expand Gamma by Strike', 'spy gamma by strike');
  await page.getByRole('button', { name: /Breakouts/ }).click();
  await page.waitForSelector('.se-grid-breakouts', { timeout: 10000 });
  await assertCanvasDrawn('.se-breakout-stage', 'main breakout radar');
  await assertExpandedPanel('Expand Breakout / Breakdown Radar', 'spy breakout radar');
  await assertExpandedPanel('Expand Key Levels Monitor', 'key levels monitor');
  await page.getByRole('button', { name: /Settings/ }).click();
  await page.waitForFunction(() => document.body.innerText.toLowerCase().includes('provider / readiness details'), null, { timeout: 5000 });
  await page.waitForFunction(() => document.body.innerText.toLowerCase().includes('market data'), null, { timeout: 5000 });
  const providerReadinessSnapshot = await assertProviderReadinessDetails();
  const settingsPanel = page.locator('.se-settings-panel');
  const livePollingCheckbox = settingsPanel.locator('input[type="checkbox"]');
  assert(await livePollingCheckbox.isChecked(), 'Local Settings live polling checkbox was not checked initially');
  await livePollingCheckbox.uncheck();
  assert(await topActions.getByRole('button', { name: 'Paused' }).count() === 1, 'Local Settings checkbox did not pause live polling');
  await livePollingCheckbox.check();
  assert(await topActions.getByRole('button', { name: 'Live' }).count() === 1, 'Local Settings checkbox did not resume live polling');
  await settingsPanel.locator('select').selectOption('VOL');
  assert(await topActions.getByRole('button', { name: 'VOL' }).evaluate((button) => button.classList.contains('active')), 'Local Settings heat mode select did not activate VOL');
  await settingsPanel.locator('select').selectOption('VEX');
  assert(await topActions.getByRole('button', { name: 'VEX' }).evaluate((button) => button.classList.contains('active')), 'Local Settings heat mode select did not activate VEX');
  await page.getByRole('button', { name: /Protection Ops/ }).click();
  await page.waitForSelector('.se-grid-ops', { timeout: 10000 });
  const systemHealthPulseSnapshot = await assertSystemHealthAndPulseContext();

  const moduleTabs = [
    'Trading Overview',
    'Scanner Workbench',
    'Advisor Health',
    'Experience',
    'Protection Ops',
    'P&L Tracking',
    'Market Coverage',
    'Portfolio',
    'System Settings',
    'Tutorials',
  ];
  const moduleExpectedText = {
    'Trading Overview': 'Active Tickers',
    'Scanner Workbench': 'NATIVE SCANNER CATALOG',
    'Advisor Health': 'Advisor Operations Health',
    Experience: 'Frontend Experience',
    'Protection Ops': 'Protection Command',
    'P&L Tracking': 'P&L Tracking',
    'Market Coverage': 'Total Markets',
    Portfolio: 'Portfolio Analytics',
    'System Settings': 'Configure Edge behavior',
    Tutorials: 'Sentinel Edge Learning Center',
  };
  const moduleSnapshots = [];
  const moduleDeepChecks = {};
  for (const label of moduleTabs) {
    await page.locator('.se-ops-module-tabs').getByRole('tab', { name: new RegExp(label.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')) }).click();
    const expectedText = moduleExpectedText[label];
    let panelText = '';
    for (let attempt = 0; attempt < 40; attempt += 1) {
      panelText = await page.locator('.se-ops-module-content').innerText({ timeout: 10000 }).catch(() => '');
      if (panelText.includes(expectedText) && !panelText.toLowerCase().includes('loading')) break;
      await page.waitForTimeout(250);
    }
    if (!panelText.includes(expectedText) || panelText.toLowerCase().includes('loading')) {
      throw new Error(`Operations module ${label} did not render expected text "${expectedText}". Rendered: ${panelText.replace(/\s+/g, ' ').slice(0, 240)}`);
    }
    const activeLabel = await page.locator('.se-ops-module-tabs').evaluate((nav) => {
      const active = nav.querySelector('[aria-selected="true"]') ?? nav.querySelector('.active');
      return active?.querySelector('span')?.textContent?.trim() ?? '';
    });
    assert(activeLabel === label, `Expected active operations module ${label}, got ${activeLabel}`);

    if (label === 'Scanner Workbench') {
      const validateStartCount = apiResponses.filter((response) => response.url.includes('/api/scanner-workbench/watch-intent/validate')).length;
      await page.locator('.se-ops-module-content').getByRole('button', { name: 'Validate watch intent' }).click();
      await page.waitForFunction(() => {
        const text = document.querySelector('.se-ops-module-content')?.textContent ?? '';
        return text.includes('Watch intent matches the current catalog.') || text.includes('stale watch selections need review.');
      }, null, { timeout: 10000 });
      const scannerText = await page.locator('.se-ops-module-content').innerText();
      const validateEndCount = apiResponses.filter((response) => response.url.includes('/api/scanner-workbench/watch-intent/validate')).length;
      assert(validateEndCount > validateStartCount, 'Scanner Workbench validate did not call watch-intent validation endpoint');
      assert(scannerText.includes('Watch validation'), 'Scanner Workbench did not keep validation status visible');
      moduleDeepChecks.scannerWorkbench = {
        watchIntentValidated: true,
        validationText: scannerText.replace(/\s+/g, ' ').match(/Watch validation[^.]+[.]/)?.[0] ?? 'validated',
      };
      panelText = scannerText;
    }

    if (label === 'Experience') {
      assert(panelText.toLowerCase().includes('rum'), `Experience module did not surface RUM status text: ${panelText.slice(0, 240)}`);
      moduleDeepChecks.experience = { rumStatusVisible: true };
    }

    if (label === 'System Settings') {
      assert(panelText.includes('Pulse advisory contract'), 'System Settings did not surface the Pulse advisory contract panel');
      assert(panelText.includes('Operator notification paths'), 'System Settings did not surface operator notification paths');
      assert(panelText.includes('secret_values'), 'System Settings did not render redacted notification secret status');
      moduleDeepChecks.systemSettings = {
        pulseContractVisible: true,
        notificationPathsVisible: true,
        redactedSecretsVisible: true,
      };
    }

    moduleSnapshots.push({ label, textSample: panelText.replace(/\s+/g, ' ').slice(0, 120) });
  }

  const dialogs = [];
  let allowControlDialogs = false;
  page.on('dialog', async (dialog) => {
    const defaultValue = dialog.defaultValue?.() ?? '';
    dialogs.push({ type: dialog.type(), message: dialog.message(), defaultValue });
    if (allowControlDialogs) {
      if (dialog.type() === 'prompt') {
        await dialog.accept(defaultValue || '1.25');
      } else {
        await dialog.accept();
      }
      return;
    }
    await dialog.dismiss();
  });
  allowControlDialogs = true;
  await page.getByRole('button', { name: 'Kill Switch' }).click();
  const opsControls = page.locator('.se-ops-grid');
  await opsControls.getByRole('button', { name: /^paper$/i }).click();
  await opsControls.getByRole('button', { name: /^recommend only$/i }).click();
  await opsControls.getByRole('button', { name: '3h' }).click();
  await opsControls.getByRole('button', { name: 'Arm Trigger' }).click();
  await opsControls.getByRole('button', { name: 'Risk Sweep' }).click();
  await opsControls.getByRole('button', { name: 'Convert Alert' }).click();
  await opsControls.getByRole('button', { name: 'Mute Watch' }).click();
  const opsTextAfterAdvisory = await page.locator('body').innerText();
  assert(opsTextAfterAdvisory.includes('Prediction Horizon'), 'Prediction Horizon control did not remain visible');
  assert(opsTextAfterAdvisory.includes('SPY forecast window set to 3h'), 'Prediction horizon did not write an audit entry');
  assert(opsTextAfterAdvisory.includes('SPY risk sweep queued against live support/resistance'), 'Risk Sweep did not write an audit entry');
  assert(opsTextAfterAdvisory.includes('SPY watch muted locally'), 'Mute Watch did not write an audit entry');
  await opsControls.getByRole('button', { name: 'Diagnostics' }).click();
  await opsControls.getByRole('button', { name: 'Ack Alerts' }).click();
  await opsControls.getByRole('button', { name: 'Lock Buys' }).click();
  await opsControls.getByRole('button', { name: 'Advise Stops' }).click();
  await opsControls.getByRole('button', { name: 'Reduce Size', exact: true }).click();
  const opsTextAfterProtection = await page.locator('body').innerText();
  assert(opsTextAfterProtection.includes('Runtime diagnostics reviewed'), 'Diagnostics did not write an audit entry');
  assert(opsTextAfterProtection.includes('Visible alert stack acknowledged'), 'Ack Alerts did not write an audit entry');
  assert(opsTextAfterProtection.includes('buy-side advisory posture locked'), 'Lock Buys did not write an audit entry');
  assert(opsTextAfterProtection.includes('stop review staged from current support'), 'Advise Stops did not write an audit entry');
  assert(opsTextAfterProtection.includes('size-reduction advisory recorded'), 'Reduce Size did not write an audit entry');
  await opsControls.getByRole('button', { name: 'Inject Break' }).click();
  await opsControls.getByRole('button', { name: 'Allow Guarded Breakout' }).click();
  await opsControls.getByRole('button', { name: 'Block Buy Below Support' }).click();
  await opsControls.getByRole('button', { name: 'Reduce Size On Heat Spike' }).click();
  await opsControls.getByRole('button', { name: 'Resimulate Greeks' }).click();
  await opsControls.getByRole('button', { name: 'Export Levels' }).click();
  const opsTextAfterChartDirectives = await page.locator('body').innerText();
  assert(opsTextAfterChartDirectives.includes('synthetic breakout/breakdown scenario injected'), 'Inject Break did not write an audit entry');
  assert(opsTextAfterChartDirectives.includes('guarded breakout directive staged'), 'Allow Guarded Breakout did not write an audit entry');
  assert(opsTextAfterChartDirectives.includes('buy-side block recorded below current support'), 'Block Buy Below Support did not write an audit entry');
  assert(opsTextAfterChartDirectives.includes('heat-spike size-reduction directive staged'), 'Reduce Size On Heat Spike did not write an audit entry');
  assert(opsTextAfterChartDirectives.includes('Greek surface resimulation requested'), 'Resimulate Greeks did not write an audit entry');
  assert(opsTextAfterChartDirectives.includes('key-level export recorded in the audit trail'), 'Export Levels did not write an audit entry');
  await opsControls.getByRole('button', { name: 'Pause', exact: true }).click();
  await opsControls.getByRole('button', { name: 'Resume', exact: true }).click();
  await opsControls.getByRole('button', { name: 'Enable Ticker' }).click();
  await opsControls.getByRole('button', { name: 'Disable Ticker' }).click();
  await opsControls.getByRole('button', { name: 'Add Current Input' }).click();
  const auditFilter = page.locator('.se-audit-filter');
  await auditFilter.getByRole('button', { name: /Operator/ }).click();
  const operatorAuditText = await page.locator('.se-audit-list').innerText();
  assert(operatorAuditText.includes('Operator'), 'Operator audit filter did not show operator rows');
  assert(!operatorAuditText.includes('Automation Gate'), 'Operator audit filter still showed backend/system rows');
  await auditFilter.getByRole('button', { name: /Backend\/System/ }).click();
  const systemAuditText = await page.locator('.se-audit-list').innerText();
  assert(systemAuditText.includes('Automation Gate') || systemAuditText.includes('Readiness Guard'), 'Backend/System audit filter did not show system rows');
  assert(!systemAuditText.includes('Prediction Horizon'), 'Backend/System audit filter still showed operator rows');
  await auditFilter.getByRole('button', { name: /All Activity/ }).click();
  const auditDownloadPromise = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Export Audit Log' }).click();
  const auditDownload = await auditDownloadPromise;
  const auditPath = await auditDownload.path();
  assert(auditPath, 'Audit export did not produce a readable download path');
  const auditJson = JSON.parse(await readFile(auditPath, 'utf8'));
  const operatorEvents = (auditJson.operator_audit_rows ?? []).map((row) => row.event);
  [
    'Prediction Horizon',
    'Arm Trigger',
    'Risk Sweep',
    'Convert Alert',
    'Mute Watch',
    'Diagnostics',
    'Ack Alerts',
    'Lock Buys',
    'Advise Stops',
    'Reduce Size',
    'Inject Break',
    'Allow Guarded Breakout',
    'Block Buy Below Support',
    'Reduce Size On Heat Spike',
    'Resimulate Greeks',
    'Export Levels',
    'Save Heatmap',
  ].forEach((event) => {
    assert(operatorEvents.includes(event), `Audit export did not include operator event ${event}`);
  });
  await opsControls.getByRole('button', { name: 'Emergency Exit' }).click();
  await opsControls.getByRole('button', { name: /^Remove SPY$/ }).click();
  await opsControls.getByRole('button', { name: 'Trailing Stop', exact: true }).click();
  await page.waitForTimeout(500);
  const hasControlRequest = (method, pathname, searchPart = '', bodyPart = '') => interceptedControls.some((request) => (
    request.method === method
    && request.pathname === pathname
    && (!searchPart || request.search.includes(searchPart))
    && (!bodyPart || request.body.includes(bodyPart))
  ));
  assert(hasControlRequest('POST', '/api/emergency/kill-switch', 'state='), 'Kill Switch did not issue intercepted POST /api/emergency/kill-switch');
  assert(hasControlRequest('PUT', '/api/automation', '', '"mode":"paper"'), 'Paper mode did not issue intercepted PUT /api/automation with mode paper');
  assert(hasControlRequest('PUT', '/api/automation', '', '"mode":"recommend_only"'), 'Recommend-only mode did not issue intercepted PUT /api/automation with mode recommend_only');
  assert(hasControlRequest('POST', '/api/control/pause'), 'Pause control did not issue intercepted POST /api/control/pause');
  assert(hasControlRequest('POST', '/api/control/resume'), 'Resume control did not issue intercepted POST /api/control/resume');
  assert(hasControlRequest('PUT', '/api/automation/tickers/SPY'), 'Enable/disable ticker did not issue intercepted PUT /api/automation/tickers/SPY');
  assert(hasControlRequest('POST', '/api/tickers/NVDA'), 'Topbar symbol input did not issue intercepted POST /api/tickers/NVDA');
  assert(hasControlRequest('POST', '/api/tickers/SPY'), 'Add Current Input did not issue intercepted POST /api/tickers/SPY');
  assert(hasControlRequest('DELETE', '/api/tickers/SPY'), 'Remove ticker did not issue intercepted DELETE /api/tickers/SPY');
  assert(hasControlRequest('POST', '/api/pulse/emergency-exit/SPY'), 'Emergency Exit did not issue intercepted POST /api/pulse/emergency-exit/SPY');
  assert(hasControlRequest('POST', '/api/pulse/trailing-stop/SPY', 'percent=1.25'), 'Trailing Stop did not issue intercepted POST /api/pulse/trailing-stop/SPY?percent=1.25');
  assert(dialogs.some((dialog) => dialog.type === 'confirm' && dialog.message.includes('kill switch')), 'Kill Switch did not show confirmation');
  assert(dialogs.some((dialog) => dialog.type === 'confirm' && dialog.message.includes('emergency-exit')), 'Emergency Exit did not show confirmation');
  assert(dialogs.some((dialog) => dialog.type === 'confirm' && dialog.message.includes('Remove SPY')), 'Remove ticker did not show confirmation');
  assert(dialogs.some((dialog) => dialog.type === 'prompt' && dialog.message.includes('Trailing stop percent')), 'Trailing Stop did not show prompt');

  const failedApi = apiResponses.filter((response) => response.status >= 500);
  const toleratedRateLimitFailures = httpFailures.filter((response) => (
    response.status === 429
    && (
      response.url.includes('/api/stats')
      || response.url.includes('/api/rate-limit/status')
    )
  ));
  const toleratedOrbEmptyResponses = httpFailures.filter(isToleratedOrbEmptyResponse);
  const unexpectedHttpFailures = httpFailures.filter((response) => (
    !toleratedRateLimitFailures.includes(response)
    && !toleratedOrbEmptyResponses.includes(response)
  ));
  const { unexpectedConsoleErrors, toleratedOrbConsoleErrors } = splitConsoleErrors(consoleErrors, {
    toleratedOrbEmptyCount: toleratedOrbEmptyResponses.length,
  });
  const marketDataProviderResponses = apiResponses.filter((response) => response.url.includes('/api/market-data/providers'));
  assert(marketDataProviderResponses.some((response) => response.status === 200), `Market data provider status was not fetched successfully: ${JSON.stringify(marketDataProviderResponses)}`);
  assert(failedApi.length === 0, `API calls returned server errors: ${JSON.stringify(failedApi)}`);
  assert(unexpectedHttpFailures.length === 0, `Unexpected HTTP failures: ${JSON.stringify(unexpectedHttpFailures)}; tolerated rate limits: ${JSON.stringify(toleratedRateLimitFailures)}; tolerated empty ORB routes: ${JSON.stringify(toleratedOrbEmptyResponses)}`);
  assert(unexpectedConsoleErrors.length === 0, `Browser console errors: ${JSON.stringify(unexpectedConsoleErrors)}; tolerated rate-limit console entries: ${JSON.stringify(consoleErrors.filter((message) => message.includes('status of 429 (Too Many Requests)')))}; tolerated empty ORB console entries: ${JSON.stringify(toleratedOrbConsoleErrors)}`);

  const fallbackProbe = await assertSupportResistanceFallback();
  const killSwitchStatusProbe = await assertKillSwitchStatusRendering();

  const mobileContext = await browser.newContext({
    viewport: { width: 390, height: 844 },
    isMobile: true,
    hasTouch: true,
  });
  const mobilePage = await mobileContext.newPage();
  const mobileConsoleErrors = [];
  const mobileHttpFailures = [];
  mobilePage.on('console', (message) => {
    if (message.type() === 'error') mobileConsoleErrors.push(message.text());
  });
  mobilePage.on('response', (response) => {
    if (response.url().includes('/api/') && response.status() >= 400) {
      mobileHttpFailures.push({ url: response.url(), status: response.status() });
    }
  });

  await mobilePage.goto(appUrl, { waitUntil: 'domcontentloaded', timeout: 15000 });
  await mobilePage.waitForSelector('.se-shell', { timeout: 15000 });
  await mobilePage.waitForFunction(() => document.body.innerText.includes('S/R API support / resistance'), null, { timeout: 20000 });
  const mobileBrandSubtitle = await mobilePage.locator('.se-brand p').innerText();
  assert(mobileBrandSubtitle === 'Risk Control Brain', `Unexpected mobile brand subtitle: ${mobileBrandSubtitle}`);
  assert(!(await mobilePage.locator('body').innerText()).includes('Legacy Asset Command Console'), 'Legacy console text still appears on mobile');
  const mobileOverflow = await mobilePage.evaluate(() => ({
    innerWidth: window.innerWidth,
    documentWidth: document.documentElement.scrollWidth,
    bodyWidth: document.body.scrollWidth,
  }));
  assert(
    mobileOverflow.documentWidth <= mobileOverflow.innerWidth + 2 && mobileOverflow.bodyWidth <= mobileOverflow.innerWidth + 2,
    `Mobile layout has horizontal overflow: ${JSON.stringify(mobileOverflow)}`,
  );
  await mobilePage.getByRole('button', { name: /Breakouts/ }).click();
  await mobilePage.waitForSelector('.se-grid-breakouts', { timeout: 10000 });
  await mobilePage.getByRole('button', { name: /Settings/ }).click();
  await mobilePage.waitForFunction(() => document.body.innerText.toLowerCase().includes('market data'), null, { timeout: 5000 });
  await mobilePage.getByRole('button', { name: /Protection Ops/ }).click();
  await mobilePage.waitForSelector('.se-ops-grid', { timeout: 10000 });
  const mobileOpsButtons = await mobilePage.locator('.se-ops-grid button').count();
  assert(mobileOpsButtons >= 20, `Expected recovered mobile ops controls, found ${mobileOpsButtons}`);
  await mobileContext.close();
  const mobileToleratedRateLimitFailures = mobileHttpFailures.filter((response) => (
    response.status === 429
    && (
      response.url.includes('/api/stats')
      || response.url.includes('/api/rate-limit/status')
    )
  ));
  const mobileToleratedOrbEmptyResponses = mobileHttpFailures.filter(isToleratedOrbEmptyResponse);
  const mobileUnexpectedHttpFailures = mobileHttpFailures.filter((response) => (
    !mobileToleratedRateLimitFailures.includes(response)
    && !mobileToleratedOrbEmptyResponses.includes(response)
  ));
  const {
    unexpectedConsoleErrors: mobileUnexpectedConsoleErrors,
    toleratedOrbConsoleErrors: mobileToleratedOrbConsoleErrors,
  } = splitConsoleErrors(mobileConsoleErrors, {
    toleratedOrbEmptyCount: mobileToleratedOrbEmptyResponses.length,
  });
  assert(mobileUnexpectedHttpFailures.length === 0, `Unexpected mobile HTTP failures: ${JSON.stringify(mobileUnexpectedHttpFailures)}; tolerated rate limits: ${JSON.stringify(mobileToleratedRateLimitFailures)}; tolerated empty ORB routes: ${JSON.stringify(mobileToleratedOrbEmptyResponses)}`);
  assert(mobileUnexpectedConsoleErrors.length === 0, `Mobile browser console errors: ${JSON.stringify(mobileUnexpectedConsoleErrors)}; tolerated rate-limit console entries: ${JSON.stringify(mobileConsoleErrors.filter((message) => message.includes('status of 429 (Too Many Requests)')))}; tolerated empty ORB console entries: ${JSON.stringify(mobileToleratedOrbConsoleErrors)}`);

  console.log(JSON.stringify({
    ok: true,
    expected: {
      currentPrice,
      support: support.price,
      resistance: resistance.price,
      srLevelCount: sr.levels.items.length,
    },
    firstRowCells,
    qqqFirstRowCells,
    nvdaInputRowCells,
    safeUiControls: {
      copiedSnapshot,
      topbarLiveToggle: true,
      manualRefreshTriggeredApiCalls: apiResponses.length > refreshStartApiCount,
      localSettingsLivePolling: true,
      toleratedOrbEmptyResponses: toleratedOrbEmptyResponses.length,
      toleratedOrbConsoleErrors: toleratedOrbConsoleErrors.length,
      mobileToleratedOrbEmptyResponses: mobileToleratedOrbEmptyResponses.length,
      mobileToleratedOrbConsoleErrors: mobileToleratedOrbConsoleErrors.length,
      localSettingsHeatMode: 'VEX',
    },
    kpiSnapshot,
    botEcosystemSnapshot,
    decisionFeedSnapshot,
    policyStackSnapshot,
    providerReadinessSnapshot,
    systemHealthPulseSnapshot,
    exportedHeatmap: {
      filename: heatmapDownload.suggestedFilename(),
      mode: heatmapJson.mode,
      seriesPoints: heatmapJson.series.length,
      tooltip: heatmapTooltipText,
    },
    expandedPopouts,
    canvasStats,
    auditFilters: {
      operatorRowsVisible: operatorAuditText.includes('Operator'),
      systemRowsVisible: systemAuditText.includes('Automation Gate') || systemAuditText.includes('Readiness Guard'),
    },
    moduleSnapshots,
    moduleDeepChecks,
    exportedOperatorEvents: operatorEvents,
    dialogs,
    interceptedControls,
    apiCallCount: apiResponses.length,
    marketDataProviderResponses,
    toleratedRateLimitFailures,
    fallbackProbe,
    killSwitchStatusProbe,
    mobile: {
      viewport: mobileOverflow.innerWidth,
      documentWidth: mobileOverflow.documentWidth,
      opsButtons: mobileOpsButtons,
      toleratedRateLimitFailures: mobileToleratedRateLimitFailures,
    },
  }, null, 2));
} finally {
  await browser.close();
}
