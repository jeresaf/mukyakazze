from datetime import timedelta
from io import BytesIO
import pytest
from django.test import Client
from django.utils import timezone
from openpyxl import load_workbook
from events.models import Verification
from test_editorial import staff, issue, roster, entry, occurrences

pytestmark = pytest.mark.django_db
URL = '/api/v1/admin/reports/'
PERIOD = '?from=2026-12-10&to=2026-12-16'


@pytest.mark.parametrize('role', ['Collector', 'Verifier', 'Publisher'])
def test_reports_restricted(role):
    c, _, _ = staff(role)
    assert c.get(URL+PERIOD).status_code == 403
    assert c.get(URL+'export/'+PERIOD).status_code == 403


def test_reports_anonymous():
    assert Client().get(URL+PERIOD).status_code == 403
    assert Client().get(URL+'export/'+PERIOD).status_code == 403


def test_cohort_counts_and_editor_privacy(occurrences):
    c,t,_ = staff('Editor')
    i=issue(c,t)
    assert roster(c,t,i,[entry(occurrences[0],rank=1,why_go='Example',paid_feature=True)]).status_code==200
    r=c.get(URL+PERIOD); assert r.status_code==200,r.content
    d=r.json(); assert d['active']==3 and d['cancelled']==1
    assert dict((x['label'],x['count']) for x in d['by_status'])['VERIFIED']==2
    assert sum(x['count'] for x in d['categories'])==3
    assert sum(x['count'] for x in d['venues'])==3
    assert sum(x['count'] for x in d['areas'])==3
    assert d['staff'] is None
    assert d['issues'][0]['picks']==1 and d['issues'][0]['paid_disclosures']==1
    assert d['issues'][0]['state']=='DRAFT' and not d['issues'][0]['ready']
    assert c.get(URL+'export/'+PERIOD).status_code==200


def test_staff_and_verification_timing(occurrences):
    c,_,u=staff('Administrator'); row=occurrences[0]
    row.assigned_reviewer=u; row.save(update_fields=['assigned_reviewer'])
    a=Verification.objects.create(occurrence=row,actor=row.event.created_by,action='submit',reason='Test',version=2)
    b=Verification.objects.create(occurrence=row,actor=u,action='verify',reason='Test',version=3)
    now=timezone.now(); Verification.objects.filter(pk=a.pk).update(created_at=now-timedelta(hours=2)); Verification.objects.filter(pk=b.pk).update(created_at=now)
    d=c.get(URL+PERIOD).json(); assert d['verification']['completed_cycles']==1 and d['verification']['mean_hours']==2
    owner=next(x for x in d['staff'] if x['id']==str(row.event.created_by_id))
    admin=next(x for x in d['staff'] if x['id']==str(u.pk))
    assert owner['creator_occurrences']==3 and admin['verify_actions']==1 and admin['review_assignments']==1
    assert 'email' not in admin and 'evidence' not in str(d)


def test_invalid_dates_and_empty():
    c,_,_=staff('Editor')
    for query in ['?from=no&to=2026-12-10','?from=2026-12-17&to=2026-12-10','?from=2025-01-01&to=2026-12-10','?from=2026-12-10&from=2026-12-11&to=2026-12-16','?unexpected=1']:
        assert c.get(URL+query).status_code==400
    d=c.get(URL+PERIOD).json(); assert d['active']==d['cancelled']==0 and d['verification']['mean_hours'] is None


def test_export_safe_text_and_scope(occurrences):
    c,_,_=staff('Editor'); venue=occurrences[0].venue; venue.name='=1+1'; venue.save(update_fields=['name'])
    r=c.get(URL+'export/'+PERIOD); assert r.status_code==200,r.content
    assert r['Cache-Control']=='no-store'
    wb=load_workbook(BytesIO(r.content)); assert 'Staff' not in wb.sheetnames
    assert wb['Venues']['A2'].value.startswith('=1+1') and wb['Venues']['A2'].data_type=='s'
    assert all(cell.data_type!='f' for sheet in wb for row in sheet for cell in row)
    assert wb['Summary']['B4'].value==3
