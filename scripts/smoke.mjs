import {chromium} from 'playwright';
import assert from 'node:assert/strict';
const base=process.env.BASE_URL;
if(!base||!base.startsWith('https://'))throw new Error('Set BASE_URL to the verified production HTTPS origin.');
const browser=await chromium.launch({channel:process.env.BROWSER_CHANNEL||'chromium'});
try{
  for(const role of ['REGISTRAR','JUDGE','LAWYER']){
    const email=process.env[role+'_EMAIL'];const password=process.env[role+'_PASSWORD'];
    if(!email||!password)throw new Error(`Supply ${role}_EMAIL and ${role}_PASSWORD privately.`);
    const context=await browser.newContext();const page=await context.newPage();
    assert.equal((await page.goto(base+'/health/')).status(),200);
    await page.goto(base+'/login/');await page.getByLabel('Email address').fill(email);await page.getByLabel('Password').fill(password);
    await page.getByRole('button',{name:'Sign in to Casework'}).click();await page.getByRole('heading',{name:'A clear view of your day.'}).waitFor();
    const cookie=(await context.cookies()).find(c=>c.name==='sessionid');
    assert(cookie?.secure&&cookie.httpOnly&&cookie.sameSite==='Lax');
    await page.goto(base+'/cases/');assert(await page.getByRole('heading',{name:'Case register',exact:true}).isVisible());
    await page.goto(base+'/agenda/');assert(await page.getByRole('heading',{name:'Hearing agenda',exact:true}).isVisible());
    if(role!=='REGISTRAR') assert.equal((await page.goto(base+'/accounts/')).status(),403);
    console.log(`${role}: HTTPS sign-in, secure session, case browse, agenda and role boundary PASS`);
    await context.close();
  }
}finally{await browser.close();}
