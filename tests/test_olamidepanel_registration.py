import importlib.util
from pathlib import Path
import sqlite3
import unittest

spec = importlib.util.spec_from_file_location('panel_registration', Path(__file__).parents[1]/'server'/'olamidepanel-register.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class Cursor:
    def __init__(self, cursor): self.cursor = cursor; self.lastrowid = cursor.lastrowid
    def fetchone(self):
        row = self.cursor.fetchone()
        return dict(row) if row else None
    def fetchall(self): return [dict(row) for row in self.cursor.fetchall()]

class Connection:
    def __init__(self):
        self.raw = sqlite3.connect(':memory:')
        self.raw.row_factory = sqlite3.Row
        self.raw.executescript('''CREATE TABLE users(id INTEGER PRIMARY KEY,username TEXT,email TEXT,active INTEGER,role TEXT);
            CREATE TABLE domains(id INTEGER PRIMARY KEY,owner INTEGER,name TEXT UNIQUE,created INTEGER);
            CREATE TABLE website_requests(domain_id INTEGER,state TEXT);
            CREATE TABLE audit(actor TEXT,action TEXT,created INTEGER);''')
        self.raw.execute("INSERT INTO users VALUES(1,'owner','owner@example.test',1,'root')")
    def execute(self, sql, args=()): return Cursor(self.raw.execute(sql.replace(' FOR UPDATE', ''), args))

class RegistrationTests(unittest.TestCase):
    def setUp(self): self.connection = Connection()
    def tearDown(self): self.connection.raw.close()
    def test_inspect_never_writes(self):
        r = module.register(self.connection, 'kakakin.africandroid.com')
        self.assertEqual(r['owner'], 'owner')
        self.assertFalse(r['changed'])
        self.assertEqual(self.connection.raw.execute('SELECT COUNT(*) FROM domains').fetchone()[0], 0)
    def test_registration_is_idempotent_and_audited_once(self):
        self.assertTrue(module.register(self.connection, 'kakakin.africandroid.com', apply=True)['changed'])
        self.assertFalse(module.register(self.connection, 'kakakin.africandroid.com', apply=True)['changed'])
        self.assertEqual(self.connection.raw.execute('SELECT COUNT(*) FROM audit').fetchone()[0], 1)
        self.assertEqual(self.connection.raw.execute('SELECT COUNT(*) FROM website_requests').fetchone()[0], 0)
    def test_existing_owner_cannot_be_reassigned(self):
        self.connection.raw.execute("INSERT INTO users VALUES(2,'tenant','tenant@example.test',1,'user')")
        self.connection.raw.execute("INSERT INTO domains VALUES(1,2,'kakakin.africandroid.com',0)")
        self.assertEqual(module.register(self.connection, 'kakakin.africandroid.com')['owner'], 'tenant')
        with self.assertRaisesRegex(ValueError, 'another panel account'):
            module.register(self.connection, 'kakakin.africandroid.com', username='owner', apply=True)
    def test_ambiguous_root_requires_explicit_owner(self):
        self.connection.raw.execute("INSERT INTO users VALUES(2,'other','other@example.test',1,'root')")
        with self.assertRaisesRegex(ValueError, 'exactly one'):
            module.register(self.connection, 'kakakin.africandroid.com')
    def test_static_publisher_request_is_never_overwritten(self):
        self.connection.raw.execute("INSERT INTO domains VALUES(1,1,'kakakin.africandroid.com',0)")
        self.connection.raw.execute("INSERT INTO website_requests VALUES(1,'queued')")
        with self.assertRaisesRegex(ValueError, 'static Site Publisher'):
            module.register(self.connection, 'kakakin.africandroid.com', apply=True)
        self.assertEqual(self.connection.raw.execute('SELECT state FROM website_requests').fetchone()[0], 'queued')
    def test_suspended_owner_is_rejected(self):
        self.connection.raw.execute("INSERT INTO domains VALUES(1,1,'kakakin.africandroid.com',0)")
        self.connection.raw.execute('UPDATE users SET active=0 WHERE id=1')
        with self.assertRaisesRegex(ValueError, 'suspended'):
            module.register(self.connection, 'kakakin.africandroid.com', apply=True)

if __name__ == '__main__': unittest.main()
