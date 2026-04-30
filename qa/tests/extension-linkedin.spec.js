/**
 * StealthRole Chrome extension — real LinkedIn smoke (no mocks, not skipped when logged in).
 *
 * Prerequisites:
 *   - Log into LinkedIn once using the persistent profile (browser is non-headless).
 *     Directory: qa/chrome-profile (auto-created; session is local-only, gitignored).
 *   - Extension path: repo / extension
 *
 * Run: npm run test:playwright:extension
 *
 * Optional env:
 *   LINKEDIN_QA_PROFILE_URL   (default: Satya Nadella public profile)
 *   LINKEDIN_QA_CONNECTIONS_URL
 *   PW_CHROME_CHANNEL         (default: chrome; use chromium if Chrome is not installed)
 *
 * Output: qa/reports/raw-findings.json (full diagnostics each run)
 */

const fs = require("fs");
const path = require("path");
const { test, expect, chromium } = require("@playwright/test");

const REPO_ROOT = path.resolve(__dirname, "../..");
const EXTENSION_PATH = path.join(REPO_ROOT, "extension");
const USER_DATA_DIR = path.join(REPO_ROOT, "qa", "chrome-profile");
const REPORT_PATH = path.join(REPO_ROOT, "qa", "reports", "raw-findings.json");

const DEFAULT_PROFILE_URL =
  process.env.LINKEDIN_QA_PROFILE_URL ||
  "https://www.linkedin.com/in/satyanadella/";
const DEFAULT_CONNECTIONS_URL =
  process.env.LINKEDIN_QA_CONNECTIONS_URL ||
  "https://www.linkedin.com/mynetwork/invite-connect/connections/";

/** Backend / app API we assert on (exclude LinkedIn voyager noise). */
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
    if (msg.type() === "error") {
      bucket.consoleErrors.push(msg.text());
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
      if (ct.includes("json")) {
        bodySnippet = (await res.text()).slice(0, 800);
      }
    } catch {
      /* ignore */
    }
    bucket.apiHttpErrors.push({
      url,
      status,
      statusText: res.statusText(),
      bodySnippet: bodySnippet || undefined,
    });
  });
  page.on("requestfailed", (req) => {
    const url = req.url();
    if (!isStealthRoleBackendUrl(url)) return;
    bucket.requestFailed.push({
      url,
      error: req.failure()?.errorText || "unknown",
    });
  });
}

function emptyBucket() {
  return {
    consoleErrors: [],
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
  extensionPath: EXTENSION_PATH,
  userDataDir: USER_DATA_DIR,
  profileUrl: DEFAULT_PROFILE_URL,
  connectionsUrl: DEFAULT_CONNECTIONS_URL,
  startupError: null,
  tests: [],
};

function writeReport() {
  findings.summary = {
    allPassed:
      findings.tests.length > 0 &&
      findings.tests.every((t) => t.passed === true),
    failedTestNames: findings.tests.filter((t) => !t.passed).map((t) => t.name),
  };
  fs.mkdirSync(path.dirname(REPORT_PATH), { recursive: true });
  fs.writeFileSync(REPORT_PATH, JSON.stringify(findings, null, 2), "utf8");
}

let context;

test.describe.configure({ mode: "serial" });
test.describe("StealthRole extension on real LinkedIn", () => {
  test.setTimeout(240000);

  test.beforeAll(async () => {
    try {
      fs.mkdirSync(USER_DATA_DIR, { recursive: true });
      if (!fs.existsSync(path.join(EXTENSION_PATH, "manifest.json"))) {
        throw new Error(`Extension not found at ${EXTENSION_PATH} (manifest.json missing)`);
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

  test("profile: #sr-overlay-btn shows Save Contact, click, record diagnostics", async () => {
    const bucket = emptyBucket();
    const page = await context.newPage();
    attachDiagnostics(page, bucket);

    const result = {
      name: "linkedin_profile_save_contact",
      profileUrl: DEFAULT_PROFILE_URL,
      expectedUi: "#sr-overlay-btn text ~ /Save Contact/i (see extension labels.profile)",
      observedLabel: null,
      thrown: null,
      diagnostics: null,
      passed: false,
    };

    try {
      await page.goto(DEFAULT_PROFILE_URL, {
        timeout: 180000,
        waitUntil: "domcontentloaded",
      });

      const btn = page.locator("#sr-overlay-btn");
      await expect(btn).toBeVisible({ timeout: 120000 });

      result.observedLabel = (await btn.innerText()).trim();
      await expect(btn).toHaveText(/save contact/i);

      await btn.click();
      await sleep(10000);

      const backendOk =
        bucket.apiHttpErrors.length === 0 && bucket.requestFailed.length === 0;
      const noPageCrash = bucket.pageErrors.length === 0;
      result.passed = noPageCrash && backendOk;
    } catch (e) {
      result.thrown = String(e && e.message ? e.message : e);
      result.passed = false;
    } finally {
      result.diagnostics = { ...bucket };
      findings.tests.push(result);
      writeReport();
      await page.close();
    }

    expect(result.thrown).toBeNull();
    expect(
      bucket.pageErrors,
      `Page errors:\n${bucket.pageErrors.join("\n")}`
    ).toEqual([]);
    expect(
      bucket.apiHttpErrors,
      `API HTTP errors:\n${JSON.stringify(bucket.apiHttpErrors, null, 2)}`
    ).toEqual([]);
    expect(
      bucket.requestFailed,
      `Failed requests:\n${JSON.stringify(bucket.requestFailed, null, 2)}`
    ).toEqual([]);
  });

  test("connections: Sync Connections control; click (import path)", async () => {
    const bucket = emptyBucket();
    const page = await context.newPage();
    attachDiagnostics(page, bucket);

    const result = {
      name: "linkedin_connections_sync",
      connectionsUrl: DEFAULT_CONNECTIONS_URL,
      observedPrimaryLabel: null,
      observedSecondaryLabel: null,
      note: null,
      thrown: null,
      diagnostics: null,
      passed: false,
    };

    try {
      await page.goto(DEFAULT_CONNECTIONS_URL, {
        timeout: 180000,
        waitUntil: "domcontentloaded",
      });

      const primary = page.locator("#sr-overlay-btn");
      await expect(primary).toBeVisible({ timeout: 120000 });
      result.observedPrimaryLabel = (await primary.innerText()).trim();
      await expect(primary).toHaveText(/sync connections/i);

      const syncExtra = page.locator("#sr-sync-btn");
      if (await syncExtra.isVisible().catch(() => false)) {
        result.observedSecondaryLabel = (await syncExtra.innerText()).trim();
        result.note = "Clicked primary #sr-overlay-btn (Sync Connections).";
        await primary.click();
      } else {
        result.note =
          "Full Sync button not present; same click triggers manual import scrape.";
        await primary.click();
      }

      await sleep(8000);

      const backendOk =
        bucket.apiHttpErrors.length === 0 && bucket.requestFailed.length === 0;
      const noPageCrash = bucket.pageErrors.length === 0;
      result.passed = noPageCrash && backendOk;
    } catch (e) {
      result.thrown = String(e && e.message ? e.message : e);
      result.passed = false;
    } finally {
      result.diagnostics = { ...bucket };
      findings.tests.push(result);
      writeReport();
      await page.close();
    }

    expect(result.thrown).toBeNull();
    expect(
      bucket.pageErrors,
      `Page errors:\n${bucket.pageErrors.join("\n")}`
    ).toEqual([]);
    expect(bucket.apiHttpErrors).toEqual([]);
    expect(bucket.requestFailed).toEqual([]);
  });
});
