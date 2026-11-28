import {test,expect,type Page} from '@playwright/test';

// Browser interaction fixtures use real staff login, but intercept editorial reads.
// No issue, event or media records are created/modified by these cases.
const issueId='00000000-0000-4000-8000-000000000001';
const occurrenceId='00000000-0000-4000-8000-000000000002';
const issue={id:issueId,number:501,week_start:'2026-12-10',week_end:'2026-12-16',grid_day:'2026-12-11',version:1,picks_title:"BUGY'S PICKS",picks_byline:'',picks_intro:'',status:'DRAFT',entries:[]};
const candidate={occurrence_id:occurrenceId,occurrence_version:1,title:'Synthetic event',category:'Music',venue:'Synthetic venue',editorial_date:'2026-12-11',starts_at:'2026-12-11T20:00:00+03:00'};
const paginated=(results:unknown[])=>({count:results.length,next:null,previous:null,results});
async function setup(page:Page){
 const email=process.env.E2E_EMAIL,password=process.env.E2E_PASSWORD;
 if(!email||!password)throw Error('Set isolated E2E administrator credentials');
 await page.route('**/api/v1/admin/issues/**',async route=>{
  const path=new URL(route.request().url()).pathname;
  if(route.request().method()!=='GET')return route.fulfill({status:405,json:{message:'Fixture is read only'}});
  if(path.endsWith('/issues/'))return route.fulfill({json:paginated([issue])});
  if(path.endsWith('/candidates/'))return route.fulfill({json:paginated([candidate])});
  if(path.endsWith('/cover/'))return route.fulfill({json:{version:1,accent:'#FFD400',name:'',subtitle:'',lines:[],photo:null,headshot:null,warnings:[]}});
  if(path.endsWith('/review/'))return route.fulfill({json:{version:1,fingerprint:'fixture',state:'DRAFT',ready:false,checks:[],actions:[],decision_id:null,history:[]}});
  if(path.endsWith('/'+issueId+'/'))return route.fulfill({json:issue});
  return route.fulfill({status:404,json:{message:'Unknown fixture path'}});
 });
 await page.goto('/');await page.getByLabel('Email address').fill(email);await page.getByLabel('Password').fill(password);await page.getByRole('button',{name:'Sign in'}).click();
 await page.getByRole('navigation',{name:'Admin navigation'}).getByRole('button',{name:'Weekly issues & picks',exact:true}).click();
 await page.getByRole('button',{name:'Open issue',exact:true}).click();
 await expect(page.getByRole('heading',{name:'Edition summary'})).toBeVisible();
}
test('editorial tabs retain unsaved selection and settings',async({page})=>{
 await setup(page);const tabs=page.getByRole('navigation',{name:'Issue sections'});
 await page.getByLabel('Byline').fill('Synthetic byline');
 await tabs.getByRole('button',{name:'Events',exact:true}).click();
 await expect(page.getByRole('heading',{name:'Eligible events'})).toBeVisible();
 await page.getByRole('button',{name:'Include',exact:true}).click();
 await tabs.getByRole('button',{name:'Bugy’s Picks',exact:true}).click();
 await expect(page.getByText('1 selected · 0/7 ranked picks')).toBeVisible();
 await page.getByLabel('Pick rank').selectOption('1');await page.getByLabel('Why go?').fill('Synthetic reason');
 await tabs.getByRole('button',{name:'Summary',exact:true}).click();await expect(page.getByLabel('Byline')).toHaveValue('Synthetic byline');
 page.once('dialog',d=>d.dismiss());await tabs.getByRole('button',{name:'Approval',exact:true}).click();
 await expect(page.getByRole('heading',{name:'Edition summary'})).toBeVisible();
 page.once('dialog',d=>d.accept());await tabs.getByRole('button',{name:'Approval',exact:true}).click();
 await expect(page.getByRole('heading',{name:'Editorial readiness & approval'})).toBeVisible();
 await tabs.getByRole('button',{name:'Bugy’s Picks',exact:true}).click();await expect(page.getByText('0 selected · 0/7 ranked picks')).toBeVisible();
});
test('cover tab guards unsaved changes during tab and sidebar navigation',async({page})=>{
 await setup(page);const tabs=page.getByRole('navigation',{name:'Issue sections'});
 await tabs.getByRole('button',{name:'Cover',exact:true}).click();await page.getByLabel('Cover personality / name').fill('Synthetic cover');
 await expect(page.getByText(/Unsaved changes\. Save before/)).toBeVisible();
 page.once('dialog',d=>d.dismiss());await tabs.getByRole('button',{name:'Summary',exact:true}).click();
 await expect(page.getByLabel('Cover personality / name')).toHaveValue('Synthetic cover');
 const overview=page.getByRole('navigation',{name:'Admin navigation'}).getByRole('button',{name:'Overview',exact:true});
 page.once('dialog',d=>d.dismiss());await overview.click();await expect(page.getByLabel('Cover personality / name')).toHaveValue('Synthetic cover');
 page.once('dialog',d=>d.accept());await overview.click();await expect(page.getByRole('heading',{name:'Overview',exact:true})).toBeVisible();
});
