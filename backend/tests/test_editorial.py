from datetime import date, datetime, timezone
import pytest
from django.contrib.auth.models import Group
from django.test import Client
from accounts.models import User, AuditEvent
from accounts.services import provision_roles
from catalog.models import Category, City, Area, Venue
from events.models import Event, Occurrence, Price
from editorial.models import Issue, IssueEvent

pytestmark=pytest.mark.django_db
BASE='/api/v1/admin/'
URL=BASE+'issues/'
PASSWORD='Editorial-test-only-49!'


def staff(role):
    provision_roles()
    user=User.objects.create_user(role.lower()+'@example.test',PASSWORD)
    user.groups.add(Group.objects.get(name=role))
    c=Client(enforce_csrf_checks=True)
    token=c.get(BASE+'auth/session/').json()['csrf_token']
    r=c.post(BASE+'auth/login/',{'email':user.email,'password':PASSWORD},content_type='application/json',HTTP_X_CSRFTOKEN=token)
    assert r.status_code==200,r.content
    return c,r.json()['csrf_token'],user


def write(c,t,method,url,body):
    return getattr(c,method)(url,body,content_type='application/json',HTTP_X_CSRFTOKEN=t)


def issue(c,t):
    r=write(c,t,'post',URL,{'number':1,'week_start':'2026-12-10'})
    assert r.status_code==201,r.content
    return r.json()


def roster(c,t,i,entries):
    return write(c,t,'put',URL+i['id']+'/roster/',{'expected_version':i['version'],'entries':entries})


def entry(row,**kw):
    return {'occurrence_id':str(row.pk),'occurrence_version':row.version,**kw}


@pytest.fixture
def occurrences():
    user=User.objects.create_user('owner@example.test',PASSWORD)
    category=Category.objects.get(code='MUSIC')
    area=Area.objects.create(city=City.objects.get(name='Kampala',country__name='Uganda'),name='Synthetic area')
    venue=Venue.objects.create(name='Synthetic venue',area=area)
    def make(title,day,status='VERIFIED',cancelled=False):
        event=Event.objects.create(title=title,category=category,created_by=user)
        row=Occurrence.objects.create(event=event,venue=venue,editorial_date=date(2026,12,day),starts_at=datetime(2026,12,day,18,tzinfo=timezone.utc),status=status,is_cancelled=cancelled,submitted_by=user,source='Synthetic')
        Price.objects.create(occurrence=row)
        return row
    return [make('Eligible one',10),make('Eligible two',16),make('Outside',17),make('Cancelled',11,cancelled=True),make('Draft',12,'DRAFT')]


def test_issue_creation_and_validation():
    c,t,u=staff('Editor'); i=issue(c,t)
    assert i['week_end']=='2026-12-16' and i['grid_day']=='2026-12-11'
    assert i['status']=='DRAFT' and i['entries']==[]
    assert AuditEvent.objects.filter(actor=u,action='issue_created',target_id=i['id']).exists()
    for body in [{'number':1,'week_start':'2026-12-17'},{'number':2,'week_start':'2026-12-10'},{'number':2,'week_start':'2026-12-11'},{'number':2,'week_start':'2026-12-17','grid_day':'2026-12-24'}]:
        assert write(c,t,'post',URL,body).status_code==400
    assert Issue.objects.count()==1


@pytest.mark.parametrize('role',['Collector','Verifier','Publisher'])
def test_no_editorial_access(role):
    c,t,_=staff(role)
    assert c.get(URL).status_code==403
    assert write(c,t,'post',URL,{'number':1,'week_start':'2026-12-10'}).status_code==403
    assert c.get(BASE+'auth/session/').json()['permissions']['view_issues'] is False


def test_candidates_and_roster(occurrences):
    c,t,u=staff('Administrator'); i=issue(c,t)
    r=c.get(URL+i['id']+'/candidates/').json()
    assert {x['occurrence_id'] for x in r['results']}=={str(x.pk) for x in occurrences[:2]}
    r=roster(c,t,i,[entry(occurrences[0],rank=1,why_go='Synthetic pick',curator_playing=True,paid_feature=True),entry(occurrences[1])]); assert r.status_code==200,r.content
    updated=r.json(); assert updated['version']==2 and len(updated['entries'])==2
    assert updated['entries'][0]['rank']==1 and updated['entries'][0]['paid_feature']
    assert AuditEvent.objects.filter(actor=u,action='issue_roster_replaced',target_id=i['id']).exists()
    assert roster(c,t,i,[]).status_code==409
    r=roster(c,t,updated,[entry(occurrences[1],rank=1,why_go='New pick')]); assert r.status_code==200,r.content
    assert IssueEvent.objects.count()==1


def test_reject_invalid_selection_atomically(occurrences):
    c,t,_=staff('Editor'); i=issue(c,t)
    for row in occurrences[2:]:
        assert roster(c,t,i,[entry(occurrences[0]),entry(row)]).status_code==400
    for payload in [[entry(occurrences[0]),entry(occurrences[0])],[entry(occurrences[0],rank=1,why_go='A'),entry(occurrences[1],rank=1,why_go='B')],[entry(occurrences[0],rank=8,why_go='A')],[entry(occurrences[0],rank=1)],[entry(occurrences[0],why_go='A')]]:
        assert roster(c,t,i,payload).status_code==400
    assert IssueEvent.objects.count()==0
    assert Issue.objects.get(pk=i['id']).version==1


def test_stale_or_cancelled_selection_visible(occurrences):
    c,t,_=staff('Editor'); i=issue(c,t); row=occurrences[0]
    r=roster(c,t,i,[entry(row)]); assert r.status_code==200,r.content
    updated=r.json()
    Occurrence.objects.filter(pk=row.pk).update(version=2)
    detail=c.get(URL+i['id']+'/').json(); assert detail['entries'][0]['stale'] and detail['entries'][0]['eligible']
    assert roster(c,t,updated,[entry(row)]).status_code==409
    Occurrence.objects.filter(pk=row.pk).update(is_cancelled=True)
    assert c.get(URL+i['id']+'/').json()['entries'][0]['eligible'] is False
    assert roster(c,t,updated,[entry(row)]).status_code==400
    assert roster(c,t,updated,[]).status_code==200


def test_settings_and_csrf():
    c,t,_=staff('Editor'); i=issue(c,t); path=URL+i['id']+'/'
    assert Client().get(URL).status_code==403
    assert c.patch(path,{'expected_version':1,'picks_title':'New'},content_type='application/json').status_code==403
    assert write(c,t,'patch',path,{'expected_version':1,'week_start':'2026-12-17'}).status_code==400
    r=write(c,t,'patch',path,{'expected_version':1,'grid_day':'2026-12-12','picks_intro':'Synthetic intro'}); assert r.status_code==200,r.content
    assert r.json()['version']==2 and r.json()['grid_day']=='2026-12-12'
    assert write(c,t,'patch',path,{'expected_version':1,'picks_title':'Stale'}).status_code==409
