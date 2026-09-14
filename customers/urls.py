from django.http import HttpResponse
from django.urls import path

app_name = "customers"
urlpatterns = [
    path("", lambda request: HttpResponse("Customers"), name="list"),
    path("customers/new/", lambda request: HttpResponse("New"), name="new"),
]
