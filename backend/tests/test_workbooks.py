from datetime import date,time
from io import BytesIO
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from openpyxl import Workbook,load_workbook
from accounts.models import AuditEvent
from events.models import Occurrence
from events.workbooks import HEADERS
from test_events import staff, catalog, full, draft

pytestmark=pytest.mark.django_db
URL='/api/v1/admin/events/workbook/'

def workbook(*, duplicate=False, mock=False, formula=False, venue='Test venue', title='Imported synthetic event', amount=None):
    w=Workbook();s=w.active;s.title='Events';s.append(HEADERS)
    row=[None,title,'MUSIC',date(2026,12,11),time(0,30),time(2),venue,'Test area',amount,None,None,'Test promoter','0700000000','legacy@example.test','Verified','AB',1,'Legacy pick','No','No',None,1,'Private note',None,None,None]
    if formula:row[1]='=1+1'
    s.append(row)
    if duplicate:s.append(row)
    if mock:w.create_sheet('Issue').append(['Mock Label','MOCK-UP'])
    b=BytesIO();w.save(b);return b.getvalue()

def submit(c,t,b,mode='preview',**extra):
    return c.post(URL+'import/',{'file':SimpleUploadedFile('collector.xlsx',b),'mode':mode,**extra},HTTP_X_CSRFTOKEN=t)

def test_preview_commit_replay(catalog):
    c,t,u=staff('Editor','importer');b=workbook()
    p=submit(c,t,b);assert p.status_code==200,p.content
    data=p.json();assert data['can_commit'] and data['ready']==1 and Occurrence.objects.count()==0
    assert data['rows'][0]['actual_start']=='2026-12-12T00:30:00+03:00'
    assert submit(c,t,b,'commit',token=data['token']).status_code==400
    result=submit(c,t,b,'commit',token=data['token'],confirm='yes');assert result.status_code==201,result.content
    row=Occurrence.objects.get();assert row.status=='DRAFT' and row.submitted_by is None and row.prices.get().kind=='UNKNOWN'
    entry=AuditEvent.objects.get(action='event_workbook_imported',target_id=row.pk);assert entry.details['legacy']['Verified By']=='AB'
    assert submit(c,t,b,'commit',token=data['token'],confirm='yes').status_code==400
    assert Occurrence.objects.count()==1

@pytest.mark.parametrize('options',[{'duplicate':True},{'mock':True},{'formula':True},{'venue':'Missing venue'}])
def test_invalid_preview_no_writes(catalog,options):
    c,t,_=staff('Administrator','admin');p=submit(c,t,workbook(**options));assert p.status_code==200,p.content
    assert not p.json()['can_commit'] and not p.json()['token'] and Occurrence.objects.count()==0

def test_permissions_and_changed_file(catalog):
    c,t,_=staff('Editor','editor');other,ot,_=staff('Editor','other');collector,ct,_=staff('Collector','collector')
    b=workbook();token=submit(c,t,b).json()['token']
    assert submit(collector,ct,b).status_code==403
    assert collector.get(URL+'export/').status_code==403
    assert submit(other,ot,b,'commit',token=token,confirm='yes').status_code==400
    assert submit(c,t,workbook(title='Changed'),'commit',token=token,confirm='yes').status_code==400
    assert c.post(URL+'import/',{'file':SimpleUploadedFile('collector.xlsx',b)}).status_code==403
    assert Occurrence.objects.count()==0

def test_export_safe_strings_and_private_exclusion(full):
    c,t,_=staff('Administrator','admin');draft(c,t,{**full,'title':'=1+1','notes':'Private secret note'})
    r=c.get(URL+'export/');assert r.status_code==200,r.content
    w=load_workbook(BytesIO(r.content));s=w['Event report']
    assert s['C2'].value=='=1+1' and s['C2'].data_type=='s'
    assert 'Private secret note' not in str(list(s.values))
    assert w['Ticket prices']['C2'].value=='UNKNOWN'
    assert AuditEvent.objects.filter(action='event_workbook_exported').exists()
