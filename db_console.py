"""Read-only SQL console; no SQLite CLI installation needed."""
import argparse,json,sqlite3
from pathlib import Path
import database as db
p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True);g.add_argument('--query');g.add_argument('--file');a=p.parse_args()
if not db.DB.exists():p.error('Database not created yet. Start app.py first.')
query=a.query if a.query else Path(a.file).read_text(encoding='utf-8')
with sqlite3.connect(db.DB.resolve().as_uri()+'?mode=ro',uri=True,timeout=10) as c:
 c.row_factory=sqlite3.Row;c.execute('PRAGMA query_only=ON');buffer=''
 for line in (query+'\n').splitlines(keepends=True):
  buffer+=line
  if sqlite3.complete_statement(buffer):
   cursor=c.execute(buffer);print('\nSQL:',buffer.strip());print(json.dumps([dict(r) for r in cursor],indent=2));buffer=''
 if buffer.strip():
  cursor=c.execute(buffer);print(json.dumps([dict(r) for r in cursor],indent=2))
