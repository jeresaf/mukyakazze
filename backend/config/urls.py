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
