from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views

urlpatterns = [
    path("", views.gallery, name="gallery"),
    path("deconnexion/", LogoutView.as_view(), name="logout"),
    path("photos/ajouter/", views.upload, name="upload"),
    path("categories/creer/", views.create_category, name="category-create"),
    path("photos/<int:pk>/modifier/", views.edit_photo, name="photo-edit"),
    path("photos/<int:pk>/supprimer/", views.delete_photo, name="photo-delete"),
    path("photos/<int:pk>/<str:variant>.webp", views.photo_file, name="photo-file"),
]
