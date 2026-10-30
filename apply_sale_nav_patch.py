from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parent
app = ROOT / "frontend" / "src" / "App.jsx"
if not app.exists():
    raise SystemExit(f"App.jsx not found at {app}. Extract the package into the Fashion_store project root first.")
text = app.read_text(encoding="utf-8")
old_nav = "else if (label === 'Shop' || label === 'Sale') { setCategory(label === 'Sale' ? 'All Products' : 'All Products'); setSort(label === 'Sale' ? 'priceLow' : 'featured'); navigate('shop'); }"
new_nav = "else if (label === 'Shop') { setCategory('All Products'); setSort('featured'); navigate('shop'); }\n    else if (label === 'Sale') { setCategory('Sale'); setSort('featured'); navigate('shop'); }"
old_categories = "['All Products', 'Men', 'Women', 'Kids', 'Accessories', 'Beauty']"
new_categories = "['All Products', 'Men', 'Women', 'Kids', 'Accessories', 'Beauty', 'Sale']"
nav_count = text.count(old_nav)
cat_count = text.count(old_categories)
if nav_count != 1 or cat_count < 1:
    print("No changes were made because App.jsx does not match the expected original text exactly.")
    print(f"Expected one Sale navigation clause; found {nav_count}. Category array occurrences: {cat_count}.")
    print("Send the exact chooseNav and catalog-category-tabs lines to patch safely.")
    sys.exit(2)
backup = app.with_name("App.jsx.backup_before_sale_nav_patch")
if not backup.exists():
    shutil.copy2(app, backup)
text = text.replace(old_nav, new_nav, 1)
text = text.replace(old_categories, new_categories)
app.write_text(text, encoding="utf-8")
print("Updated only the Sale navigation clause and category arrays in App.jsx.")
print(f"Backup saved as: {backup}")
