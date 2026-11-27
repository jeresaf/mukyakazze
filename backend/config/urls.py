from django.urls import path
from accounts import views
from catalog import views as catalog_views

base = 'api/v1/admin/'
urlpatterns = [path('health/live/', views.live), path('health/ready/', views.ready), path(base + 'auth/session/', views.Session.as_view()), path(base + 'auth/login/', views.Login.as_view()), path(base + 'auth/logout/', views.Logout.as_view()), path(base + 'roles/', views.Roles.as_view()), path(base + 'users/', views.Users.as_view()), path(base + 'users/<uuid:pk>/', views.UserDetail.as_view()), path(base + 'users/<uuid:pk>/revoke/', views.Revoke.as_view()), path(base + 'audit/', views.Audit.as_view()), path(base + 'categories/', catalog_views.Categories.as_view()), path(base + 'categories/<uuid:pk>/', catalog_views.CategoryDetail.as_view())]

from catalog.directory import RESOURCES, DirectoryList, DirectoryDetail

for resource in RESOURCES:
    urlpatterns += [path(base + resource + "/", DirectoryList.as_view(resource=resource)), path(base + resource + "/<uuid:pk>/", DirectoryDetail.as_view(resource=resource))]

from catalog.media import MediaList, MediaDetail, MediaContent
urlpatterns += [path(base+'media/', MediaList.as_view()), path(base+'media/<uuid:pk>/', MediaDetail.as_view()), path(base+'media/<uuid:pk>/content/', MediaContent.as_view())]

from events.api import Events, EventDetail, EventAction, EventHistory
urlpatterns += [path(base+'events/', Events.as_view()), path(base+'events/<uuid:pk>/', EventDetail.as_view()), path(base+'events/<uuid:pk>/actions/', EventAction.as_view()), path(base+'events/<uuid:pk>/history/', EventHistory.as_view())]

from events.advanced import RepeatOccurrences, TicketTiers, EventStatistics
urlpatterns += [path(base+'events/statistics/', EventStatistics.as_view()), path(base+'events/<uuid:pk>/repeat/', RepeatOccurrences.as_view()), path(base+'events/<uuid:pk>/ticket-tiers/', TicketTiers.as_view())]

from events.assignments import AssignmentChoices, Assignments, Attachments
urlpatterns += [path(base+'events/assignment-choices/', AssignmentChoices.as_view()), path(base+'events/<uuid:pk>/assignments/', Assignments.as_view()), path(base+'events/<uuid:pk>/attachments/', Attachments.as_view())]

from events.workbooks import WorkbookImport, WorkbookExport
urlpatterns += [path(base+'events/workbook/import/', WorkbookImport.as_view()), path(base+'events/workbook/export/', WorkbookExport.as_view())]

from editorial.api import Issues, IssueDetail, Candidates, IssueRoster
urlpatterns += [path(base+'issues/', Issues.as_view()), path(base+'issues/<uuid:pk>/', IssueDetail.as_view()), path(base+'issues/<uuid:pk>/candidates/', Candidates.as_view()), path(base+'issues/<uuid:pk>/roster/', IssueRoster.as_view())]

from editorial.presentation import Cover, Grid
urlpatterns += [path(base+'issues/<uuid:pk>/cover/', Cover.as_view()), path(base+'issues/<uuid:pk>/grid/', Grid.as_view())]
