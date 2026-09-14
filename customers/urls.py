from django.urls import path

from customers import views

app_name = "customers"
urlpatterns = [
    path("", views.customer_list, name="list"),
    path("customers/new/", views.customer_new, name="new"),
    path("customers/duplicates/", views.duplicates_check, name="duplicates"),
    path("customers/<int:pk>/", views.customer_detail, name="detail"),
    path("customers/<int:pk>/edit/", views.customer_edit, name="edit"),
    path("customers/<int:pk>/archive/", views.customer_archive, name="archive"),
    path("customers/members/<int:pk>/archive/", views.member_archive, name="member_archive"),
]
