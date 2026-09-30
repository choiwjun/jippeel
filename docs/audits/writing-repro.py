import os,sys,json,asyncio
os.environ["DATABASE_URL"]="sqlite:///:memory:"
sys.dont_write_bytecode=True
sys.stdout.reconfigure(encoding="utf-8")
from app.database import Base,engine,SessionLocal
from app.models import Project,Chapter,LoreEntry,Foreshadow,AiEndpoint
from app.services import bootstrap,canon,quality,parallel_writer,llm
from app.routers import ai_panel
from app.schemas import GenerateRequest,ParallelGenerateRequest
Base.metadata.create_all(engine)
db=SessionLocal()
p=Project(title="test",style_profile="STYLE_SENTINEL",synopsis="SYNOPSIS_SENTINEL")
db.add(p);db.flush()
chs=[Chapter(project_id=p.id,title=f"chapter {i}",sort_order=i,content_md="") for i in (1,2,100)]
db.add_all(chs);db.flush()
lore=LoreEntry(project_id=p.id,title="은빛목걸이",category="용어",content="보호막을 생성하는 유물",keywords=["은빛목걸이"])
future=Foreshadow(project_id=p.id,title="FUTURE_SENTINEL",status="설치",planted_chapter_id=chs[2].id,audience_knows=False)
ep=AiEndpoint(name="fake",base_url="http://unused.invalid",default_model="fake")
db.add_all([lore,future,ep]);db.commit()
brief=dict(emotion_goal="불안",core_events=["은빛목걸이를 찾아낸다"],character_choices=["수색한다"],cost="시간",prohibitions=["새 사건 금지"],next_hook="열린 문")
req=GenerateRequest(endpoint_id=ep.id,prompt_override="집필해줘",context=dict(chapter_id=chs[0].id,auto_lore=True,auto_foreshadow=True,style_profile=True,brief=brief))
_,messages,injected,_,fs=ai_panel._build_messages(req,db)
print("brief_lore_injected",injected)
print("future_foreshadow_injected",fs)
print("style_normal", "STYLE_SENTINEL" in str(messages))
print("synopsis_injected", "SYNOPSIS_SENTINEL" in str(messages))
print("canon_future", "FUTURE_SENTINEL" in str(canon.build_messages(db,chs[0])[0]))
outline=bootstrap._coerce_outline({"volumes":[{"volume":1,"chapters":[{"order":1,"title":"A"}]},{"volume":2,"chapters":[{"order":1,"title":"B"},{"order":2,"title":"C"}]}]},2,2)
print("outline",[(c.volume,c.order,c.sort_order,c.title) for c in outline])
for raw in ('{}','{"issues":"not-an-array"}','{"issues":null}'):
 try: print("canon_parse",raw,canon.parse_issues(raw))
 except Exception as e: print("canon_parse",raw,type(e).__name__)
for text in ('', '"가나다라?" 마바사아자차카타파하.'):
 m=quality.analyze_text(text);print("quality",repr(text),quality.score_and_suggest(m)[0],m)
plan=parallel_writer.parse_parallel_plan(json.dumps({"scenes":[dict(order=i,title=f"장면{i}",purpose="대립",objective="탈출",choice="희생",cost="상처",required_beats=["탈출 실패"],characters=["주인공"],opening_state="갇힘",closing_hook="문 열림") for i in (1,2)]}))
print("one_char_scenes_valid",parallel_writer.validate_results([parallel_writer.SceneResult(s.order,s.title,"가") for s in plan.scenes],plan.scenes))
captured=[]
async def fake_complete(client,model,msgs,**kw):
 captured.append(msgs)
 return json.dumps(plan.model_dump(),ensure_ascii=False) if len(captured)==1 else "원고"
async def fake_stream(client,model,msgs,**kw):
 captured.append(msgs)
 yield "감수 의견"
llm.make_client=lambda *a:object()
llm.complete_chat=fake_complete
llm.stream_chat=fake_stream
async def run():
 payload=ParallelGenerateRequest(endpoint_id=ep.id,prompt_override="집필",context=req.context)
 response=await ai_panel.generate_parallel(payload,db)
 async for event in response.body_iterator: pass
 print("style_parallel_calls",["STYLE_SENTINEL" in str(m) for m in captured])
asyncio.run(run())
