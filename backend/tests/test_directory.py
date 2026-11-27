import pytest
from django.contrib.auth.models import Group
from django.test import Client
from accounts.models import AuditEvent, User
from accounts.services import provision_roles
from catalog.models import Country, City, Area, Venue, Promoter

pytestmark = pytest.mark.django_db
BASE = '/api/v1/admin/'
PASSWORD = 'Directory-test-only-49!'


def session(role):
    provision_roles()
    user = User.objects.create_user(role.lower()+'@example.test', PASSWORD)
    user.groups.add(Group.objects.get(name=role))
    client = Client(enforce_csrf_checks=True)
    token = client.get(BASE+'auth/session/').json()['csrf_token']
    response = client.post(BASE+'auth/login/', {'email': user.email, 'password': PASSWORD}, content_type='application/json', HTTP_X_CSRFTOKEN=token)
    assert response.status_code == 200, response.content
    return client, response.json()['csrf_token'], user


def write(client, token, method, path, data, code):
    response = getattr(client, method)(BASE+path, data, content_type='application/json', HTTP_X_CSRFTOKEN=token)
    assert response.status_code == code, response.content
    return response.json() if code != 405 else None


def test_seed_defaults():
    assert City.objects.filter(name='Kampala', country__name='Uganda', is_active=True).exists()
    assert Area.objects.count() == Venue.objects.count() == Promoter.objects.count() == 0


@pytest.mark.parametrize('role', ['Administrator','Editor','Collector','Verifier','Publisher'])
def test_permissions(role):
    c,t,_ = session(role)
    flags = c.get(BASE+'auth/session/').json()['permissions']
    allowed = role in ('Administrator','Editor')
    assert flags['view_directory'] is True
    assert flags['manage_directory'] is allowed
    assert flags['view_private_contacts'] is allowed
    for path in ('countries/', 'cities/', 'areas/', 'venues/', 'promoters/'):
        assert c.get(BASE+path).status_code == 200
    write(c,t,'post','countries/',{'name':'Synthetic country'},201 if allowed else 403)


def test_hierarchy_archive_restore_and_duplicate():
    c,t,u = session('Administrator')
    country=write(c,t,'post','countries/',{'name':'Synthetic country'},201)
    city=write(c,t,'post','cities/',{'name':'Synthetic city','country_id':country['id']},201)
    area=write(c,t,'post','areas/',{'name':'Synthetic area','city_id':city['id']},201)
    venue=write(c,t,'post','venues/',{'name':'Synthetic venue','area_id':area['id'],'latitude':'0.313600','longitude':'32.581100'},201)
    write(c,t,'post','areas/',{'name':'synthetic AREA','city_id':city['id']},400)
    for path,row in [('countries/',country),('cities/',city),('areas/',area)]:
        write(c,t,'patch',path+row['id']+'/',{'expected_version':1,'is_active':False},400)
    assert c.get(BASE+'venues/?parent='+area['id']).json()['count']==1
    for path,row in [('venues/',venue),('areas/',area),('cities/',city),('countries/',country)]:
        write(c,t,'patch',path+row['id']+'/',{'expected_version':1,'is_active':False},200)
    write(c,t,'patch','venues/'+venue['id']+'/',{'expected_version':2,'is_active':True},400)
    write(c,t,'post','cities/',{'name':'Another city','country_id':country['id']},400)
    for path,row in [('countries/',country),('cities/',city),('areas/',area),('venues/',venue)]:
        write(c,t,'patch',path+row['id']+'/',{'expected_version':2,'is_active':True},200)
    assert AuditEvent.objects.filter(actor=u,action='venue_restored',target_id=venue['id']).exists()


def test_promoter_contacts_and_audit():
    c,t,u = session('Administrator')
    row=write(c,t,'post','promoters/',{'name':'Synthetic promoter','contact_name':'Synthetic contact','contact_phone':'0000000000','contact_email':'contact@example.test'},201)
    read,token,_=session('Collector')
    for result in (read.get(BASE+'promoters/').json()['results'][0],read.get(BASE+'promoters/'+row['id']+'/').json()):
        assert not {'contact_name','contact_email','contact_phone'} & result.keys()
    assert c.get(BASE+'promoters/'+row['id']+'/').json()['contact_email']=='contact@example.test'
    assert 'contact@example.test' not in str(AuditEvent.objects.get(action='promoter_created',target_id=row['id']).details)
    write(read,token,'patch','promoters/'+row['id']+'/',{'expected_version':1,'name':'Not allowed'},403)
    write(c,t,'patch','promoters/'+row['id']+'/',{'expected_version':1,'name':'Renamed'},200)
    write(c,t,'patch','promoters/'+row['id']+'/',{'expected_version':1,'name':'Stale'},409)
    write(c,t,'post','promoters/',{'name':'renamed'},400)


def test_validation_and_csrf():
    c,t,_=session('Administrator')
    assert Client().get(BASE+'countries/').status_code==403
    assert c.post(BASE+'countries/',{'name':'Denied'},content_type='application/json').status_code==403
    city=City.objects.get(name='Kampala')
    area=Area.objects.create(name='Synthetic area',city=city)
    payload={'name':'Synthetic venue','area_id':str(area.pk)}
    for invalid in ({'latitude':'0.1'},{'latitude':'91','longitude':'1'},{'website':'ftp://example.test'},{'is_active':False}):
        write(c,t,'post','venues/',{**payload,**invalid},400)
    row=write(c,t,'post','venues/',payload,201)
    write(c,t,'patch','venues/'+row['id']+'/',{'expected_version':1,'area_id':str(area.pk)},400)
    assert c.get(BASE+'venues/?parent=invalid').status_code==400
    assert c.delete(BASE+'venues/'+row['id']+'/',HTTP_X_CSRFTOKEN=t).status_code in (403,405)
