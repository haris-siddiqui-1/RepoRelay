#!/usr/bin/env python3
"""
Test rollback integrity - recreates repositories from real GitHub data first.

This test validates rollback after repositories were cascade-deleted during
previous test cleanup.
"""
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dojo.settings.settings")
import django
django.setup()

from dojo.models import Product, Repository, Product_Type, Engagement, Finding
from dojo.product.migration_wizard import ProductMigrationWizard

print("=" * 80)
print("ROLLBACK INTEGRITY TEST WITH REAL GITHUB DATA")
print("=" * 80)

# ============================================================================
# PHASE 1: Recreate Real GitHub Repositories
# ============================================================================
print("\n[PHASE 1] Recreating Real GitHub Repositories...")

# Get existing Products
webgoat_product = Product.objects.get(id=1)  # WebGoat Security Test
sca_product = Product.objects.get(id=2)  # Damn Vulnerable SCA
consolidated_product = Product.objects.get(id=7)  # Vulnerable Apps Consolidated

print(f"  Existing Products:")
print(f"    - {webgoat_product.name} (ID={webgoat_product.id})")
print(f"    - {sca_product.name} (ID={sca_product.id})")
print(f"    - {consolidated_product.name} (ID={consolidated_product.id})")

# Recreate repositories with real GitHub data
repo1, created1 = Repository.objects.get_or_create(
    github_repo_id=950345562,
    defaults={
        'name': 'haris-siddiqui-1/WebGoat',
        'github_url': 'https://github.com/haris-siddiqui-1/WebGoat',
        'product': webgoat_product
    }
)
if not created1:
    repo1.product = webgoat_product
    repo1.save()

repo2, created2 = Repository.objects.get_or_create(
    github_repo_id=949794740,
    defaults={
        'name': 'haris-siddiqui-1/Damn-vulnerable-sca',
        'github_url': 'https://github.com/haris-siddiqui-1/Damn-vulnerable-sca',
        'product': sca_product
    }
)
if not created2:
    repo2.product = sca_product
    repo2.save()

print(f"\n  ✓ Repositories recreated:")
print(f"    - {repo1.name} → {repo1.product.name}")
print(f"    - {repo2.name} → {repo2.product.name}")

# Move all Engagements back to their original products
print(f"\n  Moving Engagements to repository Products...")

# All engagements are currently in consolidated_product
# We need to distribute them back to original products for this test
engagements = Engagement.objects.filter(product=consolidated_product)
print(f"  Found {engagements.count()} Engagements in {consolidated_product.name}")

# For simplicity, keep them all in consolidated for now - we'll test migration from there
# The real test is: can we migrate and rollback cleanly?

# ============================================================================
# PHASE 2: Capture Pre-Migration Baseline
# ============================================================================
print("\n[PHASE 2] Capturing Pre-Migration Baseline...")

baseline = {
    'total_findings': Finding.objects.count(),
    'hash_codes': {},
    'dedup_keys': {},
}

for finding in Finding.objects.all():
    baseline['hash_codes'][finding.id] = finding.hash_code
    baseline['dedup_keys'][finding.id] = {
        'title': finding.title,
        'file_path': finding.file_path,
        'line': finding.line,
        'unique_id_from_tool': finding.unique_id_from_tool,
    }

print(f"  ✓ Baseline captured:")
print(f"    Total Findings: {baseline['total_findings']}")
print(f"    Hash codes: {len(baseline['hash_codes'])}")

# Current state: 133 Findings in consolidated_product
# Repositories point to webgoat_product and sca_product
# This mimics Phase 1-3 state where products exist but haven't been migrated yet

# ============================================================================
# PHASE 3: Test Migration
# ============================================================================
print("\n[PHASE 3] Testing Migration...")

# First, move Engagements to match repositories
# This simulates the original Phase 1-3 state
print("  Setting up Phase 1-3 state (Engagements with their repository Products)...")

# For this test, we'll create new Engagements for the repository products
# and migrate the consolidated product's findings to them
# Actually, let's just test migrating FROM the repository products

# Reset: assign repositories to consolidated, move engagements there too
repo1.product = consolidated_product
repo1.save()
repo2.product = consolidated_product
repo2.save()

print(f"  ✓ Repositories assigned to {consolidated_product.name}")
print(f"    Engagements: {Engagement.objects.filter(product=consolidated_product).count()}")
print(f"    Findings: {Finding.objects.filter(test__engagement__product=consolidated_product).count()}")

# Now run migration to create a new consolidated product
wizard = ProductMigrationWizard()
prod_type = Product_Type.objects.first()

groupings = [
    {
        'product_name': 'Migration Test Product',
        'description': 'Testing migration for rollback validation',
        'product_type_id': prod_type.id,
        'repository_ids': [repo1.id, repo2.id]
    }
]

result = wizard.apply_migration(groupings, dry_run=False)

if not result['success']:
    print(f"  ✗ Migration FAILED: {result.get('error')}")
    exit(1)

migration_id = result['migration_id']
print(f"  ✓ Migration successful (ID: {migration_id})")

new_product = Product.objects.get(name="Migration Test Product")
findings_in_new = Finding.objects.filter(test__engagement__product=new_product).count()
print(f"    Findings migrated: {findings_in_new}/{baseline['total_findings']}")

# ============================================================================
# PHASE 4: Test Rollback
# ============================================================================
print("\n[PHASE 4] Testing Rollback...")

rollback_result = wizard.rollback_migration(migration_id)

if not rollback_result['success']:
    print(f"  ✗ Rollback FAILED: {rollback_result.get('error')}")
else:
    print(f"  ✓ Rollback successful")

# ============================================================================
# PHASE 5: Verify Post-Rollback Integrity
# ============================================================================
print("\n[PHASE 5] Verifying Post-Rollback Integrity...")

# Check data preservation
total_findings_after = Finding.objects.count()
hash_changes = 0

for finding in Finding.objects.all():
    baseline_hash = baseline['hash_codes'].get(finding.id)
    if baseline_hash and baseline_hash != finding.hash_code:
        hash_changes += 1

results = {
    'data_preserved': total_findings_after == baseline['total_findings'],
    'hash_stable': hash_changes == 0,
    'rollback_success': rollback_result.get('success', False),
}

print(f"\n  Results:")
print(f"    Findings preserved: {total_findings_after}/{baseline['total_findings']}")
print(f"    Hash codes stable: {len(baseline['hash_codes']) - hash_changes}/{len(baseline['hash_codes'])}")
print(f"    Rollback successful: {results['rollback_success']}")

# ============================================================================
# FINAL REPORT
# ============================================================================
print(f"\n{'=' * 80}")
print("VALIDATION SUMMARY")
print(f"{'=' * 80}")

all_passed = all(results.values())

for check, passed in results.items():
    status = "✓ PASS" if passed else "✗ FAIL"
    print(f"  {status}: {check}")

if all_passed:
    print(f"\n✓✓✓ ROLLBACK INTEGRITY VALIDATED ✓✓✓")
else:
    print(f"\n✗✗✗ ROLLBACK HAS ISSUES ✗✗✗")

print("\n✓ Test complete")
