from django.urls import re_path

from orbit.dashboard.orbs import views

urlpatterns = [
    re_path(r'^$', views.IndexView.as_view(), name='index'),
    re_path(r'^(?P<orb_id>[^/]+)/$', views.DetailView.as_view(),
            name='detail'),
]
