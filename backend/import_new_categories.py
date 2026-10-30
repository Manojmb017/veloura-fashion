from __future__ import annotations
import json
import os
from pathlib import Path
import sys
import mysql.connector
from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BACKEND_DIR.parent
CATALOG_FILE = BACKEND_DIR / "catalog_additions.json"
load_dotenv(BACKEND_DIR / ".env")


def main() -> None:
    if not CATALOG_FILE.exists():
        raise SystemExit(f"Missing file: {CATALOG_FILE}")
    products = json.loads(CATALOG_FILE.read_text(encoding="utf-8"))
    if not isinstance(products, list) or not products:
        raise SystemExit("catalog_additions.json must contain a non-empty product list.")

    missing = []
    for item in products:
        url = item.get("image_url", "")
        local_image = PROJECT_DIR / "frontend" / "public" / url.lstrip("/")
        if not url.startswith("/products/") or not local_image.exists():
            missing.append((item.get("slug", "unknown"), str(local_image)))
    if missing:
        print("Some image files are missing. Extract the package into your existing project root first:")
        for slug, path in missing[:10]:
            print(f"  {slug}: {path}")
        raise SystemExit(f"Stopped without importing. Missing image count: {len(missing)}")

    counts = {}
    for item in products:
        counts[item["category"]] = counts.get(item["category"], 0) + 1
    print("\nThis will ADD/UPDATE only the new product slugs in this package.")
    print("It will NOT delete or deactivate existing products.")
    print(f"Database configured in backend/.env: {os.getenv('DB_NAME', 'Fashion_store')}")
    print(f"Products to process: {len(products)}")
    for category in sorted(counts):
        print(f"  {category}: {counts[category]}")
    answer = input("Type YES to continue: ").strip()
    if answer != "YES":
        print("Cancelled. No database changes made.")
        return

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
        existing_columns = {row[0] for row in cursor.fetchall()}
        if "available_sizes" not in existing_columns:
            cursor.execute("ALTER TABLE products ADD COLUMN available_sizes JSON NULL")
        if "gallery_images" not in existing_columns:
            cursor.execute("ALTER TABLE products ADD COLUMN gallery_images JSON NULL")

        statement = (
            "INSERT INTO products "
            "(name, slug, description, category, product_type, price, compare_at_price, image_url, color, stock_quantity, is_active, available_sizes, gallery_images) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
            "ON DUPLICATE KEY UPDATE name=VALUES(name), description=VALUES(description), category=VALUES(category), "
            "product_type=VALUES(product_type), price=VALUES(price), compare_at_price=VALUES(compare_at_price), "
            "image_url=VALUES(image_url), color=VALUES(color), stock_quantity=VALUES(stock_quantity), "
            "is_active=TRUE, available_sizes=VALUES(available_sizes), gallery_images=VALUES(gallery_images)"
        )
        for item in products:
            cursor.execute(statement, (
                item["name"], item["slug"], item["description"], item["category"],
                item["product_type"], item["price"], item.get("compare_at_price"),
                item["image_url"], item["color"], int(item["stock_quantity"]),
                bool(item.get("is_active", 1)),
                json.dumps(item["available_sizes"], ensure_ascii=False),
                json.dumps(item["gallery_images"], ensure_ascii=False),
            ))
        connection.commit()
        cursor.execute("SELECT category, COUNT(*) FROM products WHERE is_active=TRUE GROUP BY category ORDER BY category")
        print("\nCatalog import complete. Active products by category:")
        for category, total in cursor.fetchall():
            print(f"  {category}: {total}")
        print("\nNo existing product rows were deleted or deactivated by this script.")
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()

if __name__ == "__main__":
    try:
        main()
    except mysql.connector.Error as exc:
        print(f"MySQL error: {exc}", file=sys.stderr)
        sys.exit(1)
