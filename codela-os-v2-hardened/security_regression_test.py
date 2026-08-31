"""Security regression suite. Run after installing requirements: python security_regression_test.py"""
import os,tempfile
os.environ.setdefault("CODELA_ENV","testing")
import database
from app import create_app

def main():
 fd,path=tempfile.mkstemp(prefix="codela-sec-",suffix=".db");os.close(fd);database.DB_PATH=path;database.USE_POSTGRES=False;database.init_db();app=create_app();app.config.update(TESTING=True);c=app.test_client()
 def reg(email,company):
  r=c.post('/api/auth/register',json={'name':'Test User','email':email,'password':'CorrectHorseBattery9!','company_name':company});assert r.status_code==201,r.get_json();return r.get_json()
 a,b=reg('a@example.test','A'),reg('b@example.test','B');AH={'Authorization':'Bearer '+a['access_token']};BH={'Authorization':'Bearer '+b['access_token']}
 r=c.post('/api/leads',headers=BH,json={'name':'B Lead'});assert r.status_code==201;r=r.get_json();lid=r['id']
 for method,url_path,payload in [('get',f'/api/leads/{lid}',None),('patch',f'/api/leads/{lid}',{'name':'stolen'})]:
  r=getattr(c,method)(url_path,headers=AH,**({'json':payload} if payload else {}));assert r.status_code in (403,404),(method,r.status_code,r.get_json())
 # FK IDOR
 r=c.post('/api/leads',headers=AH,json={'name':'bad','assigned_sales_id':b['user']['id']});assert r.status_code==400
 r=c.post('/api/clients',headers=BH,json={'name':'B Client'});assert r.status_code==201;cid=r.get_json()['id']
 r=c.post('/api/projects',headers=BH,json={'name':'B Project','client_id':cid});assert r.status_code==201;pid=r.get_json()['id']
 r=c.get(f'/api/projects/{pid}',headers=AH);assert r.status_code in (403,404)
 r=c.post('/api/communication/send',headers=AH,json={'channel':'whatsapp','to':'+201','body':'x','client_id':cid});assert r.status_code==400
 # auth lifecycle
 r=c.post('/api/auth/login',json={'email':'a@example.test','password':'CorrectHorseBattery9!'});assert r.status_code==200;tok=r.get_json()['access_token'];ref=r.get_json()['refresh_token'];h={'Authorization':'Bearer '+tok}
 r=c.post('/api/auth/refresh',json={'refresh_token':ref});assert r.status_code==200;newref=r.get_json()['refresh_token'];assert newref!=ref
 r=c.post('/api/auth/refresh',json={'refresh_token':ref});assert r.status_code==401
 r=c.post('/api/auth/logout',headers={'Authorization':'Bearer '+r.get_json().get('access_token','')},json={'refresh_token':newref}) if False else c.post('/api/auth/logout',headers={'Authorization':'Bearer '+tok},json={'refresh_token':newref});assert r.status_code==200
 r=c.get('/api/auth/me',headers={'Authorization':'Bearer '+tok});assert r.status_code==401
 # validation + headers
 r=c.post('/api/auth/login',json={'email':'a@example.test','password':'x','unexpected':'x'});assert r.status_code==400
 r=c.get('/api/health',headers={'Origin':'https://evil.example'});assert r.headers.get('Access-Control-Allow-Origin')!='*';assert r.headers.get('X-Content-Type-Options')=='nosniff';assert 'Content-Security-Policy' in r.headers;assert 'Permissions-Policy' in r.headers;assert r.headers.get('X-Request-ID')
 os.unlink(path);print('PASS: tenant isolation, FK IDOR, refresh rotation, logout revocation, validation and security headers')
if __name__=='__main__':main()
