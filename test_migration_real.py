#!/usr/bin/env python3
"""Test migration wizard with real GitHub repository data."""
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dojo.settings.settings")
import django
django.setup()

from dojo.models import Repository, Product, Product_Type
from dojo.product.migration_wizard import ProductMigrationWizard
import json

# Get current state
repos = Repository.objects.all()
products = Product.objects.all()
product_types = Product_Type.objects.all()

print("=== Initial State ===")
print(f"Repositories: {repos.count()}")
print(f"Products: {products.count()}")
print(f"Product Types: {product_types.count()}\n")

# Get or create a Product_Type
if product_types.exists():
    prod_type = product_types.first()
    print(f"Using existing Product_Type: {prod_type.name} (ID={prod_type.id})")
else:
    prod_type = Product_Type.objects.create(name="Security Testing")
    print(f"Created Product_Type: {prod_type.name} (ID={prod_type.id})")

print("\n=== Step 1: Preview Migration ===")
wizard = ProductMigrationWizard()

# Create grouping based on clustering result
groupings = [
    {
        'product_name': 'Vulnerable Apps Consolidated',
        'description': 'Consolidated vulnerable test applications',
        'product_type_id': prod_type.id,
        'repository_ids': [repo.id for repo in repos]
    }
]

print(f"Grouping: Consolidate {len(groupings[0]['repository_ids'])} repos into '{groupings[0]['product_name']}'")

# Preview migration
preview = wizard.preview_migration(groupings)

print(f"\nPreview Success: {preview['success']}")
if not preview['success']:
    print("Validation Errors:")
    for error in preview['validation_errors']:
        print(f"  - {error}")
else:
    print("\nValidation Warnings:")
    for warning in preview.get('validation_warnings', []):
        print(f"  - {warning}")

    print("\nImpact:")
    for key, value in preview['impact'].items():
        print(f"  {key}: {value}")

    print("\nBreakdown:")
    for item in preview['breakdown']:
        print(f"  Product '{item['product_name']}': {item['repository_count']} repos")
        for repo_name in item['repository_names']:
            print(f"    - {repo_name}")

print("\n=== Step 2: Dry-Run Migration ===")
if preview['success']:
    dry_result = wizard.apply_migration(groupings, dry_run=True)

    print(f"Dry-run Success: {dry_result['success']}")
    if dry_result['success']:
        print(f"Migration ID: {dry_result['migration_id']}")
        print(f"Would create {dry_result['created_products']} products")
        print(f"Would update {dry_result['updated_repositories']} repositories")
        print(f"Would archive {dry_result['archived_products']} products")
    else:
        print(f"Error: {dry_result.get('error')}")

print("\n=== Step 3: Actual Migration ===")
if preview['success'] and dry_result['success']:
    # Show current Products before migration
    print("Products before migration:")
    for p in Product.objects.all():
        repo_count = Repository.objects.filter(product=p).count()
        print(f"  - {p.name} (ID={p.id}, repos={repo_count})")

    # Apply migration
    result = wizard.apply_migration(groupings, dry_run=False)

    print(f"\nMigration Success: {result['success']}")
    if result['success']:
        print(f"Migration ID: {result['migration_id']}")
        print(f"\nCreated Products:")
        for p in result['created_products']:
            print(f"  - {p['name']} (ID={p['id']})")

        print(f"\nUpdated Repositories:")
        for r in result['updated_repositories']:
            print(f"  - {r['name']} → Product ID {r['new_product_id']}")

        print(f"\nArchived Products:")
        for p in result['archived_products']:
            print(f"  - {p['name']} (ID={p['id']}) → Migrated to ID {p['migrated_to_id']}")

        # Verify final state
        print("\n=== Final State ===")
        print("Products after migration:")
        for p in Product.objects.all():
            repo_count = Repository.objects.filter(product=p).count()
            is_placeholder = p.is_repository_placeholder
            print(f"  - {p.name} (ID={p.id}, repos={repo_count}, placeholder={is_placeholder})")
    else:
        print(f"Error: {result.get('error')}")
        if 'validation_errors' in result:
            for err in result['validation_errors']:
                print(f"  - {err}")

print("\n✓ Migration test complete")
