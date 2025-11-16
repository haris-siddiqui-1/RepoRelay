#!/usr/bin/env python3
"""Test Engagement migration fix - recreate repos and test."""
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dojo.settings.settings")
import django
django.setup()

from dojo.models import Repository, Product, Product_Type, Engagement, Finding
from dojo.product.migration_wizard import ProductMigrationWizard

print("=== TESTING ENGAGEMENT MIGRATION FIX ===\n")

# Step 1: Recreate repositories and assign to old products
print("Step 1: Recreating repositories...")

# Get old products
webgoat_product = Product.objects.get(id=1)  # WebGoat Security Test
sca_product = Product.objects.get(id=2)  # Damn Vulnerable SCA

# Delete any existing consolidated product from previous test
Product.objects.filter(name__contains="Vulnerable Apps Consolidated").delete()

# Create repositories
repo1, created1 = Repository.objects.get_or_create(
    name="haris-siddiqui-1/WebGoat",
    defaults={
        'github_repo_id': 950345562,
        'github_url': 'https://github.com/haris-siddiqui-1/WebGoat',
        'product': webgoat_product
    }
)
if not created1:
    repo1.product = webgoat_product
    repo1.save()

repo2, created2 = Repository.objects.get_or_create(
    name="haris-siddiqui-1/Damn-vulnerable-sca",
    defaults={
        'github_repo_id': 949794740,
        'github_url': 'https://github.com/haris-siddiqui-1/Damn-vulnerable-sca',
        'product': sca_product
    }
)
if not created2:
    repo2.product = sca_product
    repo2.save()

print(f"  ✓ Created/updated {repo1.name} → {webgoat_product.name}")
print(f"  ✓ Created/updated {repo2.name} → {sca_product.name}")

print("\n=== Initial State ===")
products = Product.objects.all().order_by('id')
for p in products:
    repos = Repository.objects.filter(product=p).count()
    engagements = Engagement.objects.filter(product=p).count()
    findings = Finding.objects.filter(test__engagement__product=p).count()
    print(f"{p.name} (ID={p.id}): {repos} repos, {engagements} engagements, {findings} findings")

total_findings_before = Finding.objects.count()
print(f"\nTotal Findings in DB: {total_findings_before}")

# Step 2: Run migration with fixed code
print("\n=== Step 2: Running Migration with Engagement Fix ===")
wizard = ProductMigrationWizard()

prod_type = Product_Type.objects.first()
repos = Repository.objects.all()

groupings = [
    {
        'product_name': 'Vulnerable Apps Consolidated',
        'description': 'Consolidated vulnerable test applications with Engagement migration',
        'product_type_id': prod_type.id,
        'repository_ids': [repo.id for repo in repos]
    }
]

# Actual migration (no dry-run, we want to see the fix in action)
result = wizard.apply_migration(groupings, dry_run=False)
print(f"Migration success: {result['success']}")
if result['success']:
    print(f"Migration ID: {result['migration_id']}")
    print(f"Created {len(result['created_products'])} products")
    print(f"Updated {len(result['updated_repositories'])} repositories")
    print(f"Archived {len(result['archived_products'])} products")

# Step 3: Verify Findings are accessible
print("\n=== Step 3: VERIFICATION ===")
new_product = Product.objects.get(name="Vulnerable Apps Consolidated")
engagements = Engagement.objects.filter(product=new_product)
findings = Finding.objects.filter(test__engagement__product=new_product)

print(f"\nNew Product: {new_product.name} (ID={new_product.id})")
print(f"  Repositories: {Repository.objects.filter(product=new_product).count()}")
print(f"  Engagements: {engagements.count()}")
for eng in engagements:
    eng_findings = Finding.objects.filter(test__engagement=eng)
    print(f"    - {eng.name}: {eng_findings.count()} findings")
print(f"  Total Findings: {findings.count()}")

# Check old products
old_products = Product.objects.filter(is_repository_placeholder=True).order_by('id')
print(f"\nOld Products (archived):")
for old_product in old_products:
    old_repos = Repository.objects.filter(product=old_product).count()
    old_engagements = Engagement.objects.filter(product=old_product).count()
    old_findings = Finding.objects.filter(test__engagement__product=old_product).count()
    print(f"  {old_product.name} (ID={old_product.id}): {old_repos} repos, {old_engagements} engagements, {old_findings} findings")

# Final verification
total_findings_after = Finding.objects.count()
findings_in_new = Finding.objects.filter(test__engagement__product=new_product).count()
findings_in_old = Finding.objects.filter(test__engagement__product__is_repository_placeholder=True).count()

print(f"\n=== FINAL RESULT ===")
print(f"Total Findings BEFORE migration: {total_findings_before}")
print(f"Total Findings AFTER migration: {total_findings_after}")
print(f"Findings under NEW Product: {findings_in_new}")
print(f"Findings under OLD Products: {findings_in_old}")

if findings_in_new == total_findings_before and findings_in_old == 0 and total_findings_after == total_findings_before:
    print(f"\n✅ SUCCESS! All {total_findings_before} Findings are accessible under the new Product!")
    print("✅ Engagement migration fix is working correctly!")
    print("✅ No Findings lost during migration!")
else:
    print(f"\n❌ FAILURE!")
    if findings_in_new != total_findings_before:
        print(f"  Expected {total_findings_before} findings in new product, got {findings_in_new}")
    if findings_in_old != 0:
        print(f"  Expected 0 findings in old products, got {findings_in_old}")
    if total_findings_after != total_findings_before:
        print(f"  DATA LOSS! Lost {total_findings_before - total_findings_after} findings!")

print("\n✓ Test complete")
