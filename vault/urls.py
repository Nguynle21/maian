from django.urls import path

from vault import views

app_name = "vault"
urlpatterns = [
    path("upload/<int:customer_pk>/", views.upload, name="upload"),
    path("<int:pk>/download/", views.download, name="download"),
    path("<int:pk>/archive/", views.archive_document, name="archive"),
]
