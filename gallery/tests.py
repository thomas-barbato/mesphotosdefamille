from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.exceptions import ValidationError
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from PIL import Image

from .models import Category, Photo


def image_upload(name="souvenir.png", size=(80, 60), image_format="PNG", exif=None):
    buffer = BytesIO()
    image = Image.new("RGB", size, "#bf7655")
    image.save(buffer, image_format, **({"exif": exif} if exif else {}))
    return SimpleUploadedFile(name, buffer.getvalue(), content_type=f"image/{image_format.lower()}")


class GalleryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user("famille", password="NotreAlbum-2026!")
        cls.other = get_user_model().objects.create_user("autre", password="AutreAlbum-2026!")
        cls.staff = get_user_model().objects.create_user("admin", password="AdminAlbum-2026!", is_staff=True)
        cls.category = Category.objects.create(name="Vacances")

    def setUp(self):
        self.media = TemporaryDirectory()
        self.addCleanup(self.media.cleanup)
        self.settings_override = override_settings(MEDIA_ROOT=self.media.name)
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.client.force_login(self.user)

    def upload(self, **kwargs):
        data = {"photos": [image_upload()], "caption": "Un été ensemble", "category": self.category.pk}
        data.update(kwargs)
        return self.client.post(reverse("upload"), data)

    def test_gallery_and_files_require_login(self):
        self.upload()
        photo = Photo.objects.get()
        self.client.logout()
        for url in [reverse("gallery"), reverse("photo-file", args=[photo.pk, "grande"]),
                    reverse("photo-file", args=[photo.pk, "miniature"]),
                    reverse("photo-edit", args=[photo.pk])]:
            with self.subTest(url=url):
                self.assertRedirects(self.client.get(url), reverse("login"))
        self.assertRedirects(self.client.get(reverse("photo-file", args=[999999, "grande"])), reverse("login"))
        for url in [reverse("upload"), reverse("category-create"), reverse("photo-delete", args=[photo.pk])]:
            with self.subTest(url=url):
                self.assertRedirects(self.client.post(url, {}), reverse("login"))
        self.assertEqual(self.client.get(f"/media/{photo.image.name}").status_code, 404)

    def test_old_photo_login_links_redirect_to_clean_login(self):
        self.upload()
        photo = Photo.objects.get()
        self.client.logout()
        photo_url = reverse("photo-file", args=[photo.pk, "grande"])
        response = self.client.get(reverse("login"), {"next": photo_url})
        self.assertRedirects(response, reverse("login"))
        login_page = self.client.get(response.url)
        self.assertNotContains(login_page, photo_url)
        self.assertNotContains(login_page, 'name="next"')
        self.assertIn("no-store", response["Cache-Control"])

    def test_login_always_returns_to_gallery_without_photo_next(self):
        self.upload()
        photo_url = reverse("photo-file", args=[Photo.objects.get().pk, "grande"])
        self.client.logout()
        data = {"username": "famille", "password": "wrong", "next": photo_url}
        failed = self.client.post(reverse("login"), data)
        self.assertRedirects(failed, reverse("login"))
        self.assertEqual(self.client.get(failed.url).status_code, 200)
        data["password"] = "NotreAlbum-2026!"
        self.assertRedirects(self.client.post(reverse("login"), data), reverse("gallery"))
        self.assertRedirects(self.client.get(reverse("login"), {"next": photo_url}), reverse("gallery"))

    def test_upload_converts_and_removes_metadata(self):
        exif = Image.Exif()
        exif[274] = 6  # Camera orientation: rotate a landscape image to portrait.
        exif[270] = "Private camera metadata"
        response = self.upload(photos=[image_upload("camera.jpg", image_format="JPEG", exif=exif)])
        self.assertEqual(response.status_code, 302)
        photo = Photo.objects.get()
        self.assertEqual((photo.width, photo.height), (60, 80))
        self.assertEqual(photo.owner, self.user)
        for field in (photo.image, photo.thumbnail):
            self.assertTrue(field.name.endswith(".webp"))
            with Image.open(field.path) as stored:
                self.assertEqual(stored.format, "WEBP")
                self.assertFalse(stored.getexif())
                self.assertNotIn("exif", stored.info)
        self.assertEqual(photo.size, Path(photo.image.path).stat().st_size + Path(photo.thumbnail.path).stat().st_size)

    def test_large_photos_and_thumbnails_are_resized(self):
        self.upload(photos=[image_upload(size=(3200, 1600))])
        photo = Photo.objects.get()
        self.assertEqual((photo.width, photo.height), (2560, 1280))
        with Image.open(photo.thumbnail.path) as thumbnail:
            self.assertEqual(thumbnail.size, (600, 300))

    def test_async_upload_returns_get_url_and_new_photo(self):
        response = self.client.post(reverse("upload"), {
            "photos": [image_upload(), image_upload("second.png")],
            "caption": "Une belle journée", "category": self.category.pk,
        }, HTTP_X_REQUESTED_WITH="fetch")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Photo.objects.count(), 2)
        gallery = self.client.get(response.json()["url"])
        self.assertContains(gallery, "Une belle journée")
        self.assertEqual(len(gallery.context["page_obj"]), 2)

    def test_refresh_after_upload_does_not_resubmit(self):
        response = self.upload()
        for _ in range(2):
            self.assertEqual(self.client.get(response.url).status_code, 200)
        self.assertEqual(Photo.objects.count(), 1)

    def test_invalid_batch_leaves_no_photos_or_files(self):
        bad = SimpleUploadedFile("fake.jpg", b"This is not an image", content_type="image/jpeg")
        response = self.upload(photos=[image_upload(), bad])
        self.assertRedirects(response, reverse("gallery"))
        self.assertEqual(Photo.objects.count(), 0)
        self.assertEqual(list(Path(self.media.name).rglob("*.webp")), [])

    def test_async_errors_keep_form_open(self):
        response = self.client.post(reverse("upload"), {}, HTTP_X_REQUESTED_WITH="fetch")
        self.assertEqual(response.status_code, 400)
        self.assertIn("photos", response.json()["errors"])

    def test_conversion_failure_rolls_back_entire_batch(self):
        from .images import prepare_image
        calls = 0

        def fail_on_second(upload):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise ValidationError("Fichier incomplet.")
            return prepare_image(upload)

        with patch("gallery.views.prepare_image", side_effect=fail_on_second):
            response = self.upload(photos=[image_upload(), image_upload("second.png")])
        self.assertRedirects(response, reverse("gallery"))
        self.assertEqual(Photo.objects.count(), 0)
        self.assertEqual(list(Path(self.media.name).rglob("*.webp")), [])

    @override_settings(MAX_PHOTO_BYTES=20)
    def test_oversize_file_is_rejected(self):
        self.assertEqual(self.upload().status_code, 302)
        self.assertEqual(Photo.objects.count(), 0)

    @override_settings(MAX_PHOTO_PIXELS=100)
    def test_pixel_limit_is_checked_before_conversion(self):
        self.assertEqual(self.upload().status_code, 302)
        self.assertEqual(Photo.objects.count(), 0)

    def test_upload_limit_and_unsupported_format(self):
        self.upload(photos=[image_upload(f"{i}.png") for i in range(13)])
        self.assertEqual(Photo.objects.count(), 0)
        self.upload(photos=[image_upload("animation.gif", image_format="GIF")])
        self.assertEqual(Photo.objects.count(), 0)

    def test_category_creation_normalizes_and_prevents_duplicates(self):
        response = self.client.post(reverse("category-create"), {"name": "  Les   fêtes  "}, HTTP_X_REQUESTED_WITH="fetch")
        self.assertEqual(response.status_code, 200)
        category = Category.objects.get(name="Les fêtes")
        self.assertEqual(response.json()["url"], f"/?categorie={category.pk}")
        duplicate = self.client.post(reverse("category-create"), {"name": "VACANCES"}, HTTP_X_REQUESTED_WITH="fetch")
        self.assertEqual(duplicate.status_code, 400)
        self.assertEqual(Category.objects.count(), 2)
        unicode_duplicate = self.client.post(reverse("category-create"), {"name": "LES FÊTES"}, HTTP_X_REQUESTED_WITH="fetch")
        self.assertEqual(unicode_duplicate.status_code, 400)

    def test_categories_search_and_html_escaping(self):
        self.upload(caption='<script>alert("bonjour")</script>')
        other_category = Category.objects.create(name="Anniversaires")
        self.upload(category=other_category.pk, caption="Le gâteau")
        response = self.client.get(reverse("gallery"), {"categorie": self.category.pk})
        self.assertEqual(response.context["page_obj"].paginator.count, 1)
        self.assertNotContains(response, '<script>alert("bonjour")</script>')
        search = self.client.get(reverse("gallery"), {"q": "gâteau"})
        self.assertEqual(search.context["page_obj"].paginator.count, 1)
        self.assertContains(search, "Le gâteau")
        for invalid in ("abc", "9999999999999999999999999999999"):
            self.assertEqual(self.client.get(reverse("gallery"), {"categorie": invalid}).status_code, 404)

    def test_private_file_response(self):
        self.upload()
        photo = Photo.objects.get()
        response = self.client.get(reverse("photo-file", args=[photo.pk, "grande"]))
        self.assertEqual(response["Content-Type"], "image/webp")
        self.assertIn("no-store", response["Cache-Control"])
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        response.close()
        self.assertEqual(self.client.get(reverse("photo-file", args=[photo.pk, "unknown"])).status_code, 404)
        self.assertIn("no-store", self.client.get(reverse("gallery"))["Cache-Control"])

    def test_only_owner_and_staff_can_edit_or_delete(self):
        self.upload()
        photo = Photo.objects.get()
        self.client.force_login(self.other)
        for url in (reverse("photo-edit", args=[photo.pk]), reverse("photo-delete", args=[photo.pk])):
            self.assertEqual(self.client.post(url, {"caption": "Autre légende"}).status_code, 404)
        self.client.force_login(self.staff)
        response = self.client.post(reverse("photo-edit", args=[photo.pk]), {"caption": "La famille", "category": ""})
        self.assertEqual(response.status_code, 302)
        photo.refresh_from_db()
        self.assertEqual(photo.caption, "La famille")
        self.assertIsNone(photo.category)

    def test_delete_removes_both_files_and_refresh_is_safe(self):
        self.upload()
        photo = Photo.objects.get()
        paths = [Path(photo.image.path), Path(photo.thumbnail.path)]
        response = self.client.post(reverse("photo-delete", args=[photo.pk]))
        self.assertEqual(response.status_code, 302)
        self.client.get(response.url)
        self.client.get(response.url)
        self.assertEqual(Photo.objects.count(), 0)
        self.assertTrue(all(not path.exists() for path in paths))

    def test_category_deletion_keeps_its_photos(self):
        self.upload()
        self.category.delete()
        self.assertEqual(Photo.objects.count(), 1)
        self.assertIsNone(Photo.objects.get().category)

    def test_csrf_and_post_only_actions(self):
        secure_client = Client(enforce_csrf_checks=True)
        secure_client.force_login(self.user)
        self.assertEqual(secure_client.post(reverse("upload"), {}).status_code, 403)
        for name in ("upload", "category-create", "logout"):
            self.assertEqual(self.client.get(reverse(name)).status_code, 405)

    def test_login_success_failure_and_logout_use_redirects(self):
        self.client.logout()
        response = self.client.post(reverse("login"), {"username": "famille", "password": "wrong"})
        self.assertEqual(response.status_code, 302)
        self.assertContains(self.client.get(response.url), "incorrect")
        self.assertEqual(self.client.get(response.url).status_code, 200)
        response = self.client.post(reverse("login"), {"username": "famille", "password": "NotreAlbum-2026!", "next": "https://evil.example"})
        self.assertRedirects(response, reverse("gallery"))
        self.assertRedirects(self.client.post(reverse("logout")), reverse("login"))

    def test_accounts_are_only_created_by_admin(self):
        self.assertEqual(self.client.get("/inscription/").status_code, 404)
        self.assertEqual(self.client.get(reverse("admin:index")).status_code, 302)

    def test_gallery_is_paginated(self):
        Photo.objects.bulk_create([
            Photo(owner=self.user, caption=f"Souvenir {i}", image=f"{i}.webp",
                  thumbnail=f"{i}-thumb.webp", width=80, height=60, size=100)
            for i in range(26)
        ])
        first = self.client.get(reverse("gallery"))
        second = self.client.get(reverse("gallery"), {"page": 2})
        self.assertEqual(len(first.context["page_obj"]), 24)
        self.assertEqual(len(second.context["page_obj"]), 2)
