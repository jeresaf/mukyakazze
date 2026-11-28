"""Revision-bound editorial decisions. No publication authority is granted here."""
import hashlib
import json
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from rest_framework import serializers
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView
from accounts.models import AuditEvent
from accounts.serializers import StrictSerializer
from accounts.services import audit
from catalog.directory import directory_lock
from catalog.models import Category, MediaAsset, Sponsor
from .api import EditorialAccess, eligible, week_end
from .features import feature_data, teaser_data
from .models import Issue
from .presentation import cover_data, grid_data

ACTIONS = ('issue_review_submitted', 'issue_review_approved', 'issue_review_returned')
CONTRIBUTIONS = ('issue_created', 'issue_updated', 'issue_roster_replaced', 'issue_cover_updated', 'issue_grid_updated', 'issue_feature_updated', 'issue_teasers_replaced')


def digest(value):
    return hashlib.sha256(json.dumps(value, cls=DjangoJSONEncoder, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def fingerprint_ref(row):
    return [str(row.pk), row.version, row.is_active] if row else None


def readiness(issue):
    checks = []
    def check(code, label, passed, detail, warning=False):
        checks.append(dict(code=code, label=label, passed=bool(passed), detail=detail, severity='warning' if warning else 'blocker'))

    entries = list(issue.entries.select_related('occurrence__event__category', 'occurrence__event__promoter', 'occurrence__venue__area__city__country').order_by('occurrence_id'))
    teasers = list(issue.teasers.select_related('category').all())
    category_ids = {x.occurrence.event.category_id for x in entries if x.occurrence.event.category_id} | {x.category_id for x in teasers}
    media_ids = {x for x in (issue.cover_photo_id, issue.headshot_id, issue.sponsor_logo_id) if x}
    media_ids |= {x.occurrence.poster_id for x in entries if x.occurrence.poster_id}
    for item in entries:
        media_ids.update(item.occurrence.attachments.values_list('asset_id', flat=True))
    # Category and media mutations use row locks rather than the directory advisory lock.
    # Read fresh rows under those same locks before evaluating the revision.
    categories = {x.pk: x for x in Category.objects.select_for_update().filter(pk__in=category_ids).order_by('pk')}
    media = {x.pk: x for x in MediaAsset.objects.defer('content').select_for_update().filter(pk__in=media_ids).order_by('pk')}
    if issue.sponsor_id:
        Sponsor.objects.select_for_update().get(pk=issue.sponsor_id)
    cover, grid, feature, upcoming = cover_data(issue), grid_data(issue), feature_data(issue), teaser_data(issue)
    ranks = sorted(x.rank for x in entries if x.rank is not None)
    check('week', 'Edition dates', issue.week_start.weekday()==3 and issue.week_start <= issue.grid_day <= week_end(issue), 'Thursday start; grid day inside week.')
    check('picks', 'Seven ranked picks', ranks == list(range(1,8)) and all(x.why_go.strip() for x in entries if x.rank is not None), f'{len(ranks)}/7 ranked picks; each needs Why Go.')
    check('curator', 'Curator content', bool(issue.picks_title.strip() and issue.picks_byline.strip() and issue.picks_intro.strip()), 'Title, byline and introduction required.')
    check('cover_text', 'Cover content', bool(cover['name'].strip() and cover['subtitle'].strip() and len(cover['lines'])==3 and all(x['title'].strip() and x['body'].strip() for x in cover['lines'])), 'Name, subtitle and three complete cover lines required.')
    check('cover_media', 'Cover and headshot', all(x and x['valid'] for x in (cover['photo'],cover['headshot'])), 'Select active cover and curator images of the correct type.')
    check('grid', 'Night Grid', bool(grid['placements']) and not grid['warnings'], '; '.join(grid['warnings']) or ('Grid contains selected events.' if grid['placements'] else 'Select at least one eligible grid event.'))
    check('feature', 'Editorial feature', bool(issue.feature_title.strip() and issue.feature_subtitle.strip() and issue.feature_kicker.strip() and issue.feature_tips and all(x['title'].strip() and x['body'].strip() for x in issue.feature_tips)), 'Title, subtitle, kicker and at least one complete tip required.')
    check('sponsor', 'Sponsor placement', (not feature['sponsor'] and not feature['logo']) or bool(feature['sponsor'] and feature['sponsor']['valid'] and feature['logo'] and feature['logo']['valid']), 'Optional; if selected, sponsor and logo must both be active.')
    check('teasers', 'Coming Up eligibility', not upcoming['warnings'] and all(x.source.strip() for x in teasers), '; '.join(upcoming['warnings']) or 'Upcoming entries need a source and active category; dates must follow this edition.')
    check('contacts', 'Public contact labels', all(x.strip() for x in (issue.website_label,issue.whatsapp_label,issue.submission_contact)), 'Website, WhatsApp and submissions contact required.', warning=True)
    check('layout', 'Layout suggestions', not cover['warnings'] and all(len(x['body'])<=110 for x in issue.feature_tips) and all(len(x.why_go)<=70 for x in entries if x.rank), '; '.join(cover['warnings']) or 'Review tip and recommendation lengths.', warning=True)
    records = []
    problems = []
    unknown = 0
    for entry in entries:
        row = entry.occurrence
        event = row.event
        cat = categories.get(event.category_id)
        venue = row.venue
        refs = [cat, venue, venue.area if venue else None, venue.area.city if venue else None, venue.area.city.country if venue else None]
        attachments = list(row.attachments.order_by('position').values_list('asset_id','position'))
        images = [media.get(x) for x in ([row.poster_id] if row.poster_id else []) + [x[0] for x in attachments]]
        prices = list(row.prices.order_by('tier','pk').values('tier','kind','amount_ugx','note','ticket_url'))
        if (not eligible(issue,row) or entry.occurrence_version != row.version or not all(x and x.is_active for x in refs)
                or (event.promoter and not event.promoter.is_active) or any(not x or not x.is_active for x in images)
                or not prices or not row.source.strip()):
            problems.append(event.title)
        unknown += sum(p['kind']=='UNKNOWN' for p in prices)
        records.append({'entry':str(entry.pk),'occurrence':str(row.pk),'version':row.version,'selected_version':entry.occurrence_version,
                        'status':row.status,'cancelled':row.is_cancelled,'title':event.title,'description':event.description,
                        'editorial_date':row.editorial_date,'starts_at':row.starts_at,'ends_at':row.ends_at,
                        'refs':[fingerprint_ref(x) for x in refs+[event.promoter]], 'media':[fingerprint_ref(x) for x in images],
                        'prices':prices,'rank':entry.rank,'why_go':entry.why_go,'curator_playing':entry.curator_playing,'paid_feature':entry.paid_feature})
    check('events','Verified event selection', bool(entries) and not problems, 'Review: '+', '.join(problems) if problems else f'{len(entries)} selected occurrences.')
    check('prices','Unknown prices', not unknown, f'{unknown} unknown ticket prices; do not infer free admission.', warning=True)
    check('teaser_review','Upcoming teaser review', not teasers, f'{len(teasers)} unverified teasers; approver must check their sources explicitly.', warning=True)
    # Revision binding includes related catalogue/media versions. No private data or file bytes are returned.
    fingerprint = digest({'issue':str(issue.pk),'version':issue.version,'entries':records,'cover':cover,'grid':grid,'feature':feature,'teasers':upcoming,
                          'sponsor':fingerprint_ref(issue.sponsor),'category_refs':[fingerprint_ref(x) for x in categories.values()],
                          'media_refs':[fingerprint_ref(x) for x in media.values()]})
    return checks, fingerprint


def review_state(issue, user):
    checks, fingerprint = readiness(issue)
    latest = AuditEvent.objects.filter(target_id=issue.pk,action__in=ACTIONS).order_by('-created_at','-id').first()
    ready = all(x['passed'] for x in checks if x['severity']=='blocker')
    state = 'DRAFT'
    if latest:
        state = {'issue_review_submitted':'SUBMITTED','issue_review_approved':'APPROVED','issue_review_returned':'RETURNED'}[latest.action]
        if state in ('SUBMITTED','APPROVED') and (latest.details.get('fingerprint') != fingerprint or not ready):
            state = 'STALE'
    contributor = issue.created_by_id == user.pk or AuditEvent.objects.filter(target_id=issue.pk,actor=user,action__in=CONTRIBUTIONS).exists()
    can_approve = user.has_perm('accounts.manage_accounts') and not contributor and latest is not None and latest.actor_id != user.pk
    actions = []
    if user.has_perm('editorial.change_issue'):
        if state in ('DRAFT','RETURNED','STALE') and ready: actions.append('submit')
        if state == 'SUBMITTED' and can_approve: actions += ['approve','return']
    history = AuditEvent.objects.filter(target_id=issue.pk,action__in=ACTIONS).order_by('-created_at','-id')[:25]
    return {'version':issue.version,'fingerprint':fingerprint,'state':state,'ready':ready,'checks':checks,'actions':actions,
            'decision_id':str(latest.pk) if latest else None,'history':[{'id':str(x.pk),'action':x.action,'actor_id':str(x.actor_id),'created_at':x.created_at,'reason':x.details.get('reason',''),'issue_version':x.details.get('issue_version')} for x in history]}


class ReviewInput(StrictSerializer):
    action = serializers.ChoiceField(choices=['submit','approve','return'])
    expected_version = serializers.IntegerField(min_value=1)
    fingerprint = serializers.RegexField(r'^[0-9a-f]{64}$')
    decision_id = serializers.UUIDField(allow_null=True)
    reason = serializers.CharField(max_length=2000)
    acknowledge_warnings = serializers.BooleanField(default=False)
    review_teasers = serializers.BooleanField(default=False)


class IssueReview(APIView):
    permission_classes = [EditorialAccess]

    @transaction.atomic
    def get(self, request, pk):
        directory_lock()
        issue = get_object_or_404(Issue.objects.select_for_update(), pk=pk)
        return Response(review_state(issue,request.user))

    @transaction.atomic
    def post(self, request, pk):
        data = ReviewInput(data=request.data); data.is_valid(raise_exception=True)
        v = data.validated_data
        directory_lock()
        issue = get_object_or_404(Issue.objects.select_for_update(), pk=pk)
        current = review_state(issue,request.user)
        if (v['expected_version']!=issue.version or v['fingerprint']!=current['fingerprint'] or
                (str(v['decision_id']) if v['decision_id'] else None)!=current['decision_id']):
            return Response({'code':'stale_review','message':'Refresh readiness before recording a decision.'},status=409)
        action = v['action']
        if action not in current['actions']:
            return Response({'code':'review_not_allowed','message':'Action unavailable: readiness, state, permission or independent reviewer requirement not met.'},status=403)
        if action in ('submit','approve') and any(not x['passed'] for x in current['checks'] if x['severity']=='warning') and not v['acknowledge_warnings']:
            raise serializers.ValidationError({'acknowledge_warnings':'Acknowledge all warnings before proceeding.'})
        if action=='approve' and issue.teasers.exists() and not v['review_teasers']:
            raise serializers.ValidationError({'review_teasers':'Confirm independent review of the upcoming teaser sources.'})
        audit(request.user,{'submit':ACTIONS[0],'approve':ACTIONS[1],'return':ACTIONS[2]}[action],issue.pk,
              issue_version=issue.version,fingerprint=current['fingerprint'],reason=v['reason'],acknowledge_warnings=v['acknowledge_warnings'],review_teasers=v['review_teasers'],previous_decision=current['decision_id'])
        return Response(review_state(issue,request.user))
