from django.contrib import admin
from django.urls import include, path

from gallery.views import PrivateLoginView

admin.site.site_header = "Mes photos de famille"
admin.site.site_title = "Administration des souvenirs"
admin.site.index_title = "La maison des souvenirs"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("connexion/", PrivateLoginView.as_view(), name="login"),
    path("", include("gallery.urls")),
]
