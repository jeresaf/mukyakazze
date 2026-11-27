import hashlib
from io import BytesIO
import pytest
from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.contrib.auth.models import Group
from accounts.models import User, AuditEvent
from accounts.services import provision_roles
from catalog.models import MediaAsset, Sponsor

pytestmark = pytest.mark.django_db
BASE='/api/v1/admin/'
PASSWORD='Synthetic-media-test-49!'

def session(role):
    provision_roles()
    user=User.objects.create_user(role.lower()+'@example.test',PASSWORD)
    user.groups.add(Group.objects.get(name=role))
    c=Client(enforce_csrf_checks=True)
    token=c.get(BASE+'auth/session/').json()['csrf_token']
    r=c.post(BASE+'auth/login/',{'email':user.email,'password':PASSWORD},content_type='application/json',HTTP_X_CSRFTOKEN=token)
    assert r.status_code==200,r.content
    return c,r.json()['csrf_token']

def image_file(fmt='PNG'):
    buf=BytesIO(); Image.new('RGB',(16,12),'yellow').save(buf,format=fmt)
    return SimpleUploadedFile('sample.png',buf.getvalue(),content_type='image/png')

def upload(c,t,file=None,**extra):
    return c.post(BASE+'media/',{'name':'Synthetic image','kind':'poster','file':file if file is not None else image_file(),**extra},HTTP_X_CSRFTOKEN=t)

def patch(c,t,path,data):
    return c.patch(BASE+path,data,content_type='application/json',HTTP_X_CSRFTOKEN=t)

@pytest.mark.parametrize('role',['Administrator','Editor','Collector','Verifier','Publisher'])
def test_permissions(role):
    c,t=session(role)
    allowed=role in ('Administrator','Editor')
    flags=c.get(BASE+'auth/session/').json()['permissions']
    assert flags['view_media'] and flags['manage_media']==allowed
    assert c.get(BASE+'sponsors/').status_code==200
    assert c.get(BASE+'media/').status_code==200
    r=c.post(BASE+'sponsors/',{'name':'Synthetic sponsor'},content_type='application/json',HTTP_X_CSRFTOKEN=t)
    assert r.status_code==(201 if allowed else 403),r.content
    r=upload(c,t)
    assert r.status_code==(201 if allowed else 403),r.content

def test_sponsor_private_duplicate_archive():
    c,t=session('Administrator'); reader,_=session('Collector')
    r=c.post(BASE+'sponsors/',{'name':'Synthetic sponsor','contact_email':'private@example.test'},content_type='application/json',HTTP_X_CSRFTOKEN=t)
    assert r.status_code==201,r.content
    path='sponsors/'+r.json()['id']+'/'
    assert 'contact_email' not in reader.get(BASE+path).json()
    assert 'private@example.test' not in str(AuditEvent.objects.get(action='sponsor_created').details)
    assert c.post(BASE+'sponsors/',{'name':'synthetic SPONSOR'},content_type='application/json',HTTP_X_CSRFTOKEN=t).status_code==400
    assert patch(c,t,path,{'expected_version':1,'is_active':False}).status_code==200
    assert patch(c,t,path,{'expected_version':2,'is_active':True}).status_code==200
    assert Sponsor.objects.get().is_active

def test_media_lifecycle_and_content():
    c,t=session('Administrator'); reader,_=session('Collector')
    r=upload(c,t,alt_text='Sample'); assert r.status_code==201,r.content
    row=r.json(); path='media/'+row['id']+'/'
    assert 'content' not in row and row['width']==16 and row['height']==12
    response=reader.get(BASE+path+'content/'); assert response.status_code==200
    assert response['Content-Type']=='image/png' and response['Cache-Control']=='private, no-store'
    assert hashlib.sha256(response.content).hexdigest()==row['sha256']
    assert Client().get(BASE+path+'content/').status_code==403
    assert patch(c,t,path,{'expected_version':1,'name':'Renamed'}).status_code==200
    assert patch(c,t,path,{'expected_version':1,'name':'Stale'}).status_code==409
    assert patch(c,t,path,{'expected_version':2,'is_active':False}).status_code==200
    assert reader.get(BASE+path+'content/').status_code==404
    assert c.get(BASE+'media/?status=archived&kind=poster&search=Renamed').json()['count']==1
    assert patch(c,t,path,{'expected_version':3,'is_active':True}).status_code==200
    assert AuditEvent.objects.filter(action='media_restored',target_id=row['id']).exists()

def test_media_rejects_invalid_and_protected_fields():
    c,t=session('Editor')
    for f in (SimpleUploadedFile('bad.png',b'<svg/>'),image_file('GIF'),SimpleUploadedFile('big.png',b'x'*(5*1024*1024+1))):
        assert upload(c,t,f).status_code==400
    assert upload(c,t,sha256='fake').status_code==400
    assert upload(c,t,kind='invalid').status_code==400
    assert c.post(BASE+'media/',{'name':'No CSRF','kind':'poster','file':image_file()}).status_code==403
    assert MediaAsset.objects.count()==0
