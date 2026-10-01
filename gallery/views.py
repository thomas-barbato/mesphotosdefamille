import uuid
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Count, Sum
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from .forms import CategoryForm, PhotoForm, UploadForm
from .images import prepare_image
from .models import Category, Photo


class PrivateLoginView(LoginView):
    template_name = "registration/login.html"
    redirect_authenticated_user = True

    def get(self, request, *args, **kwargs):
        if "next" in request.GET:
            return redirect("login")
        return super().get(request, *args, **kwargs)

    def get_redirect_url(self):
        return ""

    def form_invalid(self, form):
        messages.error(self.request, "L’identifiant ou le mot de passe est incorrect.")
        return redirect("login")


def is_async(request):
    return request.headers.get("X-Requested-With") == "fetch"


def gallery_url(category=None):
    url = reverse("gallery")
    return f"{url}?{urlencode({'categorie': category.pk})}" if category else url


@login_required(redirect_field_name=None)
@never_cache
@require_GET
def gallery(request):
    categories = Category.objects.annotate(photo_count=Count("photos"))
    photos = Photo.objects.select_related("category", "owner")
    current_category = None
    category_id = request.GET.get("categorie", "")
    if category_id:
        try:
            current_category = get_object_or_404(Category, pk=int(category_id))
        except (ValueError, OverflowError) as error:
            raise Http404 from error
        photos = photos.filter(category=current_category)
    query = request.GET.get("q", "").strip()[:100]
    if query:
        photos = photos.filter(caption__icontains=query)
    page = Paginator(photos, 24).get_page(request.GET.get("page"))
    totals = Photo.objects.aggregate(count=Count("pk"), size=Sum("size"))
    return render(request, "gallery/gallery.html", {
        "categories": categories, "current_category": current_category,
        "query": query, "page_obj": page, "totals": totals,
        "upload_form": UploadForm(initial={"category": current_category}),
        "category_form": CategoryForm(),
        "page_query": urlencode({key: value for key, value in
            {"categorie": category_id, "q": query}.items() if value}),
    })


@login_required(redirect_field_name=None)
@require_POST
def upload(request):
    form = UploadForm(request.POST, request.FILES)
    if not form.is_valid():
        return form_error(request, form)
    stored_fields = []
    try:
        with transaction.atomic():
            for uploaded in form.cleaned_data["photos"]:
                full, thumbnail, (width, height) = prepare_image(uploaded)
                name = f"{uuid.uuid4().hex}.webp"
                photo = Photo(
                    owner=request.user, caption=form.cleaned_data["caption"],
                    category=form.cleaned_data["category"], width=width, height=height,
                    size=len(full) + len(thumbnail),
                )
                photo.image.save(name, ContentFile(full), save=False)
                stored_fields.append(photo.image)
                photo.thumbnail.save(name, ContentFile(thumbnail), save=False)
                stored_fields.append(photo.thumbnail)
                photo.save()
    except Exception as error:
        # Filesystem writes are not rolled back by the database transaction.
        for field in stored_fields:
            field.delete(save=False)
        if isinstance(error, ValidationError):
            form.add_error("photos", error)
            return form_error(request, form)
        raise
    count = len(form.cleaned_data["photos"])
    messages.success(request, f"{count} photo{'s' if count > 1 else ''} ajoutée{'s' if count > 1 else ''}. Vos souvenirs sont à leur place.")
    url = gallery_url(form.cleaned_data["category"])
    return JsonResponse({"url": url}) if is_async(request) else redirect(url)


@login_required(redirect_field_name=None)
@require_POST
def create_category(request):
    form = CategoryForm(request.POST)
    if not form.is_valid():
        return form_error(request, form)
    try:
        category = form.save()
    except IntegrityError:
        form.add_error("name", "Cette catégorie existe déjà.")
        return form_error(request, form)
    messages.success(request, f"La catégorie « {category.name} » est prête à accueillir vos photos.")
    url = gallery_url(category)
    return JsonResponse({"url": url}) if is_async(request) else redirect(url)


def form_error(request, form):
    if is_async(request):
        return JsonResponse({"errors": form.errors.get_json_data()}, status=400)
    # Even validation failures follow Post/Redirect/Get for non-JS submissions.
    for errors in form.errors.values():
        for error in errors:
            messages.error(request, error)
    return redirect("gallery")


@login_required(redirect_field_name=None)
@never_cache
@require_GET
def photo_file(request, pk, variant):
    if variant not in {"miniature", "grande"}:
        raise Http404
    photo = get_object_or_404(Photo, pk=pk)
    field = photo.thumbnail if variant == "miniature" else photo.image
    try:
        response = FileResponse(field.open("rb"), content_type="image/webp")
    except FileNotFoundError as error:
        raise Http404 from error
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response


def editable_photo(request, pk):
    photos = Photo.objects.all() if request.user.is_staff else Photo.objects.filter(owner=request.user)
    return get_object_or_404(photos, pk=pk)


@login_required(redirect_field_name=None)
@never_cache
def edit_photo(request, pk):
    photo = editable_photo(request, pk)
    form = PhotoForm(request.POST or None, instance=photo)
    if request.method == "POST":
        if form.is_valid():
            form.save()
            messages.success(request, "Votre souvenir a été mis à jour.")
            return redirect(gallery_url(photo.category))
        for errors in form.errors.values():
            for error in errors:
                messages.error(request, error)
        return redirect("photo-edit", pk=pk)
    return render(request, "gallery/edit.html", {"photo": photo, "form": form})


@login_required(redirect_field_name=None)
@require_POST
def delete_photo(request, pk):
    photo = editable_photo(request, pk)
    url = gallery_url(photo.category)
    photo.delete()
    messages.success(request, "La photo a été supprimée.")
    return redirect(url)
