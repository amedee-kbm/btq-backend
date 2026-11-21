"""Seed the catalog from a folder of photos, one product per photo.

    uv run python manage.py seed_catalog <photos-dir> [--wipe]

Each top-level folder becomes a category and each folder inside it a
subcategory (two levels at most). Every photo becomes a published product with
just that photo and its category: no name, price or variants, to be filled in
from the admin. Videos and other files are skipped.

A top-level folder named "new arrivals ..." becomes the New Arrivals collection
instead of a category. Its photos are copies of ones in the category folders,
matched by content, so they point at those products rather than duplicating
them. Categories left with no folder and no products are removed.

Photos are keyed by their storage path, so re-running after a dropped
connection picks up where it left off. --wipe first deletes every product,
category, collection and tag, and every uploaded product and category photo.
Sizes and colours are kept.
"""

import hashlib
import io
import time
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import OperationalError, connection, transaction
from django.utils.text import slugify
from PIL import Image, ImageOps

from catalog import revalidate
from catalog.models import (
    Category,
    Collection,
    CollectionProduct,
    Product,
    ProductImage,
    Tag,
)

MAX_IMAGE_SIDE = 1600
PHOTO_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
UPLOAD_DIRS = ["products", "categories"]
NEW_ARRIVALS_PREFIX = "new arrivals"


def file_hash(path):
    return hashlib.md5(path.read_bytes()).hexdigest()


def web_jpeg(path):
    with Image.open(path) as im:
        im = ImageOps.exif_transpose(im).convert("RGB")
        im.thumbnail((MAX_IMAGE_SIDE, MAX_IMAGE_SIDE))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=82, optimize=True, progressive=True)
    return buf.getvalue()


def display_name(folder_name):
    return folder_name[:1].upper() + folder_name[1:]


def upload_name_for(photo, category):
    # "WA0049(1)" -> "wa0049-1", not "wa00491".
    stem = photo.stem.replace("(", "-")
    return f"products/{category.slug}/{slugify(stem)}.jpg"


def photos_in(folder):
    return sorted(
        p
        for p in folder.iterdir()
        if p.is_file() and p.suffix.lower() in PHOTO_SUFFIXES
    )


class Command(BaseCommand):
    help = "Seed one product per photo, with categories from the folder names."

    def add_arguments(self, parser):
        parser.add_argument("photos_dir", type=Path)
        parser.add_argument(
            "--wipe",
            action="store_true",
            help="Delete all products, categories, collections, tags and photos first.",
        )

    def handle(self, photos_dir, wipe, **options):
        if not photos_dir.is_dir():
            raise CommandError(f"{photos_dir} is not a directory")
        arrivals = [
            p
            for p in photos_dir.iterdir()
            if p.is_dir() and p.name.lower().startswith(NEW_ARRIVALS_PREFIX)
        ]
        tree = self.read_tree(photos_dir, skip=arrivals)

        # One webhook at the end instead of one per product.
        revalidate_url = settings.FRONTEND_REVALIDATE_URL
        settings.FRONTEND_REVALIDATE_URL = ""
        try:
            if wipe:
                self.wipe()
            categories = self.seed(tree)
            self.seed_new_arrivals(tree, categories, arrivals)
        finally:
            settings.FRONTEND_REVALIDATE_URL = revalidate_url
        with transaction.atomic():
            revalidate.schedule("catalog")

    def read_tree(self, root, skip=()):
        """[(folder, parent folder or None, photos)], parents before children."""
        tree = []
        for folder in sorted(p for p in root.iterdir() if p.is_dir()):
            if folder in skip:
                continue
            tree.append((folder, None, photos_in(folder)))
            for child in sorted(p for p in folder.iterdir() if p.is_dir()):
                if any(p.is_dir() for p in child.iterdir()):
                    raise CommandError(f"{child}: categories nest two levels at most")
                tree.append((child, folder, photos_in(child)))
        if not any(photos for _, _, photos in tree):
            raise CommandError(f"No photos found in {root}")
        slugs = [slugify(folder.name) for folder, _, _ in tree]
        if len(set(slugs)) != len(slugs):
            raise CommandError(f"Two folders share a slug: {slugs}")
        names = [
            f"{slugify(folder.name)}/{slugify(p.stem.replace('(', '-'))}"
            for folder, _, photos in tree
            for p in photos
        ]
        if len(set(names)) != len(names):
            raise CommandError("Two photos in one folder share a storage name")
        return tree

    def wipe(self):
        with transaction.atomic():
            count = Product.objects.count()
            Product.objects.all().delete()  # images, variants, favorites cascade
            Collection.objects.all().delete()
            Tag.objects.all().delete()
            Category.objects.filter(parent__isnull=False).delete()  # parent is PROTECT
            Category.objects.all().delete()
        # Everything under the upload folders, orphans included. Files go only
        # once the rows are gone for good.
        storage = ProductImage._meta.get_field("image").storage
        files = 0
        for top in UPLOAD_DIRS:
            for name in self.walk(storage, top):
                storage.delete(name)
                files += 1
        self.stdout.write(f"Deleted {count} products and {files} files.")

    def walk(self, storage, path):
        try:
            dirs, files = storage.listdir(path)
        except FileNotFoundError:
            return
        for name in files:
            yield f"{path}/{name}"
        for name in dirs:
            yield from self.walk(storage, f"{path}/{name}")

    def seed(self, tree):
        categories = {}
        with transaction.atomic():
            for position, (folder, parent, _) in enumerate(tree):
                category, _ = Category.objects.update_or_create(
                    slug=slugify(folder.name),
                    defaults={
                        "name": display_name(folder.name),
                        "parent": categories.get(parent),
                        "position": position,
                    },
                )
                categories[folder] = category
            # e.g. a folder renamed between runs.
            Category.objects.exclude(pk__in=[c.pk for c in categories.values()]).filter(
                products__isnull=True, children__isnull=True
            ).delete()

        # Oldest photo first, so the newest ones list first on the site.
        photos = sorted(
            ((photo, folder) for folder, _, photos in tree for photo in photos),
            key=lambda item: item[0].name,
        )
        created = 0
        for i, (photo, folder) in enumerate(photos, start=1):
            category = categories[folder]
            upload_name = upload_name_for(photo, category)
            if ProductImage.objects.filter(image=upload_name).exists():
                continue
            self.with_retries(lambda: self.seed_product(photo, category, upload_name))
            created += 1
            self.stdout.write(f"  [{i}/{len(photos)}] {folder.name}/{photo.name}")

        with transaction.atomic():
            for category in categories.values():
                first = (
                    ProductImage.objects.filter(product__categories=category)
                    .order_by("product__created_at", "id")
                    .first()
                )
                # Reuses the product photo's file; no second upload.
                category.cover_image = first.image.name if first else ""
                category.save(update_fields=["cover_image"])

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {len(categories)} categories and {created} new products "
                f"({len(photos)} photos in total)."
            )
        )
        return categories

    def seed_new_arrivals(self, tree, categories, folders):
        if not folders:
            return
        by_hash = {
            file_hash(photo): upload_name_for(photo, categories[folder])
            for folder, _, photos in tree
            for photo in photos
        }
        uploads = dict(
            ProductImage.objects.filter(image__in=by_hash.values()).values_list(
                "image", "product_id"
            )
        )
        product_ids, unmatched = [], []
        for folder in folders:
            for photo in photos_in(folder):
                product_id = uploads.get(by_hash.get(file_hash(photo)))
                if product_id is None:
                    unmatched.append(f"{folder.name}/{photo.name}")
                elif product_id not in product_ids:
                    product_ids.append(product_id)

        with transaction.atomic():
            collection, _ = Collection.objects.update_or_create(
                slug="new-arrivals",
                defaults={"name": "New Arrivals", "position": 0, "is_active": True},
            )
            CollectionProduct.objects.filter(collection=collection).delete()
            CollectionProduct.objects.bulk_create(
                CollectionProduct(collection=collection, product_id=pk, position=i)
                for i, pk in enumerate(product_ids)
            )
        self.stdout.write(
            self.style.SUCCESS(f"New Arrivals: {len(product_ids)} products.")
        )
        for name in unmatched:
            self.stderr.write(f"  not in any category folder, skipped: {name}")

    def with_retries(self, fn, attempts=3):
        for attempt in range(1, attempts + 1):
            try:
                with transaction.atomic():
                    return fn()
            except OperationalError:
                if attempt == attempts:
                    raise
                self.stderr.write("  connection lost, retrying...")
                connection.close()
                time.sleep(5 * attempt)

    def seed_product(self, photo, category, upload_name):
        product = Product.objects.create(is_published=True)
        product.categories.set(filter(None, [category, category.parent]))
        image = ProductImage(product=product, position=0)
        storage = image.image.storage
        # Left over from a run whose DB write was lost; no row uses it.
        if storage.exists(upload_name):
            storage.delete(upload_name)
        # The storage path is the resume key, so it must come out exactly.
        image.image.name = storage.save(
            upload_name, ContentFile(web_jpeg(photo))
        )
        if image.image.name != upload_name:
            raise CommandError(f"Storage renamed {upload_name} to {image.image.name}")
        image.save()
        return product
