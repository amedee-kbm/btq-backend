"""Seed the catalog with the Zita Boutique range.

    uv run python manage.py seed_catalog <photos-dir> [--wipe]

<photos-dir> holds the shots named like "Long dress 25k_(1).jpg": the product
name and price come from the file name. Shots without a price ("Finished_*",
"Sold out", raw WhatsApp exports) are seeded as unpublished drafts with price 0
so they can be priced in the admin; "Finished"/"Sold out" ones are also marked
unavailable.

Products are keyed by code, so re-running updates them in place and skips
photos already uploaded (--replace-images re-uploads them). --wipe first
deletes every product (and its photos) and any category or collection this
seed doesn't define.
"""

import io
import re
import time
from pathlib import Path

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import OperationalError, connection, transaction
from django.utils.text import slugify
from PIL import Image, ImageOps

from catalog.models import (
    Category,
    Collection,
    CollectionProduct,
    Color,
    Product,
    ProductImage,
    Size,
    Tag,
    Variant,
)

MAX_IMAGE_SIDE = 1600

SIZES = ["S", "M", "L", "XL", "XXL", "Free size"]

COLORS = {
    "Beige": "#D8C3A5",
    "Black": "#111111",
    "Black & White": "",
    "Blush": "#F2C4C0",
    "Brown": "#6B4226",
    "Burgundy": "#7B1E2B",
    "Champagne": "#E8D9B5",
    "Charcoal": "#36454F",
    "Cream": "#F3EBD8",
    "Denim": "#3B5B92",
    "Fuchsia": "#D1236F",
    "Green": "#1F6B45",
    "Grey": "#8E8E8E",
    "Lemon": "#F4E68C",
    "Lime": "#9BC53D",
    "Magenta": "#9E2A6B",
    "Mauve": "#B784A7",
    "Mint": "#BDE5C8",
    "Multicolor": "",
    "Mustard": "#D4A82A",
    "Navy": "#1F2A5A",
    "Olive": "#8A8B2E",
    "Orange": "#E07A1F",
    "Pink": "#E8A0B4",
    "Plum": "#5B2350",
    "Purple": "#7A3E8E",
    "Red": "#C8102E",
    "Royal Blue": "#2643A6",
    "Rust": "#A3462C",
    "Sky Blue": "#8EC9EC",
    "Taupe": "#8B7D72",
    "Teal": "#137C86",
    "White": "#FFFFFF",
    "Yellow": "#F6D01E",
}

# (name, parent slug or None, position)
CATEGORIES = [
    ("Dresses", None, 0),
    ("Completes", None, 1),
    ("Boubous", None, 2),
    ("Knitwear", None, 3),
    ("Tops & Bottoms", None, 4),
    ("Long", "dresses", 0),
    ("Short", "dresses", 1),
    ("Party", "dresses", 2),
    ("Office", "dresses", 3),
    ("Satin", "dresses", 4),
    ("Summer", "dresses", 5),
    ("Denim", "dresses", 6),
    ("Trouser Sets", "completes", 0),
    ("Print Sets", "completes", 1),
    ("Knit Sets", "completes", 2),
    ("Suits", "completes", 3),
    ("Jumpsuits", "completes", 4),
]

TAGS = [
    "Wedding guest",
    "Party",
    "Church",
    "Office",
    "Weekend",
    "Plus size",
    "Satin",
    "Lace",
    "Denim",
    "Knit",
]

DRESS_SIZES = ["S", "M", "L", "XL", "XXL"]
FREE_SIZE = ["Free size"]

# Each entry is one product. files: its shots, first one is the cover; name and
# price come from the first file name unless given. colors are read off the
# photos. finished=True marks a sold-out shot.
PRODUCTS = [
    # --- Dresses ---
    dict(files=["Ceremonial dress 35k.jpg"], cat="long", colors=["Mauve"], tags=["Church", "Wedding guest"]),
    dict(files=["Ceremony dress 35k.jpg"], cat="long", colors=["Lemon"], tags=["Church", "Wedding guest"]),
    dict(files=["Classy dress 30k.jpg"], cat="long", colors=["Black", "Brown"], tags=["Church", "Office"]),
    dict(files=["Long casual dress 25k_.jpg"], cat="long", colors=["Burgundy", "Brown", "Green", "Black"], tags=["Weekend"]),
    dict(files=["Long dress 25k_(1).jpg"], cat="long", colors=["Sky Blue", "Yellow", "Green", "Brown"], tags=["Church"]),
    dict(files=["Long dress 25k_(2).jpg"], cat="long", colors=["Red", "Green", "Sky Blue", "Navy", "Yellow"], tags=["Church", "Office"]),
    dict(files=["Long dress 25k_(3).jpg"], cat="long", colors=["Black & White"], tags=["Weekend"]),
    dict(files=["Long dress 25k_(4).jpg"], cat="long", colors=["Brown"], tags=["Weekend"]),
    dict(files=["Long dress 25k_.jpg", "Long dress 25k_(5).jpg"], cat="long", colors=["Mustard", "Magenta", "Rust", "Black", "Pink"], tags=["Church", "Plus size"]),
    dict(files=["Long dress 30k.jpg"], cat="long", colors=["Mustard"], tags=["Church"]),
    dict(files=["Long dress cotton 30k.jpg"], name="Long cotton dress", cat="long", colors=["Olive", "Navy", "Cream"], tags=["Weekend", "Office"]),
    dict(files=["Long straight dress 25k_(1).jpg"], cat="long", colors=["Beige", "Red", "Sky Blue", "Navy", "Green"], tags=["Church", "Office"]),
    dict(files=["Long straight dress 25k_.jpg"], cat="long", colors=["Sky Blue", "Red", "Royal Blue", "Black", "White", "Green"], tags=["Wedding guest", "Church"]),
    dict(files=["long top dress 25k.jpg"], cat="long", colors=["Grey", "Burgundy", "Green", "Navy"], tags=["Weekend", "Plus size"], sizes=FREE_SIZE),
    dict(files=["Petetre 30k.jpg"], cat="long", colors=["Green", "Brown", "Rust", "Black", "Red", "Cream"], tags=["Church", "Office"]),
    dict(files=["Short casual dress 25k_.jpg"], cat="short", colors=["Black", "White", "Beige"], tags=["Weekend"]),
    dict(files=["Short dress 25k_(1).jpg"], cat="short", colors=["Orange", "Charcoal", "White", "Red", "Yellow"], tags=["Weekend", "Plus size"]),
    dict(files=["Short dress 25k_(2).jpg"], cat="short", colors=["Beige", "Black", "White", "Pink"], tags=["Wedding guest", "Lace"]),
    dict(files=["Short dress 25k_(3).jpg"], cat="short", colors=["Fuchsia", "White", "Black", "Pink", "Beige"], tags=["Church", "Lace"]),
    dict(files=["Short dress 25k_(4).jpg"], cat="short", colors=["Multicolor"], tags=["Weekend", "Party"]),
    dict(files=["Short dress 25k_(5).jpg"], cat="short", colors=["White", "Red"], tags=["Party"]),
    dict(files=["Short dress 25k_.jpg"], cat="short", colors=["Mustard", "Orange", "White", "Black", "Lime"], tags=["Weekend", "Plus size"]),
    dict(files=["Short mini dress 25k_.jpg"], cat="short", colors=["Olive"], tags=["Weekend"]),
    dict(files=["Shirt dress 25k_(1).jpg"], cat="short", colors=["Red", "White", "Mustard", "Green", "Fuchsia", "Royal Blue", "Black", "Brown", "Orange"], tags=["Weekend"]),
    dict(files=["Shirt dress 25k_(2).jpg"], cat="short", colors=["White", "Sky Blue"], tags=["Weekend"]),
    dict(files=["Shirt dress 25k_.jpg"], cat="short", colors=["Mint", "Beige", "Pink", "Sky Blue", "Orange", "Grey"], tags=["Weekend", "Plus size"]),
    dict(files=["Party dress 25k_(1).jpg"], cat="party", colors=["Yellow"], tags=["Party"]),
    dict(files=["Party dress 25k_(2).jpg"], cat="party", colors=["Plum"], tags=["Party", "Wedding guest"]),
    dict(files=["Party dress 25k_(3).jpg", "Party dress 25k_(6).jpg"], cat="party", colors=["Red"], tags=["Party", "Wedding guest"]),
    dict(files=["Party dress 25k_(4).jpg", "Party dress 25k_(5).jpg"], cat="party", colors=["Sky Blue", "Lemon"], tags=["Party"]),
    dict(files=["Party dress 25k_(7).jpg"], cat="party", colors=["Pink", "White", "Mauve", "Yellow", "Sky Blue", "Red"], tags=["Party"]),
    dict(files=["Party dress 25k_.jpg"], cat="party", colors=["Black"], tags=["Party"]),
    dict(files=["Party mini dress 25k_.jpg", "Short min dress 25k_.jpg"], cat="party", colors=["Red", "Brown", "Black"], tags=["Party"]),
    dict(files=["Princess dress 25k.jpg"], cat="party", colors=["Red", "Black"], tags=["Party", "Wedding guest"]),
    dict(files=["Classy dress 25k_.jpg"], cat="office", colors=["Navy"], tags=["Office"]),
    dict(files=["Classy dress 35k.jpg"], cat="office", colors=["Lime", "Brown", "Olive", "Black", "Red", "Cream"], tags=["Office", "Church"]),
    dict(files=["Classy dress 35k_.jpg"], cat="office", colors=["Black", "Green", "Brown", "Orange", "Cream", "Red"], tags=["Office", "Church"]),
    dict(files=["Office dress 25k.jpg"], cat="office", colors=["Black & White"], tags=["Office"]),
    dict(files=["Office dress 30k.jpg"], cat="office", colors=["Black & White"], tags=["Office"]),
    dict(files=["Office dress 35k.jpg"], cat="office", colors=["Black"], tags=["Office"]),
    dict(files=["Straight dress 25k_.jpg"], cat="office", colors=["Navy"], tags=["Office"]),
    dict(files=["Long satin dress 25k_(1).jpg"], cat="satin", colors=["Pink", "Teal", "Red", "Brown", "Olive", "Black", "Champagne", "Rust"], tags=["Wedding guest", "Satin"]),
    dict(files=["Long satin dress 25k_(2).jpg"], cat="satin", colors=["Lime"], tags=["Party", "Satin"]),
    dict(files=["Long satin dress 25k_(3).jpg"], cat="satin", colors=["Blush", "Mustard", "Lime", "Champagne", "Black", "Red", "Brown"], tags=["Wedding guest", "Satin"]),
    dict(files=["Long satin dress 25k_(4).jpg"], cat="satin", colors=["Brown", "Cream", "Mustard", "Orange", "Pink", "Black"], tags=["Party", "Satin"]),
    dict(files=["Long satin dress 25k_.jpg"], cat="satin", colors=["Mustard", "Brown", "Champagne", "Pink", "Black", "Royal Blue"], tags=["Wedding guest", "Satin"]),
    dict(files=["satin ceremonial dress 25,000.jpeg"], cat="satin", colors=["Burgundy"], tags=["Wedding guest", "Satin"]),
    dict(files=["Summer dress 25k.jpg"], cat="summer", colors=["Orange", "Lime", "Sky Blue", "Fuchsia"], tags=["Weekend"]),
    dict(files=["Summer dress 25k_(1).jpg"], cat="summer", colors=["Sky Blue"], tags=["Weekend"]),
    dict(files=["Summer dress 25k_(2).jpg"], cat="summer", colors=["Yellow", "Black", "Sky Blue", "White", "Pink"], tags=["Weekend"]),
    dict(files=["Summer dress 25k_(3).jpg"], cat="summer", colors=["Orange", "Pink", "Fuchsia", "Yellow", "Sky Blue"], tags=["Weekend"]),
    dict(files=["Summer dress 25k_.jpg"], cat="summer", colors=["Yellow"], tags=["Weekend"]),
    dict(files=["Summer dress 30k.jpg"], cat="summer", colors=["Yellow"], tags=["Weekend"]),
    dict(files=["Summer long dress 25k_.jpg"], cat="summer", colors=["Fuchsia", "Sky Blue", "Yellow", "Orange", "White", "Black", "Pink"], tags=["Weekend", "Plus size"]),
    dict(files=["Denim dress 25k.jpg", "Denim dress 25k_.jpg"], cat="denim", colors=["Denim"], tags=["Denim", "Weekend"]),
    dict(files=["Denim dress 30k.jpg"], cat="denim", colors=["Denim"], tags=["Denim", "Plus size"]),
    dict(files=["Denim dress 30k_(1).jpg"], cat="denim", colors=["Denim"], tags=["Denim", "Plus size"], sizes=FREE_SIZE),
    dict(files=["Denim dress 30k_(2).jpg"], cat="denim", colors=["Denim"], tags=["Denim", "Party"]),
    dict(files=["Denim dress 30k_(3).jpg"], cat="denim", colors=["Brown", "Denim"], tags=["Denim", "Plus size"]),
    dict(files=["Denim dress 30k_.jpg"], cat="denim", colors=["Denim"], tags=["Denim", "Weekend"]),
    dict(files=["Short denim 25k.jpg"], name="Short denim dress", cat="denim", colors=["Denim"], tags=["Denim", "Weekend"]),
    dict(files=["Short denim dress 25k.jpg"], cat="denim", colors=["Denim"], tags=["Denim", "Weekend", "Plus size"]),
    # --- Completes ---
    dict(files=["Casual complete 25k.jpg"], cat="trouser-sets", colors=["Navy"], tags=["Weekend"]),
    dict(files=["Classy complete 30k.jpg"], cat="trouser-sets", colors=["Mustard", "Cream", "Rust", "Green", "Brown", "Black"], tags=["Party"]),
    dict(files=["Classy complete 35k.jpg", "Classy complete 35k_.jpg"], cat="trouser-sets", colors=["Cream", "Burgundy", "Grey", "Charcoal"], tags=["Office"]),
    dict(files=["Classy complete 35k_(1).jpg", "Women complete 35k.jpg"], cat="trouser-sets", colors=["Sky Blue", "Burgundy", "White", "Lime", "Purple", "Black"], tags=["Office"]),
    dict(files=["Classy complete 35k_(2).jpg"], cat="trouser-sets", colors=["Burgundy", "Black", "Orange", "Sky Blue", "Pink"], tags=["Office"]),
    dict(files=["Complete 25k.jpg"], cat="trouser-sets", colors=["Brown", "Burgundy", "Navy"], tags=["Office", "Weekend"]),
    dict(files=["Complete 35k_.jpg"], cat="trouser-sets", colors=["Black", "Cream", "Orange", "Burgundy", "Brown"], tags=["Office"]),
    dict(files=["Men_ women sets 30k.jpg"], name="Men & women set", cat="trouser-sets", colors=["Navy", "Cream", "Olive", "Black"], tags=["Weekend"]),
    dict(files=["3pieces complete 35k.jpg"], name="3-piece complete", cat="knit-sets", colors=["Cream", "Taupe", "Brown", "Grey", "Navy", "Black"], tags=["Knit"], sizes=FREE_SIZE),
    dict(files=["Complete 35k.jpg", "Complete 35k_(2).jpg"], cat="knit-sets", colors=["Burgundy", "Green"], tags=["Knit"], sizes=FREE_SIZE),
    dict(files=["Complete 35k_(1).jpg"], cat="knit-sets", colors=["Brown"], tags=["Knit"], sizes=FREE_SIZE),
    dict(files=["Complete 40,000.jpeg"], cat="knit-sets", colors=["Taupe", "Brown", "Black"], tags=["Knit"], sizes=FREE_SIZE),
    dict(files=["Complete 40k(1).jpeg"], cat="knit-sets", colors=["Beige", "Black", "Brown", "Grey"], tags=["Knit"], sizes=FREE_SIZE),
    dict(files=["Complete 40k(2).jpeg"], cat="knit-sets", colors=["Beige", "Brown", "Taupe", "Black"], tags=["Knit"], sizes=FREE_SIZE),
    dict(files=["Complete 40k.jpeg"], cat="knit-sets", colors=["Grey", "Beige", "Burgundy", "Cream", "Black"], tags=["Knit", "Office"], sizes=FREE_SIZE),
    dict(files=["Women suit 40k.jpg", "Women suit 40k(1).jpg"], cat="suits", colors=["Green", "Black", "Navy"], tags=["Office"]),
    dict(files=["Jumpsuit 25k.jpg"], cat="jumpsuits", colors=["Lime"], tags=["Weekend", "Party"]),
    # --- Boubous, knitwear, separates ---
    dict(files=["Boubou 25k(1).jpg"], cat="boubous", colors=["Burgundy"], tags=["Plus size", "Church"], sizes=FREE_SIZE),
    dict(files=["Boubou 25k.jpg"], cat="boubous", colors=["Pink"], tags=["Plus size", "Weekend"], sizes=FREE_SIZE),
    dict(files=["Simple Boubou lait 25k.jpg", "Simple Boubou lait 25k_.jpg"], cat="boubous", colors=["Multicolor"], tags=["Plus size", "Weekend"], sizes=FREE_SIZE),
    dict(files=["Bug size sweater 25k.jpg"], name="Big size sweater", cat="knitwear", colors=["Pink"], tags=["Knit", "Plus size"], sizes=FREE_SIZE),
    dict(files=["Simple sweater 18k.jpg", "Simple sweater 18k_.jpg"], cat="knitwear", colors=["Grey", "Black"], tags=["Knit"], sizes=FREE_SIZE),
    dict(files=["Sweater 25k_.jpg"], cat="knitwear", colors=["White", "Beige", "Brown", "Black", "Grey", "Pink"], tags=["Knit"], sizes=FREE_SIZE),
    dict(files=["Top 18k(1).jpg"], cat="tops-bottoms", colors=["Olive", "Black", "Burgundy", "Purple"], tags=["Weekend"]),
    dict(files=["Top 18k.jpg"], cat="tops-bottoms", colors=["Black", "White", "Beige", "Red"], tags=["Office"]),
    dict(files=["Cotton skirts 12k.jpg"], name="Cotton skirt", cat="tops-bottoms", colors=["Red", "Mustard", "Navy", "Purple", "Burgundy", "Grey", "Black"], tags=["Office"]),
    dict(files=["Office trousers 18k.jpg"], cat="tops-bottoms", colors=["Red", "Beige", "Teal"], tags=["Office"]),
    # --- Unpriced: drafts ---
    dict(files=["Finished_.jpg"], name="One-shoulder lace maxi dress", cat="long", colors=["Red", "Black", "Lemon"], tags=["Party", "Lace"], finished=True),
    dict(files=["Finished_(1).jpg"], name="Puff-sleeve pencil dress", cat="office", colors=["White", "Sky Blue", "Black", "Pink", "Navy", "Mint"], tags=["Office", "Church"], finished=True),
    dict(files=["Finished_(2).jpg"], name="Flower appliqué swing dress", cat="short", colors=["Sky Blue"], tags=["Weekend"], finished=True),
    dict(files=["Finished_(3).jpg"], name="Denim shirt dress", cat="denim", colors=["Denim"], tags=["Denim", "Weekend"], finished=True),
    dict(files=["Finished_(4).jpg"], name="Printed kaftan with headwrap", cat="boubous", colors=["Black & White"], tags=["Plus size"], sizes=FREE_SIZE, finished=True),
    dict(files=["Finished_(5).jpg"], name="Puff-sleeve double-breasted set", cat="trouser-sets", colors=["Cream", "Brown", "Magenta", "Burgundy", "Navy"], tags=["Office"], finished=True),
    dict(files=["Finished_(6).jpg"], name="Belted wrap top & trouser set", cat="trouser-sets", colors=["Taupe", "Orange", "Cream", "Burgundy", "Black", "Green"], tags=["Office"], finished=True),
    dict(files=["Finished_(7).jpg", "Finished_(8).jpg"], name="Statement-button vest & trouser set", cat="trouser-sets", colors=["Red", "White"], tags=["Office", "Party"], finished=True),
    dict(files=["Finished_(9).jpg"], name="Brooch top & wide-leg set", cat="trouser-sets", colors=["Burgundy", "White", "Lime", "Sky Blue", "Black"], tags=["Office"], finished=True),
    dict(files=["Finished_(10).jpg"], name="Striped cape & trouser set", cat="knit-sets", colors=["Taupe"], tags=["Knit"], sizes=FREE_SIZE, finished=True),
    dict(files=["Finished_(11).jpg"], name="Swirl print shirt & trouser set", cat="print-sets", colors=["Cream"], tags=["Weekend"], finished=True),
    dict(files=["Finished_(12).jpg"], name="Striped shirt & trouser set", cat="print-sets", colors=["Mustard"], tags=["Weekend"], finished=True),
    dict(files=["Finished_(13).jpg"], name="Geometric print shirt & trouser set", cat="print-sets", colors=["Black"], tags=["Weekend"], finished=True),
    dict(files=["Finished_(14).jpg"], name="Wavy stripe shirt & trouser set", cat="print-sets", colors=["Brown", "Black"], tags=["Weekend", "Plus size"], finished=True),
    dict(files=["Finished_(15).jpg"], name="Chain print shirt & trouser set", cat="print-sets", colors=["Brown"], tags=["Weekend", "Plus size"], finished=True),
    dict(files=["Finished_(16).jpg"], name="Tropical print cardigan set", cat="knit-sets", colors=["Yellow", "Black"], tags=["Knit"], sizes=FREE_SIZE, finished=True),
    dict(files=["Finished_(17).jpg"], name="Tropical print knit cardigan set", cat="knit-sets", colors=["Beige", "Brown"], tags=["Knit"], sizes=FREE_SIZE, finished=True),
    dict(files=["Finished_(18).jpg"], name="Striped knit poncho set", cat="knit-sets", colors=["Grey"], tags=["Knit"], sizes=FREE_SIZE, finished=True),
    dict(files=["Finished_(19).jpg"], name="Scarf print knit poncho set", cat="knit-sets", colors=["Brown", "Burgundy", "Cream", "Black", "Beige"], tags=["Knit"], sizes=FREE_SIZE, finished=True),
    dict(files=["Finished_(20).jpg"], name="Zebra print shirt & trouser set", cat="print-sets", colors=["Black & White"], tags=["Weekend"], finished=True),
    dict(files=["Finished_(21).jpg"], name="Abstract print shirt & trouser set", cat="print-sets", colors=["Black & White"], tags=["Weekend"], finished=True),
    dict(files=["Sold out.jpeg"], name="Button-front maxi shirt dress", cat="long", colors=["Royal Blue"], tags=["Church"], finished=True),
    dict(files=["IMG-20261008-WA0014.jpg"], name="Striped shirt dress", cat="short", colors=["Sky Blue"], tags=["Weekend"]),
    dict(files=["WhatsApp Image 2026-06-27 at 7.59.20 PM.jpeg"], name="Puff-sleeve lace midi dress", cat="short", colors=["Pink", "Black", "White", "Mauve"], tags=["Wedding guest", "Lace"]),
    dict(files=["WhatsApp Image 2026-06-27 at 7.59.19 PM (1).jpeg"], name="Square-neck lace midi dress", cat="short", colors=["Mauve", "Pink", "Black", "White"], tags=["Wedding guest", "Lace"]),
    dict(files=["WhatsApp Image 2026-06-27 at 7.59.19 PM (2).jpeg"], name="Bow-neck lace pencil dress", cat="office", colors=["White", "Pink", "Sky Blue", "Black"], tags=["Church", "Lace"]),
]

NEW_ARRIVALS = 12

# "Long dress 25k_(1)" -> ("Long dress", 25000); "Complete 40,000" -> ("Complete", 40000)
PRICE_RE = re.compile(
    r"^(?P<name>.*?)\s+(?:(?P<k>\d+)k|(?P<full>\d{1,3}(?:,\d{3})+))(?![A-Za-z0-9])"
)


def parse_file_name(file_name):
    match = PRICE_RE.match(Path(file_name).stem)
    if not match:
        return None, None
    price = int(match["k"]) * 1000 if match["k"] else int(match["full"].replace(",", ""))
    return match["name"].strip().capitalize(), price


def web_jpeg(path):
    with Image.open(path) as im:
        im = ImageOps.exif_transpose(im).convert("RGB")
        im.thumbnail((MAX_IMAGE_SIDE, MAX_IMAGE_SIDE))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=82, optimize=True, progressive=True)
    return buf.getvalue()


class Command(BaseCommand):
    help = "Seed the catalog with products and photos named '<name> <price>k.jpg'."

    def add_arguments(self, parser):
        parser.add_argument("photos_dir", type=Path)
        parser.add_argument(
            "--wipe",
            action="store_true",
            help="Delete all existing products and their photos first.",
        )
        parser.add_argument(
            "--replace-images",
            action="store_true",
            help="Re-upload photos for products that already have them.",
        )

    def handle(self, photos_dir, wipe, replace_images, **options):
        if not photos_dir.is_dir():
            raise CommandError(f"{photos_dir} is not a directory")
        missing = [
            f for p in PRODUCTS for f in p["files"] if not (photos_dir / f).exists()
        ]
        if missing:
            raise CommandError(f"Missing photos: {missing}")

        if wipe:
            self.wipe()
        with transaction.atomic():
            categories = self.seed_categories()
            sizes = {
                name: Size.objects.update_or_create(
                    name=name, defaults={"position": i}
                )[0]
                for i, name in enumerate(SIZES)
            }
            colors = {
                name: Color.objects.update_or_create(
                    name=name, defaults={"hex_code": hex_code}
                )[0]
                for name, hex_code in COLORS.items()
            }
            tags = {
                name: Tag.objects.get_or_create(
                    slug=slugify(name), defaults={"name": name}
                )[0]
                for name in TAGS
            }

        # One transaction per product so a dropped connection only costs that
        # product; re-running picks up where it left off.
        products = []
        for i, data in enumerate(PRODUCTS, start=1):
            product = self.with_retries(
                lambda: self.seed_product(
                    i, data, categories, sizes, colors, tags, photos_dir, replace_images
                )
            )
            products.append(product)
            self.stdout.write(f"  {product}")

        published = [p for p in products if p.is_published]
        with transaction.atomic():
            self.seed_collection(
                "New Arrivals",
                0,
                "The latest pieces in the boutique.",
                published[:NEW_ARRIVALS],
            )
            self.seed_collection(
                "Promos",
                1,
                "Limited-time prices.",
                [p for p in published if p.sale_price],
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {len(products)} products ({len(published)} published)."
            )
        )

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

    def wipe(self):
        with transaction.atomic():
            files = list(ProductImage.objects.values_list("image", flat=True))
            count = Product.objects.count()
            Product.objects.all().delete()
            keep = {slugify(name) for name, _, _ in CATEGORIES}
            stale = Category.objects.exclude(slug__in=keep)
            # Children first: parent is PROTECT.
            stale.filter(parent__isnull=False).delete()
            stale.delete()
        # Files go only once the rows are gone for good.
        storage = ProductImage._meta.get_field("image").storage
        for name in files:
            storage.delete(name)
        self.stdout.write(f"Deleted {count} products.")

    def seed_categories(self):
        categories = {}
        for name, parent_slug, position in CATEGORIES:
            slug = slugify(name)
            category, _ = Category.objects.update_or_create(
                slug=slug,
                defaults={
                    "name": name,
                    "parent": categories.get(parent_slug),
                    "position": position,
                },
            )
            categories[slug] = category
        return categories

    def seed_product(
        self, i, data, categories, sizes, colors, tags, photos_dir, replace_images
    ):
        code = f"ZB-{i:04d}"
        file_name, price = parse_file_name(data["files"][0])
        name = data.get("name") or file_name
        priced = price is not None
        product, _ = Product.objects.update_or_create(
            code=code,
            defaults={
                "name": name,
                "slug": f"{slugify(name)}-{code.lower()}",
                "description": data.get("description", ""),
                "material": data.get("material", ""),
                "fit_note": data.get("fit", ""),
                "price": price or 0,
                "sale_price": data.get("sale"),
                "is_published": priced,
            },
        )
        category = categories[data["cat"]]
        product.categories.set(filter(None, [category, category.parent]))
        product.tags.set([tags[t] for t in data["tags"]])

        # Batched: one query per variant is far too slow over a remote DB.
        available = not data.get("finished", False)
        have = set(product.variants.values_list("size_id", "color_id"))
        Variant.objects.bulk_create(
            Variant(product=product, size=size, color=color, is_available=available)
            for size in (sizes[s] for s in data.get("sizes", DRESS_SIZES))
            for color in (colors[c] for c in data["colors"])
            if (size.pk, color.pk) not in have
        )
        product.variants.update(is_available=available)

        existing = list(product.images.all())
        if (
            not replace_images
            and len(existing) == len(data["files"])
            and all(img.image.storage.exists(img.image.name) for img in existing)
        ):
            return product
        for old in product.images.all():
            old.image.delete(save=False)
            old.delete()
        only_color = data["colors"][0] if len(data["colors"]) == 1 else None
        for position, file in enumerate(data["files"]):
            color = colors[only_color] if only_color else None
            alt = (
                f"{product.name} in {only_color}"
                if color
                else f"{product.name}, all colors"
            )
            img = ProductImage(
                product=product, color=color, alt_text=alt, position=position
            )
            img.image.save(
                f"{slugify(product.name)}-{code.lower()}-{position + 1}.jpg",
                ContentFile(web_jpeg(photos_dir / file)),
                save=True,
            )
        return product

    def seed_collection(self, name, position, description, products):
        collection, _ = Collection.objects.update_or_create(
            slug=slugify(name),
            defaults={"name": name, "position": position, "description": description},
        )
        CollectionProduct.objects.filter(collection=collection).delete()
        CollectionProduct.objects.bulk_create(
            CollectionProduct(collection=collection, product=p, position=i)
            for i, p in enumerate(products)
        )
