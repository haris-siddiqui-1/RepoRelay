#!/usr/bin/env python3
"""Test Engagement migration fix with real data."""
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dojo.settings.settings")
import django
django.setup()

from dojo.models import Repository, Product, Product_Type, Engagement, Finding
from dojo.product.migration_wizard import ProductMigrationWizard

print("=== TESTING ENGAGEMENT MIGRATION FIX ===\n")

# Step 1: Reset database to pre-migration state
print("Step 1: Resetting to pre-migration state...")

# Delete the consolidated product if it exists
try:
    consolidated = Product.objects.get(name="Vulnerable Apps Consolidated")
    consolidated.delete()
    print("  ✓ Deleted consolidated product")
except Product.DoesNotExist:
    print("  - No consolidated product to delete")

# Un-archive old products and restore repositories
old_products = Product.objects.filter(is_repository_placeholder=True)
for old_product in old_products:
    old_product.is_repository_placeholder = False
    old_product.migrated_to_product = None
    old_product.migration_date = None
    old_product.save()

    # Restore repository to this product
    repo_name = old_product.name.replace("Damn Vulnerable SCA", "haris-siddiqui-1/Damn-vulnerable-sca").replace("WebGoat Security Test", "haris-siddiqui-1/WebGoat")
    try:
        repo = Repository.objects.get(name=repo_name)
        repo.product = old_product
        repo.save()
        print(f"  ✓ Restored {repo.name} → {old_product.name}")
    except Repository.DoesNotExist:
        pass

print("\n=== Initial State ===")
products = Product.objects.all().order_by('id')
for p in products:
    repos = Repository.objects.filter(product=p).count()
    engagements = Engagement.objects.filter(product=p).count()
    findings = Finding.objects.filter(test__engagement__product=p).count()
    print(f"{p.name} (ID={p.id}): {repos} repos, {engagements} engagements, {findings} findings")

# Step 2: Run migration with fixed code
print("\n=== Step 2: Running Migration with Engagement Fix ===")
wizard = ProductMigrationWizard()

prod_type = Product_Type.objects.first()
repos = Repository.objects.all()

groupings = [
    {
        'product_name': 'Vulnerable Apps Consolidated (Fixed)',
        'description': 'Consolidated vulnerable test applications with Engagement migration',
        'product_type_id': prod_type.id,
        'repository_ids': [repo.id for repo in repos]
    }
]

# Preview
preview = wizard.preview_migration(groupings)
print(f"Preview success: {preview['success']}")
print(f"Impact: {preview['impact']}")

# Dry-run
dry_result = wizard.apply_migration(groupings, dry_run=True)
print(f"\nDry-run success: {dry_result['success']}")

# Actual migration
result = wizard.apply_migration(groupings, dry_run=False)
print(f"\nMigration success: {result['success']}")
if result['success']:
    print(f"Migration ID: {result['migration_id']}")
    print(f"Created {len(result['created_products'])} products")
    print(f"Updated {len(result['updated_repositories'])} repositories")
    print(f"Archived {len(result['archived_products'])} products")

# Step 3: Verify Findings are accessible
print("\n=== Step 3: VERIFICATION ===")
new_product = Product.objects.get(name="Vulnerable Apps Consolidated (Fixed)")
engagements = Engagement.objects.filter(product=new_product)
findings = Finding.objects.filter(test__engagement__product=new_product)

print(f"\nNew Product: {new_product.name} (ID={new_product.id})")
print(f"  Repositories: {Repository.objects.filter(product=new_product).count()}")
print(f"  Engagements: {engagements.count()}")
print(f"  Findings: {findings.count()}")

# Check old products
old_products = Product.objects.filter(is_repository_placeholder=True)
print(f"\nOld Products (archived):")
for old_product in old_products:
    old_findings = Finding.objects.filter(test__engagement__product=old_product)
    print(f"  {old_product.name}: {old_findings.count()} findings")

# Final verification
total_findings = Finding.objects.count()
findings_in_new = Finding.objects.filter(test__engagement__product=new_product).count()
findings_in_old = Finding.objects.filter(test__engagement__product__is_repository_placeholder=True).count()

print(f"\n=== FINAL RESULT ===")
print(f"Total Findings in DB: {total_findings}")
print(f"Findings under NEW Product: {findings_in_new}")
print(f"Findings under OLD Products: {findings_in_old}")

if findings_in_new == 133 and findings_in_old == 0:
    print("\n✅ SUCCESS! All 133 Findings are accessible under the new Product!")
    print("✅ Engagement migration fix is working correctly!")
else:
    print(f"\n❌ FAILURE! Expected 133 findings in new product, got {findings_in_new}")
    print(f"❌ Expected 0 findings in old products, got {findings_in_old}")

print("\n✓ Test complete")
