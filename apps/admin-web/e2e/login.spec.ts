import {test,expect} from '@playwright/test';
test('staff login, navigation and logout',async({page})=>{
 const email=process.env.E2E_EMAIL,password=process.env.E2E_PASSWORD;if(!email||!password)throw Error('Set isolated E2E account credentials');
 await page.goto('/');await page.getByLabel('Email address').fill(email);await page.getByLabel('Password').fill(password);await page.getByRole('button',{name:'Sign in'}).click();await expect(page.getByRole('heading',{name:'Overview'})).toBeVisible();await page.getByRole('button',{name:'Users & roles'}).click();await expect(page.getByRole('heading',{name:'Users & roles'})).toBeVisible();await page.getByRole('button',{name:'Sign out'}).click();await expect(page.getByRole('heading',{name:'Welcome back'})).toBeVisible();
});
