import os
os.environ['DATABASE_URL']='sqlite://'
from sqlalchemy import create_engine, event
from sqlalchemy.pool import StaticPool
import app.database as d
d.engine.dispose()
d.engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
event.listen(d.engine,'connect',d.apply_sqlite_pragmas)
d.SessionLocal.configure(bind=d.engine)
from app.main import app
from fastapi.testclient import TestClient
from app.models import RefineRun
with TestClient(app,raise_server_exceptions=False) as c:
 def post(path,data):
  r=c.post('/api/v1'+path,json=data); assert r.status_code in (200,201),(r.status_code,r.text); return r.json()
 def get(path): return c.get('/api/v1'+path)
 p=post('/projects',{'title':'A'})['id']; q=post('/projects',{'title':'B'})['id']
 a=post(f'/projects/{p}/chapters',{'title':'A1','volume':1})['id']; b=post(f'/projects/{q}/chapters',{'title':'B1'})['id']
 s=post(f'/chapters/{b}/scenes',{'title':'B scene','sort_order':1})['id']
 r=c.patch(f'/api/v1/chapters/{a}/scenes/order',json={'items':[{'id':s,'sort_order':99}]})
 print('foreign scene reorder',r.status_code,get(f'/scenes/{s}').json()['sort_order'])
 f=post(f'/projects/{p}/foreshadows',{'title':'A foreshadow','planted_chapter_id':b})
 print('foreign foreshadow ref',f['project_id'],f['planted_chapter_id'])
 print('delete referenced chapter',c.delete(f'/api/v1/chapters/{b}').status_code)
 x=post(f'/projects/{p}/characters',{'name':'X'})['id']; y=post(f'/projects/{p}/characters',{'name':'Y'})['id']
 post(f'/projects/{p}/characters/relations',{'from_character_id':x,'to_character_id':y})
 print('delete related character',c.delete(f'/api/v1/characters/{x}').status_code)
 e=post('/projects',{'title':'Empty chapters'})['id']; post(f'/projects/{e}/foreshadows',{'title':'pending'})
 print('empty chapters reminder',get(f'/projects/{e}/foreshadows/reminder').status_code)
 post(f'/projects/{p}/lore',{'title':'dragon','content':'dragon'})
 l=post(f'/projects/{q}/lore',{'title':'dragon','content':'dragon'})['id']
 r=get(f'/projects/{q}/lore/search?q=dragon&limit=1'); print('scoped lore search',r.status_code,r.json(),'expected entry',l)
 c.put(f'/api/v1/chapters/{a}/content',json={'content_md':'old manuscript'})
 with d.SessionLocal() as db:
  run=RefineRun(chapter_id=a,report_json={'original_text':'old manuscript'},result_text='old refined manuscript');db.add(run);db.commit();rid=run.id
 c.put(f'/api/v1/chapters/{a}/content',json={'content_md':'NEW manual manuscript'})
 r=c.post(f'/api/v1/refine/runs/{rid}/accept'); print('stale refine accept',r.status_code,get(f'/chapters/{a}').json()['content_md'])
 r=c.patch(f'/api/v1/projects/{p}/chapters/reorder',json={'items':[{'id':a,'volume':None}]});print('reorder unassign volume',r.status_code,get(f'/chapters/{a}').json()['volume'])
