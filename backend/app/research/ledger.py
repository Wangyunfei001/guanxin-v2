"""Conversation-scoped research accounting and evidence; no execution loop."""
from contextlib import closing
from datetime import datetime, timezone

from app.core.sqlite import connect, transaction


def initialize():
    with transaction() as db:
        db.execute('''CREATE TABLE IF NOT EXISTS research_ledgers (
            conversation_id TEXT PRIMARY KEY REFERENCES conversations(conversation_id) ON DELETE CASCADE,
            calls INTEGER NOT NULL DEFAULT 0, actions INTEGER NOT NULL DEFAULT 0,
            max_calls INTEGER NOT NULL, max_actions INTEGER NOT NULL,
            pending INTEGER NOT NULL DEFAULT 0, uncertain INTEGER NOT NULL DEFAULT 0)''')
        db.execute('''CREATE TABLE IF NOT EXISTS citation_evidence (
            conversation_id TEXT NOT NULL REFERENCES conversations(conversation_id) ON DELETE CASCADE,
            url TEXT NOT NULL, body TEXT NOT NULL DEFAULT '', fetched_at TEXT NOT NULL DEFAULT '',
            sha256 TEXT NOT NULL DEFAULT '', final_url TEXT NOT NULL DEFAULT '', PRIMARY KEY(conversation_id,url))''')
        columns = {r[1] for r in db.execute('PRAGMA table_info(citation_evidence)')}
        if 'final_url' not in columns:
            db.execute("ALTER TABLE citation_evidence ADD COLUMN final_url TEXT NOT NULL DEFAULT ''")
        db.execute('''CREATE TABLE IF NOT EXISTS citation_claims (
            conversation_id TEXT NOT NULL REFERENCES conversations(conversation_id) ON DELETE CASCADE,
            claim TEXT NOT NULL, url TEXT NOT NULL, quote TEXT NOT NULL,
            PRIMARY KEY(conversation_id,claim,url,quote))''')


def reserve(cid, mode):
    initialize()
    with transaction() as db:
        db.execute('INSERT OR IGNORE INTO research_ledgers(conversation_id,max_calls,max_actions) VALUES (?,?,?)',
                   (cid, 4 if mode == 'deep' else 2, 40 if mode == 'deep' else 20))
        row = db.execute('SELECT * FROM research_ledgers WHERE conversation_id=?', (cid,)).fetchone()
        if row['uncertain'] or row['pending']:
            return '上次搜索仍在进行或用量未知；暂停新的搜索请求。'
        if row['calls'] >= row['max_calls'] or row['actions'] >= row['max_actions']:
            return '本会话搜索预算已用完；请基于现有证据作答并说明缺口。'
        db.execute('UPDATE research_ledgers SET calls=calls+1,pending=1 WHERE conversation_id=?', (cid,))
    return None


def finish(cid, result=None):
    # A failed/cancelled request may already have been billed; never refund it.
    with transaction() as db:
        db.execute('UPDATE research_ledgers SET pending=0,uncertain=?,actions=actions+? WHERE conversation_id=?',
                   (int(result is None), result.search_actions if result else 0, cid))
        if result:
            for source in result.sources:
                db.execute('INSERT OR IGNORE INTO citation_evidence(conversation_id,url) VALUES (?,?)', (cid, source.url))


def evidence(cid, url):
    with closing(connect()) as db:
        row = db.execute('SELECT * FROM citation_evidence WHERE conversation_id=? AND url=?', (cid, url)).fetchone()
        return dict(row) if row else None


def save_body(cid, url, body, sha256, final_url=None):
    with transaction() as db:
        db.execute('UPDATE citation_evidence SET body=?,sha256=?,fetched_at=?,final_url=? WHERE conversation_id=? AND url=? AND body=""',
                   (body, sha256, datetime.now(timezone.utc).isoformat(), final_url or url, cid, url))


def save_claim(cid, claim, url, quote):
    with transaction() as db:
        db.execute('INSERT OR IGNORE INTO citation_claims VALUES (?,?,?,?)', (cid, claim, url, quote))


def snapshot(cid):
    initialize()
    with closing(connect()) as db:
        budget = db.execute('SELECT * FROM research_ledgers WHERE conversation_id=?', (cid,)).fetchone()
        claims = db.execute('''SELECT c.claim,c.url,c.quote,e.fetched_at,e.sha256,e.final_url FROM citation_claims c
            JOIN citation_evidence e ON c.conversation_id=e.conversation_id AND c.url=e.url
            WHERE c.conversation_id=?''', (cid,)).fetchall()
    return {'budget': dict(budget) if budget else None,
            'claims': [{**dict(row), 'quote_match': True, 'entailment': 'requires_human_review'} for row in claims]}
