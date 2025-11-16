#!/usr/bin/env python3
"""Test rollback functionality with real migrated data."""
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dojo.settings.settings")
import django
django.setup()

from dojo.models import Repository, Product, Finding
from dojo.product.migration_wizard import ProductMigrationWizard

print("=== State Before Rollback ===")
products = Product.objects.all().order_by('id')
print("Products:")
for p in products:
    repo_count = Repository.objects.filter(product=p).count()
    finding_count = Finding.objects.filter(test__engagement__product=p).count()
    is_placeholder = p.is_repository_placeholder
    migrated_to = p.migrated_to_product_id if hasattr(p, 'migrated_to_product') else None
    print(f"  - {p.name} (ID={p.id})")
    print(f"    Repos: {repo_count}, Findings: {finding_count}")
    print(f"    Placeholder: {is_placeholder}, Migrated to: {migrated_to}")

print("\nRepositories:")
repos = Repository.objects.all()
for r in repos:
    print(f"  - {r.name} → Product '{r.product.name}' (ID={r.product_id})")

print("\n=== Step 1: Test Rollback ===")
# Get the migration ID from the last migration
# We know from the previous test it was mig_20251116_202143
migration_id = "mig_20251116_202143"

wizard = ProductMigrationWizard()
result = wizard.rollback_migration(migration_id)

print(f"\nRollback Success: {result['success']}")
if result['success']:
    print(f"Migration ID: {result['migration_id']}")
    print(f"Restored repositories: {result['restored_repositories']}")
    print(f"Deleted products: {result['deleted_products']}")
    print(f"Message: {result['message']}")
else:
    print(f"Error: {result.get('error')}")

print("\n=== State After Rollback ===")
products = Product.objects.all().order_by('id')
print("Products:")
for p in products:
    repo_count = Repository.objects.filter(product=p).count()
    finding_count = Finding.objects.filter(test__engagement__product=p).count()
    is_placeholder = getattr(p, 'is_repository_placeholder', False)
    migrated_to = p.migrated_to_product_id if hasattr(p, 'migrated_to_product') and p.migrated_to_product else None
    print(f"  - {p.name} (ID={p.id})")
    print(f"    Repos: {repo_count}, Findings: {finding_count}")
    print(f"    Placeholder: {is_placeholder}, Migrated to: {migrated_to}")

print("\nRepositories:")
repos = Repository.objects.all()
for r in repos:
    print(f"  - {r.name} → Product '{r.product.name}' (ID={r.product_id})")

# Verify Findings still intact
total_findings = Finding.objects.count()
print(f"\n=== Data Integrity Check ===")
print(f"Total Findings in database: {total_findings}")
print(f"Expected: 133")
print(f"Data preserved: {'✓ YES' if total_findings == 133 else '✗ NO - DATA LOSS!'}")

print("\n✓ Rollback test complete")
