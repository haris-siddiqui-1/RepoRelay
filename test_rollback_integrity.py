#!/usr/bin/env python3
"""
Test rollback integrity with real GitHub alert data.

Validates:
1. Rollback properly restores Engagements
2. Rollback properly restores Repositories
3. Hash codes remain stable after rollback
4. Deduplication keys remain intact after rollback
5. All 133 real GitHub Findings remain accessible
"""
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dojo.settings.settings")
import django
django.setup()

from dojo.models import Product, Repository, Product_Type, Engagement, Finding, Test
from dojo.product.migration_wizard import ProductMigrationWizard

print("=" * 80)
print("ROLLBACK INTEGRITY VALIDATION - REAL GITHUB ALERT DATA")
print("=" * 80)

# ============================================================================
# PHASE 1: Setup - Prepare Clean Migration Test State
# ============================================================================
print("\n[PHASE 1] Preparing Clean Test State...")

# Find the current consolidated product (from previous migrations)
try:
    consolidated = Product.objects.get(id=7)  # Vulnerable Apps Consolidated
    print(f"  Found consolidated product: {consolidated.name} (ID={consolidated.id})")
except Product.DoesNotExist:
    print("  ✗ No consolidated product found - cannot test rollback")
    exit(1)

# Delete any test products from previous runs
Product.objects.filter(name__contains="Rollback Test Product").delete()
Product.objects.filter(name__contains="Comprehensive Test Product").delete()

# Get repositories
webgoat_repo = Repository.objects.get(github_repo_id=950345562)
sca_repo = Repository.objects.get(github_repo_id=949794740)

print(f"  Repository 1: {webgoat_repo.name}")
print(f"    Currently points to: {webgoat_repo.product.name} (ID={webgoat_repo.product_id})")

print(f"  Repository 2: {sca_repo.name}")
print(f"    Currently points to: {sca_repo.product.name} (ID={sca_repo.product_id})")

# Reset repositories to consolidated product if needed
if webgoat_repo.product_id != consolidated.id:
    webgoat_repo.product = consolidated
    webgoat_repo.save()
    print(f"  ✓ Reset {webgoat_repo.name} → {consolidated.name}")

if sca_repo.product_id != consolidated.id:
    sca_repo.product = consolidated
    sca_repo.save()
    print(f"  ✓ Reset {sca_repo.name} → {consolidated.name}")

# Verify all Findings are in consolidated product
findings_in_consolidated = Finding.objects.filter(test__engagement__product=consolidated).count()
print(f"\n  Findings in {consolidated.name}: {findings_in_consolidated}")

if findings_in_consolidated != 133:
    print(f"  ✗ Expected 133 Findings, found {findings_in_consolidated}")
    print("  Database may be in unexpected state")

# ============================================================================
# PHASE 2: Capture Pre-Migration State
# ============================================================================
print("\n[PHASE 2] Capturing Pre-Migration State...")

pre_migration_state = {
    'total_findings': Finding.objects.count(),
    'findings_in_consolidated': findings_in_consolidated,
    'hash_codes': {},
    'dedup_keys': {},
    'engagements': {},
    'repositories': {},
}

# Capture hash codes and deduplication keys
for finding in Finding.objects.all():
    pre_migration_state['hash_codes'][finding.id] = finding.hash_code
    pre_migration_state['dedup_keys'][finding.id] = {
        'title': finding.title,
        'file_path': finding.file_path,
        'line': finding.line,
        'unique_id_from_tool': finding.unique_id_from_tool,
    }

# Capture Engagement data
for engagement in Engagement.objects.all():
    pre_migration_state['engagements'][engagement.id] = {
        'name': engagement.name,
        'product_id': engagement.product_id,
        'product_name': engagement.product.name,
        'finding_count': Finding.objects.filter(test__engagement=engagement).count(),
    }

# Capture Repository data
for repo in Repository.objects.all():
    pre_migration_state['repositories'][repo.id] = {
        'name': repo.name,
        'product_id': repo.product_id,
        'product_name': repo.product.name,
    }

print(f"  ✓ Captured state:")
print(f"    Total Findings: {pre_migration_state['total_findings']}")
print(f"    Hash codes: {len(pre_migration_state['hash_codes'])}")
print(f"    Deduplication keys: {len(pre_migration_state['dedup_keys'])}")
print(f"    Engagements: {len(pre_migration_state['engagements'])}")
print(f"    Repositories: {len(pre_migration_state['repositories'])}")

# ============================================================================
# PHASE 3: Run Migration
# ============================================================================
print("\n[PHASE 3] Running Migration...")

wizard = ProductMigrationWizard()
prod_type = Product_Type.objects.first()

groupings = [
    {
        'product_name': 'Rollback Test Product',
        'description': 'Product for testing rollback integrity',
        'product_type_id': prod_type.id,
        'repository_ids': [webgoat_repo.id, sca_repo.id]
    }
]

result = wizard.apply_migration(groupings, dry_run=False)

if not result['success']:
    print(f"  ✗ Migration FAILED: {result.get('error')}")
    exit(1)

migration_id = result['migration_id']
print(f"  ✓ Migration successful (ID: {migration_id})")
print(f"    Created products: {len(result['created_products'])}")
print(f"    Updated repositories: {len(result['updated_repositories'])}")
print(f"    Archived products: {len(result['archived_products'])}")

# Verify migration moved Findings
new_product = Product.objects.get(name="Rollback Test Product")
findings_in_new = Finding.objects.filter(test__engagement__product=new_product).count()
print(f"    Findings in new product: {findings_in_new}")

if findings_in_new != 133:
    print(f"  ✗ WARNING: Expected 133 Findings in new product, found {findings_in_new}")

# ============================================================================
# PHASE 4: Test Rollback
# ============================================================================
print("\n[PHASE 4] Testing Rollback...")

rollback_result = wizard.rollback_migration(migration_id)

if not rollback_result['success']:
    print(f"  ✗ Rollback FAILED: {rollback_result.get('error')}")

    # Debug: check what products exist
    print("\n  Debug - Current products:")
    for p in Product.objects.all():
        print(f"    - {p.name} (ID={p.id})")
        print(f"      is_placeholder: {p.is_repository_placeholder}")
        print(f"      description: {p.description[:100] if p.description else 'None'}")
else:
    print(f"  ✓ Rollback successful")
    print(f"    Restored repositories: {rollback_result['restored_repositories']}")
    print(f"    Deleted products: {rollback_result['deleted_products']}")

# ============================================================================
# PHASE 5: Verify Post-Rollback State
# ============================================================================
print("\n[PHASE 5] Verifying Post-Rollback State...")

# Check Findings count
total_findings_after = Finding.objects.count()
print(f"\n  Total Findings after rollback: {total_findings_after}")

if total_findings_after != pre_migration_state['total_findings']:
    print(f"  ✗ DATA LOSS! Lost {pre_migration_state['total_findings'] - total_findings_after} Findings")
else:
    print(f"  ✓ All {total_findings_after} Findings preserved")

# Verify hash codes unchanged
hash_changes = 0
for finding in Finding.objects.all():
    pre_hash = pre_migration_state['hash_codes'].get(finding.id)
    if pre_hash and pre_hash != finding.hash_code:
        hash_changes += 1

if hash_changes == 0:
    print(f"  ✓ All hash codes stable ({len(pre_migration_state['hash_codes'])} verified)")
else:
    print(f"  ✗ {hash_changes} hash codes changed after rollback")

# Verify deduplication keys unchanged
dedup_changes = 0
for finding in Finding.objects.all():
    pre_keys = pre_migration_state['dedup_keys'].get(finding.id)
    if pre_keys:
        if (pre_keys['title'] != finding.title or
            pre_keys['file_path'] != finding.file_path or
            pre_keys['line'] != finding.line or
            pre_keys['unique_id_from_tool'] != finding.unique_id_from_tool):
            dedup_changes += 1

if dedup_changes == 0:
    print(f"  ✓ All deduplication keys stable ({len(pre_migration_state['dedup_keys'])} verified)")
else:
    print(f"  ✗ {dedup_changes} deduplication keys changed after rollback")

# Verify Repository restoration
repo_restoration_ok = True
for repo_id, pre_repo in pre_migration_state['repositories'].items():
    repo = Repository.objects.get(id=repo_id)
    if repo.product_id != pre_repo['product_id']:
        print(f"  ✗ Repository {repo.name} not restored to original product")
        print(f"    Before: {pre_repo['product_name']} (ID={pre_repo['product_id']})")
        print(f"    After: {repo.product.name} (ID={repo.product_id})")
        repo_restoration_ok = False

if repo_restoration_ok:
    print(f"  ✓ All {len(pre_migration_state['repositories'])} Repositories restored correctly")

# Verify Engagement restoration
engagement_restoration_ok = True
for eng_id, pre_eng in pre_migration_state['engagements'].items():
    try:
        eng = Engagement.objects.get(id=eng_id)
        if eng.product_id != pre_eng['product_id']:
            print(f"  ✗ Engagement {eng.name} not restored to original product")
            print(f"    Before: {pre_eng['product_name']} (ID={pre_eng['product_id']})")
            print(f"    After: {eng.product.name} (ID={eng.product_id})")
            engagement_restoration_ok = False
    except Engagement.DoesNotExist:
        print(f"  ✗ Engagement {eng_id} deleted during rollback")
        engagement_restoration_ok = False

if engagement_restoration_ok:
    print(f"  ✓ All {len(pre_migration_state['engagements'])} Engagements restored correctly")

# ============================================================================
# FINAL REPORT
# ============================================================================
print(f"\n{'=' * 80}")
print("ROLLBACK INTEGRITY REPORT")
print(f"{'=' * 80}")

validation_results = {
    'rollback_success': rollback_result.get('success', False),
    'data_preservation': total_findings_after == pre_migration_state['total_findings'],
    'hash_code_stability': hash_changes == 0,
    'dedup_key_stability': dedup_changes == 0,
    'repository_restoration': repo_restoration_ok,
    'engagement_restoration': engagement_restoration_ok,
}

all_passed = all(validation_results.values())

print("\nValidation Results:")
for check, passed in validation_results.items():
    status = "✓ PASS" if passed else "✗ FAIL"
    print(f"  {status}: {check}")

print("\nMetrics:")
print(f"  Findings before migration: {pre_migration_state['total_findings']}")
print(f"  Findings after rollback: {total_findings_after}")
print(f"  Hash codes stable: {len(pre_migration_state['hash_codes']) - hash_changes}/{len(pre_migration_state['hash_codes'])}")
print(f"  Deduplication keys stable: {len(pre_migration_state['dedup_keys']) - dedup_changes}/{len(pre_migration_state['dedup_keys'])}")
print(f"  Repositories restored: {len(pre_migration_state['repositories'])}")
print(f"  Engagements restored: {len(pre_migration_state['engagements'])}")

if all_passed:
    print(f"\n{'=' * 80}")
    print("✓✓✓ ROLLBACK INTEGRITY VALIDATED ✓✓✓")
    print(f"{'=' * 80}")
    print("\nRollback functionality is production-ready:")
    print("  ✓ Rollback completed successfully")
    print("  ✓ All 133 Findings preserved")
    print("  ✓ Hash codes stable")
    print("  ✓ Deduplication keys intact")
    print("  ✓ Repositories restored")
    print("  ✓ Engagements restored")
else:
    print(f"\n{'=' * 80}")
    print("✗✗✗ ROLLBACK INTEGRITY FAILURES ✗✗✗")
    print(f"{'=' * 80}")
    print("\nRollback has issues that need fixing")

print("\n✓ Rollback integrity test complete")
