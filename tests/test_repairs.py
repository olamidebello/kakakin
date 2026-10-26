import importlib.util
from pathlib import Path
import unittest
import tempfile
import subprocess

ROOT=Path(__file__).parents[1]
def load(name, path):
    spec=importlib.util.spec_from_file_location(name, ROOT/path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
nginx=load('repair_nginx','server/repair-nginx.py')
dns=load('repair_dns','server/repair-dns.py')

class RouteRepairTests(unittest.TestCase):
    def test_preserves_other_domains_and_nested_locations(self):
        text='server { server_name other.test; location / { return 200; } }\nserver { server_name kakakin.africandroid.world; location / { proxy_pass http://127.0.0.1:99; } }'
        result,count=nginx.remove_exclusive_blocks(text,'kakakin.africandroid.world')
        self.assertEqual(count,1);self.assertIn('server_name other.test',result);self.assertNotIn('127.0.0.1:99',result)
    def test_unused_kakakin_zone_is_removed_without_touching_other_zones(self):
        text='limit_req_zone $binary_remote_addr zone=kakakin_login:10m rate=6r/m;\nlimit_req_zone $binary_remote_addr zone=other_login:10m rate=6r/m;\nserver { server_name kakakin.africandroid.world; }'
        result,count=nginx.remove_exclusive_blocks(text,'kakakin.africandroid.world')
        self.assertEqual(count,1);self.assertNotIn('zone=kakakin_login:',result);self.assertIn('zone=other_login:',result)
    def test_shared_vhost_is_not_modified(self):
        with self.assertRaises(ValueError): nginx.remove_exclusive_blocks('server { server_name other.test kakakin.africandroid.world; }','kakakin.africandroid.world')
    def test_quoted_braces_and_comments_do_not_break_parser(self):
        text='# server { server_name kakakin.africandroid.world; }\nserver { server_name "kakakin.africandroid.world"; location / { return 200 "a}b{"; } }'
        result,count=nginx.remove_exclusive_blocks(text,'kakakin.africandroid.world')
        self.assertEqual(count,1);self.assertTrue(result.startswith('# server'))
    def test_no_match_is_unchanged(self):
        text='server { server_name other.test; }';self.assertEqual(nginx.remove_exclusive_blocks(text,'kakakin.africandroid.world'),(text,0))
    def test_unbalanced_vhost_refuses_changes(self):
        with self.assertRaises(ValueError): nginx.remove_exclusive_blocks('server { server_name kakakin.africandroid.world;','kakakin.africandroid.world')

class DNSRepairTests(unittest.TestCase):
    config={'domain':'kakakin.africandroid.world','ipv4':'154.16.170.86','auto':True}
    def test_correct_dns_never_calls_provider(self):
        result=dns.run(self.config,resolver=lambda _:dict(a=['154.16.170.86'],aaaa=[]),provisioner=lambda _:self.fail('No DNS write allowed'))
        self.assertTrue(result['ready']);self.assertFalse(result['changed'])
    def test_missing_credentials_returns_actionable_dns_record(self):
        def fail(_):raise ValueError('No account')
        result=dns.run(self.config,resolver=lambda _:dict(a=[],aaaa=[]),provisioner=fail)
        self.assertFalse(result['ready']);self.assertIn('154.16.170.86',result['message']);self.assertEqual(result['state'],'manual_required')
    def test_provisions_once_then_rechecks(self):
        calls=[];lookups=[dict(a=[],aaaa=[]),dict(a=['154.16.170.86'],aaaa=[])]
        result=dns.run(self.config,resolver=lambda _:lookups.pop(0),provisioner=lambda c:calls.append(c) or True)
        self.assertEqual(len(calls),1);self.assertTrue(result['ready']);self.assertTrue(result['changed'])
    def test_stale_ipv6_is_reported_without_deleting_records(self):
        result=dns.run(self.config,resolver=lambda _:dict(a=['154.16.170.86'],aaaa=['2001:db8::99']),provisioner=lambda _:self.fail('Do not alter IPv6 records'))
        self.assertFalse(result['ready']);self.assertIn('IPv6',result['message'])
    def test_provider_failure_does_not_leak_secret(self):
        def fail(_):raise RuntimeError('API key SECRET-VALUE')
        result=dns.run(self.config,resolver=lambda _:dict(a=[],aaaa=[]),provisioner=fail)
        self.assertNotIn('SECRET-VALUE',str(result))

certificate=load('certificate_check','server/check-certificate.py')
class CertificateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder=tempfile.TemporaryDirectory();cls.cert=Path(cls.folder.name)/'cert.pem'
        subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-keyout',str(Path(cls.folder.name)/'key.pem'),'-out',str(cls.cert),'-days','2','-subj','/CN=kakakin.africandroid.world','-addext','subjectAltName=DNS:kakakin.africandroid.world'],check=True,capture_output=True)
    @classmethod
    def tearDownClass(cls):cls.folder.cleanup()
    def test_correct_certificate_is_valid(self):self.assertTrue(certificate.check(self.cert,'kakakin.africandroid.world',0)['valid'])
    def test_hostname_mismatch_is_rejected_even_when_openssl_returns_zero(self):self.assertFalse(certificate.check(self.cert,'wrong.example',0)['valid'])
    def test_near_expiry_requires_renewal(self):self.assertFalse(certificate.check(self.cert,'kakakin.africandroid.world',604800)['valid'])
    def test_missing_certificate_is_reported(self):self.assertFalse(certificate.check(Path(self.folder.name)/'absent.pem','kakakin.africandroid.world',0)['valid'])

if __name__=='__main__':unittest.main()
