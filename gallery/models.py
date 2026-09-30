from django.conf import settings
from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver


class Category(models.Model):
    name = models.CharField("nom", max_length=50, unique=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "catégorie"

    def __str__(self):
        return self.name


class Photo(models.Model):
    caption = models.CharField("légende", max_length=500, blank=True)
    category = models.ForeignKey(
        Category, verbose_name="catégorie", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="photos",
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="ajoutée par", on_delete=models.PROTECT,
    )
    image = models.FileField("photo", upload_to="photos/%Y/%m/")
    thumbnail = models.FileField("miniature", upload_to="thumbnails/%Y/%m/")
    width = models.PositiveIntegerField()
    height = models.PositiveIntegerField()
    size = models.PositiveIntegerField("taille enregistrée")
    created_at = models.DateTimeField("ajoutée le", auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        verbose_name = "photo"

    def __str__(self):
        return self.caption or f"Photo {self.pk}"


@receiver(post_delete, sender=Photo)
def remove_photo_files(sender, instance, **kwargs):
    # Also releases disk space for deletions made through Django admin.
    instance.image.delete(save=False)
    instance.thumbnail.delete(save=False)
