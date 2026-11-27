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

# Phase 03B.1: shared event identity, independent schedules and ticket tiers.
def repeat(c,t,row,dates):
    return write(c,t,'post',URL+row['id']+'/repeat/',{'expected_version':row['version'],'dates':dates})

def tiers(c,t,row,items):
    return write(c,t,'put',URL+row['id']+'/ticket-tiers/',{'expected_version':row['version'],'tiers':items})

VIP={'tier':'VIP','kind':'PAID','amount_ugx':50000,'note':'','ticket_url':''}

def test_repeat_overnight_shared_identity(full):
    c,t,u=staff('Collector','owner')
    row=draft(c,t,full)
    r=repeat(c,t,row,['2026-12-18','2026-12-25'])
    assert r.status_code==201,r.content
    data=r.json(); assert data['source']['version']==2 and data['source']['shared_event']
    assert len(data['created_ids'])==2
    child=c.get(URL+data['created_ids'][0]+'/').json()
    assert child['event_id']==row['event_id'] and child['status']=='DRAFT'
    assert child['starts_at']=='2026-12-19T00:30:00+03:00'
    assert child['ends_at']=='2026-12-19T02:00:00+03:00'
    assert child['editorial_date']=='2026-12-18'
    assert AuditEvent.objects.filter(actor=u,action='event_occurrence_created').count()==2
    assert repeat(c,t,row,['2027-01-01']).status_code==409
    changed=successful(write(c,t,'patch',URL+child['id']+'/',{'expected_version':1,'notes':'Changed session only','title':row['title']}))
    assert changed['notes']=='Changed session only'
    assert write(c,t,'patch',URL+child['id']+'/',{'expected_version':2,'title':'Changed shared title'}).status_code==400
    assert successful(action(c,t,changed,'submit'))['status']=='SUBMITTED'
    assert c.get(URL+row['id']+'/').json()['status']=='DRAFT'

def test_repeat_atomic_and_invalid_dates(full):
    c,t,_=staff('Collector','owner'); row=draft(c,t,full)
    draft(c,t,{**full,'editorial_date':'2026-12-25','starts_at':'2026-12-26T00:30:00+03:00','ends_at':'2026-12-26T02:00:00+03:00'})
    for dates in [['2026-12-18','2026-12-25'],['2026-12-11'],['2026-12-18','2026-12-18'],['2028-01-01'],[]]:
        assert repeat(c,t,row,dates).status_code==400
        assert Occurrence.objects.count()==2
        assert c.get(URL+row['id']+'/').json()['version']==1
    incomplete=draft(c,t,{'title':'Incomplete'})
    assert repeat(c,t,incomplete,['2026-12-18']).status_code==400

def test_repeat_scope_and_state(full):
    c,t,_=staff('Collector','owner'); a,at,_=staff('Administrator','admin'); other,ot,_=staff('Collector','other')
    row=draft(c,t,full)
    assert repeat(other,ot,row,['2026-12-18']).status_code==404
    assert repeat(a,at,row,['2026-12-18']).status_code==403
    row=successful(action(c,t,row,'submit'))
    assert repeat(c,t,row,['2026-12-18']).status_code==409

def test_ticket_tiers_replace_copy_and_audit(full):
    c,t,u=staff('Collector','owner'); row=draft(c,t,full)
    row=successful(tiers(c,t,row,[VIP,{'tier':'Early bird','kind':'FREE','amount_ugx':0}]))
    assert row['version']==2
    assert Price.objects.filter(occurrence_id=row['id']).count()==3
    assert AuditEvent.objects.filter(actor=u,action='event_ticket_tiers_updated',target_id=row['id']).exists()
    r=repeat(c,t,row,['2026-12-18']); assert r.status_code==201,r.content
    child=r.json()['created_ids'][0]; source=r.json()['source']
    assert Price.objects.filter(occurrence_id=child).count()==3
    assert Price.objects.get(occurrence_id=child,tier='VIP').amount_ugx==50000
    source=successful(tiers(c,t,source,[]))
    assert Price.objects.filter(occurrence_id=row['id']).count()==1
    assert Price.objects.filter(occurrence_id=child).count()==3
    assert c.get(URL+child+'/ticket-tiers/').json()['version']==1

def test_ticket_tier_validation_and_stale(full):
    c,t,_=staff('Collector','owner'); row=draft(c,t,full)
    for items in [[VIP,{**VIP,'tier':'vip'}],[{**VIP,'tier':'General'}],[{**VIP,'amount_ugx':0}],[{**VIP,'kind':'CONDITIONAL_FREE','amount_ugx':None}],[{**VIP,'ticket_url':'ftp://example.test/t'}]]:
        assert tiers(c,t,row,items).status_code==400
        assert Price.objects.filter(occurrence_id=row['id']).count()==1
    updated=successful(tiers(c,t,row,[VIP])); assert updated['version']==2
    assert tiers(c,t,row,[]).status_code==409
    assert Price.objects.filter(occurrence_id=row['id']).count()==2

def test_tier_scope_and_locked_state(full):
    c,t,_=staff('Collector','owner'); other,ot,_=staff('Collector','other'); v,vt,_=staff('Verifier','reviewer')
    row=draft(c,t,full)
    assert other.get(URL+row['id']+'/ticket-tiers/').status_code==404
    assert tiers(other,ot,row,[VIP]).status_code==404
    row=successful(action(c,t,row,'submit'))
    assert v.get(URL+row['id']+'/ticket-tiers/').status_code==200
    assert tiers(v,vt,row,[VIP]).status_code==403
    assert tiers(c,t,row,[VIP]).status_code==409

def test_scoped_statistics_and_filters(full,catalog):
    c,t,_=staff('Collector','owner'); other,ot,_=staff('Collector','other'); a,at,_=staff('Administrator','admin'); p,pt,_=staff('Publisher','pub')
    row=draft(c,t,full); draft(other,ot,{'title':'Another private draft'})
    category,venue,promoter=catalog
    for key,value in [('category',category.pk),('venue',venue.pk),('area',venue.area_id),('promoter',promoter.pk),('event',row['event_id'])]:
        assert c.get(URL+'?'+key+'='+str(value)).json()['count']==1
    assert c.get(URL+'?cancelled=invalid').status_code==400
    assert c.get(URL+'?venue=invalid').status_code==400
    assert c.get(URL+'statistics/').json()['active']==1
    assert a.get(URL+'statistics/').json()['active']==2
    assert p.get(URL+'statistics/').status_code==403
    row=successful(action(a,at,row,'cancel',reason='Synthetic cancellation'))
    assert c.get(URL+'statistics/').json()['cancelled']==1
    assert c.get(URL+'statistics/').json()['active']==0
    assert c.get(URL+'?cancelled=true').json()['count']==1
    assert c.get(URL+'?cancelled=false').json()['count']==0


def assign(c,t,row,collector=None,reviewer=None):
    return write(c,t,'put',URL+row['id']+'/assignments/',{'expected_version':row['version'],'collector_id':str(collector.pk) if collector else None,'reviewer_id':str(reviewer.pk) if reviewer else None})


def test_assignment_scope_and_reassignment(full):
    owner,ot,_=staff('Collector','owner'); c,t,u=staff('Collector','assigned'); other,_,_=staff('Collector','other'); a,at,admin=staff('Administrator','admin')
    row=draft(owner,ot,full); detail=URL+row['id']+'/'
    assert c.get(detail).status_code==404
    assert c.get(URL+'assignment-choices/?role=collector').status_code==403
    assert assign(owner,ot,row,u).status_code==403
    row=successful(assign(a,at,row,u))
    assert c.get(detail).status_code==200 and other.get(detail).status_code==404
    assert c.get(URL+'?assigned=collection').json()['count']==1
    assert c.get(detail+'assignments/').json()['collector_id']==str(u.pk)
    assert 'collector_name' not in c.get(detail+'assignments/').json()
    assert assign(a,at,{**row,'version':1},u).status_code==409
    row=successful(write(c,t,'patch',detail,{'expected_version':row['version'],'notes':'Assigned staff edit'}))
    row=successful(assign(a,at,row))
    assert c.get(detail).status_code==404 and owner.get(detail).status_code==200
    assert AuditEvent.objects.filter(actor=admin,target_id=row['id'],action='event_assignments_updated').count()==2


def test_assigned_review_and_independent_editor(full):
    c,t,_=staff('Collector','owner'); a,at,admin=staff('Administrator','admin'); v,vt,verifier=staff('Verifier','reviewer'); other,ot,_=staff('Verifier','other')
    row=draft(c,t,full)
    row=successful(write(a,at,'patch',URL+row['id']+'/',{'expected_version':row['version'],'notes':'Editor contribution'}))
    assert assign(a,at,row,reviewer=admin).status_code==400
    row=successful(assign(a,at,row,reviewer=verifier))
    row=successful(action(c,t,row,'submit'))
    assert v.get(URL+'?assigned=review').json()['count']==1
    assert action(other,ot,row,'review',reason='Not assigned').status_code==403
    assert action(a,at,row,'review',reason='Contributor').status_code==403
    row=successful(action(v,vt,row,'review',reason='Assigned review'))
    row=successful(action(v,vt,row,'verify',reason='Independent',method='Call',evidence='Synthetic'))
    assert assign(a,at,row).status_code==409


def test_assignment_role_validation(full):
    a,t,admin=staff('Administrator','admin'); c,ct,collector=staff('Collector','collector'); p,pt,publisher=staff('Publisher','pub'); v,vt,verifier=staff('Verifier','reviewer')
    row=draft(a,t,full)
    assert assign(a,t,row,collector=publisher).status_code==400
    assert assign(a,t,row,reviewer=collector).status_code==400
    assert assign(a,t,row,collector=verifier,reviewer=verifier).status_code==400
    assert assign(a,t,row,reviewer=admin).status_code==400
    verifier.is_active=False;verifier.save(update_fields=['is_active'])
    assert assign(a,t,row,reviewer=verifier).status_code==400
    choices=a.get(URL+'assignment-choices/?role=reviewer').json()['results']
    assert str(verifier.pk) not in [x['id'] for x in choices]


def make_event_image(c,t,kind='photo'):
    from io import BytesIO
    from PIL import Image
    from django.core.files.uploadedfile import SimpleUploadedFile
    b=BytesIO();Image.new('RGB',(16,12),'blue').save(b,format='PNG')
    response=c.post(BASE+'media/',{'name':'Synthetic '+kind,'kind':kind,'file':SimpleUploadedFile('image.png',b.getvalue(),content_type='image/png')},HTTP_X_CSRFTOKEN=t)
    assert response.status_code==201,response.content
    return response.json()['id']


def attachments(c,t,row,ids):
    return write(c,t,'put',URL+row['id']+'/attachments/',{'expected_version':row['version'],'asset_ids':ids})


def test_attachment_order_scope_and_repeated_copy(full):
    a,at,_=staff('Administrator','admin'); c,t,_=staff('Collector','owner'); other,ot,_=staff('Collector','other')
    photo=make_event_image(a,at);poster=make_event_image(a,at,'poster')
    row=draft(c,t,full);detail=URL+row['id']+'/'
    assert other.get(detail+'attachments/').status_code==404
    row=successful(attachments(c,t,row,[photo,poster]))
    assert [i['asset_id'] for i in c.get(detail+'attachments/').json()['images']]==[photo,poster]
    assert attachments(c,t,{**row,'version':1},[]).status_code==409
    row=successful(attachments(c,t,row,[poster,photo]))
    r=write(c,t,'post',detail+'repeat/',{'expected_version':row['version'],'dates':['2026-12-18']})
    assert r.status_code==201,r.content
    child=r.json()['created_ids'][0]
    assert [i['asset_id'] for i in c.get(URL+child+'/attachments/').json()['images']]==[poster,photo]
    assert c.get(URL+child+'/assignments/').json()['collector_id'] is None
    assert AuditEvent.objects.filter(target_id=row['id'],action='event_attachments_updated').count()==2


def test_attachment_validation_and_archived_asset(full):
    a,at,_=staff('Administrator','admin'); c,t,_=staff('Collector','owner')
    photo=make_event_image(a,at);poster=make_event_image(a,at,'poster');logo=make_event_image(a,at,'logo')
    row=draft(c,t,{**full,'poster_id':poster})
    for ids in ([photo,photo],[poster],[logo],[photo]*13):
        assert attachments(c,t,row,ids).status_code==400
    row=successful(attachments(c,t,row,[photo]))
    assert write(a,at,'patch',BASE+'media/'+photo+'/',{'expected_version':1,'is_active':False}).status_code==200
    assert action(c,t,row,'submit').status_code==400
    row=successful(attachments(c,t,row,[]))
    row=successful(action(c,t,row,'submit'))
    assert attachments(c,t,row,[]).status_code==409


def test_media_editor_cannot_verify_after_reassignment(full):
    c,t,_=staff('Collector','owner'); a,at,_=staff('Administrator','admin'); v,vt,verifier=staff('Verifier','contributor'); other,ot,_=staff('Verifier','other')
    photo=make_event_image(a,at); row=draft(c,t,full)
    row=successful(assign(a,at,row,collector=verifier))
    row=successful(attachments(v,vt,row,[photo]))
    row=successful(assign(a,at,row))
    assert assign(a,at,row,reviewer=verifier).status_code==400
    row=successful(action(c,t,row,'submit'))
    assert action(v,vt,row,'review',reason='Former contributor').status_code==403
    assert action(other,ot,row,'review',reason='Independent').status_code==200
