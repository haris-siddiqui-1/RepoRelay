from django.urls import re_path

from dojo.home import views

urlpatterns = [
    #  dojo home pages
    re_path(r"^$", views.home, name="home"),
    re_path(r"^dashboard$", views.dashboard, name="dashboard"),
    re_path(r"^dashboard_modern$", views.dashboard_modern, name="dashboard_modern"),
    re_path(r"^support$", views.support, name="support"),
    re_path(r"^datatable-demo$", views.datatable_demo, name="datatable_demo"),
]
