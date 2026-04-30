const { test, expect } = require('@playwright/test');

test('StealthRole local smoke test', async ({ page }) => {
  const errors = [];

  page.on('console', msg => {
    if (msg.type() === 'error') {
      errors.push(`Console error: ${msg.text()}`);
    }
  });

  page.on('pageerror', err => {
    errors.push(`Page error: ${err.message}`);
  });

  await page.goto('http://localhost:3000', { waitUntil: 'domcontentloaded' });

  await page.screenshot({ path: 'qa/screenshots/home.png', fullPage: true });

  const title = await page.title();
  console.log('PAGE TITLE:', title);

  const bodyText = await page.locator('body').innerText();

  if (bodyText.length < 50) {
    errors.push('Page body is almost empty.');
  }

  const badTexts = [
    'undefined',
    'null',
    'NaN',
    '404',
    '500',
    'Something went wrong'
  ];

  for (const text of badTexts) {
    if (bodyText.includes(text)) {
      errors.push(`Suspicious text found: ${text}`);
    }
  }

  if (errors.length > 0) {
    throw new Error(errors.join('\n'));
  }

  await expect(page.locator('body')).toBeVisible();
});
