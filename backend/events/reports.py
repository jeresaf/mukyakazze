"""Bounded operational reports; editorial dates select the occurrence cohort."""
from collections import Counter, defaultdict
from io import BytesIO
from django.db import transaction
from django.http import HttpResponse
from django.utils import timezone
from openpyxl import Workbook
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from rest_framework import permissions, serializers
from rest_framework.response import Response
from rest_framework.views import APIView
from accounts.models import User
from catalog.directory import directory_lock
from editorial.models import Issue
from editorial.readiness import review_state
from .api import scope, KAMPALA
from .models import STATES, Verification


class ReportAccess(permissions.BasePermission):
    def has_permission(self, request, view):
        u = request.user
        return u.is_authenticated and u.has_perm('events.view_occurrence') and u.has_perm('events.manage_all_occurrences')


def period(params):
    if set(params) - {'from', 'to'} or any(len(params.getlist(k)) != 1 for k in params):
        raise serializers.ValidationError('Use one from and one to editorial date.')
    today = timezone.now().astimezone(KAMPALA).date()
    field = serializers.DateField(input_formats=['%Y-%m-%d'])
    start = field.run_validation(params.get('from', today.replace(day=1).isoformat()))
    end = field.run_validation(params.get('to', today.isoformat()))
    if start > end or (end-start).days > 365:
        raise serializers.ValidationError('Choose an inclusive date range of 1–366 days.')
    return start, end


def breakdown(rows, id_key, label_keys):
    counts = Counter((str(r[id_key]) if r[id_key] else None, ' / '.join(str(r[k]) for k in label_keys if r[k]) or 'Not specified') for r in rows)
    return [{'id':key, 'label':label, 'count':n} for (key,label),n in sorted(counts.items(),key=lambda x:(-x[1],x[0][1],x[0][0] or ''))]


@transaction.atomic
def build_report(user, params):
    start,end = period(params)
    directory_lock()
    qs = scope(user).filter(editorial_date__range=(start,end))
    rows = list(qs.order_by('pk').values('id','status','is_cancelled','editorial_date','event__category_id','event__category__label','venue_id','venue__name','venue__area_id','venue__area__name','venue__area__city__name','event__created_by_id','submitted_by_id','assigned_collector_id','assigned_reviewer_id')[:5001])
    if len(rows)>5000:
        raise serializers.ValidationError('More than 5000 occurrences; narrow the report dates.')
    active = [r for r in rows if not r['is_cancelled']]
    statuses = Counter(r['status'] for r in active)
    decisions = list(Verification.objects.filter(occurrence_id__in=[r['id'] for r in active],action__in=['submit','review','verify','return','reject','reopen']).order_by('occurrence_id','version').values('occurrence_id','actor_id','action','created_at')[:20001])
    if len(decisions)>20000:
        raise serializers.ValidationError('More than 20000 review actions; narrow the report dates.')
    last_submit = {}; durations = []; actions = Counter()
    for d in decisions:
        key,action = d['occurrence_id'],d['action']; actions[action]+=1
        if action=='submit': last_submit[key]=d['created_at']
        elif action in ('verify','return','reject','reopen'):
            submitted = last_submit.pop(key,None)
            if action=='verify' and submitted is not None and submitted<=d['created_at']:
                durations.append((d['created_at']-submitted).total_seconds()/3600)
    report = {'from':start.isoformat(),'to':end.isoformat(),'active':len(active),'cancelled':len(rows)-len(active),
              'by_status':[{'label':s,'count':statuses[s]} for s,_ in STATES],
              'categories':breakdown(active,'event__category_id',['event__category__label']),
              'venues':breakdown(active,'venue_id',['venue__name','venue__area__name']),
              'areas':breakdown(active,'venue__area_id',['venue__area__city__name','venue__area__name']),
              'by_date':[{'label':d.isoformat(),'count':n} for d,n in sorted(Counter(r['editorial_date'] for r in active).items())],
              'verification':{'actions':[{'label':s,'count':actions[s]} for s in ('submit','review','verify','return','reject','reopen')], 'completed_cycles':len(durations),'mean_hours':round(sum(durations)/len(durations),2) if durations else None},
              'staff':None,'issues':None}
    if user.has_perm('accounts.manage_accounts'):
        staff = defaultdict(Counter)
        for r in active:
            for key,label in [('event__created_by_id','creator_occurrences'),('submitted_by_id','current_submissions'),('assigned_collector_id','collection_assignments'),('assigned_reviewer_id','review_assignments')]:
                if r[key]: staff[r[key]][label]+=1
        for d in decisions:
            if d['action']=='verify': staff[d['actor_id']]['verify_actions']+=1
        users = User.objects.in_bulk(staff)
        fields = ('creator_occurrences','current_submissions','collection_assignments','review_assignments','verify_actions')
        report['staff']=[{'id':str(k),'label':users[k].display_name or str(k),**{f:v[f] for f in fields}} for k,v in sorted(staff.items(),key=lambda x:str(x[0])) if k in users]
    if user.has_perm('editorial.view_issue'):
        issues = list(Issue.objects.select_for_update().filter(week_start__range=(start,end)).order_by('week_start','pk'))
        report['issues']=[]
        for i in issues:
            state=review_state(i,user)
            entries=i.entries.all()
            report['issues'].append({'number':i.number,'week_start':i.week_start.isoformat(),'state':state['state'],'ready':state['ready'], 'checks_passed':sum(c['passed'] for c in state['checks']),'checks_total':len(state['checks']),'selected':entries.count(),'picks':entries.filter(rank__isnull=False).count(),'paid_disclosures':entries.filter(paid_feature=True).count()})
    return report


def report_workbook(report):
    wb=Workbook(); summary=wb.active; summary.title='Summary'
    def write(sheet, values):
        sheet.append([ILLEGAL_CHARACTERS_RE.sub("", v) if isinstance(v,str) else v for v in values])
        for cell in sheet[sheet.max_row]:
            if isinstance(cell.value,str): cell.data_type='s'
    for row in [('Metric','Value'),('From editorial date',report['from']),('To editorial date',report['to']),('Active occurrences',report['active']),('Cancelled occurrences',report['cancelled']),('Verified cycles',report['verification']['completed_cycles']),('Mean hours, submit to verify',report['verification']['mean_hours']),('Definition','Active occurrences by editorial date; historical review actions in that cohort; issue reports by week start. Paid disclosures are not revenue.')]: write(summary,row)
    for key,title in [('by_status','Statuses'),('categories','Categories'),('venues','Venues'),('areas','Areas'),('by_date','Dates')]:
        sheet=wb.create_sheet(title); write(sheet,['Label','Count'])
        for row in report[key]: write(sheet,[row['label'],row['count']])
    sheet=wb.create_sheet('Review actions'); write(sheet,['Action','Count'])
    for row in report['verification']['actions']: write(sheet,[row['label'],row['count']])
    for key,title,cols in [('staff','Staff',['id','label','creator_occurrences','current_submissions','collection_assignments','review_assignments','verify_actions']),('issues','Issues',['number','week_start','state','ready','checks_passed','checks_total','selected','picks','paid_disclosures'])]:
        if report[key] is not None:
            sheet=wb.create_sheet(title); write(sheet,cols)
            for row in report[key]: write(sheet,[row[c] for c in cols])
    for sheet in wb:
        sheet.freeze_panes='A2'; sheet.auto_filter.ref=sheet.dimensions
        for col in sheet.columns:
            sheet.column_dimensions[col[0].column_letter].width=min(60,max(14,max(len(str(c.value or '')) for c in col)+2))
    out=BytesIO(); wb.save(out); return out.getvalue()


class OperationalReports(APIView):
    permission_classes=[ReportAccess]
    def get(self,request):
        response=Response(build_report(request.user,request.query_params)); response['Cache-Control']='no-store'; return response


class OperationalReportExport(APIView):
    permission_classes=[ReportAccess]
    def get(self,request):
        response=HttpResponse(report_workbook(build_report(request.user,request.query_params)),content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition']='attachment; filename="mukyakazze-operational-report.xlsx"'; response['Cache-Control']='no-store'; return response
