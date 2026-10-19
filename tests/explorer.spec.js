const {test,expect}=require('@playwright/test');
const {pathToFileURL}=require('node:url');
const path=require('node:path');
const url=pathToFileURL(path.resolve(__dirname,'../index.html')).href;
test('catalog, search, favorites, source and interactive demo',async({page})=>{
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(url);const total=await page.evaluate(()=>COOKBOOK.recipes.length);
 await expect(page.locator('.card')).toHaveCount(total-6);
 await page.locator('#archive').check();await expect(page.locator('.card')).toHaveCount(total);
 await page.locator('#search').fill('anthropic-chat');await expect(page.locator('.card')).toHaveCount(1);
 await page.locator('.save').click();await expect(page.locator('#favorite-count')).toHaveText('1');
 await page.locator('.open-recipe').click();await expect(page.locator('#detail')).toBeVisible();
 await page.locator('#prompt').fill('Привет');await page.locator('#send').click();await expect(page.locator('.bubble').last()).toContainText('Исходный Python-код',{timeout:10000});
 await page.locator('[data-tab="code"]').click();await page.locator('[data-file]').filter({hasText:'app.py'}).click();await expect(page.locator('#source-code')).toContainText('import');
 await page.locator('[data-tab="setup"]').click();await expect(page.locator('#panel')).toContainText('git clone');
 await page.keyboard.press('Escape');await expect(page.locator('#detail')).not.toBeVisible();
 await page.locator('#search').fill('no_such_recipe');await expect(page.locator('#empty')).toBeVisible();await page.locator('#reset').click();await expect(page.locator('.card')).toHaveCount(total);
 expect(errors).toEqual([]);
});
test('all recipes open with source and setup',async({page})=>{
 await page.goto(url);const ids=await page.evaluate(()=>COOKBOOK.recipes.map(r=>r.id));
 for(const id of ids){await page.evaluate(id=>openRecipe(id),id);await expect(page.locator('#detail')).toBeVisible();await page.locator('[data-tab="code"]').click();await expect(page.locator('#source-code')).not.toBeEmpty();await page.locator('[data-tab="setup"]').click();await expect(page.locator('#panel')).toContainText(id);await page.locator('#close').click()}
});
test('desktop and mobile layouts',async({page})=>{
 await page.setViewportSize({width:1440,height:1100});await page.goto(url);await page.screenshot({path:'desktop-preview.png',fullPage:false});
 await page.setViewportSize({width:390,height:844});await page.screenshot({path:'mobile-preview.png',fullPage:false});
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 await page.locator('.open-recipe').first().click();await expect(page.locator('#detail')).toBeVisible();expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
});
test('filters, approval, file selection and direct links',async({page})=>{
 await page.goto(url);await page.locator('[data-category="Интерфейс"]').click();await expect(page.locator('.card')).toHaveCount(11);
 await page.locator('[data-category="Все примеры"]').click();await page.locator('[data-tag="MCP"]').click();await expect(page.locator('.card')).toHaveCount(2);
 await page.goto(url+'#confirm-action');await expect(page.locator('#detail')).toBeVisible();await page.locator('[data-decision]').first().click();await expect(page.locator('.bubble').last()).toContainText('Подтверждено');await page.keyboard.press('Escape');
 await page.evaluate(()=>openRecipe('pdf-qa'));await page.locator('#upload').setInputFiles({name:'sample.pdf',mimeType:'application/pdf',buffer:Buffer.from('demo')});await expect(page.locator('.bubble').last()).toContainText('sample.pdf');await page.keyboard.press('Escape');
 await page.locator('.save').first().click();await page.reload();await expect(page.locator('#favorite-count')).toHaveText('1');await page.locator('#favorites').click();await expect(page.locator('.card')).toHaveCount(1);
});
