from __future__ import annotations
import json
import os
from pathlib import Path
import mysql.connector
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / "backend" / ".env")
CATALOG_FILE = ROOT / "frontend" / "src" / "data" / "catalog.json"


def main():
    if not CATALOG_FILE.exists():
        raise SystemExit(f"Catalog not found: {CATALOG_FILE}. Copy the complete frontend folder first.")
    catalog = json.loads(CATALOG_FILE.read_text(encoding="utf-8"))
    connection = mysql.connector.connect(
        host=os.getenv("DB_HOST", "127.0.0.1"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "Fashion_store"),
    )
    cursor = connection.cursor()
    try:
        cursor.execute("SHOW COLUMNS FROM products")
        existing = {row[0] for row in cursor.fetchall()}
        if "available_sizes" not in existing:
            cursor.execute("ALTER TABLE products ADD COLUMN available_sizes JSON NULL")
        if "gallery_images" not in existing:
            cursor.execute("ALTER TABLE products ADD COLUMN gallery_images JSON NULL")
        # Deactivate the original demo inventory to avoid showing duplicate stock-photo records.
        old_demo_slugs = [
            "everyday-overshirt", "soft-form-knit", "everyday-mini-tote", "relaxed-weekend-set",
            "clean-sneaker", "daily-glow-serum", "sculpted-shoulder-bag", "weekend-linen-shirt",
            "solene-blazer", "keila-reversible-coat", "everyday-tailored-set", "satin-slingback-heels",
            "sculpted-everyday-tote", "soft-touch-knit", "classic-black-tee", "soft-weekend-hoodie",
            "little-daydream-set", "minimal-gold-ring", "linen-relaxed-shirt"
        ]
        cursor.executemany("UPDATE products SET is_active=FALSE WHERE slug=%s", [(s,) for s in old_demo_slugs])
        statement = (
            "INSERT INTO products "
            "(name, slug, description, category, product_type, price, compare_at_price, image_url, color, stock_quantity, is_active, available_sizes, gallery_images) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
            "ON DUPLICATE KEY UPDATE name=VALUES(name), description=VALUES(description), category=VALUES(category), "
            "product_type=VALUES(product_type), price=VALUES(price), compare_at_price=VALUES(compare_at_price), "
            "image_url=VALUES(image_url), color=VALUES(color), stock_quantity=VALUES(stock_quantity), "
            "is_active=TRUE, available_sizes=VALUES(available_sizes), gallery_images=VALUES(gallery_images)"
        )
        for product in catalog:
            cursor.execute(statement, (
                product["name"], product["slug"], product["description"], product["category"],
                product["product_type"], product["price"], product.get("compare_at_price"),
                product["image_url"], product["color"], int(product["stock_quantity"]), bool(product.get("is_active", 1)),
                json.dumps(product["available_sizes"], ensure_ascii=False),
                json.dumps([product["image_url"]], ensure_ascii=False),
            ))
        connection.commit()
        cursor.execute("SELECT category, COUNT(*) FROM products WHERE is_active=TRUE GROUP BY category ORDER BY category")
        print("\nFashion Store catalog imported successfully.")
        print(f"Products processed: {len(catalog)}")
        print("Active products by category:")
        for category, count in cursor.fetchall(): print(f"  {category}: {count}")
        print("\nVerify with: SELECT name, category, price, available_sizes FROM products WHERE is_active=1 LIMIT 10;")
    finally:
        cursor.close()
        connection.close()

if __name__ == "__main__":
    main()
