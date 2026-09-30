import os
os.environ['DATABASE_URL']='sqlite://'
from sqlalchemy import create_engine,event,text
from sqlalchemy.pool import StaticPool
import app.database as d
e=create_engine('sqlite://',poolclass=StaticPool,connect_args={'check_same_thread':False})
event.listen(e,'connect',d.apply_sqlite_pragmas)
e.dispose=lambda:None
d.create_db_engine=lambda url=None:e
from alembic import command
from alembic.config import Config
cfg=Config('alembic.ini')
command.upgrade(cfg,'a1b2c3d4e5f6')
with e.begin() as conn:
 conn.execute(text("INSERT INTO projects (id,title) VALUES(1,'P')"))
 conn.execute(text("INSERT INTO chapters (id,project_id,volume,sort_order,title,content_md,status,word_count_cache) VALUES(1,1,1,1,'C','text',:status,4)"),{'status':'초고'})
 conn.execute(text("INSERT INTO refine_runs (id,chapter_id,changed_ratio,accepted) VALUES(1,1,0,0)"))
try:
 command.upgrade(cfg,'head')
 print('POPULATED_MIGRATION_PASS')
except Exception as ex:
 print('POPULATED_MIGRATION_FAIL',type(ex).__name__,str(ex))
