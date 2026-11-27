import pytest
from django.test import Client
from django.contrib.auth.models import Group
from accounts.models import User, AuditEvent
from accounts.services import provision_roles

BASE='/api/v1/admin/'
PASSWORD='Strong-example-only-49!'
pytestmark=pytest.mark.django_db

@pytest.fixture
def staff():
    provision_roles()
    admin=User.objects.create_user('admin@example.test',PASSWORD,display_name='Admin')
    admin.groups.add(Group.objects.get(name='Administrator'))
    collector=User.objects.create_user('collector@example.test',PASSWORD,display_name='Collector')
    collector.groups.add(Group.objects.get(name='Collector'))
    return admin,collector

def signed_in(user):
    c=Client(enforce_csrf_checks=True)
    token=c.get(BASE+'auth/session/').json()['csrf_token']
    response=c.post(BASE+'auth/login/',{'email':user.email,'password':PASSWORD},content_type='application/json',HTTP_X_CSRFTOKEN=token)
    assert response.status_code==200,response.content
    return c,response.json()['csrf_token']

def test_anonymous_and_csrf(staff):
    c=Client(enforce_csrf_checks=True)
    assert c.get(BASE+'users/').status_code==403
    assert c.post(BASE+'auth/login/',{'email':staff[0].email,'password':PASSWORD},content_type='application/json').status_code==403

def test_login_rotates_session_and_logout(staff):
    c=Client(enforce_csrf_checks=True)
    session=c.session; session['prelogin']='value'; session.save(); old=c.cookies['sessionid'].value
    token=c.get(BASE+'auth/session/').json()['csrf_token']
    r=c.post(BASE+'auth/login/',{'email':staff[0].email,'password':PASSWORD},content_type='application/json',HTTP_X_CSRFTOKEN=token)
    assert r.status_code==200
    assert c.cookies['sessionid'].value!=old
    assert c.post(BASE+'auth/logout/',HTTP_X_CSRFTOKEN=r.json()['csrf_token']).status_code==204
    assert c.get(BASE+'auth/session/').json()['user'] is None

def test_collector_cannot_manage_accounts(staff):
    c,token=signed_in(staff[1])
    assert c.get(BASE+'users/').status_code==403
    assert c.get(BASE+f'users/{staff[0].pk}/').status_code==403
    assert c.get(BASE+'audit/').status_code==403
    assert c.patch(BASE+f'users/{staff[1].pk}/',{'expected_version':1,'roles':['Administrator']},content_type='application/json',HTTP_X_CSRFTOKEN=token).status_code==403

def test_admin_create_and_audit(staff):
    c,token=signed_in(staff[0]); payload={'email':'new@example.test','display_name':'New','password':PASSWORD,'roles':['Collector']}
    r=c.post(BASE+'users/',payload,content_type='application/json',HTTP_X_CSRFTOKEN=token)
    assert r.status_code==201,r.content
    assert 'password' not in r.json()
    assert AuditEvent.objects.filter(actor=staff[0],action='account_created',target_id=r.json()['id']).exists()
    assert c.post(BASE+'users/',{**payload,'email':'other@example.test','is_superuser':True},content_type='application/json',HTTP_X_CSRFTOKEN=token).status_code==400

def test_revoke_and_disable(staff):
    admin,collector=staff; c,token=signed_in(admin); other,_=signed_in(collector)
    r=c.post(BASE+f'users/{collector.pk}/revoke/',{'expected_version':1},content_type='application/json',HTTP_X_CSRFTOKEN=token)
    assert r.status_code==200
    assert other.get(BASE+'auth/session/').json()['user'] is None
    assert c.patch(BASE+f'users/{collector.pk}/',{'expected_version':1,'is_active':False},content_type='application/json',HTTP_X_CSRFTOKEN=token).status_code==409
    assert c.patch(BASE+f'users/{collector.pk}/',{'expected_version':2,'is_active':False},content_type='application/json',HTTP_X_CSRFTOKEN=token).status_code==200
    login_token=other.get(BASE+'auth/session/').json()['csrf_token']
    assert other.post(BASE+'auth/login/',{'email':collector.email,'password':PASSWORD},content_type='application/json',HTTP_X_CSRFTOKEN=login_token).status_code==403

def test_admin_cannot_modify_self(staff):
    c,token=signed_in(staff[0]); assert c.patch(BASE+f'users/{staff[0].pk}/',{'expected_version':1,'is_active':False},content_type='application/json',HTTP_X_CSRFTOKEN=token).status_code==403

def test_throttle(staff):
    c=Client(enforce_csrf_checks=True); token=c.get(BASE+'auth/session/').json()['csrf_token']
    for _ in range(10): assert c.post(BASE+'auth/login/',{'email':staff[1].email,'password':'wrong'},content_type='application/json',HTTP_X_CSRFTOKEN=token).status_code==403
    assert c.post(BASE+'auth/login/',{'email':staff[1].email,'password':PASSWORD},content_type='application/json',HTTP_X_CSRFTOKEN=token).status_code==429
