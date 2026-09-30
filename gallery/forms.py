from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError

from .images import validate_image
from .models import Category, Photo


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleImageField(forms.FileField):
    widget = MultipleFileInput(attrs={"accept": "image/jpeg,image/png,image/webp"})

    def clean(self, data, initial=None):
        if not data:
            raise ValidationError("Choisissez au moins une photo.")
        uploads = data if isinstance(data, (list, tuple)) else [data]
        if len(uploads) > settings.MAX_PHOTOS_PER_UPLOAD:
            raise ValidationError("Ajoutez au maximum 12 photos à la fois.")
        # Validate the whole batch first. Conversion happens one file at a time
        # in the view so a batch never retains all uncompressed images in RAM.
        for upload in uploads:
            super().clean(upload, initial)
            validate_image(upload)
            upload.seek(0)
        return uploads


class UploadForm(forms.Form):
    photos = MultipleImageField(label="Photos")
    caption = forms.CharField(
        label="Légende", max_length=500, required=False,
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "L’histoire derrière ces photos…"}),
    )
    category = forms.ModelChoiceField(
        label="Catégorie", queryset=Category.objects.all(), required=False,
        empty_label="Sans catégorie",
    )


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ["name"]
        widgets = {"name": forms.TextInput(attrs={"placeholder": "Vacances, anniversaires, petits bonheurs…"})}

    def clean_name(self):
        name = " ".join(self.cleaned_data["name"].split())
        if not name:
            raise ValidationError("Donnez un nom à votre catégorie.")
        if any(existing.casefold() == name.casefold() for existing in Category.objects.values_list("name", flat=True)):
            raise ValidationError("Cette catégorie existe déjà.")
        return name


class PhotoForm(forms.ModelForm):
    class Meta:
        model = Photo
        fields = ["caption", "category"]
        widgets = {"caption": forms.Textarea(attrs={"rows": 4})}
