import pytest
from django.contrib.auth.models import Group
from django.test import Client
from accounts.models import User, AuditEvent
from accounts.services import provision_roles
from catalog.models import Category

pytestmark = pytest.mark.django_db
BASE = '/api/v1/admin/'
URL = BASE + 'categories/'
PASSWORD = 'Category-test-only-49!'
PAYLOAD = {'code': 'TEST_CATEGORY', 'label': 'Test category', 'colour': '#abcdef', 'display_order': 20}


def sign_in(role):
    provision_roles()
    user = User.objects.create_user(role.lower() + '@example.test', PASSWORD)
    user.groups.add(Group.objects.get(name=role))
    client = Client(enforce_csrf_checks=True)
    token = client.get(BASE + 'auth/session/').json()['csrf_token']
    response = client.post(BASE + 'auth/login/', {'email': user.email, 'password': PASSWORD}, content_type='application/json', HTTP_X_CSRFTOKEN=token)
    assert response.status_code == 200, response.content
    return client, response.json()['csrf_token'], user


def write(client, token, method, url, data):
    return getattr(client, method)(url, data, content_type='application/json', HTTP_X_CSRFTOKEN=token)


def test_seed_exact():
    expected = {'MUSIC':'#FFD400','NIGHTLIFE':'#FF4FA3','COMEDY':'#5CF0A0','STAGE':'#FF8A3D','FILM':'#5EC4FF','ART':'#C3A2FF','FOOD':'#C6F432','FAMILY':'#F4F1EA','SPORT':'#7FE3D8','FAITH':'#FFC9A8','BUSINESS & NETWORKING':'#B9C7DA'}
    assert dict(Category.objects.values_list('label','colour')) == expected


@pytest.mark.parametrize('role', ['Administrator','Editor','Collector','Verifier','Publisher'])
def test_role_access(role):
    client, token, user = sign_in(role)
    assert client.get(URL).status_code == 200
    flags = client.get(BASE+'auth/session/').json()['permissions']
    assert flags['view_categories'] is True
    allowed = role in ('Administrator','Editor')
    assert flags['manage_categories'] is allowed
    assert write(client, token, 'post', URL, PAYLOAD).status_code == (201 if allowed else 403)
    category = Category.objects.get(code='MUSIC')
    assert write(client, token, 'patch', URL+str(category.pk)+'/', {'expected_version':1,'label':'Music updated'}).status_code == (200 if allowed else 403)


def test_lifecycle_and_audit():
    c,t,u = sign_in('Administrator')
    result = write(c,t,'post',URL,PAYLOAD)
    assert result.status_code == 201, result.content
    d = result.json()
    assert d['colour'] == '#ABCDEF'
    detail = URL+d['id']+'/'
    assert write(c,t,'patch',detail,{'expected_version':1,'label':'Changed'}).status_code == 200
    assert write(c,t,'patch',detail,{'expected_version':1,'label':'Stale'}).status_code == 409
    assert write(c,t,'patch',detail,{'expected_version':2,'is_active':False}).status_code == 200
    assert c.get(URL+'?search=TEST_CATEGORY').json()['count'] == 0
    assert c.get(URL+'?status=archived&search=TEST_CATEGORY').json()['count'] == 1
    assert write(c,t,'patch',detail,{'expected_version':3,'is_active':True}).status_code == 200
    assert c.get(detail).json()['version'] == 4
    assert set(AuditEvent.objects.filter(actor=u,target_id=d['id']).values_list('action',flat=True)) == {'category_created','category_updated','category_archived','category_restored'}
    assert c.delete(detail,HTTP_X_CSRFTOKEN=t).status_code == 405


def test_validation_and_csrf():
    c,t,_ = sign_in('Administrator')
    assert Client().get(URL).status_code == 403
    assert c.post(URL,PAYLOAD,content_type='application/json').status_code == 403
    for change in [{'code':'MUSIC'}, {'label':'music'}, {'colour':'red'}, {'display_order':-1}, {'is_active':False}, {'code':'bad code'}]:
        assert write(c,t,'post',URL,{**PAYLOAD,**change}).status_code == 400
    detail=URL+str(Category.objects.get(code='MUSIC').pk)+'/'
    assert write(c,t,'patch',detail,{'expected_version':1,'code':'NEW'}).status_code == 400
    assert c.get(URL+'?status=invalid').status_code == 400
    assert Category.objects.count() == 11
