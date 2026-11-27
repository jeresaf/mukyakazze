from django.urls import path
from accounts import views

base = 'api/v1/admin/'
urlpatterns = [path('health/live/', views.live), path('health/ready/', views.ready), path(base + 'auth/session/', views.Session.as_view()), path(base + 'auth/login/', views.Login.as_view()), path(base + 'auth/logout/', views.Logout.as_view()), path(base + 'roles/', views.Roles.as_view()), path(base + 'users/', views.Users.as_view()), path(base + 'users/<uuid:pk>/', views.UserDetail.as_view()), path(base + 'users/<uuid:pk>/revoke/', views.Revoke.as_view()), path(base + 'audit/', views.Audit.as_view())]
