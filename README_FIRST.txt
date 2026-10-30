FASHION STORE — ADD ACCESSORIES, BEAUTY & SALE PRODUCTS
=======================================================

WHAT THIS PACKAGE CONTAINS
--------------------------
- 20 Accessories products and their uploaded product images
- 20 Beauty products and their uploaded product images
- 20 Sale products and their uploaded outfit images
- A 60-product JSON data file and a CSV preview
- An additive MySQL importer that asks for confirmation before writing
- A safety-checked, minimal Sale navigation patch (it creates an App.jsx backup first)

IMPORTANT SAFETY NOTES
----------------------
- This package does NOT contain a replacement App.jsx or styles.css. Your restored design is preserved.
- It does NOT delete, deactivate, or overwrite the existing Men, Women, or Kids catalogue.
- One original uploaded image is used per product. No artificial angle crops were made.
- Prices and compare-at prices are suggested estimates in INR inferred for this demo. Review CATALOG_ADDITIONS_PREVIEW.csv and backend/catalog_additions.json before importing.
- The Sale category is separate in the database. The small patch below changes only the Sale navigation clause and category arrays.

STEP 1 — BACK UP AND EXTRACT
----------------------------
1. Make a copy of your working Fashion_store folder first.
2. Extract this ZIP into:
   C:\Users\manoj\Documents\Fashion_store
   Allow the new folders/files to merge. Do not replace App.jsx or styles.css; this ZIP does not include either file.
3. Confirm these new paths exist:
   frontend\public\products\accessories\
   frontend\public\products\beauty\
   frontend\public\products\sale\
   backend\catalog_additions.json
   backend\import_new_categories.py
   apply_sale_nav_patch.py

STEP 2 — IMPORT THE 60 PRODUCTS
-------------------------------
Open the existing backend terminal, activate the same backend .venv, and run:
  cd "C:\Users\manoj\Documents\Fashion_store\backend"
  python import_new_categories.py

Review the printed categories and counts. Type YES only if these look correct. The script uses your existing backend\.env and does not print your password. It adds/updates only the 60 new slugs and never deletes or deactivates existing items.

STEP 3 — ENABLE THE SALE NAVIGATION
-----------------------------------
After the import completes, open a PowerShell terminal in the project root and run:
  cd "C:\Users\manoj\Documents\Fashion_store"
  python apply_sale_nav_patch.py

The patch helper creates `frontend/src/App.jsx.backup_before_sale_nav_patch` before changing the file. It will modify only the expected Sale navigation clause and category arrays. If your App.jsx differs, the script stops without changes; send the displayed message rather than replacing files manually.

STEP 4 — CHECK THE SITE
-----------------------
- Make sure Django is running: http://127.0.0.1:8000/api/products/
- Open the React site: http://127.0.0.1:5173/
- The small status indicator should say Live catalogue. If it says Local catalogue, start the Django server in a backend terminal with `python manage.py runserver 8000` after activating `.venv`.
- Click Accessories, Beauty and Sale and confirm products appear.

PRICE NOTE
----------
Names, product types, colors, sizes, and prices are inferred from the uploaded images. These values are suggested demo prices, not supplier-confirmed prices. The Shoe sizes in this demo are sample ranges; adjust them to actual stock before launch.
