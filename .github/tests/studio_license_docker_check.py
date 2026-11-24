"""Opt-in: real Compose rendering + real Nginx TLS + a recording backend.

No production License Key is used and no activation is claimed. Requires Docker,
openssl, python:3.11-slim and nginx:alpine. All containers are removed in finally.
"""
import json
import os
from pathlib import Path
import shutil
import ssl
import subprocess
import tempfile
import time
import urllib.request
import uuid
from test_studio_license import extract, ROOT, CALLBACK

def command(args):
    p=subprocess.run(args,text=True,capture_output=True)
    if p.returncode: raise RuntimeError(' '.join(args)+'\n'+p.stderr)
    return p.stdout.strip()

def check():
    name='studio-license-check-'+uuid.uuid4().hex[:8]
    proxy=name+'-nginx'
    with tempfile.TemporaryDirectory(prefix='studio-license-check-') as temp:
        root=Path(temp)
        domain=extract(os.environ.get('INSTALLER_UNDER_TEST',ROOT/'deploy.sh'),root)
        for file in ('.env.studio','.env.middleware','docker-compose.studio.yaml'):
            shutil.copyfile(ROOT/file,root/file)
        # Test the missing settings in an old deployment too.
        domain.ops.edit_env(root/'.env.studio',{'LICENSE_HUB_API_URL':'','LICENSE_HUB_WEBHOOK_URL':''})
        (root/'backend.py').write_text('''import json, os
from http.server import BaseHTTPRequestHandler, HTTPServer
class Handler(BaseHTTPRequestHandler):
 def do_POST(self):
  body=self.rfile.read(int(self.headers.get('Content-Length','0'))).decode()
  data=dict(path=self.path,body=body,proto=self.headers.get('X-Forwarded-Proto'),
            hub=os.environ['LICENSE_HUB_API_URL'],callback=os.environ['LICENSE_HUB_WEBHOOK_URL'])
  self.send_response(200); self.end_headers(); self.wfile.write(json.dumps(data).encode())
HTTPServer(('0.0.0.0',12001),Handler).serve_forever()
''')
        cert=root/'cert.pem'; key=root/'key.pem'
        command(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-days','1','-subj','/CN=studio.example.com',
                 '-addext','subjectAltName=DNS:studio.example.com,DNS:new.example.com,IP:127.0.0.1',
                 '-keyout',str(key),'-out',str(cert)])
        for host in ('studio.example.com','new.example.com'):
            dest=root/'certs'/host; dest.mkdir(parents=True)
            shutil.copyfile(cert,dest/'fullchain.pem'); shutil.copyfile(key,dest/'privkey.pem')
        active=False
        recreates=[]
        def start_backend():
            cfg=json.loads(command(['docker','compose','--env-file',str(root/'.env.middleware'),
                '--env-file',str(root/'.env.studio'),'-f',str(root/'docker-compose.studio.yaml'),'config','--format','json']))
            env=cfg['services']['studio']['environment']
            args=['docker','run','-d','--name',name,'-p','127.0.0.1::443','-v',str(root)+':/fixture:ro']
            for field in ('LICENSE_HUB_API_URL','LICENSE_HUB_WEBHOOK_URL'):
                args+=['--env',field+'='+env[field]]
            command(args+['python:3.11-slim','python','/fixture/backend.py'])
        def capture(args):
            if args[:2]==['docker','ps']:
                return name if active and 'label=com.docker.compose.service=studio' in args else ''
            if 'printenv' in args: return command(['docker','exec',name,'printenv',args[-1]])
            raise AssertionError(args)
        def up(group,services,**kwargs):
            assert group=='studio' and services==['studio'] and kwargs['recreate']
            command(['docker','rm','-f',proxy]); command(['docker','rm','-f',name])
            start_backend(); recreates.append(True)
        domain.ops.capture=capture
        domain.ops.up=up
        def request(host):
            (root/'site.conf').write_text(domain.nginx_text(host,12000,True,'studio'))
            args=['docker','run','--rm','--network','container:'+name,
                  '-v',str(root/'site.conf')+':/etc/nginx/conf.d/default.conf:ro',
                  '-v',str(root/'certs')+':/etc/letsencrypt/live:ro','nginx:alpine','nginx','-t']
            command(args)
            command(['docker','run','-d','--name',proxy,'--network','container:'+name,
                     '-v',str(root/'site.conf')+':/etc/nginx/conf.d/default.conf:ro',
                     '-v',str(root/'certs')+':/etc/letsencrypt/live:ro','nginx:alpine'])
            port=command(['docker','port',name,'443/tcp']).rsplit(':',1)[1]
            req=urllib.request.Request('https://127.0.0.1:'+port+CALLBACK+'?test=1',
                data=b'{"test":"not-a-license"}',headers={'Host':host,'Content-Type':'application/json'})
            ctx=ssl.create_default_context(cafile=str(cert))
            for attempt in range(30):
                try:
                    with urllib.request.urlopen(req,context=ctx,timeout=3) as response:
                        result=json.load(response)
                    break
                except OSError:
                    if attempt==29: raise
                    time.sleep(.2)
            assert result['path']==CALLBACK+'?test=1',result
            assert result['body']=='{"test":"not-a-license"}',result
            assert result['proto']=='https',result
            assert result['hub']=='https://license-hub.aos.work',result
            expected=domain.ops.read_env(root/'.env.studio')['LICENSE_HUB_WEBHOOK_URL']
            assert result['callback']==expected,result
            domain.verify_studio_license()
            return result
        try:
            domain.apply_urls('studio','studio.example.com')
            start_backend(); active=True
            request('studio.example.com')
            domain.apply_urls('studio','new.example.com')
            result=request('new.example.com')
            assert result['callback']=='https://new.example.com'+CALLBACK
            domain.ops.edit_env(root/'.env.studio',{'LICENSE_HUB_WEBHOOK_URL':'https://custom.example.com/callback'})
            domain.apply_urls('studio','studio.example.com')
            result=request('studio.example.com')
            assert result['callback']=='https://custom.example.com/callback'
            assert len(recreates)==2
            print('PASS: real Compose env injection, backend recreation, TLS POST path/body/proto forwarding, custom callback preservation')
        finally:
            for container in (proxy,name):
                subprocess.run(['docker','rm','-f',container],capture_output=True)

if __name__=='__main__': check()
