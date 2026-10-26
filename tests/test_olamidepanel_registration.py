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
            CREATE TABLE website_requests(domain_id INTEGER,state TEXT,message TEXT DEFAULT '',updated INTEGER DEFAULT 0);
            CREATE TABLE audit(actor TEXT,action TEXT,created INTEGER);''')
        self.raw.execute("INSERT INTO users VALUES(1,'owner','owner@example.test',1,'root')")
    def execute(self, sql, args=()): return Cursor(self.raw.execute(sql.replace(' FOR UPDATE', ''), args))

class RegistrationTests(unittest.TestCase):
    def setUp(self): self.connection = Connection()
    def tearDown(self): self.connection.raw.close()
    def test_inspect_never_writes(self):
        r = module.register(self.connection, 'kakakin.africandroid.world')
        self.assertEqual(r['owner'], 'owner')
        self.assertFalse(r['changed'])
        self.assertEqual(self.connection.raw.execute('SELECT COUNT(*) FROM domains').fetchone()[0], 0)
    def test_registration_is_idempotent_and_audited_once(self):
        self.assertTrue(module.register(self.connection, 'kakakin.africandroid.world', apply=True)['changed'])
        self.assertFalse(module.register(self.connection, 'kakakin.africandroid.world', apply=True)['changed'])
        self.assertEqual(self.connection.raw.execute('SELECT COUNT(*) FROM audit').fetchone()[0], 1)
        self.assertEqual(self.connection.raw.execute('SELECT COUNT(*) FROM website_requests').fetchone()[0], 0)
    def test_existing_owner_cannot_be_reassigned(self):
        self.connection.raw.execute("INSERT INTO users VALUES(2,'tenant','tenant@example.test',1,'user')")
        self.connection.raw.execute("INSERT INTO domains VALUES(1,2,'kakakin.africandroid.world',0)")
        self.assertEqual(module.register(self.connection, 'kakakin.africandroid.world')['owner'], 'tenant')
        with self.assertRaisesRegex(ValueError, 'another panel account'):
            module.register(self.connection, 'kakakin.africandroid.world', username='owner', apply=True)
    def test_ambiguous_root_requires_explicit_owner(self):
        self.connection.raw.execute("INSERT INTO users VALUES(2,'other','other@example.test',1,'root')")
        with self.assertRaisesRegex(ValueError, 'exactly one'):
            module.register(self.connection, 'kakakin.africandroid.world')
    def test_static_publisher_request_is_never_overwritten(self):
        self.connection.raw.execute("INSERT INTO domains VALUES(1,1,'kakakin.africandroid.world',0)")
        self.connection.raw.execute("INSERT INTO website_requests(domain_id,state) VALUES(1,'queued')")
        with self.assertRaisesRegex(ValueError, 'static Site Publisher'):
            module.register(self.connection, 'kakakin.africandroid.world', apply=True)
        self.assertEqual(self.connection.raw.execute('SELECT state FROM website_requests').fetchone()[0], 'queued')
    def static_request(self):
        self.connection.raw.execute("INSERT INTO domains VALUES(1,1,'kakakin.africandroid.world',0)")
        self.connection.raw.execute("INSERT INTO website_requests(domain_id,state,message) VALUES(1,'queued','Original request')")
    def test_repair_inspection_allows_static_conflict_without_writing(self):
        self.static_request()
        result=module.register(self.connection,'kakakin.africandroid.world',allow_static=True)
        self.assertFalse(result['changed'])
        self.assertEqual(self.connection.raw.execute('SELECT state FROM website_requests').fetchone()[0],'queued')
    def test_retirement_is_backed_up_scoped_and_idempotent(self):
        self.static_request();snapshots=[]
        def backup(record):snapshots.append(record);return '/protected/snapshot.json'
        result=module.retire_static(self.connection,'kakakin.africandroid.world',backup=backup)
        self.assertTrue(result['changed']);self.assertEqual(snapshots[0]['static_request']['state'],'queued')
        self.assertEqual(snapshots[0]['static_request']['message'],'Original request')
        self.assertEqual(self.connection.raw.execute('SELECT state FROM website_requests').fetchone()[0],'external_backend')
        self.assertEqual(self.connection.raw.execute('SELECT owner FROM domains').fetchone()[0],1)
        self.assertFalse(module.retire_static(self.connection,'kakakin.africandroid.world',backup=backup)['changed'])
        self.assertEqual(len(snapshots),1)
        self.assertTrue(module.register(self.connection,'kakakin.africandroid.world',apply=True)['ok'])
    def test_failed_backup_never_retires_job(self):
        self.static_request()
        def failed(_):raise OSError('Backup unavailable')
        with self.assertRaises(OSError):module.retire_static(self.connection,'kakakin.africandroid.world',backup=failed)
        self.assertEqual(self.connection.raw.execute('SELECT state FROM website_requests').fetchone()[0],'queued')
        self.assertEqual(self.connection.raw.execute('SELECT COUNT(*) FROM audit').fetchone()[0],0)
    def test_repair_cannot_take_over_another_domain(self):
        with self.assertRaises(ValueError):module.retire_static(self.connection,'other.africandroid.world',backup=lambda _:self.fail('No write permitted'))
    def test_suspended_owner_is_rejected(self):
        self.connection.raw.execute("INSERT INTO domains VALUES(1,1,'kakakin.africandroid.world',0)")
        self.connection.raw.execute('UPDATE users SET active=0 WHERE id=1')
        with self.assertRaisesRegex(ValueError, 'suspended'):
            module.register(self.connection, 'kakakin.africandroid.world', apply=True)

if __name__ == '__main__': unittest.main()
