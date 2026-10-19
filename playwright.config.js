const {defineConfig}=require('@playwright/test');
module.exports=defineConfig({testDir:'./tests',use:{headless:true,launchOptions:{executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'}},reporter:'list'});
