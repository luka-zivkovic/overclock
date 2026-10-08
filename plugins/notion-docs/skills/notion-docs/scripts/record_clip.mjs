#!/usr/bin/env node
/**
 * record_clip.mjs - record a scripted browser walkthrough as a short looping GIF for feature docs.
 *
 * Subcommands
 *   setup     [--deps DIR] [--playwright-version V]   install Playwright and Chromium into DIR
 *   doctor    [--deps DIR]                              report what is installed; never installs
 *   validate  SCENE.json                                check a scene offline, no browser
 *   snapshot  SCENE.json --out DIR [--url URL] [--after-steps] [--deps DIR]
 *                                                       screenshot plus accessibility tree for selector writing
 *   record    SCENE.json --out DIR [--deps DIR] [--headed]
 *                                                       record the scene to DIR/<name>.gif with poster, last frame, and manifest
 *   encode    --frames DIR --out FILE.gif [--fps N | --delay-ms N]
 *                                                       build a GIF from a directory of PNG frames
 *   login     --url URL --out STATE.json [--deps DIR]   open a headed browser, wait for a manual login, save storage state
 *   check     SCENE.json --out DIR [--baseline ARIA.yaml] [--deps DIR]
 *                                                       resolve every selector against the live app and diff the screen
 *   sheet     --clips DIR --out FILE.png [--columns N]   lay out every <name>.last.png in DIR as one contact sheet
 *
 * The only dependency is Playwright, resolved from the deps directory (default
 * ~/.cache/notion-docs/deps, or $NOTION_DOCS_DEPS). Frames are captured through the Chrome
 * DevTools screencast and encoded to GIF here, so no ffmpeg or image library is needed.
 */
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import zlib from 'node:zlib';
import readline from 'node:readline';
import { spawnSync } from 'node:child_process';
import { createRequire } from 'node:module';

const PLAYWRIGHT_VERSION = '1.63.0';
const DEFAULTS = Object.freeze({
  viewport: { width: 1280, height: 800 },
  scale: 0.75,
  fps: 10,
  max_seconds: 15,
  end_hold_ms: 1500,
  settle_ms: 600,
  timeout_ms: 10000,
  cursor: true,
  captions: true,
  color_scheme: 'light',
});
const ACTIONS = ['goto', 'click', 'dblclick', 'hover', 'fill', 'type', 'press', 'select', 'check', 'uncheck', 'scroll', 'wait', 'caption'];
const SELECTOR_ACTIONS = new Set(['click', 'dblclick', 'hover', 'fill', 'type', 'select', 'check', 'uncheck']);
const CREDENTIAL_FIELD = /password|passwd|secret|token|api[-_ ]?key/i;
const CURSOR_TRAVEL_MS = 480;
const RIPPLE_MS = 160;
const CAPTION_PAUSE_MS = 400;

// ---------------------------------------------------------------- cli plumbing

function parseArgs(argv) {
  const out = { _: [] };
  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];
    if (arg.startsWith('--')) {
      const key = arg.slice(2);
      const next = argv[i + 1];
      if (next === undefined || next.startsWith('--')) out[key] = true;
      else { out[key] = next; i++; }
    } else {
      out._.push(arg);
    }
  }
  return out;
}

function usage(code = 2) {
  const text = fs.readFileSync(new URL(import.meta.url), 'utf8');
  const doc = text.split('\n').slice(1).join('\n').split('*/')[0];
  process.stderr.write(doc.replace(/^ \* ?/gm, '') + '\n');
  process.exit(code);
}

function fail(message, code = 1) {
  process.stderr.write(`record_clip: ${message}\n`);
  process.exit(code);
}

function printJson(value) {
  process.stdout.write(JSON.stringify(value, null, 2) + '\n');
}

function log(message) {
  process.stderr.write(message + '\n');
}

function isInt(value, min, max) {
  return Number.isInteger(value) && value >= min && value <= max;
}

function isNum(value, min, max) {
  return typeof value === 'number' && Number.isFinite(value) && value >= min && value <= max;
}

// ---------------------------------------------------------------- dependencies

function depsDir(opts) {
  const raw = opts.deps || process.env.NOTION_DOCS_DEPS || path.join(os.homedir(), '.cache', 'notion-docs', 'deps');
  return path.resolve(String(raw));
}

function inspectDeps(dir) {
  const report = {
    node: process.version,
    deps_dir: dir,
    playwright_version: null,
    chromium_path: null,
    chromium_installed: false,
    ready: false,
    error: null,
  };
  try {
    const req = createRequire(path.join(dir, 'package.json'));
    report.playwright_version = req('playwright/package.json').version;
    const { chromium } = req('playwright');
    report.chromium_path = chromium.executablePath();
    report.chromium_installed = fs.existsSync(report.chromium_path);
  } catch (error) {
    report.error = String(error.message || error).split('\n')[0];
  }
  report.ready = Boolean(report.playwright_version) && report.chromium_installed;
  if (!report.ready) {
    report.next = `node ${path.basename(new URL(import.meta.url).pathname)} setup --deps ${dir}`;
  }
  return report;
}

function loadPlaywright(dir) {
  const report = inspectDeps(dir);
  if (!report.ready) {
    fail(`Playwright is not ready under ${dir} (${report.error || 'browser missing'}). Run: ${report.next}`);
  }
  const req = createRequire(path.join(dir, 'package.json'));
  return req('playwright');
}

function cmdDoctor(opts) {
  printJson(inspectDeps(depsDir(opts)));
}

function cmdSetup(opts) {
  const dir = depsDir(opts);
  const version = String(opts['playwright-version'] || PLAYWRIGHT_VERSION);
  if (!/^\d+\.\d+\.\d+$/.test(version)) fail('--playwright-version must look like 1.63.0');
  fs.mkdirSync(dir, { recursive: true });
  const manifest = path.join(dir, 'package.json');
  if (!fs.existsSync(manifest)) {
    fs.writeFileSync(manifest, JSON.stringify({
      name: 'notion-docs-deps',
      private: true,
      description: 'Playwright for the notion-docs clip recorder. Safe to delete; `setup` recreates it.',
    }, null, 2) + '\n');
  }
  const npm = process.platform === 'win32' ? 'npm.cmd' : 'npm';
  log(`Installing playwright@${version} into ${dir}`);
  const install = spawnSync(npm, ['install', '--prefix', dir, '--no-audit', '--no-fund', `playwright@${version}`], { stdio: 'inherit' });
  if (install.status !== 0) fail('npm install failed');
  const cli = path.join(dir, 'node_modules', 'playwright', 'cli.js');
  log('Installing Chromium for Playwright (skipped when the matching build is already cached)');
  const browsers = spawnSync(process.execPath, [cli, 'install', 'chromium'], { stdio: 'inherit' });
  if (browsers.status !== 0) fail('playwright install chromium failed');
  printJson(inspectDeps(dir));
}

// ---------------------------------------------------------------- scenes

function loadScene(file) {
  const scenePath = path.resolve(String(file));
  let raw;
  try {
    raw = fs.readFileSync(scenePath, 'utf8');
  } catch (error) {
    fail(`cannot read scene ${scenePath}: ${error.message}`);
  }
  let scene;
  try {
    scene = JSON.parse(raw);
  } catch (error) {
    fail(`scene ${scenePath} is not valid JSON: ${error.message}`);
  }
  return { scene, scenePath, sceneDir: path.dirname(scenePath) };
}

function validateStep(step, where, inSetup, errors, warnings) {
  if (!step || typeof step !== 'object' || Array.isArray(step)) {
    errors.push(`${where}: step must be an object`);
    return;
  }
  if (!ACTIONS.includes(step.action)) {
    errors.push(`${where}: unknown action ${JSON.stringify(step.action)}; valid actions: ${ACTIONS.join(', ')}`);
    return;
  }
  const selector = typeof step.selector === 'string' ? step.selector.trim() : '';
  if (SELECTOR_ACTIONS.has(step.action) && !selector) errors.push(`${where}: ${step.action} needs a selector`);
  if (step.nth !== undefined && !isInt(step.nth, 0, 999)) errors.push(`${where}: nth must be an integer from 0 to 999`);
  if (step.caption !== undefined && (typeof step.caption !== 'string' || step.caption.length > 80)) {
    errors.push(`${where}: caption must be a string of at most 80 characters`);
  }
  switch (step.action) {
    case 'goto':
      if (typeof step.url !== 'string' || !/^(https?|file):\/\//.test(step.url)) errors.push(`${where}: goto needs a url starting with http://, https://, or file://`);
      break;
    case 'fill':
    case 'type': {
      const hasText = typeof step.text === 'string';
      const hasEnv = typeof step.text_env === 'string';
      if (hasText === hasEnv) errors.push(`${where}: ${step.action} needs exactly one of text or text_env`);
      if (hasEnv && !inSetup) errors.push(`${where}: text_env is allowed only in setup steps; recorded steps must not type secrets`);
      if (hasEnv && !/^[A-Z][A-Z0-9_]*$/.test(step.text_env)) errors.push(`${where}: text_env must name an environment variable such as APP_PASSWORD`);
      if (hasText && CREDENTIAL_FIELD.test(selector)) {
        if (inSetup) errors.push(`${where}: literal text into a credential-looking field; use text_env so the secret stays out of the scene file`);
        else errors.push(`${where}: recorded steps must not type into credential fields; log in during setup with text_env instead`);
      }
      if (step.action === 'type' && step.delay_ms !== undefined && !isInt(step.delay_ms, 0, 500)) errors.push(`${where}: delay_ms must be an integer from 0 to 500`);
      break;
    }
    case 'press':
      if (typeof step.key !== 'string' || !step.key) errors.push(`${where}: press needs a key such as Enter or Control+k`);
      break;
    case 'select':
      if (typeof step.value !== 'string') errors.push(`${where}: select needs a value`);
      break;
    case 'scroll':
      if (!selector && !isInt(step.y, -20000, 20000)) errors.push(`${where}: scroll needs a selector or a y offset in pixels`);
      break;
    case 'wait': {
      const hasMs = step.ms !== undefined;
      if (hasMs === Boolean(selector)) errors.push(`${where}: wait needs exactly one of ms or selector`);
      if (hasMs && !isInt(step.ms, 0, 10000)) errors.push(`${where}: wait ms must be an integer from 0 to 10000`);
      if (step.state !== undefined && !['visible', 'hidden', 'attached', 'detached'].includes(step.state)) errors.push(`${where}: wait state must be visible, hidden, attached, or detached`);
      break;
    }
    case 'caption':
      if (typeof step.text !== 'string') errors.push(`${where}: caption needs text; an empty string clears the caption`);
      break;
    default:
      break;
  }
}

function estimateStepMs(step, scene) {
  switch (step.action) {
    case 'wait': return step.ms !== undefined ? step.ms : 500;
    case 'caption': return CAPTION_PAUSE_MS;
    case 'goto': return 800 + scene.settle_ms;
    case 'type': return (step.text ? step.text.length : 8) * (step.delay_ms ?? 45) + CURSOR_TRAVEL_MS + RIPPLE_MS + scene.settle_ms;
    case 'press': case 'scroll': return 200 + scene.settle_ms;
    default: return CURSOR_TRAVEL_MS + RIPPLE_MS + scene.settle_ms;
  }
}

function normalizeScene(input, sceneDir) {
  const scene = { ...DEFAULTS, ...input };
  scene.viewport = { ...DEFAULTS.viewport, ...(input.viewport || {}) };
  scene.setup = Array.isArray(input.setup) ? input.setup : [];
  scene.steps = Array.isArray(input.steps) ? input.steps : [];
  if (typeof input.storage_state === 'string') {
    scene.storage_state = path.resolve(sceneDir, input.storage_state);
  }
  return scene;
}

function validateScene(input, sceneDir) {
  const errors = [];
  const warnings = [];
  if (!input || typeof input !== 'object' || Array.isArray(input)) {
    return { ok: false, errors: ['scene must be a JSON object'], warnings, summary: null };
  }
  if (typeof input.name !== 'string' || !/^[a-z0-9][a-z0-9-]{0,63}$/.test(input.name)) {
    errors.push('name: a lowercase slug of letters, digits, and hyphens, up to 64 characters');
  }
  if (typeof input.url !== 'string' || !/^(https?|file):\/\//.test(input.url)) {
    errors.push('url: must start with http://, https://, or file://');
  }
  const vp = { ...DEFAULTS.viewport, ...(input.viewport || {}) };
  if (!isInt(vp.width, 320, 3840) || !isInt(vp.height, 240, 2160)) errors.push('viewport: width 320..3840 and height 240..2160');
  if (input.scale !== undefined && !isNum(input.scale, 0.25, 1)) errors.push('scale: a number from 0.25 to 1');
  if (input.fps !== undefined && !isInt(input.fps, 4, 15)) errors.push('fps: an integer from 4 to 15');
  if (input.max_seconds !== undefined && !isNum(input.max_seconds, 1, 30)) errors.push('max_seconds: a number from 1 to 30');
  if (input.end_hold_ms !== undefined && !isInt(input.end_hold_ms, 0, 5000)) errors.push('end_hold_ms: an integer from 0 to 5000');
  if (input.settle_ms !== undefined && !isInt(input.settle_ms, 0, 3000)) errors.push('settle_ms: an integer from 0 to 3000');
  if (input.timeout_ms !== undefined && !isInt(input.timeout_ms, 1000, 60000)) errors.push('timeout_ms: an integer from 1000 to 60000');
  if (input.cursor !== undefined && typeof input.cursor !== 'boolean') errors.push('cursor: true or false');
  if (input.captions !== undefined && typeof input.captions !== 'boolean') errors.push('captions: true or false');
  if (input.color_scheme !== undefined && !['light', 'dark'].includes(input.color_scheme)) errors.push('color_scheme: light or dark');
  if (input.mutates !== undefined && typeof input.mutates !== 'boolean') errors.push('mutates: true or false');
  if (input.storage_state !== undefined) {
    if (typeof input.storage_state !== 'string') errors.push('storage_state: a path to a Playwright storage state file');
    else if (sceneDir && !fs.existsSync(path.resolve(sceneDir, input.storage_state))) errors.push(`storage_state: file not found at ${path.resolve(sceneDir, input.storage_state)}`);
  }
  if (input.setup !== undefined && !Array.isArray(input.setup)) errors.push('setup: must be an array of steps');
  if (!Array.isArray(input.steps) || input.steps.length === 0) errors.push('steps: at least one recorded step is required');
  const knownKeys = new Set(['name', 'url', 'viewport', 'scale', 'fps', 'max_seconds', 'end_hold_ms', 'settle_ms', 'timeout_ms', 'cursor', 'captions', 'color_scheme', 'storage_state', 'setup', 'steps', 'description', 'mutates']);
  for (const key of Object.keys(input)) if (!knownKeys.has(key)) warnings.push(`unknown top-level key ${JSON.stringify(key)} is ignored`);
  (Array.isArray(input.setup) ? input.setup : []).forEach((step, i) => validateStep(step, `setup[${i}]`, true, errors, warnings));
  (Array.isArray(input.steps) ? input.steps : []).forEach((step, i) => validateStep(step, `steps[${i}]`, false, errors, warnings));

  let summary = null;
  if (errors.length === 0) {
    const scene = normalizeScene(input, sceneDir || '.');
    const estimated = scene.steps.reduce((sum, step) => sum + estimateStepMs(step, scene), 0) + scene.end_hold_ms;
    summary = {
      name: scene.name,
      url: scene.url,
      setup_steps: scene.setup.length,
      recorded_steps: scene.steps.length,
      mutates: Boolean(scene.mutates),
      output_width: Math.round(scene.viewport.width * scene.scale),
      output_height: Math.round(scene.viewport.height * scene.scale),
      estimated_seconds: Math.round(estimated / 100) / 10,
      max_seconds: scene.max_seconds,
    };
    if (estimated > scene.max_seconds * 1000) warnings.push(`estimated duration ${summary.estimated_seconds}s exceeds max_seconds ${scene.max_seconds}; split the scene or raise max_seconds`);
    if (scene.steps.length > 12) warnings.push('more than 12 recorded steps rarely reads well as one clip; consider splitting');
  }
  return { ok: errors.length === 0, errors, warnings, summary };
}

function cmdValidate(opts) {
  const file = opts._[1];
  if (!file) usage();
  const { scene, sceneDir } = loadScene(file);
  const result = validateScene(scene, sceneDir);
  printJson(result);
  process.exit(result.ok ? 0 : 1);
}

function requireValidScene(file) {
  const { scene, scenePath, sceneDir } = loadScene(file);
  const result = validateScene(scene, sceneDir);
  if (!result.ok) {
    printJson(result);
    fail(`scene ${scenePath} is invalid`);
  }
  for (const warning of result.warnings) log(`warning: ${warning}`);
  return { scene: normalizeScene(scene, sceneDir), scenePath };
}

// ---------------------------------------------------------------- in-page overlay

const OVERLAY_SCRIPT = String.raw`(() => {
  if (window.__nd) return;
  const Z = 2147483647;
  let root = null, cursor = null, ring = null, pill = null, cur = null;
  function ensure() {
    if (root && root.isConnected) return;
    root = document.createElement('div');
    root.id = '__nd-overlay';
    root.setAttribute('style', 'position:fixed;inset:0;pointer-events:none;z-index:' + Z + ';');
    const style = document.createElement('style');
    style.textContent = '@keyframes __nd-ripple{from{transform:scale(.4);opacity:.95}to{transform:scale(2.4);opacity:0}}';
    root.appendChild(style);
    ring = document.createElement('div');
    ring.setAttribute('style', 'position:absolute;border:2px solid #ff5a36;border-radius:7px;box-shadow:0 0 0 4px rgba(255,90,54,.22);opacity:0;transition:opacity 160ms,left 160ms,top 160ms,width 160ms,height 160ms;');
    pill = document.createElement('div');
    pill.setAttribute('style', 'position:absolute;left:50%;bottom:26px;transform:translateX(-50%);max-width:82%;padding:9px 16px;border-radius:999px;background:rgba(17,17,17,.9);color:#fff;font:500 16px/1.3 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;opacity:0;transition:opacity 160ms;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;');
    cursor = document.createElement('div');
    cursor.setAttribute('style', 'position:absolute;left:0;top:0;width:22px;height:30px;transform:translate(-9999px,-9999px);transition:transform 440ms cubic-bezier(.22,.61,.36,1);filter:drop-shadow(0 1px 2px rgba(0,0,0,.5));');
    cursor.innerHTML = '<svg width="22" height="30" viewBox="0 0 22 30"><path d="M3 2 L3 24 L8.5 18.5 L12.5 27 L16 25.5 L12 17 L19.5 17 Z" fill="#fff" stroke="#111" stroke-width="1.6" stroke-linejoin="round"/></svg>';
    root.append(ring, pill, cursor);
    (document.documentElement || document.body).appendChild(root);
  }
  window.__nd = {
    move(x, y) { ensure(); cur = { x, y }; cursor.style.transform = 'translate(' + (x - 3) + 'px,' + (y - 2) + 'px)'; },
    jump(x, y) { ensure(); const t = cursor.style.transition; cursor.style.transition = 'none'; this.move(x, y); void cursor.offsetWidth; cursor.style.transition = t; },
    ripple() {
      ensure(); if (!cur) return;
      const r = document.createElement('div');
      r.setAttribute('style', 'position:absolute;left:' + (cur.x - 14) + 'px;top:' + (cur.y - 14) + 'px;width:28px;height:28px;border-radius:50%;border:3px solid #ff5a36;animation:__nd-ripple 480ms ease-out forwards;');
      root.appendChild(r);
      setTimeout(() => r.remove(), 540);
    },
    highlight(box) {
      ensure();
      if (!box) { ring.style.opacity = '0'; return; }
      ring.style.left = (box.x - 4) + 'px'; ring.style.top = (box.y - 4) + 'px';
      ring.style.width = (box.width + 8) + 'px'; ring.style.height = (box.height + 8) + 'px';
      ring.style.opacity = '1';
    },
    caption(text) { ensure(); if (!text) { pill.style.opacity = '0'; return; } pill.textContent = text; pill.style.opacity = '1'; },
    hideCursor() { ensure(); cursor.style.display = 'none'; },
  };
})();`;

// ---------------------------------------------------------------- browser driving

function locate(page, step) {
  let loc = page.locator(step.selector);
  if (step.nth !== undefined) loc = loc.nth(step.nth);
  return loc;
}

// The occurrence a non-strict wait watches: the nth one when the step names it, else the first.
function waitTarget(page, step) {
  return step.nth !== undefined ? locate(page, step) : page.locator(step.selector).first();
}

function resolveText(step) {
  if (typeof step.text === 'string') return step.text;
  const value = process.env[step.text_env];
  if (value === undefined) throw new Error(`environment variable ${step.text_env} is not set`);
  return value;
}

function describeStep(step) {
  const target = step.selector ? ` ${step.selector}${step.nth !== undefined ? ` [${step.nth}]` : ''}` : step.url ? ` ${step.url}` : step.key ? ` ${step.key}` : step.ms !== undefined ? ` ${step.ms}ms` : '';
  return `${step.action}${target}`;
}

async function openScene(pw, scene, { headed = false } = {}) {
  const browser = await pw.chromium.launch({ headless: !headed });
  const contextOptions = {
    viewport: scene.viewport,
    deviceScaleFactor: 1,
    colorScheme: scene.color_scheme,
    reducedMotion: 'no-preference',
  };
  if (scene.storage_state) contextOptions.storageState = scene.storage_state;
  const context = await browser.newContext(contextOptions);
  await context.addInitScript(OVERLAY_SCRIPT);
  const page = await context.newPage();
  page.setDefaultTimeout(scene.timeout_ms);
  page.setDefaultNavigationTimeout(Math.max(scene.timeout_ms, 30000));
  return { browser, context, page };
}

function makeOverlay(page, scene) {
  const evaluate = async (fn, arg) => {
    try { await page.evaluate(fn, arg); } catch { /* page navigating; overlay is re-created on the next call */ }
  };
  return {
    async approach(loc, highlight) {
      const box = await loc.boundingBox();
      if (!box) return;
      const x = box.x + box.width / 2;
      const y = box.y + box.height / 2;
      if (highlight && scene.cursor) await evaluate((b) => window.__nd && window.__nd.highlight(b), box);
      if (scene.cursor) {
        await evaluate(([cx, cy]) => window.__nd && window.__nd.move(cx, cy), [x, y]);
        await page.waitForTimeout(CURSOR_TRAVEL_MS);
      } else {
        await page.waitForTimeout(160);
      }
    },
    async ripple() {
      if (!scene.cursor) return;
      await evaluate(() => window.__nd && window.__nd.ripple());
      await page.waitForTimeout(RIPPLE_MS);
    },
    async unhighlight() {
      await evaluate(() => window.__nd && window.__nd.highlight(null));
    },
    async caption(text) {
      if (!scene.captions) return;
      await evaluate((t) => window.__nd && window.__nd.caption(t), text);
    },
    async place(x, y) {
      if (!scene.cursor) return;
      await evaluate(([cx, cy]) => window.__nd && window.__nd.jump(cx, cy), [x, y]);
    },
  };
}

async function runStep(page, scene, overlay, step, recording) {
  const loc = step.selector && step.action !== 'wait' ? locate(page, step) : null;
  if (recording && step.caption) {
    await overlay.caption(step.caption);
  }
  switch (step.action) {
    case 'goto':
      await page.goto(step.url, { waitUntil: 'load' });
      break;
    case 'click':
    case 'dblclick':
    case 'hover':
    case 'check':
    case 'uncheck':
    case 'select':
    case 'fill':
    case 'type': {
      await loc.waitFor({ state: 'visible' });
      await loc.scrollIntoViewIfNeeded();
      if (recording) await overlay.approach(loc, step.action !== 'hover');
      if (step.action === 'hover') {
        await loc.hover();
      } else {
        if (recording) await overlay.ripple();
        if (step.action === 'click') await loc.click({ button: step.button || 'left' });
        else if (step.action === 'dblclick') await loc.dblclick();
        else if (step.action === 'check') await loc.check();
        else if (step.action === 'uncheck') await loc.uncheck();
        else if (step.action === 'select') await loc.selectOption(step.value);
        else if (step.action === 'fill') { await loc.click(); await loc.fill(resolveText(step)); }
        else if (step.action === 'type') { await loc.click(); await loc.pressSequentially(resolveText(step), { delay: step.delay_ms ?? (recording ? 45 : 0) }); }
      }
      if (recording) await overlay.unhighlight();
      break;
    }
    case 'press':
      if (loc) await loc.press(step.key);
      else await page.keyboard.press(step.key);
      break;
    case 'scroll':
      if (loc) await loc.scrollIntoViewIfNeeded();
      else await page.mouse.wheel(0, step.y);
      break;
    case 'wait':
      if (step.ms !== undefined) await page.waitForTimeout(step.ms);
      else {
        // wait is not strict: without nth it watches the first match, so a wait selector that can
        // match something already on the page passes at once. Scenes should wait for a state only
        // the action can produce (a dialog hidden, a toast) or pin the element with nth.
        await waitTarget(page, step).waitFor({ state: step.state || 'visible' });
      }
      break;
    case 'caption':
      if (recording) {
        await overlay.caption(step.text);
        await page.waitForTimeout(CAPTION_PAUSE_MS);
      }
      break;
    default:
      throw new Error(`unknown action ${step.action}`);
  }
  if (recording && !['wait', 'caption'].includes(step.action)) {
    await page.waitForTimeout(scene.settle_ms);
  }
}

async function runSteps(page, scene, overlay, steps, recording, results, label) {
  for (let i = 0; i < steps.length; i++) {
    const step = steps[i];
    const started = Date.now();
    const entry = { index: i, phase: label, action: step.action, selector: step.selector, status: 'ok', duration_ms: 0 };
    log(`[${label} ${i + 1}/${steps.length}] ${describeStep(step)}`);
    try {
      await runStep(page, scene, overlay, step, recording);
    } catch (error) {
      entry.status = 'failed';
      entry.error = String(error.message || error).split('\n').slice(0, 3).join(' ');
      results.push(entry);
      throw Object.assign(new Error(`${label} step ${i + 1} (${describeStep(step)}) failed: ${entry.error}`), { stepEntry: entry });
    } finally {
      entry.duration_ms = Date.now() - started;
      if (entry.status === 'ok') results.push(entry);
    }
  }
}

// ---------------------------------------------------------------- PNG decode

function decodePNG(buf) {
  if (buf.length < 8 || buf.readUInt32BE(0) !== 0x89504e47) throw new Error('not a PNG');
  let pos = 8;
  let width = 0, height = 0, bitDepth = 0, colorType = 0, interlace = 0;
  const idats = [];
  while (pos + 8 <= buf.length) {
    const len = buf.readUInt32BE(pos);
    const type = buf.toString('latin1', pos + 4, pos + 8);
    const data = buf.subarray(pos + 8, pos + 8 + len);
    if (type === 'IHDR') {
      width = data.readUInt32BE(0); height = data.readUInt32BE(4);
      bitDepth = data[8]; colorType = data[9]; interlace = data[12];
    } else if (type === 'IDAT') {
      idats.push(data);
    } else if (type === 'IEND') {
      break;
    }
    pos += 12 + len;
  }
  if (bitDepth !== 8 || ![2, 6].includes(colorType) || interlace !== 0) {
    throw new Error(`unsupported PNG (bit depth ${bitDepth}, color type ${colorType}, interlace ${interlace}); 8-bit RGB or RGBA without interlace is required`);
  }
  const bpp = colorType === 6 ? 4 : 3;
  const stride = width * bpp;
  const raw = zlib.inflateSync(Buffer.concat(idats));
  if (raw.length < height * (stride + 1)) throw new Error('PNG data is truncated');
  const rgb = new Uint8Array(width * height * 3);
  let prev = new Uint8Array(stride);
  let cur = new Uint8Array(stride);
  for (let y = 0; y < height; y++) {
    const filter = raw[y * (stride + 1)];
    const off = y * (stride + 1) + 1;
    for (let i = 0; i < stride; i++) {
      const x = raw[off + i];
      const a = i >= bpp ? cur[i - bpp] : 0;
      const b = prev[i];
      const c = i >= bpp ? prev[i - bpp] : 0;
      let v;
      switch (filter) {
        case 0: v = x; break;
        case 1: v = x + a; break;
        case 2: v = x + b; break;
        case 3: v = x + ((a + b) >> 1); break;
        case 4: {
          const p = a + b - c;
          const pa = Math.abs(p - a), pb = Math.abs(p - b), pc = Math.abs(p - c);
          v = x + (pa <= pb && pa <= pc ? a : pb <= pc ? b : c);
          break;
        }
        default: throw new Error(`bad PNG filter ${filter}`);
      }
      cur[i] = v & 255;
    }
    for (let x = 0; x < width; x++) {
      const s = x * bpp, d = (y * width + x) * 3;
      rgb[d] = cur[s]; rgb[d + 1] = cur[s + 1]; rgb[d + 2] = cur[s + 2];
    }
    [prev, cur] = [cur, prev];
  }
  return { width, height, rgb };
}

// ---------------------------------------------------------------- palette + GIF encode

function addToHistogram(hist, rgb, stepPx) {
  const n = rgb.length / 3;
  for (let i = 0; i < n; i += stepPx) {
    const key = (rgb[i * 3] << 16) | (rgb[i * 3 + 1] << 8) | rgb[i * 3 + 2];
    hist.set(key, (hist.get(key) || 0) + 1);
  }
}

function buildPalette(hist, maxColors = 256) {
  const entries = [];
  for (const [key, count] of hist) entries.push({ r: (key >> 16) & 255, g: (key >> 8) & 255, b: key & 255, c: count });
  if (entries.length === 0) return [[0, 0, 0]];
  if (entries.length <= maxColors) return entries.map((e) => [e.r, e.g, e.b]);
  const ranges = (box) => {
    let rMin = 255, rMax = 0, gMin = 255, gMax = 0, bMin = 255, bMax = 0, total = 0;
    for (const e of box) {
      if (e.r < rMin) rMin = e.r; if (e.r > rMax) rMax = e.r;
      if (e.g < gMin) gMin = e.g; if (e.g > gMax) gMax = e.g;
      if (e.b < bMin) bMin = e.b; if (e.b > bMax) bMax = e.b;
      total += e.c;
    }
    const spans = [['r', rMax - rMin], ['g', gMax - gMin], ['b', bMax - bMin]].sort((x, y) => y[1] - x[1]);
    return { channel: spans[0][0], range: spans[0][1], total };
  };
  const boxes = [entries];
  while (boxes.length < maxColors) {
    let bestIndex = -1, bestScore = -1, bestChannel = 'r';
    for (let i = 0; i < boxes.length; i++) {
      if (boxes[i].length < 2) continue;
      const { channel, range, total } = ranges(boxes[i]);
      if (range === 0) continue;
      const score = range * Math.log(1 + total);
      if (score > bestScore) { bestScore = score; bestIndex = i; bestChannel = channel; }
    }
    if (bestIndex < 0) break;
    const box = boxes[bestIndex];
    box.sort((x, y) => x[bestChannel] - y[bestChannel]);
    const total = box.reduce((sum, e) => sum + e.c, 0);
    let acc = 0, cut = 0;
    for (; cut < box.length - 2; cut++) {
      acc += box[cut].c;
      if (acc >= total / 2) break;
    }
    boxes.splice(bestIndex, 1, box.slice(0, cut + 1), box.slice(cut + 1));
  }
  return boxes.map((box) => {
    let mode = box[0], total = 0, r = 0, g = 0, b = 0;
    for (const e of box) {
      total += e.c; r += e.r * e.c; g += e.g * e.c; b += e.b * e.c;
      if (e.c > mode.c) mode = e;
    }
    // A dominant exact color (flat UI backgrounds, brand colors) stays exact; blends average.
    if (mode.c * 2 >= total) return [mode.r, mode.g, mode.b];
    return [Math.round(r / total), Math.round(g / total), Math.round(b / total)];
  });
}

function makeMapper(palette) {
  const cache = new Map();
  for (let i = 0; i < palette.length; i++) {
    const [r, g, b] = palette[i];
    cache.set((r << 16) | (g << 8) | b, i);
  }
  return function mapFrame(rgb) {
    const n = rgb.length / 3;
    const out = new Uint8Array(n);
    for (let i = 0; i < n; i++) {
      const r = rgb[i * 3], g = rgb[i * 3 + 1], b = rgb[i * 3 + 2];
      const key = (r << 16) | (g << 8) | b;
      let index = cache.get(key);
      if (index === undefined) {
        let best = 0, bestDist = Infinity;
        for (let p = 0; p < palette.length; p++) {
          const dr = r - palette[p][0], dg = g - palette[p][1], db = b - palette[p][2];
          const dist = dr * dr + dg * dg + db * db;
          if (dist < bestDist) { bestDist = dist; best = p; if (dist === 0) break; }
        }
        index = best;
        cache.set(key, index);
      }
      out[i] = index;
    }
    return out;
  };
}

function lzwEncode(indices, minCodeSize) {
  const CLEAR = 1 << minCodeSize;
  const EOI = CLEAR + 1;
  const blocks = [];
  let block = Buffer.alloc(255);
  let blockLen = 0;
  let acc = 0, accBits = 0;
  const emitByte = (byte) => {
    block[blockLen++] = byte;
    if (blockLen === 255) { blocks.push(block); block = Buffer.alloc(255); blockLen = 0; }
  };
  const emit = (code, size) => {
    acc |= code << accBits;
    accBits += size;
    while (accBits >= 8) { emitByte(acc & 255); acc >>>= 8; accBits -= 8; }
  };
  const table = new Int32Array(4096 * 256);
  let generation = 1;
  let codeSize = minCodeSize + 1;
  let next = EOI + 1;
  emit(CLEAR, codeSize);
  if (indices.length === 0) {
    emit(EOI, codeSize);
  } else {
    let prefix = indices[0];
    for (let i = 1; i < indices.length; i++) {
      const k = indices[i];
      const key = (prefix << 8) | k;
      const entry = table[key];
      if ((entry >>> 12) === generation) { prefix = entry & 4095; continue; }
      emit(prefix, codeSize);
      if (next >= (1 << codeSize) && codeSize < 12) codeSize++;
      if (next >= 4095) {
        emit(CLEAR, codeSize);
        generation++;
        if (generation >= (1 << 19)) { table.fill(0); generation = 1; }
        codeSize = minCodeSize + 1;
        next = EOI + 1;
      } else {
        table[key] = (generation << 12) | next;
        next++;
      }
      prefix = k;
    }
    emit(prefix, codeSize);
    if (next >= (1 << codeSize) && codeSize < 12) codeSize++;
    emit(EOI, codeSize);
  }
  if (accBits > 0) emitByte(acc & 255);
  if (blockLen > 0) blocks.push(block.subarray(0, blockLen));
  return blocks;
}

function encodeGIF({ width, height, palette, frames, loop = 0 }) {
  const parts = [Buffer.from('GIF89a', 'latin1')];
  const lsd = Buffer.alloc(7);
  lsd.writeUInt16LE(width, 0); lsd.writeUInt16LE(height, 2);
  lsd[4] = 0xF7; lsd[5] = 0; lsd[6] = 0;
  parts.push(lsd);
  const gct = Buffer.alloc(256 * 3);
  palette.forEach(([r, g, b], i) => { gct[i * 3] = r; gct[i * 3 + 1] = g; gct[i * 3 + 2] = b; });
  parts.push(gct);
  parts.push(Buffer.from([0x21, 0xFF, 0x0B, ...Buffer.from('NETSCAPE2.0', 'latin1'), 0x03, 0x01, loop & 255, (loop >> 8) & 255, 0x00]));
  for (const frame of frames) {
    const delay = Math.max(2, Math.min(65535, Math.round(frame.delay_ms / 10)));
    parts.push(Buffer.from([0x21, 0xF9, 0x04, 0x04, delay & 255, (delay >> 8) & 255, 0x00, 0x00]));
    const descriptor = Buffer.alloc(10);
    descriptor[0] = 0x2C;
    descriptor.writeUInt16LE(0, 1); descriptor.writeUInt16LE(0, 3);
    descriptor.writeUInt16LE(width, 5); descriptor.writeUInt16LE(height, 7);
    descriptor[9] = 0;
    parts.push(descriptor, Buffer.from([8]));
    for (const block of lzwEncode(frame.indices, 8)) parts.push(Buffer.from([block.length]), block);
    parts.push(Buffer.from([0]));
  }
  parts.push(Buffer.from([0x3B]));
  return Buffer.concat(parts);
}

/** frames: [{ png: Buffer, delay_ms }] in display order, all the same size. */
function framesToGif(frames) {
  if (frames.length === 0) throw new Error('no frames to encode');
  const first = decodePNG(frames[0].png);
  const { width, height } = first;
  const hist = new Map();
  const sampleCount = Math.min(frames.length, 12);
  const sampleStride = Math.max(1, Math.floor(frames.length / sampleCount));
  const pixelStride = Math.max(1, Math.round((width * height * sampleCount) / 400000));
  for (let i = 0; i < frames.length; i += sampleStride) {
    const decoded = i === 0 ? first : decodePNG(frames[i].png);
    if (decoded.width !== width || decoded.height !== height) continue;
    addToHistogram(hist, decoded.rgb, pixelStride);
  }
  if ((frames.length - 1) % sampleStride !== 0) {
    const last = decodePNG(frames[frames.length - 1].png);
    if (last.width === width && last.height === height) addToHistogram(hist, last.rgb, pixelStride);
  }
  const palette = buildPalette(hist, 256);
  const mapFrame = makeMapper(palette);
  const encoded = [];
  let skipped = 0;
  for (let i = 0; i < frames.length; i++) {
    const decoded = i === 0 ? first : decodePNG(frames[i].png);
    if (decoded.width !== width || decoded.height !== height) { skipped++; continue; }
    const indices = mapFrame(decoded.rgb);
    const previous = encoded[encoded.length - 1];
    if (previous && Buffer.compare(Buffer.from(previous.indices.buffer), Buffer.from(indices.buffer)) === 0) {
      previous.delay_ms += frames[i].delay_ms;
      continue;
    }
    encoded.push({ indices, delay_ms: frames[i].delay_ms });
  }
  const gif = encodeGIF({ width, height, palette, frames: encoded });
  return {
    gif,
    width,
    height,
    frames: encoded.length,
    skipped_frames: skipped,
    duration_ms: encoded.reduce((sum, f) => sum + f.delay_ms, 0),
    palette_size: palette.length,
  };
}

// ---------------------------------------------------------------- screencast capture

function startCapture(cdp, fps) {
  const interval = 1000 / fps;
  const buckets = []; // one frame per interval bucket: the latest state seen in that bucket
  let origin = null;
  const onFrame = ({ data, metadata, sessionId }) => {
    const t = metadata && typeof metadata.timestamp === 'number' ? metadata.timestamp * 1000 : Date.now();
    if (origin === null) origin = t;
    const bucket = Math.floor((t - origin) / interval);
    const frame = { png: Buffer.from(data, 'base64'), t, bucket };
    const last = buckets[buckets.length - 1];
    if (last && last.bucket === bucket) buckets[buckets.length - 1] = frame;
    else buckets.push(frame);
    cdp.send('Page.screencastFrameAck', { sessionId }).catch(() => {});
  };
  cdp.on('Page.screencastFrame', onFrame);
  return {
    frames() { return buckets; },
    stop() { cdp.off('Page.screencastFrame', onFrame); },
  };
}

function sequenceFrames(raw, endHoldMs) {
  const frames = [];
  for (let i = 0; i < raw.length; i++) {
    const nextT = i + 1 < raw.length ? raw[i + 1].t : raw[i].t + endHoldMs;
    frames.push({ png: raw[i].png, delay_ms: Math.max(20, Math.round(nextT - raw[i].t)) });
  }
  return frames;
}

async function cmdRecord(opts) {
  const file = opts._[1];
  if (!file || !opts.out || opts.out === true) usage();
  const { scene, scenePath } = requireValidScene(file);
  const outDir = path.resolve(String(opts.out));
  fs.mkdirSync(outDir, { recursive: true });
  const pw = loadPlaywright(depsDir(opts));
  const manifest = {
    name: scene.name,
    scene: scenePath,
    url: scene.url,
    status: 'failed',
    gif: null,
    poster: null,
    last_frame: null,
    width: null,
    height: null,
    frames: 0,
    duration_ms: 0,
    bytes: 0,
    fps: scene.fps,
    scale: scene.scale,
    recorded_at: new Date().toISOString(),
    steps: [],
    error: null,
  };
  const { browser, context, page } = await openScene(pw, scene, { headed: Boolean(opts.headed) });
  const overlay = makeOverlay(page, scene);
  let capture = null;
  let cdp = null;
  let recordingStarted = 0;
  try {
    await page.goto(scene.url, { waitUntil: 'load' });
    await runSteps(page, scene, overlay, scene.setup, false, manifest.steps, 'setup');
    await page.waitForTimeout(300);
    await overlay.place(scene.viewport.width * 0.56, scene.viewport.height * 0.62);
    await page.waitForTimeout(250);

    cdp = await context.newCDPSession(page);
    capture = startCapture(cdp, scene.fps);
    await cdp.send('Page.startScreencast', {
      format: 'png',
      maxWidth: Math.round(scene.viewport.width * scene.scale),
      maxHeight: Math.round(scene.viewport.height * scene.scale),
      everyNthFrame: 1,
    });
    // Nudge the cursor one pixel so the compositor emits an opening frame of the settled page.
    await overlay.place(scene.viewport.width * 0.56 + 1, scene.viewport.height * 0.62);
    await page.waitForTimeout(350);
    recordingStarted = Date.now();

    await runSteps(page, scene, overlay, scene.steps, true, manifest.steps, 'record');
    await overlay.unhighlight();
    const recordedMs = Date.now() - recordingStarted;
    await page.waitForTimeout(Math.min(scene.end_hold_ms, 600));
    await cdp.send('Page.stopScreencast');
    await page.waitForTimeout(200);
    capture.stop();

    const raw = capture.frames();
    if (raw.length === 0) throw new Error('the screencast produced no frames');
    const sequenced = sequenceFrames(raw, scene.end_hold_ms);
    const result = framesToGif(sequenced);
    const gifPath = path.join(outDir, `${scene.name}.gif`);
    const posterPath = path.join(outDir, `${scene.name}.png`);
    const lastFramePath = path.join(outDir, `${scene.name}.last.png`);
    fs.writeFileSync(gifPath, result.gif);
    fs.writeFileSync(posterPath, raw[0].png);
    fs.writeFileSync(lastFramePath, raw[raw.length - 1].png);
    Object.assign(manifest, {
      gif: gifPath,
      poster: posterPath,
      last_frame: lastFramePath,
      width: result.width,
      height: result.height,
      frames: result.frames,
      duration_ms: result.duration_ms,
      bytes: result.gif.length,
      palette_size: result.palette_size,
      recorded_ms: recordedMs,
    });
    if (recordedMs > scene.max_seconds * 1000) {
      manifest.status = 'too_long';
      manifest.error = `recorded ${Math.round(recordedMs / 100) / 10}s of interaction, above max_seconds ${scene.max_seconds}; split the scene or raise max_seconds deliberately`;
    } else if (result.gif.length > 8 * 1024 * 1024) {
      manifest.status = 'too_large';
      manifest.error = `GIF is ${(result.gif.length / 1048576).toFixed(1)} MiB; lower scale, fps, or duration so the page stays light`;
    } else {
      manifest.status = 'ok';
    }
  } catch (error) {
    manifest.error = String(error.message || error).split('\n').slice(0, 3).join(' ');
    try {
      const raw = capture ? capture.frames() : [];
      if (raw.length > 0) {
        const partial = framesToGif(sequenceFrames(raw, scene.end_hold_ms));
        const partialPath = path.join(outDir, `${scene.name}.partial.gif`);
        fs.writeFileSync(partialPath, partial.gif);
        manifest.partial_gif = partialPath;
      }
      const shot = path.join(outDir, `${scene.name}.failed.png`);
      await page.screenshot({ path: shot }).catch(() => {});
      if (fs.existsSync(shot)) manifest.failure_screenshot = shot;
    } catch { /* best effort */ }
  } finally {
    await browser.close().catch(() => {});
  }
  const manifestPath = path.join(outDir, `${scene.name}.manifest.json`);
  manifest.manifest = manifestPath;
  fs.writeFileSync(manifestPath, JSON.stringify(manifest, null, 2) + '\n');
  printJson(manifest);
  process.exit(manifest.status === 'ok' ? 0 : 1);
}

// ---------------------------------------------------------------- snapshot, login, encode

const INTERACTIVE_ROLES = ['button', 'link', 'textbox', 'searchbox', 'combobox', 'checkbox', 'radio', 'switch', 'tab', 'menuitem', 'menuitemcheckbox', 'menuitemradio', 'option', 'slider', 'spinbutton'];

function suggestSelectors(aria) {
  const seen = new Set();
  const out = [];
  const pattern = new RegExp(`^\\s*-\\s+(${INTERACTIVE_ROLES.join('|')})\\s+"((?:[^"\\\\]|\\\\.)*)"`);
  for (const line of aria.split('\n')) {
    const match = pattern.exec(line);
    if (!match) continue;
    const name = match[2].replace(/\\"/g, '"');
    const selector = `role=${match[1]}[name="${name.replace(/"/g, '\\"')}"]`;
    if (seen.has(selector)) continue;
    seen.add(selector);
    out.push(selector);
  }
  return out;
}

async function cmdSnapshot(opts) {
  const file = opts._[1];
  if (!file || !opts.out || opts.out === true) usage();
  const { scene } = requireValidScene(file);
  const outDir = path.resolve(String(opts.out));
  fs.mkdirSync(outDir, { recursive: true });
  const pw = loadPlaywright(depsDir(opts));
  const { browser, page } = await openScene(pw, scene, { headed: Boolean(opts.headed) });
  const overlay = makeOverlay(page, scene);
  const steps = [];
  try {
    await page.goto(scene.url, { waitUntil: 'load' });
    await runSteps(page, scene, overlay, scene.setup, false, steps, 'setup');
    if (opts['after-steps']) await runSteps(page, scene, overlay, scene.steps, false, steps, 'steps');
    if (typeof opts.url === 'string') await page.goto(opts.url, { waitUntil: 'load' });
    await page.waitForTimeout(500);
    const shot = path.join(outDir, 'snapshot.png');
    await page.screenshot({ path: shot });
    const aria = await page.locator('body').ariaSnapshot();
    const ariaPath = path.join(outDir, 'snapshot.aria.yaml');
    fs.writeFileSync(ariaPath, aria + '\n');
    printJson({
      url: page.url(),
      title: await page.title(),
      screenshot: shot,
      aria_snapshot: ariaPath,
      suggested_selectors: suggestSelectors(aria).slice(0, 80),
    });
  } catch (error) {
    await browser.close().catch(() => {});
    fail(`snapshot failed: ${String(error.message || error).split('\n')[0]}`);
  }
  await browser.close();
}

function waitForEnter(prompt) {
  return new Promise((resolve) => {
    const rl = readline.createInterface({ input: process.stdin, output: process.stderr });
    rl.question(prompt, () => { rl.close(); resolve(); });
  });
}

async function cmdLogin(opts) {
  if (typeof opts.url !== 'string' || typeof opts.out !== 'string') usage();
  if (!/^https?:\/\//.test(opts.url)) fail('--url must start with http:// or https://');
  const outPath = path.resolve(opts.out);
  const pw = loadPlaywright(depsDir(opts));
  const browser = await pw.chromium.launch({ headless: false });
  const context = await browser.newContext();
  const page = await context.newPage();
  await page.goto(opts.url, { waitUntil: 'load' });
  await waitForEnter(`Log in inside the browser window, then press Enter here to save the session to ${outPath} ... `);
  fs.mkdirSync(path.dirname(outPath), { recursive: true });
  await context.storageState({ path: outPath, indexedDB: true });
  await browser.close();
  printJson({ storage_state: outPath, note: 'This file holds session cookies and storage. Keep it out of version control and out of the output bundle.' });
}

function cmdEncode(opts) {
  if (typeof opts.frames !== 'string' || typeof opts.out !== 'string') usage();
  const dir = path.resolve(opts.frames);
  const files = fs.readdirSync(dir).filter((f) => f.toLowerCase().endsWith('.png')).sort();
  if (files.length === 0) fail(`no PNG frames in ${dir}`);
  let delay;
  if (opts['delay-ms'] !== undefined) {
    delay = Number(opts['delay-ms']);
    if (!isInt(delay, 20, 10000)) fail('--delay-ms must be an integer from 20 to 10000');
  } else {
    const fps = opts.fps === undefined ? DEFAULTS.fps : Number(opts.fps);
    if (!isNum(fps, 1, 50)) fail('--fps must be a number from 1 to 50');
    delay = Math.round(1000 / fps);
  }
  const frames = files.map((f) => ({ png: fs.readFileSync(path.join(dir, f)), delay_ms: delay }));
  const result = framesToGif(frames);
  const outPath = path.resolve(opts.out);
  fs.mkdirSync(path.dirname(outPath), { recursive: true });
  fs.writeFileSync(outPath, result.gif);
  printJson({
    gif: outPath,
    width: result.width,
    height: result.height,
    input_frames: files.length,
    frames: result.frames,
    skipped_frames: result.skipped_frames,
    duration_ms: result.duration_ms,
    bytes: result.gif.length,
    palette_size: result.palette_size,
  });
}

// ---------------------------------------------------------------- check, sheet

const ARIA_INTERACTIVE = new RegExp(`^\\s*-\\s+(${INTERACTIVE_ROLES.join('|')}|tab|heading)\\s+("(?:[^"\\\\]|\\\\.)*")`);

function interactiveCounts(aria) {
  const out = new Map();
  for (const line of aria.split('\n')) {
    const match = ARIA_INTERACTIVE.exec(line);
    if (match) {
      const key = `${match[1]} ${match[2]}`;
      out.set(key, (out.get(key) || 0) + 1);
    }
  }
  return out;
}

// Interactive controls are compared as a multiset, so a second "Delete" button on a screen that
// already had one is reported; the entry carries the count change when either side had several.
function diffAria(baselineText, currentText, baselinePath) {
  const before = interactiveCounts(baselineText);
  const after = interactiveCounts(currentText);
  const describe = (key, from, to) => (from === 0 || to === 0) && Math.max(from, to) === 1 ? key : `${key} (${from} -> ${to})`;
  const added = [];
  const removed = [];
  for (const key of new Set([...before.keys(), ...after.keys()])) {
    const from = before.get(key) || 0;
    const to = after.get(key) || 0;
    if (to > from) added.push(describe(key, from, to));
    else if (from > to) removed.push(describe(key, from, to));
  }
  added.sort();
  removed.sort();
  const beforeLines = new Set(baselineText.split('\n').map((l) => l.trim()).filter(Boolean));
  const afterLines = new Set(currentText.split('\n').map((l) => l.trim()).filter(Boolean));
  let changed = 0;
  for (const l of afterLines) if (!beforeLines.has(l)) changed++;
  for (const l of beforeLines) if (!afterLines.has(l)) changed++;
  return { path: baselinePath, added, removed, changed_lines: changed };
}

async function cmdCheck(opts) {
  const file = opts._[1];
  if (!file || !opts.out || opts.out === true) usage();
  const { scene, scenePath } = requireValidScene(file);
  const outDir = path.resolve(String(opts.out));
  fs.mkdirSync(outDir, { recursive: true });
  let baselineText = null;
  if (typeof opts.baseline === 'string') {
    try { baselineText = fs.readFileSync(opts.baseline, 'utf8'); } catch (error) { fail(`cannot read baseline ${opts.baseline}: ${error.message}`); }
  }
  const pw = loadPlaywright(depsDir(opts));
  const report = {
    name: scene.name,
    scene: scenePath,
    url: scene.url,
    status: 'ok',
    checked_at: new Date().toISOString(),
    aria_snapshot: null,
    baseline: null,
    steps: [],
    error: null,
  };
  const { browser, page } = await openScene(pw, scene, { headed: Boolean(opts.headed) });
  const overlay = makeOverlay(page, { ...scene, cursor: false, captions: false });
  const markRest = (from, resolution) => {
    for (let i = from; i < scene.steps.length; i++) {
      report.steps.push({ index: i, action: scene.steps[i].action, selector: scene.steps[i].selector, resolution });
    }
  };
  try {
    await page.goto(scene.url, { waitUntil: 'load' });
    await runSteps(page, scene, overlay, scene.setup, false, [], 'setup');
    await page.waitForTimeout(500);
    const aria = await page.locator('body').ariaSnapshot();
    const ariaPath = path.join(outDir, `${scene.name}.aria.yaml`);
    fs.writeFileSync(ariaPath, aria + '\n');
    report.aria_snapshot = ariaPath;
    if (baselineText !== null) {
      report.baseline = diffAria(baselineText, aria, path.resolve(opts.baseline));
      if (report.baseline.added.length || report.baseline.removed.length) report.status = 'drift';
    }
    for (let i = 0; i < scene.steps.length; i++) {
      const step = scene.steps[i];
      const entry = { index: i, action: step.action, selector: step.selector, resolution: 'n/a' };
      if (step.selector && step.action !== 'wait') {
        // count() does not auto-wait, and check skips settle_ms, so give the selector the same
        // chance record would: up to timeout_ms for the element to attach after the last action.
        await waitTarget(page, step).waitFor({ state: 'attached', timeout: scene.timeout_ms }).catch(() => {});
        const matches = await page.locator(step.selector).count();
        entry.matches = matches;
        if (matches === 0) entry.resolution = 'missing';
        else if (matches > 1 && step.nth === undefined) entry.resolution = 'ambiguous';
        else entry.resolution = (await locate(page, step).isVisible()) ? 'ok' : 'hidden';
      }
      if (entry.resolution === 'missing' || entry.resolution === 'ambiguous') {
        entry.error = entry.resolution === 'missing'
          ? 'no element matches this selector on the current screen'
          : `${entry.matches} elements match; add nth or a more specific selector`;
        report.steps.push(entry);
        report.status = 'broken';
        markRest(i + 1, 'not_reached');
        break;
      }
      try {
        await runStep(page, scene, overlay, step, false);
      } catch (error) {
        entry.resolution = 'failed';
        entry.error = String(error.message || error).split('\n').slice(0, 2).join(' ');
        report.steps.push(entry);
        report.status = 'broken';
        markRest(i + 1, 'not_reached');
        break;
      }
      report.steps.push(entry);
    }
  } catch (error) {
    report.status = 'broken';
    report.error = String(error.message || error).split('\n').slice(0, 3).join(' ');
  } finally {
    await browser.close().catch(() => {});
  }
  const reportPath = path.join(outDir, `${scene.name}.check.json`);
  report.report = reportPath;
  fs.writeFileSync(reportPath, JSON.stringify(report, null, 2) + '\n');
  printJson(report);
  process.exit(report.status === 'broken' ? 1 : 0);
}

async function cmdSheet(opts) {
  if (typeof opts.clips !== 'string' || typeof opts.out !== 'string') usage();
  const dir = path.resolve(opts.clips);
  const columns = opts.columns === undefined ? 2 : Number(opts.columns);
  if (!isInt(columns, 1, 6)) fail('--columns must be an integer from 1 to 6');
  const files = fs.readdirSync(dir).filter((f) => f.endsWith('.last.png')).sort();
  if (files.length === 0) fail(`no <name>.last.png frames in ${dir}`);
  const pw = loadPlaywright(depsDir(opts));
  const cellWidth = 600;
  const cells = files.map((f) => {
    const data = fs.readFileSync(path.join(dir, f)).toString('base64');
    const label = f.replace(/\.last\.png$/, '');
    return `<figure style="margin:0"><img alt="${label}" src="data:image/png;base64,${data}" style="width:${cellWidth}px;display:block;border:1px solid #ccc"><figcaption style="font:600 14px sans-serif;margin:4px 0 10px">${label}</figcaption></figure>`;
  }).join('');
  const html = `<!doctype html><html><body style="margin:10px;background:#fff"><div style="display:grid;grid-template-columns:repeat(${columns},${cellWidth}px);gap:12px">${cells}</div></body></html>`;
  const browser = await pw.chromium.launch();
  try {
    const page = await browser.newPage({ viewport: { width: columns * (cellWidth + 12) + 20, height: 800 } });
    await page.setContent(html);
    const outPath = path.resolve(opts.out);
    fs.mkdirSync(path.dirname(outPath), { recursive: true });
    await page.screenshot({ path: outPath, fullPage: true });
    printJson({ sheet: outPath, frames: files.length, columns });
  } finally {
    await browser.close().catch(() => {});
  }
}

// ---------------------------------------------------------------- main

async function main() {
  const opts = parseArgs(process.argv.slice(2));
  const command = opts._[0];
  if (!command || opts.help) usage(command ? 2 : 0);
  switch (command) {
    case 'setup': return cmdSetup(opts);
    case 'doctor': return cmdDoctor(opts);
    case 'validate': return cmdValidate(opts);
    case 'snapshot': return cmdSnapshot(opts);
    case 'record': return cmdRecord(opts);
    case 'encode': return cmdEncode(opts);
    case 'login': return cmdLogin(opts);
    case 'check': return cmdCheck(opts);
    case 'sheet': return cmdSheet(opts);
    default: return usage();
  }
}

main().catch((error) => fail(String(error && error.stack ? error.stack : error)));
