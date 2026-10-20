"""Seed the catalog with the Zita Boutique launch range.

    uv run python manage.py seed_catalog <photos-dir>

<photos-dir> holds the numbered shots (1.jpg ... 67.jpg). Products are keyed
by code, so re-running updates them in place; pass --replace-images to
re-upload photos for products that already have some.
"""

import io
from pathlib import Path

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
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
    ("Evening", "dresses", 0),
    ("Midi", "dresses", 1),
    ("Maxi", "dresses", 2),
    ("Casual", "dresses", 3),
    ("Denim", "dresses", 4),
    ("Trouser Sets", "completes", 0),
    ("Knit Sets", "completes", 1),
    ("Print Sets", "completes", 2),
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
KNIT_SIZES = ["Free size"]

# images: (file number, color name or None for a shared/collage shot)
PRODUCTS = [
    # --- Dresses ---
    dict(
        name="Satin Halter Mermaid Gown",
        cat="evening",
        price=55000,
        material="Satin",
        fit="Fitted through the hips",
        tags=["Wedding guest", "Party", "Satin"],
        colors=["Burgundy"],
        images=[(1, "Burgundy")],
    ),
    dict(
        name="Floral Tie-Back Skater Dress",
        cat="casual",
        price=28000,
        material="Cotton blend",
        tags=["Weekend", "Party"],
        colors=["Multicolor"],
        images=[(2, "Multicolor")],
    ),
    dict(
        name="Gold Ring Ruched Midi Dress",
        cat="midi",
        price=38000,
        material="Stretch jersey",
        fit="Stretchy",
        tags=["Party", "Wedding guest"],
        colors=["Red", "Plum"],
        images=[(3, "Red"), (4, "Plum")],
    ),
    dict(
        name="Asymmetric Strap Maxi Dress",
        cat="evening",
        price=42000,
        material="Stretch knit",
        tags=["Party", "Wedding guest"],
        colors=["Red", "Navy", "Lemon"],
        images=[(5, None)],
    ),
    dict(
        name="Off-Shoulder Drape Mermaid Dress",
        cat="evening",
        price=48000,
        material="Crepe",
        fit="Fitted through the hips",
        tags=["Party", "Wedding guest"],
        colors=["Black"],
        images=[(6, "Black")],
    ),
    dict(
        name="One-Shoulder Ruched Slit Maxi",
        cat="evening",
        price=40000,
        sale=34000,
        material="Satin",
        tags=["Party", "Satin"],
        colors=["Brown", "Cream", "Mustard", "Orange", "Pink", "Black"],
        images=[(7, None)],
    ),
    dict(
        name="Gold Ring One-Shoulder Mini Dress",
        cat="evening",
        price=32000,
        material="Stretch jersey",
        fit="Runs small",
        tags=["Party"],
        colors=["Red", "Brown", "Black"],
        images=[(8, None)],
    ),
    dict(
        name="Halter Flower Appliqué Swing Dress",
        cat="casual",
        price=30000,
        material="Chiffon",
        tags=["Weekend"],
        colors=["Sky Blue"],
        images=[(9, "Sky Blue")],
    ),
    dict(
        name="Wrap-Front Draped Satin Maxi",
        cat="evening",
        price=45000,
        material="Satin",
        tags=["Wedding guest", "Satin"],
        colors=["Mustard", "Brown", "Champagne", "Pink", "Black", "Royal Blue"],
        images=[(10, None)],
    ),
    dict(
        name="Cowl-Neck Ruched Satin Maxi",
        cat="evening",
        price=42000,
        material="Satin",
        tags=["Wedding guest", "Satin"],
        colors=["Pink", "Teal", "Red", "Brown", "Olive", "Black", "Champagne"],
        images=[(11, None)],
    ),
    dict(
        name="Balloon-Sleeve Satin Wrap Dress",
        cat="evening",
        price=46000,
        sale=39000,
        material="Satin",
        tags=["Wedding guest", "Church", "Satin"],
        colors=["Blush", "Mustard", "Lime", "Champagne", "Black", "Red", "Brown"],
        images=[(12, None)],
    ),
    dict(
        name="Cowl-Neck Lace-Up Back Satin Gown",
        cat="evening",
        price=52000,
        material="Satin",
        tags=["Party", "Wedding guest", "Satin"],
        colors=["Lime"],
        images=[(13, "Lime")],
    ),
    dict(
        name="Bow-Neck Lace Pencil Dress",
        cat="midi",
        price=45000,
        material="Lace",
        tags=["Church", "Office", "Lace"],
        colors=["White", "Pink", "Sky Blue", "Black"],
        images=[(14, None)],
    ),
    dict(
        name="Embellished Puff-Sleeve Pencil Dress",
        cat="midi",
        price=42000,
        material="Crepe",
        tags=["Church", "Office"],
        colors=["White", "Sky Blue", "Black", "Pink", "Navy", "Mint"],
        images=[(15, None)],
    ),
    dict(
        name="Side-Ruched Three-Quarter Sleeve Maxi",
        cat="maxi",
        price=36000,
        material="Crepe",
        tags=["Church", "Office"],
        colors=["Beige", "Red", "Sky Blue", "Navy", "Green"],
        images=[(16, None)],
    ),
    dict(
        name="Bow-Collar Lace Midi Dress",
        cat="midi",
        price=44000,
        material="Lace",
        tags=["Church", "Lace"],
        colors=["Fuchsia", "White", "Black", "Pink", "Beige"],
        images=[(17, None)],
    ),
    dict(
        name="Off-Shoulder Puff-Sleeve Lace Midi",
        cat="midi",
        price=48000,
        material="Lace",
        tags=["Wedding guest", "Lace"],
        colors=["Pink", "Black", "White", "Mauve"],
        images=[(18, None)],
    ),
    dict(
        name="Square-Neck Ruffle-Sleeve Lace Midi",
        cat="midi",
        price=48000,
        material="Lace",
        tags=["Wedding guest", "Church", "Lace"],
        colors=["Mauve", "Pink", "Black", "White"],
        images=[(19, None)],
    ),
    dict(
        name="V-Neck Sheer-Sleeve Lace Midi",
        cat="midi",
        price=48000,
        material="Lace",
        tags=["Wedding guest", "Lace"],
        colors=["Pink", "Black", "White", "Mauve"],
        images=[(20, None)],
    ),
    dict(
        name="Beaded Sheer-Sleeve Column Dress",
        cat="maxi",
        price=50000,
        material="Crepe with mesh sleeves",
        tags=["Wedding guest", "Church"],
        colors=["Sky Blue", "Red", "Royal Blue", "Black", "White", "Green"],
        images=[(21, None)],
    ),
    dict(
        name="Button-Front Belted Shirt Dress",
        cat="casual",
        price=30000,
        material="Crepe",
        tags=["Office", "Weekend", "Plus size"],
        colors=["Mustard", "Orange", "White", "Black", "Lime"],
        images=[(22, None)],
    ),
    dict(
        name="Ruffle-Sleeve Tiered Shirt Dress",
        cat="casual",
        price=30000,
        material="Crepe",
        tags=["Weekend", "Church", "Plus size"],
        colors=["Orange", "Grey", "White", "Red", "Yellow"],
        images=[(23, None)],
    ),
    dict(
        name="Printed Kaftan Maxi with Headwrap",
        cat="maxi",
        price=38000,
        material="Satin",
        fit="Loose, one size fits most",
        tags=["Plus size", "Weekend"],
        colors=["Black & White"],
        images=[(24, "Black & White")],
        sizes=KNIT_SIZES,
    ),
    dict(
        name="Two-Tone Denim Maxi Dress",
        cat="denim",
        price=35000,
        material="Denim",
        tags=["Denim", "Weekend", "Plus size"],
        colors=["Denim"],
        images=[(25, "Denim")],
    ),
    dict(
        name="Classic Denim Shirt Dress",
        cat="denim",
        price=30000,
        material="Denim",
        tags=["Denim", "Weekend"],
        colors=["Denim"],
        images=[(26, "Denim")],
    ),
    dict(
        name="Denim Pocket Maxi Shirt Dress",
        cat="denim",
        price=36000,
        material="Chambray",
        tags=["Denim", "Office"],
        colors=["Denim"],
        images=[(27, "Denim")],
    ),
    dict(
        name="Distressed Denim Kaftan",
        cat="denim",
        price=40000,
        material="Washed denim",
        fit="Oversized",
        tags=["Denim", "Plus size"],
        colors=["Denim"],
        images=[(28, "Denim")],
        sizes=KNIT_SIZES,
    ),
    dict(
        name="Contrast-Stitch Denim Maxi",
        cat="denim",
        price=36000,
        material="Denim",
        tags=["Denim", "Weekend", "Plus size"],
        colors=["Denim"],
        images=[(29, "Denim")],
    ),
    dict(
        name="Oversized Denim Shirt Dress",
        cat="denim",
        price=30000,
        material="Chambray",
        fit="Oversized",
        tags=["Denim", "Weekend", "Plus size"],
        colors=["Denim"],
        images=[(30, "Denim")],
    ),
    dict(
        name="Patch-Pocket Belted Denim Dress",
        cat="denim",
        price=42000,
        material="Denim",
        tags=["Denim", "Party"],
        colors=["Denim"],
        images=[(31, "Denim")],
    ),
    dict(
        name="Flutter-Sleeve Button Maxi Dress",
        cat="maxi",
        price=32000,
        material="Crepe",
        fit="Relaxed",
        tags=["Church", "Plus size"],
        colors=["Mustard", "Magenta", "Rust", "Black", "Pink"],
        images=[(32, None)],
    ),
    dict(
        name="Belted Wrap Maxi Dress",
        cat="maxi",
        price=34000,
        material="Crepe",
        tags=["Church", "Office"],
        colors=["Grey", "Yellow", "Green", "Brown"],
        images=[(33, None)],
    ),
    dict(
        name="Flower-Strap Trapeze Maxi",
        cat="maxi",
        price=35000,
        material="Cotton linen",
        fit="Loose and flowy",
        tags=["Weekend", "Plus size"],
        colors=["Yellow", "Black", "Sky Blue", "White", "Pink"],
        images=[(34, "Yellow"), (35, "Sky Blue"), (37, None)],
    ),
    dict(
        name="Tiered Ruffle Halter Maxi",
        cat="maxi",
        price=38000,
        material="Chiffon",
        tags=["Weekend", "Party"],
        colors=["Yellow"],
        images=[(36, "Yellow")],
    ),
    dict(
        name="Smocked-Waist Button Maxi Shirt Dress",
        cat="maxi",
        price=40000,
        material="Crepe",
        tags=["Church", "Plus size"],
        colors=["Royal Blue"],
        images=[(66, "Royal Blue")],
    ),
    # --- Completes ---
    dict(
        name="Puff-Sleeve Double-Button Trouser Set",
        cat="trouser-sets",
        price=52000,
        material="Crepe",
        tags=["Office", "Church"],
        colors=["Cream", "Brown", "Magenta", "Burgundy", "Navy"],
        images=[(38, None)],
    ),
    dict(
        name="Belted Sleeveless Tunic & Wide-Leg Set",
        cat="trouser-sets",
        price=48000,
        material="Crepe",
        tags=["Office"],
        colors=["Black", "Cream", "Orange", "Burgundy", "Brown"],
        images=[(39, None)],
    ),
    dict(
        name="Pinstripe Belted Vest & Trouser Set",
        cat="trouser-sets",
        price=55000,
        material="Pinstripe suiting",
        tags=["Office"],
        colors=["Cream", "Burgundy", "Grey", "Charcoal"],
        images=[(40, None)],
    ),
    dict(
        name="Wrap-Belt Blazer Top & Trouser Set",
        cat="trouser-sets",
        price=52000,
        sale=45000,
        material="Crepe",
        tags=["Office", "Church"],
        colors=["Taupe", "Orange", "Cream", "Burgundy", "Black", "Green"],
        images=[(41, None)],
    ),
    dict(
        name="Statement-Button Belted Vest Set",
        cat="trouser-sets",
        price=50000,
        material="Crepe",
        tags=["Office"],
        colors=["Sky Blue", "Burgundy", "White", "Lime", "Purple", "Black"],
        images=[(42, None)],
    ),
    dict(
        name="Asymmetric Button Vest & Trouser Set",
        cat="trouser-sets",
        price=55000,
        material="Suiting",
        tags=["Office", "Party"],
        colors=["Red", "White"],
        images=[(43, "Red"), (44, "White")],
    ),
    dict(
        name="Contrast-Collar Vest Suit Set",
        cat="trouser-sets",
        price=58000,
        material="Suiting",
        tags=["Office"],
        colors=["Burgundy", "Black", "Orange", "Sky Blue", "Pink"],
        images=[(45, None)],
    ),
    dict(
        name="Brooch Peplum Top & Wide-Leg Set",
        cat="trouser-sets",
        price=50000,
        material="Crepe",
        tags=["Office", "Church"],
        colors=["Burgundy", "White", "Lime", "Sky Blue", "Black"],
        images=[(46, None)],
    ),
    dict(
        name="H-Knit Cardigan Three-Piece Set",
        cat="knit-sets",
        price=65000,
        material="Rib knit",
        fit="Stretchy",
        tags=["Knit"],
        colors=["Brown"],
        images=[(47, "Brown")],
        sizes=KNIT_SIZES,
    ),
    dict(
        name="Striped Cape Knit Set",
        cat="knit-sets",
        price=60000,
        material="Knit",
        fit="Stretchy",
        tags=["Knit"],
        colors=["Taupe", "Grey"],
        images=[(48, "Taupe"), (64, "Grey")],
        sizes=KNIT_SIZES,
    ),
    dict(
        name="Colorblock Long Cardigan Set",
        cat="knit-sets",
        price=62000,
        material="Knit",
        fit="Stretchy",
        tags=["Knit", "Office"],
        colors=["Green", "Burgundy"],
        images=[(49, "Green"), (50, "Burgundy")],
        sizes=KNIT_SIZES,
    ),
    dict(
        name="Abstract Print Shirt & Trouser Set",
        cat="print-sets",
        price=40000,
        material="Satin",
        tags=["Weekend"],
        colors=["Cream"],
        images=[(51, "Cream")],
    ),
    dict(
        name="Striped Panel Shirt & Trouser Set",
        cat="print-sets",
        price=42000,
        material="Satin",
        tags=["Weekend", "Office"],
        colors=["Mustard"],
        images=[(52, "Mustard")],
    ),
    dict(
        name="Geometric Print Shirt & Trouser Set",
        cat="print-sets",
        price=42000,
        material="Satin",
        tags=["Weekend", "Party"],
        colors=["Black"],
        images=[(53, "Black")],
    ),
    dict(
        name="Marble Print Shirt & Trouser Set",
        cat="print-sets",
        price=40000,
        material="Satin",
        tags=["Weekend"],
        colors=["Black & White"],
        images=[(54, "Black & White")],
    ),
    dict(
        name="Wavy Stripe Shirt & Trouser Set",
        cat="print-sets",
        price=42000,
        material="Satin",
        tags=["Weekend", "Plus size"],
        colors=["Brown", "Black"],
        images=[(55, None), (67, None), (59, "Black")],
    ),
    dict(
        name="Chain Print Shirt & Trouser Set",
        cat="print-sets",
        price=42000,
        material="Satin",
        tags=["Weekend", "Plus size"],
        colors=["Brown"],
        images=[(56, "Brown")],
    ),
    dict(
        name="Tropical Print Knit Cardigan Set",
        cat="knit-sets",
        price=58000,
        material="Jacquard knit",
        fit="Stretchy",
        tags=["Knit"],
        colors=["Yellow", "Black", "Beige", "Brown"],
        images=[(57, None), (65, None)],
        sizes=KNIT_SIZES,
    ),
    dict(
        name="Ribbed Button Cardigan Set",
        cat="knit-sets",
        price=55000,
        sale=48000,
        material="Rib knit",
        fit="Stretchy",
        tags=["Knit", "Office"],
        colors=["Grey", "Beige", "Burgundy", "Cream", "Black"],
        images=[(58, None)],
        sizes=KNIT_SIZES,
    ),
    dict(
        name="Monogram Knit Poncho & Trouser Set",
        cat="knit-sets",
        price=58000,
        material="Knit",
        fit="Stretchy",
        tags=["Knit"],
        colors=["Beige", "Grey", "Black", "Brown"],
        images=[(60, None)],
        sizes=KNIT_SIZES,
    ),
    dict(
        name="Long Cardigan Three-Piece Knit Set",
        cat="knit-sets",
        price=68000,
        material="Knit",
        fit="Stretchy",
        tags=["Knit", "Office"],
        colors=["Beige", "Brown", "Taupe", "Black"],
        images=[(61, None), (63, None)],
        sizes=KNIT_SIZES,
    ),
    dict(
        name="Scarf Print Knit Poncho Set",
        cat="knit-sets",
        price=60000,
        material="Knit",
        fit="Stretchy",
        tags=["Knit"],
        colors=["Brown", "Burgundy", "Cream", "Black", "Beige"],
        images=[(62, None)],
        sizes=KNIT_SIZES,
    ),
    dict(
        name="Jacquard Button-Front Shirt Maxi Dress",
        cat="maxi",
        price=45000,
        material="Textured jacquard",
        fit="Fitted waist, full skirt",
        tags=["Church", "Office", "Wedding guest"],
        colors=["Lemon"],
        images=[(68, "Lemon")],
    ),
    dict(
        name="Oversized Linen Shirt & Wide-Leg Set",
        cat="trouser-sets",
        price=45000,
        material="Linen blend",
        fit="Relaxed",
        tags=["Office", "Weekend", "Church"],
        colors=["Brown", "Burgundy", "Navy"],
        images=[(69, None)],
    ),
]

NEW_ARRIVALS = 12


def web_jpeg(path):
    with Image.open(path) as im:
        im = ImageOps.exif_transpose(im).convert("RGB")
        im.thumbnail((MAX_IMAGE_SIDE, MAX_IMAGE_SIDE))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=82, optimize=True, progressive=True)
    return buf.getvalue()


class Command(BaseCommand):
    help = "Seed the catalog with products and photos from a folder of numbered JPEGs."

    def add_arguments(self, parser):
        parser.add_argument("photos_dir", type=Path)
        parser.add_argument(
            "--replace-images",
            action="store_true",
            help="Delete and re-upload photos for products that already have some.",
        )

    def handle(self, photos_dir, replace_images, **options):
        if not photos_dir.is_dir():
            raise CommandError(f"{photos_dir} is not a directory")
        missing = [
            n
            for p in PRODUCTS
            for n, _ in p["images"]
            if not (photos_dir / f"{n}.jpg").exists()
        ]
        if missing:
            raise CommandError(f"Missing photos: {missing}")

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

            products = []
            for i, data in enumerate(PRODUCTS, start=1):
                product = self.seed_product(
                    i, data, categories, sizes, colors, tags, photos_dir, replace_images
                )
                products.append(product)
                self.stdout.write(f"  {product}")

            self.seed_collection(
                "New Arrivals",
                0,
                "The latest pieces in the boutique.",
                products[-NEW_ARRIVALS:],
            )
            self.seed_collection(
                "Promos",
                1,
                "Limited-time prices.",
                [p for p in products if p.sale_price],
            )

        self.stdout.write(self.style.SUCCESS(f"Seeded {len(products)} products."))

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
        product, _ = Product.objects.update_or_create(
            code=code,
            defaults={
                "name": data["name"],
                "slug": slugify(data["name"]),
                "description": data.get("description", ""),
                "material": data.get("material", ""),
                "fit_note": data.get("fit", ""),
                "price": data["price"],
                "sale_price": data.get("sale"),
                "is_published": True,
            },
        )
        category = categories[data["cat"]]
        product.categories.set([category, category.parent])
        product.tags.set([tags[t] for t in data["tags"]])

        for size_name in data.get("sizes", DRESS_SIZES):
            for color_name in data["colors"]:
                Variant.objects.get_or_create(
                    product=product, size=sizes[size_name], color=colors[color_name]
                )

        if replace_images:
            for old in product.images.all():
                old.image.delete(save=False)
                old.delete()
        if not product.images.exists():
            for position, (number, color_name) in enumerate(data["images"]):
                color = colors[color_name] if color_name else None
                alt = (
                    f"{product.name} in {color_name}"
                    if color
                    else f"{product.name}, all colors"
                )
                img = ProductImage(
                    product=product, color=color, alt_text=alt, position=position
                )
                img.image.save(
                    f"{product.slug}-{position + 1}.jpg",
                    ContentFile(web_jpeg(photos_dir / f"{number}.jpg")),
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
