// App-memory experiment, the browser side: one scripted visitor uses the dashboard while
// measure/app_memory.py samples docker stats. 8 searches (migraine, cancer, epilepsy and 5 more),
// each with the drill-down on the top ingredient, and the whole list twice.
// Usage: node measure/app_memory.js <port> <events.csv>   (needs playwright: require('playwright'))
const { chromium } = require('playwright');
const fs = require('fs');
const [port, eventsFile] = process.argv.slice(2);
const CONDITIONS = ['migraine', 'cancer', 'epilepsy', 'hypertension', 'asthma', 'acne',
                    'type 2 diabetes', 'pain'];
const t0 = Date.now();
const events = ['t_ms,pass,condition,event,detail'];
const mark = (pass, condition, event, detail = '') => {
  events.push(`${Date.now() - t0},${pass},"${condition}",${event},"${String(detail).replace(/"/g, "'")}"`);
};

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
  const errors = [];
  page.on('pageerror', e => errors.push('pageerror: ' + e.message));
  // Streamlit shows its "running" widget while the script runs; wait until it is gone.
  const settle = async () => { await page.waitForTimeout(300);
    await page.locator('[data-testid="stStatusWidget"]').waitFor({ state: 'hidden', timeout: 60000 }).catch(() => {}); };
  const caption = async re => (await page.getByText(re).first().innerText()).trim();

  mark(0, '', 'open');
  await page.goto(`http://localhost:${port}`, { waitUntil: 'networkidle' });
  await page.getByText(/query time: .* \(drugs_for_condition\)/).waitFor({ timeout: 60000 });
  mark(0, 'migraine', 'first_page', await caption(/query time: .* \(drugs_for_condition\)/));
  for (const pass of [1, 2]) {
    for (const condition of CONDITIONS) {
      // type the condition, as a visitor would
      const input = page.locator('[data-testid="stTextInput"] input');
      await input.click(); await page.keyboard.press('Control+A'); await page.keyboard.press('Backspace');
      mark(pass, condition, 'search_start');
      await page.keyboard.type(condition, { delay: 20 });
      await page.keyboard.press('Enter');
      await settle();
      await page.getByText(new RegExp(`named for “${condition}”`)).waitFor({ timeout: 60000 });
      mark(pass, condition, 'search_done', await caption(/query time: .* \(drugs_for_condition\)/));
      // the drill-down: open the ingredient box and pick the first (top) ingredient
      await page.getByText('What the labels say').scrollIntoViewIfNeeded();
      const box = page.locator('[data-testid="stSelectbox"]').first();
      await box.click(); await page.waitForTimeout(300);
      const top = page.getByRole('option').first();
      const name = (await top.innerText()).trim();
      await top.click();
      await settle();
      mark(pass, condition, 'drilldown_done', `${name}: ${await caption(/labels_for_drug/)}`);
      await page.waitForTimeout(1000);                 // a short look at the page, as a person would
    }
  }
  const exceptions = await page.locator('[data-testid="stException"]').count();
  await browser.close();
  mark(0, '', 'closed', `exceptions on the page=${exceptions}; page errors=${errors.length}`);
  fs.writeFileSync(eventsFile, events.join('\n') + '\n');
  console.log(JSON.stringify({ seconds: (Date.now() - t0) / 1000, exceptions, errors }));
})();
