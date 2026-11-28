import {test,expect} from '@playwright/test';

async function login(page:import('@playwright/test').Page){
 const email=process.env.E2E_EMAIL,password=process.env.E2E_PASSWORD;
 if(!email||!password)throw Error('Set isolated E2E administrator credentials');
 await page.goto('/');await page.getByLabel('Email address').fill(email);await page.getByLabel('Password').fill(password);await page.getByRole('button',{name:'Sign in'}).click();await expect(page.getByRole('heading',{name:'Overview',exact:true})).toBeVisible();
}
test('grouped navigation and new event shortcut',async({page})=>{
 await login(page);const nav=page.getByRole('navigation',{name:'Admin navigation'});await nav.getByRole('button',{name:'Data collection',exact:true}).click();await expect(nav.getByRole('button',{name:'Events',exact:true})).toBeHidden();await nav.getByRole('button',{name:'Data collection',exact:true}).click();await expect(nav.getByRole('button',{name:'Events',exact:true})).toBeVisible();await page.getByRole('button',{name:/^New event/ }).click();await expect(page.getByRole('heading',{name:'Register event draft'})).toBeVisible();
});
test('weekly calendar and narrow screen navigation',async({page})=>{
 await page.setViewportSize({width:390,height:844});await login(page);const menu=page.getByRole('button',{name:'Menu',exact:true});await menu.click();const nav=page.getByRole('navigation',{name:'Admin navigation'});await nav.getByRole('button',{name:'Event calendar',exact:true}).click();await expect(page.getByRole('heading',{name:'Event calendar',exact:true})).toBeVisible();await expect(nav).toBeHidden();const first=page.getByRole('button',{pressed:true});const old=await first.innerText();await page.getByRole('button',{name:'Next week'}).click();await expect(page.getByRole('button',{pressed:true})).not.toHaveText(old);await page.getByRole('button',{name:'Today',exact:true}).click();await expect(page.getByRole('button',{pressed:true})).toContainText('Today');expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
});
