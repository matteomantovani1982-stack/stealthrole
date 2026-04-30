/**
 * Full StealthRole extension E2E on real LinkedIn (no mocks, no skipped tests).
 *
 * Asserts DOM IDs expected by QA:
 *   - Profile: #sr-overlay-btn (Save Contact)
 *   - Connections: #sr-overlay-btn (Sync Connections) + #sr-sync-btn (Full Sync)
 *
 * Run: npx playwright test qa/tests/full-stealthrole.ext.e2e.spec.js
 *
 * Requires: logged-in LinkedIn session in qa/chrome-profile; extension at repo/extension.
 */

const fs = require("fs");
const path = require("path");
const { test, expect, chromium } = require("@playwright/test");

const REPO_ROOT = path.resolve(__dirname, "../..");
const EXTENSION_PATH = path.join(REPO_ROOT, "extension");
const USER_DATA_DIR = path.join(REPO_ROOT, "qa", "chrome-profile");
const REPORT_PATH = path.join(REPO_ROOT, "qa", "reports", "raw-findings.json");

const PROFILE_URL =
  process.env.LINKEDIN_QA_PROFILE_URL ||
  "https://www.linkedin.com/in/satyanadella/";
const CONNECTIONS_URL =
  process.env.LINKEDIN_QA_CONNECTIONS_URL ||
  "https://www.linkedin.com/mynetwork/invite-connect/connections/";

function isStealthRoleBackendUrl(url) {
  try {
    const u = new URL(url);
    if (u.hostname === "localhost" || u.hostname === "127.0.0.1") return true;
    if (u.hostname.endsWith("stealthrole.com")) return true;
    return false;
  } catch {
    return false;
  }
}

function attachDiagnostics(page, bucket) {
  page.on("console", (msg) => {
    const t = msg.type();
    const text = msg.text();
    if (t === "error") bucket.consoleErrors.push(text);
    if (text.includes("[StealthRole") || text.includes("[SR]")) {
      bucket.srConsole.push(`[${t}] ${text}`);
    }
  });
  page.on("pageerror", (err) => {
    bucket.pageErrors.push(err.message || String(err));
  });
  page.on("response", async (res) => {
    const url = res.url();
    if (!isStealthRoleBackendUrl(url)) return;
    const status = res.status();
    if (status < 400) return;
    let bodySnippet = "";
    try {
      const ct = (res.headers()["content-type"] || "").toLowerCase();
      if (ct.includes("json")) bodySnippet = (await res.text()).slice(0, 800);
    } catch {
      /* ignore */
    }
    bucket.apiHttpErrors.push({ url, status, statusText: res.statusText(), bodySnippet: bodySnippet || undefined });
  });
  page.on("requestfailed", (req) => {
    const url = req.url();
    if (!isStealthRoleBackendUrl(url)) return;
    bucket.requestFailed.push({ url, error: req.failure()?.errorText || "unknown" });
  });
}

function emptyBucket() {
  return {
    consoleErrors: [],
    srConsole: [],
    pageErrors: [],
    apiHttpErrors: [],
    requestFailed: [],
  };
}

async function sleep(ms) {
  await new Promise((r) => setTimeout(r, ms));
}

const findings = {
  runAt: new Date().toISOString(),
  suite: "full-stealthrole.ext.e2e",
  extensionPath: EXTENSION_PATH,
  manifestJsGlob: "extension/src/*.js (source paths in manifest, not dist/)",
  userDataDir: USER_DATA_DIR,
  profileUrl: PROFILE_URL,
  connectionsUrl: CONNECTIONS_URL,
  startupError: null,
  tests: [],
};

function writeReport() {
  findings.summary = {
    allPassed:
      findings.tests.length > 0 && findings.tests.every((t) => t.passed === true),
    failedTestNames: findings.tests.filter((t) => !t.passed).map((t) => t.name),
  };
  fs.mkdirSync(path.dirname(REPORT_PATH), { recursive: true });
  fs.writeFileSync(REPORT_PATH, JSON.stringify(findings, null, 2), "utf8");
}

let context;

test.describe.configure({ mode: "serial" });
test.describe("Full StealthRole extension E2E (LinkedIn injection)", () => {
  test.setTimeout(300000);

  test.beforeAll(async () => {
    try {
      fs.mkdirSync(USER_DATA_DIR, { recursive: true });
      const manifestPath = path.join(EXTENSION_PATH, "manifest.json");
      if (!fs.existsSync(manifestPath)) {
        throw new Error(`Extension manifest missing: ${manifestPath}`);
      }
      const channel = process.env.PW_CHROME_CHANNEL || "chrome";
      context = await chromium.launchPersistentContext(USER_DATA_DIR, {
        channel,
        headless: false,
        args: [
          `--disable-extensions-except=${EXTENSION_PATH}`,
          `--load-extension=${EXTENSION_PATH}`,
        ],
        ignoreDefaultArgs: ["--disable-extensions"],
      });
    } catch (e) {
      findings.startupError = String(e);
      writeReport();
      throw e;
    }
  }, { timeout: 180000 });

  test.afterAll(async () => {
    writeReport();
    if (context) await context.close();
  });

  test("LinkedIn profile: #sr-overlay-btn visible with Save Contact", async () => {
    const bucket = emptyBucket();
    const page = await context.newPage();
    attachDiagnostics(page, bucket);

    const result = {
      name: "linkedin_profile_overlay",
      passed: false,
      thrown: null,
      observedHost: null,
      diagnostics: null,
    };

    try {
      await page.goto(PROFILE_URL, { timeout: 180000, waitUntil: "domcontentloaded" });
      result.observedHost = await page.evaluate(() => window.location.hostname);

      await page.waitForSelector("#sr-overlay-btn", {
        state: "visible",
        timeout: 120000,
      });

      const btn = page.locator("#sr-overlay-btn");
      await expect(btn).toBeVisible();
      await expect(btn).toHaveAttribute("id", "sr-overlay-btn");
      await expect(btn).toHaveText(/save contact/i);

      result.passed =
        bucket.pageErrors.length === 0 &&
        bucket.apiHttpErrors.length === 0 &&
        bucket.requestFailed.length === 0;
    } catch (e) {
      result.thrown = String(e?.message || e);
      result.passed = false;
    } finally {
      result.diagnostics = { ...bucket };
      findings.tests.push(result);
      writeReport();
      await page.close();
    }

    expect(result.thrown).toBeNull();
    expect(bucket.pageErrors, bucket.pageErrors.join("\n")).toEqual([]);
    expect(bucket.apiHttpErrors).toEqual([]);
    expect(bucket.requestFailed).toEqual([]);
  });

  test("LinkedIn connections: #sr-overlay-btn + #sr-sync-btn", async () => {
    const bucket = emptyBucket();
    const page = await context.newPage();
    attachDiagnostics(page, bucket);

    const result = {
      name: "linkedin_connections_overlay",
      passed: false,
      thrown: null,
      observedHost: null,
      diagnostics: null,
    };

    try {
      await page.goto(CONNECTIONS_URL, { timeout: 180000, waitUntil: "domcontentloaded" });
      result.observedHost = await page.evaluate(() => window.location.hostname);

      await page.waitForSelector("#sr-overlay-btn", {
        state: "visible",
        timeout: 120000,
      });

      const primary = page.locator("#sr-overlay-btn");
      await expect(primary).toBeVisible();
      await expect(primary).toHaveAttribute("id", "sr-overlay-btn");
      await expect(primary).toHaveText(/sync connections/i);

      await page.waitForSelector("#sr-sync-btn", {
        state: "visible",
        timeout: 120000,
      });
      const sync = page.locator("#sr-sync-btn");
      await expect(sync).toBeVisible();
      await expect(sync).toHaveAttribute("id", "sr-sync-btn");

      await sleep(2000);
      result.passed =
        bucket.pageErrors.length === 0 &&
        bucket.apiHttpErrors.length === 0 &&
        bucket.requestFailed.length === 0;
    } catch (e) {
      result.thrown = String(e?.message || e);
      result.passed = false;
    } finally {
      result.diagnostics = { ...bucket };
      findings.tests.push(result);
      writeReport();
      await page.close();
    }

    expect(result.thrown).toBeNull();
    expect(bucket.pageErrors, bucket.pageErrors.join("\n")).toEqual([]);
    expect(bucket.apiHttpErrors).toEqual([]);
    expect(bucket.requestFailed).toEqual([]);
  });
});
