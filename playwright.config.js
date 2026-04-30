module.exports = {
  testDir: './qa/tests',
  testMatch: ['**/*.spec.js', '**/*.e2e.spec.js'],
  timeout: 60000,
  use: {
    baseURL: 'http://localhost:3000',
    headless: false,
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    trace: 'retain-on-failure'
  },
  reporter: [
    ['list'],
    ['html', { outputFolder: 'qa/reports/html' }],
    ['json', { outputFile: 'qa/reports/results.json' }]
  ]
};
