"""Bounded, two-step legacy Events worksheet import and scoped reporting export."""
from datetime import date, datetime, time, timedelta
from hashlib import sha256
from io import BytesIO
from zipfile import ZipFile
import json
from django.core import signing
from django.db import transaction
from django.http import HttpResponse
from openpyxl import Workbook, load_workbook
from rest_framework import permissions, serializers
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView
from accounts.models import AuditEvent
from accounts.services import audit
from catalog.directory import directory_lock
from catalog.models import Category, Venue, Promoter
from .api import CreateInput, validate_values, scope, EVENT_FIELDS, OCC_FIELDS, PRICE_FIELDS, KAMPALA
from .models import Event, Occurrence, Price

HEADERS = ('Event ID','Event Name *','Category *','Date *','Start Time *','End Time','Venue *','Area *','Price (UGX)','Price Note','Ticket Link','Promoter','Contact Phone','Contact Email','Status *','Verified By','Bugy Pick Rank','Why Go','Bugy Playing?','Paid Feature?','Feature Fee (UGX)','Grid Span','Notes','Day','In This Issue?','Grid Slot')
MAX_FILE = 5*1024*1024
MAX_ROWS = 500
SALT = 'events.workbook.preview.v1'

class WorkbookAccess(permissions.BasePermission):
    def has_permission(self, request, view):
        return (request.user.is_authenticated and request.user.has_perm('events.view_occurrence')
                and request.user.has_perm('events.manage_all_occurrences')
                and request.user.has_perm('events.add_occurrence'))

def fail(message):
    raise serializers.ValidationError({'workbook':message})

def text(value):
    return '' if value is None else str(value).strip()

def parse_date(value):
    if isinstance(value, datetime):
        if value.time() != time():
            raise ValueError('Date must not contain a time.')
        return value.date()
    if isinstance(value, date): return value
    return date.fromisoformat(text(value))

def parse_time(value):
    if isinstance(value, time): result = value
    else: result = time.fromisoformat(text(value))
    if result.tzinfo or result.microsecond:
        raise ValueError('Use a local clock time (HH:MM or HH:MM:SS).')
    return result

def read_workbook(upload):
    if not upload or not upload.name.lower().endswith('.xlsx') or upload.size > MAX_FILE:
        fail('Select an XLSX file no larger than 5 MiB.')
    data = upload.read(MAX_FILE+1)
    if len(data)>MAX_FILE: fail('Workbook exceeds size limit.')
    try:
        with ZipFile(BytesIO(data)) as z:
            members=z.infolist()
            if (len(members)>500 or sum(x.file_size for x in members)>30*1024*1024
                    or any(x.flag_bits & 1 or 'vbaproject' in x.filename.lower() or x.filename.startswith('xl/externalLinks/') for x in members)):
                fail('Workbook contains unsupported or oversized ZIP contents.')
        book=load_workbook(BytesIO(data),read_only=True,data_only=False,keep_links=False)
    except serializers.ValidationError: raise
    except Exception: fail('Invalid or unsupported XLSX workbook.')
    try:
        if 'Events' not in book.sheetnames: fail('Events worksheet is missing.')
        sheet=book['Events']
        # Do not trust the ZIP worksheet dimension metadata.
        sheet.reset_dimensions()
        rows=sheet.iter_rows(max_col=26)
        head=next(rows,None)
        if head is None or tuple(text(c.value) for c in head)!=HEADERS:
            fail('Events headers must match the original Data Collector workbook exactly.')
        mock=False
        if 'Issue' in book.sheetnames:
            for row in book['Issue'].iter_rows(max_row=100,max_col=2,values_only=True):
                if text(row[0]).casefold()=='mock label' and text(row[1]): mock=True
        result=[]
        for number,row in enumerate(rows,2):
            if number>MAX_ROWS+1: fail('Use at most 500 worksheet data rows per file.')
            values=[c.value for c in row]
            if not any(v is not None and v!='' for v in values[1:23]): continue
            errors=[]
            if any(c.data_type=='f' for c in row[1:23]): errors.append('Formulas are not permitted in input fields.')
            if any(len(text(v))>5000 for v in values[1:23]): errors.append('A source field exceeds 5000 characters.')
            if 'fictional' in text(values[22]).casefold(): mock=True
            result.append((number,values,errors))
        if not result: fail('No event data rows found.')
        return sha256(data).hexdigest(), mock, result
    except serializers.ValidationError: raise
    except Exception: fail('Unable to read worksheet contents.')
    finally: book.close()

def unique(qs, field):
    matches=list(qs.values_list('pk',flat=True)[:2])
    if len(matches)!=1: raise ValueError(f'{field}: register or resolve a unique active directory record first.')
    return matches[0]

def convert(v, digest, number):
    category=unique(Category.objects.filter(label__iexact=text(v[2]),is_active=True),'Category')
    venue=unique(Venue.objects.filter(name__iexact=text(v[6]),area__name__iexact=text(v[7]),is_active=True,area__is_active=True,area__city__is_active=True,area__city__country__is_active=True),'Venue / area')
    promoter=unique(Promoter.objects.filter(name__iexact=text(v[11]),is_active=True),'Promoter') if text(v[11]) else None
    day=parse_date(v[3]); clock=parse_time(v[4]); start=datetime.combine(day,clock,KAMPALA)
    warnings=[]
    if clock<time(6):
        start+=timedelta(days=1); warnings.append('Start before 06:00 interpreted as the next calendar day (legacy editorial convention).')
    end=None
    if text(v[5]):
        end=datetime.combine(start.date(),parse_time(v[5]),KAMPALA)
        if end<start: end+=timedelta(days=1)
        if end==start: raise ValueError('Start and end are equal; clarify the duration.')
    amount=v[8]; note=text(v[9]); kind='UNKNOWN'
    if amount is not None and text(amount):
        if isinstance(amount,bool) or not isinstance(amount,(int,float)) or not float(amount).is_integer() or not 0<=amount<=999999999999:
            raise ValueError('Price must be a whole non-negative UGX amount or blank.')
        amount=int(amount)
        if amount>0: kind='PAID'
        elif note: kind='CONDITIONAL_FREE'; amount=None; warnings.append('Zero price with a note is treated as conditional; check terms.')
        else: kind='FREE'
    else: amount=None
    if text(v[14]).casefold()!='draft': warnings.append('Legacy status is retained as provenance only; imported as draft.')
    if any(text(x) for x in v[12:14]): warnings.append('Legacy contact information retained in restricted audit provenance; directory contacts unchanged.')
    if any(text(x) for x in v[16:22]): warnings.append('Legacy editorial and commercial fields retained as provenance; not applied to an issue.')
    payload={'title':text(v[1]),'category_id':category,'venue_id':venue,'promoter_id':promoter,'editorial_date':day,'starts_at':start,'ends_at':end,'price_type':kind,'amount_ugx':amount,'price_note':note,'ticket_url':text(v[10]),'source':f'Legacy workbook SHA256 {digest}, Events row {number}; requires independent verification.','notes':text(v[22])}
    ser=CreateInput(data=payload);ser.is_valid(raise_exception=True)
    values=dict(ser.validated_data);validate_values(values,complete=True)
    # Preserve legacy fields without importing the original file or granting verification.
    legacy={HEADERS[i]:text(v[i]) for i in (0,12,13,14,15,16,17,18,19,20,21) if text(v[i]) and not (i==0 and text(v[i]).startswith('='))}
    return values,legacy,warnings

def inspect(upload):
    digest,mock,rows=read_workbook(upload)
    preview=[]; ready=[]; seen=set()
    for number,v,errors in rows:
        warnings=[]
        try:
            if not errors:
                values,legacy,warnings=convert(v,digest,number)
                key=(values['title'].casefold(),values['venue_id'],values['starts_at'])
                if key in seen: raise ValueError('Duplicate event within workbook.')
                seen.add(key)
                if AuditEvent.objects.filter(action='event_workbook_imported',details__sha256=digest,details__row=number).exists():
                    raise ValueError('This workbook row was already imported.')
                ready.append((number,values,legacy))
        except (ValueError,OverflowError,serializers.ValidationError) as exc:
            errors.append(str(exc.detail) if isinstance(exc,serializers.ValidationError) else str(exc))
        preview.append({'row':number,'title':text(v[1])[:200],'date':text(v[3])[:30], 'venue':text(v[6])[:200], 'errors':errors,'warnings':warnings, 'actual_start':values['starts_at'].isoformat() if not errors else None, 'actual_end':values['ends_at'].isoformat() if not errors and values['ends_at'] else None, 'price_type':values['price_type'] if not errors else None, 'amount_ugx':values['amount_ugx'] if not errors else None})
    return digest,mock,preview,ready

def fingerprint(digest,ready):
    return sha256(json.dumps([digest,ready],default=str,sort_keys=True,separators=(',',':')).encode()).hexdigest()

class WorkbookImport(APIView):
    permission_classes=[WorkbookAccess]
    parser_classes=[MultiPartParser]
    @transaction.atomic
    def post(self,request):
        mode=request.data.get('mode','preview')
        if mode not in ('preview','commit'): fail('Use preview or commit.')
        # Serialize against other event/catalog writers; revalidate on every commit.
        directory_lock()
        digest,mock,rows,ready=inspect(request.FILES.get('file'))
        allowed=not mock and len(ready)==len(rows)
        stamp={'user':str(request.user.pk),'fingerprint':fingerprint(digest,ready)}
        if mode=='preview':
            return Response({'sha256':digest,'mock':mock,'rows':rows,'ready':len(ready),'can_commit':allowed,'token':signing.dumps(stamp,salt=SALT) if allowed else ''})
        try: previous=signing.loads(request.data.get('token',''),salt=SALT,max_age=1800)
        except signing.BadSignature: fail('Preview expired or invalid. Preview the workbook again.')
        if not allowed or previous!=stamp: fail('Workbook, directory or duplicate state changed, or the workbook is not eligible. Preview again.')
        if request.data.get('confirm')!='yes': fail('Explicitly confirm the real-data draft import.')
        ids=[]
        for number,values,legacy in ready:
            event=Event.objects.create(created_by=request.user,**{k:values[k] for k in EVENT_FIELDS if k in values})
            row=Occurrence.objects.create(event=event,**{k:values[k] for k in OCC_FIELDS if k in values})
            Price.objects.create(occurrence=row,**{v:values[k] for k,v in PRICE_FIELDS.items() if k in values})
            audit(request.user,'event_workbook_imported',row.pk,sha256=digest,row=number,legacy=legacy,event_id=str(event.pk))
            ids.append(str(row.pk))
        return Response({'created':len(ids),'ids':ids},status=201)

def safe_row(sheet, values):
    sheet.append(values)
    # Explicit string cell types prevent Excel from evaluating untrusted text.
    for cell in sheet[sheet.max_row]:
        if isinstance(cell.value,str): cell.data_type='s'

class WorkbookExport(APIView):
    permission_classes=[WorkbookAccess]
    def get(self,request):
        qs=scope(request.user).order_by('editorial_date','starts_at','pk')
        for field,lookup in [('from','editorial_date__gte'),('to','editorial_date__lte')]:
            if field in request.query_params: qs=qs.filter(**{lookup:serializers.DateField().run_validation(request.query_params[field])})
        records=list(qs.prefetch_related('prices')[:5001])
        if len(records)>5000: fail('Export limit is 5000 occurrences; select a narrower date range.')
        book=Workbook(); sheet=book.active; sheet.title='Event report'
        safe_row(sheet,['Occurrence ID','Event ID','Event name','Category','Venue','Area','Promoter','Editorial date','Actual start (Kampala)','Actual end (Kampala)','Status','Cancelled','Description'])
        tiers=book.create_sheet('Ticket prices');safe_row(tiers,['Occurrence ID','Tier','Price type','Amount UGX','Note','Ticket link'])
        for r in records:
            safe_row(sheet,[str(r.pk),str(r.event_id),r.event.title,r.event.category.label if r.event.category else '',r.venue.name if r.venue else '',r.venue.area.name if r.venue else '',r.event.promoter.name if r.event.promoter else '',r.editorial_date.isoformat() if r.editorial_date else '',r.starts_at.astimezone(KAMPALA).isoformat() if r.starts_at else '',r.ends_at.astimezone(KAMPALA).isoformat() if r.ends_at else '',r.status,r.is_cancelled,r.event.description])
            for p in r.prices.all(): safe_row(tiers,[str(r.pk),p.tier,p.kind,p.amount_ugx,p.note,p.ticket_url])
        for s in (sheet,tiers):
            s.freeze_panes='A2';s.auto_filter.ref=s.dimensions
        buf=BytesIO();book.save(buf);book.close()
        audit(request.user,'event_workbook_exported',count=len(records),date_from=request.query_params.get('from',''),date_to=request.query_params.get('to',''))
        response=HttpResponse(buf.getvalue(),content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition']='attachment; filename="mukyakazze-event-report.xlsx"';response['Cache-Control']='no-store'
        return response
