// Run: node docs/audits/frontend-static-server.cjs (separate terminal), then node docs/audits/frontend-probe.cjs
// All API calls are mocked. No real DB/LLM calls. Run only against the isolated server below.
const path = require('path');
const {chromium, expect} = require(path.resolve(__dirname, '../../frontend/node_modules/@playwright/test'));
(async()=>{
 const browser=await chromium.launch({headless:true}); const results=[];
 async function fixture(){
 const page=await browser.newPage();
 const chapters={101:{id:101,project_id:1,volume:1,sort_order:1,title:'A-one',content_md:'ORIGINAL_A',status:'초고',word_count_cache:10,memo:'A plot'},102:{id:102,project_id:1,volume:1,sort_order:2,title:'A-two',content_md:'ORIGINAL_TWO',status:'초고',word_count_cache:10,memo:''},201:{id:201,project_id:2,volume:1,sort_order:1,title:'B-one',content_md:'ORIGINAL_B',status:'초고',word_count_cache:10,memo:''}};
 const puts=[], generates=[], logs=[],scenePatches=[];const scenes=[{id:11,chapter_id:101,sort_order:1,title:'Scene Alpha',content_md:'ALPHA'},{id:12,chapter_id:101,sort_order:2,title:'Scene Beta',content_md:'BETA'}]; const projects=[1,2].map(id=>({id,title:'Project '+id,genre:'test',synopsis:'test',created_at:'2026-01-01',updated_at:'2026-01-01'}));
 await page.route('**/*',async route=>{
 const req=route.request(),u=new URL(req.url()),p=u.pathname.replace('/api/v1','');
 if(!u.pathname.startsWith('/api/')){if(u.hostname==='127.0.0.1'||u.hostname==='172.30.1.187') return route.continue(); return route.abort();}
 let data=[]; logs.push(req.method()+' '+p);
 if(p==='/chapters/101/scenes')data=scenes;
 else if(/^\/scenes\/\d+$/.test(p)&&req.method()==='PATCH'){const id=+p.split('/')[2],body=req.postDataJSON();scenePatches.push({id,...body});data=scenes.find(s=>s.id===id);Object.assign(data,body);}
 else if(p==='/projects')data=projects;
 else if(/^\/projects\/\d+\/chapters$/.test(p))data=Object.values(chapters).filter(x=>x.project_id===+p.split('/')[2]);
 else if(/^\/chapters\/\d+\/content$/.test(p)){const id=+p.split('/')[2],body=req.postDataJSON();puts.push({id,...body});Object.assign(chapters[id],body);data=chapters[id];}
 else if(/^\/chapters\/\d+$/.test(p))data=chapters[+p.split('/')[2]];
 else if(p==='/ai/endpoints')data=[{id:1,name:'MOCK',base_url:'http://mock.invalid',default_model:'mock',is_default:true,temperature:0.7}];
 else if(p.endsWith('/models'))data={data:[{id:'mock'}]};
 else if(p==='/ai/generate'){generates.push(req.postDataJSON());return route.fulfill({status:200,contentType:'text/event-stream',body:'event: message\ndata: {"delta":"GENERATED"}\n\nevent: done\ndata: {}\n\n'});}
 else if(p.endsWith('/plus-status'))data={chapter_count:2,chapter_count_met:false,done_chapter_count:0,done_chapters_3000:0,done_chars_met:false,eligible:false};
 else if(/^\/projects\/\d+$/.test(p))data=projects.find(x=>x.id===+p.split('/')[2]);
 return route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(data)});
 });
 await page.goto('http://127.0.0.1:15174/projects/1/write'); await expect(page.locator('.cm-content')).toHaveText('ORIGINAL_A');
 return {page,chapters,puts,generates,logs,scenePatches,scenes};
 }
 async function test(name,fn){try{results.push({name,...await fn()});}catch(e){results.push({name,error:e.message});}}
 await test('rapid chapter switch drops dirty draft',async()=>{let {page,chapters,puts}=await fixture();await page.clock.install();await page.locator('.cm-content').fill('UNSAVED_A');await page.getByRole('button',{name:'A-two',exact:false}).click();await expect(page.locator('.cm-content')).toHaveText('ORIGINAL_TWO');await page.clock.runFor(2000);return {puts,serverA:chapters[101].content_md,editor:await page.locator('.cm-content').innerText()};});
 await test('save then preview stale cache',async()=>{let {page,puts}=await fixture();await page.locator('.cm-content').fill('SAVED_NEW_A');await page.locator('.cm-content').press('Control+s');await expect.poll(()=>puts.length).toBe(1);await page.getByRole('tab',{name:'미리보기',exact:true}).click();let preview=await page.getByRole('tabpanel').innerText();await page.getByRole('tab',{name:'편집',exact:true}).click();return {puts,preview,remountedEditor:await page.locator('.cm-content').innerText()};});
 await test('AI current chapter omitted',async()=>{let {page,generates}=await fixture();await page.getByRole('button',{name:'AI 패널 열기 (Alt+A)'}).click();await page.getByPlaceholder('무엇을 쓸지 지시하세요…').fill('Continue current chapter');await page.getByLabel(/^현재 회차/).click();const checked=await page.getByLabel(/^현재 회차/).isChecked();await page.getByRole('button',{name:'✨ 생성 시작',exact:true}).click();await expect.poll(()=>generates.length).toBe(1);return {visibleChapter:'A-one',checkboxAfterClick:checked,request:generates[0]};});
 await test('project switch retains old chapter',async()=>{let {page,puts}=await fixture();await page.getByRole('link',{name:'← 홈으로'}).click();let card=page.locator('main .grid > div').filter({hasText:'Project 2'});await card.getByRole('link').click();await expect(page).toHaveURL(/projects\/2\/write/);let editor=await page.locator('.cm-content').innerText();await page.locator('.cm-content').fill('THOUGHT_THIS_WAS_B');await page.locator('.cm-content').press('Control+s');await expect.poll(()=>puts.length).toBe(1);return {url:page.url(),editor,puts};});

 await test('undo keyboard after typing',async()=>{let {page}=await fixture();await page.locator('.cm-content').click();await page.locator('.cm-content').press('Control+End');await page.keyboard.type(' NEW');const before=await page.locator('.cm-content').innerText();await page.keyboard.press('Control+z');return {before,after:await page.locator('.cm-content').innerText()};});

 await test('AI result applied to another chapter',async()=>{let {page,puts}=await fixture();await page.getByRole('button',{name:'AI 패널 열기 (Alt+A)'}).click();await page.getByPlaceholder('무엇을 쓸지 지시하세요…').fill('Write for A-one');await page.getByRole('button',{name:'✨ 생성 시작',exact:true}).click();await expect(page.getByRole('button',{name:'↪ 끼워넣기'})).toBeEnabled();await page.getByRole('button',{name:'패널 닫기',exact:true}).click();await page.getByRole('button',{name:'A-two',exact:false}).click();await page.getByRole('button',{name:'AI 패널 열기 (Alt+A)'}).click();await page.getByRole('button',{name:'↪ 끼워넣기'}).click();return {editor:await page.locator('.cm-content').innerText()};});
 await test('scene manager cannot open because trigger not rendered',async()=>{let {page,scenePatches,scenes}=await fixture();await page.getByRole('button',{name:'AI 패널 열기 (Alt+A)'}).click();await expect(page.getByLabel('현재 장면',{exact:true})).toBeVisible();return {sceneOptionCount:await page.locator('#ai-scene option').count(),managerTriggerCount:await page.getByRole('button',{name:'장면 관리 열기'}).count(),managerTextVisible:await page.getByText(/장면 관리/).count()};});
 await browser.close();console.log(JSON.stringify(results,null,2));
})().catch(e=>{console.error(e);process.exit(1)});
