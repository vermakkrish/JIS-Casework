import { chromium } from 'playwright';
import AxeBuilder from '@axe-core/playwright';
import assert from 'node:assert/strict';
import { readFileSync, mkdirSync, writeFileSync } from 'node:fs';
import { randomBytes } from 'node:crypto';

const base=process.env.BASE_URL||'http://127.0.0.1:8000';
const password=process.env.DEMO_PASSWORD||JSON.parse(readFileSync('private/demo-access.json')).password;
const evidence='docs/evidence'; mkdirSync(evidence,{recursive:true});
const results=[];const errors=[];
const browser=await chromium.launch({channel:process.env.BROWSER_CHANNEL||'msedge',headless:true});
const context=await browser.newContext({viewport:{width:1440,height:1000}});
const page=await context.newPage();
page.on('pageerror',e=>errors.push(e.message));
async function passed(id,description){results.push({id,description,status:'PASS'});console.log(`${id} PASS ${description}`)}
async function visible(text){await page.getByText(text,{exact:false}).first().waitFor({state:'visible'});}
async function login(role){
  await page.goto(base+'/login/');
  await page.getByLabel('Email address').fill(`${role}@jis.example.test`);
  await page.getByLabel('Password',{exact:false}).fill(password);
  await page.getByRole('button',{name:'Sign in to Casework'}).click();
  await page.getByRole('heading',{name:'A clear view of your day.'}).waitFor();
}
async function logout(){await page.getByRole('button',{name:'Sign out'}).click();await page.getByRole('heading',{name:'Welcome back.'}).waitFor();}
async function audit(name){
  const result=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();
  writeFileSync(`${evidence}/accessibility-${name}.json`,JSON.stringify(result.violations,null,2));
  assert.equal(result.violations.length,0,`${name}: ${result.violations.map(v=>v.id+': '+v.nodes.map(n=>n.target).join(',')).join('; ')}`);
}
const date=new Date();date.setUTCDate(date.getUTCDate()+14);while([0,6].includes(date.getUTCDay()))date.setUTCDate(date.getUTCDate()+1);
const day=date.toISOString().slice(0,10);
const unique=Date.now();const title=`E2E Willow v. Cedar ${unique}`;
try{
  await page.goto(base+'/login/');await page.screenshot({path:`${evidence}/login-desktop.png`,fullPage:true});await audit('login');
  await login('registrar');await page.screenshot({path:`${evidence}/registrar-desktop.png`,fullPage:true});await audit('overview');
  await passed('UI01','Registrar sign-in and data-backed overview');
  await page.getByRole('link',{name:'+ Register case'}).click();
  await page.getByLabel('Case title').fill(title);
  await page.getByLabel('Case type').selectOption('CIVIL');
  await page.getByLabel('Claimant / initiating party').fill('Fictional Willow Studio');
  await page.getByLabel('Respondent / defendant').fill('Fictional Cedar Works');
  await page.getByLabel('Case description').fill('Fictional browser acceptance case; no real proceeding or legal claim.');
  await page.getByLabel('Assigned Judge').selectOption({label:'Mira Dev'});
  await page.getByLabel('Rohan Vale').check();
  await page.getByRole('button',{name:'Register case'}).click();
  await visible('Case registered successfully');const caseURL=page.url();
  const cin=(await page.locator('.case-heading .eyebrow').innerText()).match(/JIS-\d{4}-[A-F0-9]{12}/)[0];
  await passed('UI02','R1 registration displays a persisted unique CIN');
  await page.getByRole('link',{name:'+ Schedule hearing'}).click();
  await page.getByLabel('Hearing date').fill(day);await page.getByLabel('Hearing date').press('Tab');
  await visible('available slot');await page.getByLabel('One-hour slot').selectOption('14:00');
  await page.getByRole('button',{name:'Save hearing'}).click();await visible('Hearing scheduled.');
  await page.getByRole('link',{name:'Reschedule',exact:true}).click();
  await page.getByLabel('Hearing date').fill(day);await page.getByLabel('Hearing date').press('Tab');await visible('available slot');
  await page.getByLabel('One-hour slot').selectOption('15:00');await page.getByLabel('Reason for rescheduling').fill('Fictional participant requested a later slot.');
  await page.getByRole('button',{name:'Confirm reschedule'}).click();await visible('Previous schedule retained.');
  await page.getByRole('link',{name:'Adjourn hearing',exact:true}).click();await page.getByLabel('Reason for adjournment').fill('Fictional additional preparation is needed.');
  await page.getByRole('button',{name:'Confirm adjournment'}).click();await visible('Hearing adjourned.');
  await page.locator('details.history summary').click();await visible('Fictional participant requested a later slot.');
  await passed('UI03','R2/R3 schedule, reschedule, adjourn and visible change history');
  await page.getByRole('link',{name:'Update assignments'}).click();
  await page.getByLabel('Reason',{exact:false}).fill('Confirmed the fictional evaluation team.');
  await page.getByRole('button',{name:'Save assignments'}).click();await visible('Assignments updated.');
  await page.screenshot({path:`${evidence}/case-desktop.png`,fullPage:true});await audit('case');
  await page.setViewportSize({width:390,height:844});await page.screenshot({path:`${evidence}/case-mobile.png`,fullPage:true});await audit('case-mobile');
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'Mobile page overflows viewport');
  await page.goto(base+'/');await page.screenshot({path:`${evidence}/registrar-mobile.png`,fullPage:true});
  await page.setViewportSize({width:1440,height:1000});
  await page.getByRole('link',{name:'People & access'}).click();await page.getByRole('link',{name:'+ Create account'}).click();
  const accountEmail=`browser-${unique}@example.test`;const newPassword=randomBytes(24).toString('base64url');
  await page.getByLabel('Full name').fill('Fictional Browser Lawyer');await page.getByLabel('Email address').fill(accountEmail);
  await page.getByLabel(/^Role/).selectOption('LAWYER');await page.getByLabel(/^Password/).fill(newPassword);
  await page.getByLabel('Confirm password').fill(newPassword);await page.getByRole('button',{name:'Create account'}).click();
  await visible('Lawyer account created');await page.getByRole('row').filter({hasText:accountEmail}).getByRole('link',{name:'Deactivate'}).click();
  await page.getByLabel('Reason',{exact:false}).fill('Fictional evaluation access ended.');await page.getByLabel('Remove sign-in access').check();
  await page.getByRole('button',{name:'Deactivate account'}).click();await visible('Access removed for');
  await passed('UI04','R7 account creation and deactivation with preserved attribution');
  await logout();await login('lawyer');
  await page.getByRole('navigation').getByRole('link',{name:'Case register'}).click();await page.getByLabel('Search case records').fill(cin);
  await page.getByRole('button',{name:'Apply filters'}).click();await page.getByRole('link',{name:title,exact:true}).click();
  assert.equal(await page.getByRole('link',{name:'Update assignments'}).count(),0);
  assert.equal((await page.request.post(base+'/cases/new/',{form:{title:'Unauthorized'}})).status(),403);
  await page.getByRole('link',{name:'Hearing agenda'}).click();await page.getByLabel('Hearing date').fill(day);await page.getByRole('button',{name:'Go to date'}).click();
  await visible('No hearings on this date.');await page.screenshot({path:`${evidence}/lawyer-agenda.png`,fullPage:true});await audit('agenda');
  await passed('UI05','R6 Lawyer search and read-only record/agenda; unauthorized POST rejected');
  await logout();await login('judge');
  await page.getByRole('navigation').getByRole('link',{name:'Case register'}).click();await page.getByLabel('Search case records').fill('Orchid House');
  await page.getByRole('button',{name:'Apply filters'}).click();await page.getByRole('link',{name:'Orchid House v. Elm Atelier',exact:true}).click();
  await page.getByRole('link',{name:'Record summary',exact:true}).click();await page.getByLabel('Hearing summary').fill('The fictional parties presented their positions. The demonstration hearing is complete.');
  await page.getByLabel('I have reviewed this summary').check();await page.getByRole('button',{name:'Complete hearing'}).click();await visible('Summary saved and hearing completed.');
  await passed('UI06','R4 assigned Judge records and completes the correct hearing');
  await page.getByRole('link',{name:'Record judgment & close'}).click();await page.getByLabel('Verdict / disposition').fill('Fictional matter resolved');
  await page.getByLabel('Judgment summary').fill('This fictional matter is resolved for the evaluation. This is an academic record, not legal advice.');
  await page.getByLabel('I confirm this judgment is final').check();await page.getByRole('button',{name:'Record judgment & close'}).click();
  await visible('Judgment recorded and case closed.');await page.screenshot({path:`${evidence}/judgment-desktop.png`,fullPage:true});
  await page.reload();await visible('Fictional matter resolved');assert.equal(await page.getByRole('link',{name:'Record judgment & close'}).count(),0);
  await passed('UI07','R5 judgment and closure persist after reload with final record visible');
  await page.goto(caseURL);await visible(title);
  await logout();await login('lawyer.two');
  const denial=await page.goto(caseURL);assert.equal(denial.status(),404);
  await passed('UI08','Unassigned Lawyer cannot retrieve another case by URL');
  assert.deepEqual(errors,[]);await passed('UI09','Desktop/mobile responsive checks, five axe audits and no browser script errors');
}catch(error){results.push({id:'FAILURE',status:'FAIL',description:error.message});await page.screenshot({path:`${evidence}/failure.png`,fullPage:true});throw error;}
finally{writeFileSync(`${evidence}/browser-results.json`,JSON.stringify({base,runAt:new Date().toISOString(),viewport:[1440,1000,390,844],results,scriptErrors:errors},null,2));await browser.close();}
