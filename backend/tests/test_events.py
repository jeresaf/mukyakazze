import pytest
from django.contrib.auth.models import Group
from django.db import DatabaseError, transaction
from django.test import Client
from accounts.models import User, AuditEvent
from accounts.services import provision_roles
from catalog.models import Category, Country, City, Area, Venue, Promoter
from events.models import Occurrence, Price, Verification

pytestmark = pytest.mark.django_db
BASE='/api/v1/admin/'
URL=BASE+'events/'
PASSWORD='Event-test-only-49!'

@pytest.fixture
def catalog():
    category=Category.objects.get(code='MUSIC')
    city=City.objects.get(name='Kampala',country__name='Uganda')
    area=Area.objects.create(city=city,name='Test area')
    venue=Venue.objects.create(area=area,name='Test venue')
    promoter=Promoter.objects.create(name='Test promoter')
    return category,venue,promoter

@pytest.fixture
def full(catalog):
    category,venue,promoter=catalog
    return {'title':'Synthetic test event','category_id':str(category.pk),'venue_id':str(venue.pk),'promoter_id':str(promoter.pk),'editorial_date':'2026-12-11','starts_at':'2026-12-12T00:30:00+03:00','ends_at':'2026-12-12T02:00:00+03:00','source':'Synthetic promoter confirmation','price_type':'UNKNOWN','amount_ugx':None}

def staff(role, name):
    provision_roles()
    user=User.objects.create_user(name+'@example.test',PASSWORD)
    user.groups.add(Group.objects.get(name=role))
    c=Client(enforce_csrf_checks=True)
    token=c.get(BASE+'auth/session/').json()['csrf_token']
    r=c.post(BASE+'auth/login/',{'email':user.email,'password':PASSWORD},content_type='application/json',HTTP_X_CSRFTOKEN=token)
    assert r.status_code==200,r.content
    return c,r.json()['csrf_token'],user

def write(c,t,method,url,body):
    return getattr(c,method)(url,body,content_type='application/json',HTTP_X_CSRFTOKEN=t)

def draft(c,t,body):
    r=write(c,t,'post',URL,body)
    assert r.status_code==201,r.content
    return r.json()

def action(c,t,row,name,**extra):
    return write(c,t,'post',URL+row['id']+'/actions/',{'action':name,'expected_version':row['version'],**extra})

def successful(r):
    assert r.status_code==200,r.content
    return r.json()

def test_incomplete_draft_and_edit(full):
    c,t,_=staff('Collector','collector')
    row=draft(c,t,{'title':'Incomplete'})
    assert row['status']=='DRAFT' and row['price_type']=='UNKNOWN' and row['amount_ugx'] is None
    assert action(c,t,row,'submit').status_code==400
    changed=successful(write(c,t,'patch',URL+row['id']+'/',{**full,'expected_version':1}))
    assert changed['starts_at']=='2026-12-12T00:30:00+03:00'
    assert changed['editorial_date']=='2026-12-11'
    assert write(c,t,'patch',URL+row['id']+'/',{'title':'stale','expected_version':1}).status_code==409
    assert successful(action(c,t,changed,'submit'))['status']=='SUBMITTED'

def test_workflow_and_history(full):
    c,t,owner=staff('Collector','owner'); v,vt,verifier=staff('Verifier','reviewer')
    row=draft(c,t,full); row=successful(action(c,t,row,'submit'))
    assert write(c,t,'patch',URL+row['id']+'/',{'title':'changed','expected_version':row['version']}).status_code==409
    assert action(c,t,row,'review',reason='Review').status_code==403
    row=successful(action(v,vt,row,'review',reason='Review started'))
    assert action(v,vt,row,'verify',reason='Confirmed').status_code==400
    row=successful(action(v,vt,row,'verify',reason='Confirmed',method='Promoter call',evidence='Synthetic reference'))
    assert row['status']=='VERIFIED' and row['amount_ugx'] is None
    history=v.get(URL+row['id']+'/history/').json()
    assert history['count']==3
    assert history['results'][0]['actor_id']==str(verifier.pk)
    assert AuditEvent.objects.filter(actor=verifier,action='event_verify',target_id=row['id']).exists()
    row=successful(action(v,vt,row,'cancel',reason='Cancelled by organiser'))
    assert row['is_cancelled'] and row['status']=='VERIFIED'
    row=successful(action(v,vt,row,'restore',reason='Rescheduled'))
    assert not row['is_cancelled'] and row['status']=='DRAFT'

def test_owner_scope_and_publisher(full):
    c,t,_=staff('Collector','one'); other,ot,_=staff('Collector','two'); v,vt,_=staff('Verifier','v'); p,pt,_=staff('Publisher','pub')
    row=draft(c,t,full); detail=URL+row['id']+'/'
    assert other.get(detail).status_code==404
    assert other.get(detail+'history/').status_code==404
    assert write(other,ot,'patch',detail,{'title':'unauthorized','expected_version':1}).status_code==404
    assert other.get(URL).json()['count']==0
    assert v.get(detail).status_code==404
    assert p.get(URL).status_code==403
    row=successful(action(c,t,row,'submit'))
    assert v.get(detail).status_code==200
    assert write(v,vt,'patch',detail,{'title':'unauthorized','expected_version':row['version']}).status_code==403

def test_no_self_review(full):
    c,t,_=staff('Editor','editor')
    row=successful(action(c,t,draft(c,t,full),'submit'))
    assert action(c,t,row,'review',reason='Own event').status_code==403

def test_return_correct_resubmit(full):
    c,t,_=staff('Collector','owner'); v,vt,_=staff('Verifier','v')
    row=successful(action(c,t,draft(c,t,full),'submit'))
    row=successful(action(v,vt,row,'return',reason='Correct price'))
    assert row['status']=='RETURNED'
    row=successful(write(c,t,'patch',URL+row['id']+'/',{'expected_version':row['version'],'price_type':'PAID','amount_ugx':25000}))
    assert row['status']=='DRAFT' and row['amount_ugx']==25000
    row=successful(action(c,t,row,'submit'))
    assert row['status']=='SUBMITTED'

@pytest.mark.parametrize('overrides',[
    {'price_type':'FREE','amount_ugx':None}, {'price_type':'UNKNOWN','amount_ugx':0}, {'price_type':'PAID','amount_ugx':0},
    {'ends_at':'2026-12-11T23:00:00+03:00'}, {'editorial_date':'2026-12-10'}, {'status':'VERIFIED'}, {'ticket_url':'ftp://example.test/ticket'}
])
def test_invalid_inputs(full,overrides):
    c,t,_=staff('Collector','owner')
    assert write(c,t,'post',URL,{**full,**overrides}).status_code==400
    assert Occurrence.objects.count()==0

def test_duplicate_archived_ref_and_free(full,catalog):
    c,t,_=staff('Collector','owner')
    row=draft(c,t,{**full,'price_type':'FREE','amount_ugx':0})
    assert row['amount_ugx']==0
    assert write(c,t,'post',URL,{**full,'title':full['title'].upper()}).status_code==400
    assert c.get(URL+'?search=Synthetic&from=2026-12-11&to=2026-12-11').json()['count']==1
    category,_,_=catalog;category.is_active=False;category.save()
    assert action(c,t,row,'submit').status_code==400

def test_reopen_and_decision_append_only(full):
    c,t,_=staff('Administrator','admin'); v,vt,_=staff('Verifier','v')
    row=successful(action(c,t,draft(c,t,full),'submit'))
    row=successful(action(v,vt,row,'review',reason='Review'))
    row=successful(action(v,vt,row,'reject',reason='Synthetic rejection'))
    assert row['status']=='REJECTED'
    row=successful(action(c,t,row,'reopen',reason='New information'))
    assert row['status']=='DRAFT'
    record=Verification.objects.filter(occurrence_id=row['id']).first()
    with pytest.raises(DatabaseError), transaction.atomic():
        Verification.objects.filter(pk=record.pk).update(reason='Changed')
    with pytest.raises(DatabaseError), transaction.atomic():
        Verification.objects.filter(pk=record.pk).delete()

def test_csrf_and_anonymous(full):
    c,t,_=staff('Collector','owner')
    assert Client().get(URL).status_code==403
    assert c.post(URL,full,content_type='application/json').status_code==403
