const puppeteer = require('puppeteer-core');
const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const PLAN = '/Users/robertdufala/Desktop/CihloMat_UGC_Videos/Kalkulacka_Rozpoctu/test_podorysy/plan_49681696.jpg';
const URL = 'http://localhost:5005';

async function shot(page, file){ await page.screenshot({path:'/tmp/'+file, fullPage:true}); console.log('  ->',file); }

async function analyzeFlow(page){
  await page.goto(URL,{waitUntil:'networkidle0'});
  const input = await page.$('input[type=file]');
  await input.uploadFile(PLAN);
  await new Promise(r=>setTimeout(r,400));
  await page.click('button.btn.full');
  await page.waitForSelector('.hero',{timeout:90000});
  await new Promise(r=>setTimeout(r,800));
}

(async()=>{
  const browser = await puppeteer.launch({executablePath:CHROME, args:['--no-sandbox']});
  // 1) MOBIL landing
  const m = await browser.newPage();
  await m.setViewport({width:390,height:844,deviceScaleFactor:2,isMobile:true,hasTouch:true});
  await m.goto(URL,{waitUntil:'networkidle0'});
  await shot(m,'r_land_mobile.png');
  console.log('mobil landing ok');
  // 2) MOBIL výsledok (upload)
  await analyzeFlow(m);
  await shot(m,'r_result_mobile.png');
  console.log('mobil výsledok ok');
  await m.close();
  // 3) DESKTOP výsledok
  const d = await browser.newPage();
  await d.setViewport({width:1280,height:900,deviceScaleFactor:1});
  await analyzeFlow(d);
  await shot(d,'r_result_desktop.png');
  console.log('desktop výsledok ok');
  await browser.close();
})().catch(e=>{console.error('CHYBA:',e.message);process.exit(1)});
