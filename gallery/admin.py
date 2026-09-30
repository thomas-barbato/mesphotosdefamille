from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from .models import Category, Photo


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    search_fields = ["name"]


@admin.register(Photo)
class PhotoAdmin(admin.ModelAdmin):
    list_display = ["__str__", "category", "owner", "created_at"]
    list_filter = ["category", "owner"]
    search_fields = ["caption"]
    fields = ["caption", "category", "owner", "created_at", "preview", "width", "height", "size"]
    readonly_fields = ["owner", "created_at", "preview", "width", "height", "size"]

    @admin.display(description="Photo")
    def preview(self, photo):
        return format_html('<a href="{}">Voir la photo en grand</a>', reverse("photo-file", args=[photo.pk, "grande"]))

    def has_add_permission(self, request):
        return False
