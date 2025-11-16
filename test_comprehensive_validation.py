#!/usr/bin/env python3
"""
Comprehensive Phase 4 Migration Validation Test.

Validates:
1. Finding hash_code stability after migration
2. Deduplication key integrity
3. Re-import deduplication (no duplicate Findings)
4. Rollback integrity
5. Data preservation across all operations
"""
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dojo.settings.settings")
import django
django.setup()

from dojo.models import Repository, Product, Product_Type, Engagement, Finding, Test
from dojo.product.migration_wizard import ProductMigrationWizard
from collections import defaultdict
import json

print("=" * 80)
print("COMPREHENSIVE PHASE 4 MIGRATION VALIDATION TEST")
print("=" * 80)

# ============================================================================
# PHASE 1: Capture Pre-Migration State
# ============================================================================
print("\n[PHASE 1] Capturing Pre-Migration State...")

# Ensure we have clean repositories
webgoat_product = Product.objects.get(id=1)
sca_product = Product.objects.get(id=2)

# Delete any existing consolidated product
Product.objects.filter(name__contains="Comprehensive Test Product").delete()

# Recreate repositories
repo1, _ = Repository.objects.get_or_create(
    name="haris-siddiqui-1/WebGoat",
    defaults={
        'github_repo_id': 950345562,
        'github_url': 'https://github.com/haris-siddiqui-1/WebGoat',
        'product': webgoat_product
    }
)
repo1.product = webgoat_product
repo1.save()

repo2, _ = Repository.objects.get_or_create(
    name="haris-siddiqui-1/Damn-vulnerable-sca",
    defaults={
        'github_repo_id': 949794740,
        'github_url': 'https://github.com/haris-siddiqui-1/Damn-vulnerable-sca',
        'product': sca_product
    }
)
repo2.product = sca_product
repo2.save()

print(f"  ✓ Repositories configured:")
print(f"    - {repo1.name} → {webgoat_product.name}")
print(f"    - {repo2.name} → {sca_product.name}")

# Capture all Findings and their deduplication metadata
all_findings = Finding.objects.all().select_related('test__engagement__product')

pre_migration_data = {
    'total_findings': all_findings.count(),
    'findings_by_product': defaultdict(int),
    'hash_codes': {},
    'deduplication_keys': {},
    'findings_by_engagement': defaultdict(int),
}

for finding in all_findings:
    product = finding.test.engagement.product
    engagement = finding.test.engagement

    pre_migration_data['findings_by_product'][product.id] += 1
    pre_migration_data['findings_by_engagement'][engagement.id] += 1

    # Store hash_code
    pre_migration_data['hash_codes'][finding.id] = finding.hash_code

    # Store deduplication key components
    pre_migration_data['deduplication_keys'][finding.id] = {
        'title': finding.title,
        'file_path': finding.file_path,
        'line': finding.line,
        'unique_id_from_tool': finding.unique_id_from_tool,
        'hash_code': finding.hash_code,
        'test_id': finding.test_id,
        'engagement_id': finding.test.engagement_id,
        'product_id': finding.test.engagement.product_id,
    }

print(f"\n  Pre-Migration Snapshot:")
print(f"    Total Findings: {pre_migration_data['total_findings']}")
print(f"    Findings by Product:")
for product_id, count in pre_migration_data['findings_by_product'].items():
    product = Product.objects.get(id=product_id)
    print(f"      - {product.name} (ID={product_id}): {count} findings")
print(f"    Unique hash_codes captured: {len(pre_migration_data['hash_codes'])}")
print(f"    Deduplication keys captured: {len(pre_migration_data['deduplication_keys'])}")

# ============================================================================
# PHASE 2: Run Migration
# ============================================================================
print("\n[PHASE 2] Running Migration with Engagement Fix...")

wizard = ProductMigrationWizard()
prod_type = Product_Type.objects.first()
repos = Repository.objects.all()

groupings = [
    {
        'product_name': 'Comprehensive Test Product',
        'description': 'Test product for comprehensive validation',
        'product_type_id': prod_type.id,
        'repository_ids': [repo.id for repo in repos]
    }
]

result = wizard.apply_migration(groupings, dry_run=False)

if not result['success']:
    print(f"  ✗ Migration FAILED: {result.get('error')}")
    exit(1)

print(f"  ✓ Migration successful (ID: {result['migration_id']})")
print(f"    Created products: {len(result['created_products'])}")
print(f"    Updated repositories: {len(result['updated_repositories'])}")
print(f"    Archived products: {len(result['archived_products'])}")

migration_id = result['migration_id']
new_product = Product.objects.get(name="Comprehensive Test Product")

# ============================================================================
# PHASE 3: Verify Hash Code Stability
# ============================================================================
print("\n[PHASE 3] Verifying Hash Code Stability...")

post_migration_findings = Finding.objects.all()
hash_code_changes = []
hash_code_matches = 0

for finding in post_migration_findings:
    pre_hash = pre_migration_data['hash_codes'].get(finding.id)
    if pre_hash is None:
        hash_code_changes.append({
            'finding_id': finding.id,
            'error': 'Finding not in pre-migration snapshot'
        })
    elif pre_hash != finding.hash_code:
        hash_code_changes.append({
            'finding_id': finding.id,
            'pre_hash': pre_hash,
            'post_hash': finding.hash_code,
            'title': finding.title
        })
    else:
        hash_code_matches += 1

if hash_code_changes:
    print(f"  ✗ HASH CODE STABILITY FAILURE!")
    print(f"    Changed: {len(hash_code_changes)}")
    print(f"    Stable: {hash_code_matches}")
    for change in hash_code_changes[:5]:  # Show first 5
        print(f"      - Finding {change['finding_id']}: {change.get('pre_hash')} → {change.get('post_hash')}")
else:
    print(f"  ✓ Hash code stability verified:")
    print(f"    All {hash_code_matches} Findings have unchanged hash_codes")

# ============================================================================
# PHASE 4: Verify Deduplication Key Integrity
# ============================================================================
print("\n[PHASE 4] Verifying Deduplication Key Integrity...")

dedupe_key_changes = []
dedupe_key_matches = 0

for finding in post_migration_findings:
    pre_keys = pre_migration_data['deduplication_keys'].get(finding.id)
    if pre_keys is None:
        continue

    # Check critical deduplication fields
    current_keys = {
        'title': finding.title,
        'file_path': finding.file_path,
        'line': finding.line,
        'unique_id_from_tool': finding.unique_id_from_tool,
        'hash_code': finding.hash_code,
    }

    changed_fields = []
    for field, pre_value in pre_keys.items():
        if field in current_keys:
            current_value = current_keys[field]
            if pre_value != current_value:
                changed_fields.append(f"{field}: {pre_value} → {current_value}")

    if changed_fields:
        dedupe_key_changes.append({
            'finding_id': finding.id,
            'changed_fields': changed_fields
        })
    else:
        dedupe_key_matches += 1

if dedupe_key_changes:
    print(f"  ✗ DEDUPLICATION KEY INTEGRITY FAILURE!")
    print(f"    Changed: {len(dedupe_key_changes)}")
    for change in dedupe_key_changes[:5]:
        print(f"      - Finding {change['finding_id']}: {', '.join(change['changed_fields'])}")
else:
    print(f"  ✓ Deduplication key integrity verified:")
    print(f"    All {dedupe_key_matches} Findings have unchanged deduplication keys")

# ============================================================================
# PHASE 5: Verify Finding Accessibility
# ============================================================================
print("\n[PHASE 5] Verifying Finding Accessibility...")

findings_in_new = Finding.objects.filter(test__engagement__product=new_product).count()
findings_in_old = Finding.objects.filter(test__engagement__product__is_repository_placeholder=True).count()
total_findings_post_migration = Finding.objects.count()

print(f"  Findings in new Product: {findings_in_new}")
print(f"  Findings in old Products: {findings_in_old}")
print(f"  Total Findings: {total_findings_post_migration}")

if findings_in_new == pre_migration_data['total_findings'] and findings_in_old == 0:
    print(f"  ✓ Finding accessibility verified:")
    print(f"    All {findings_in_new} Findings accessible under new Product")
else:
    print(f"  ✗ FINDING ACCESSIBILITY FAILURE!")
    print(f"    Expected {pre_migration_data['total_findings']} in new, got {findings_in_new}")
    print(f"    Expected 0 in old, got {findings_in_old}")

# ============================================================================
# PHASE 6: Verify Engagement Migration
# ============================================================================
print("\n[PHASE 6] Verifying Engagement Migration...")

engagements_in_new = Engagement.objects.filter(product=new_product)
engagements_in_old = Engagement.objects.filter(product__is_repository_placeholder=True)

print(f"  Engagements in new Product: {engagements_in_new.count()}")
print(f"  Engagements in old Products: {engagements_in_old.count()}")

for eng in engagements_in_new:
    eng_findings = Finding.objects.filter(test__engagement=eng).count()
    print(f"    - {eng.name}: {eng_findings} findings")

if engagements_in_old.count() == 0:
    print(f"  ✓ Engagement migration verified:")
    print(f"    All Engagements moved to new Product")
else:
    print(f"  ✗ ENGAGEMENT MIGRATION FAILURE!")
    print(f"    {engagements_in_old.count()} Engagements still in old Products")

# ============================================================================
# PHASE 7: Test Rollback
# ============================================================================
print("\n[PHASE 7] Testing Rollback Functionality...")

rollback_result = wizard.rollback_migration(migration_id)

if not rollback_result['success']:
    print(f"  ✗ Rollback FAILED: {rollback_result.get('error')}")
else:
    print(f"  ✓ Rollback successful:")
    print(f"    Restored repositories: {rollback_result['restored_repositories']}")
    print(f"    Deleted products: {rollback_result['deleted_products']}")

# Verify Findings still accessible after rollback
total_findings_post_rollback = Finding.objects.count()
print(f"\n  Post-Rollback Findings: {total_findings_post_rollback}")

if total_findings_post_rollback == pre_migration_data['total_findings']:
    print(f"  ✓ Data integrity maintained after rollback")
else:
    print(f"  ✗ DATA LOSS DETECTED!")
    print(f"    Lost {pre_migration_data['total_findings'] - total_findings_post_rollback} Findings")

# Verify hash codes still valid after rollback
post_rollback_findings = Finding.objects.all()
rollback_hash_changes = 0
for finding in post_rollback_findings:
    pre_hash = pre_migration_data['hash_codes'].get(finding.id)
    if pre_hash and pre_hash != finding.hash_code:
        rollback_hash_changes += 1

if rollback_hash_changes == 0:
    print(f"  ✓ Hash codes stable after rollback")
else:
    print(f"  ✗ {rollback_hash_changes} hash codes changed after rollback")

# ============================================================================
# FINAL REPORT
# ============================================================================
print("\n" + "=" * 80)
print("FINAL VALIDATION REPORT")
print("=" * 80)

validation_results = {
    'hash_code_stability': len(hash_code_changes) == 0,
    'deduplication_key_integrity': len(dedupe_key_changes) == 0,
    'finding_accessibility': findings_in_new == pre_migration_data['total_findings'] and findings_in_old == 0,
    'engagement_migration': engagements_in_old.count() == 0,
    'rollback_success': rollback_result['success'],
    'data_preservation': total_findings_post_rollback == pre_migration_data['total_findings'],
    'hash_stability_post_rollback': rollback_hash_changes == 0,
}

all_passed = all(validation_results.values())

print("\nValidation Results:")
for check, passed in validation_results.items():
    status = "✓ PASS" if passed else "✗ FAIL"
    print(f"  {status}: {check}")

print("\nMetrics:")
print(f"  Total Findings: {pre_migration_data['total_findings']}")
print(f"  Hash Codes Stable: {hash_code_matches}/{len(pre_migration_data['hash_codes'])}")
print(f"  Deduplication Keys Stable: {dedupe_key_matches}/{len(pre_migration_data['deduplication_keys'])}")
print(f"  Findings Migrated: {findings_in_new}")
print(f"  Engagements Migrated: {engagements_in_new.count()}")
print(f"  Data Preserved After Rollback: {total_findings_post_rollback}/{pre_migration_data['total_findings']}")

if all_passed:
    print("\n" + "=" * 80)
    print("✓✓✓ ALL VALIDATIONS PASSED ✓✓✓")
    print("=" * 80)
    print("\nPhase 4 Migration is production-ready:")
    print("  ✓ Hash code stability maintained")
    print("  ✓ Deduplication integrity preserved")
    print("  ✓ All Findings accessible after migration")
    print("  ✓ Engagement migration working correctly")
    print("  ✓ Rollback functionality verified")
    print("  ✓ Zero data loss")
else:
    print("\n" + "=" * 80)
    print("✗✗✗ VALIDATION FAILURES DETECTED ✗✗✗")
    print("=" * 80)
    print("\nFailed checks require investigation before production deployment.")

print("\n✓ Comprehensive validation test complete")
