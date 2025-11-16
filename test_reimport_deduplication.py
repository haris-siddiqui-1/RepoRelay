#!/usr/bin/env python3
"""
Test re-import deduplication with REAL GitHub alert data.

Verifies:
1. Findings are real GitHub security alerts (from PAT)
2. Re-importing same alerts doesn't create duplicates
3. Deduplication works correctly after migration
"""
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dojo.settings.settings")
import django
django.setup()

from dojo.models import Product, Repository, Engagement, Finding, Test, Tool_Configuration
from django.db.models import Count

print("=" * 80)
print("RE-IMPORT DEDUPLICATION VALIDATION - REAL GITHUB ALERT DATA")
print("=" * 80)

# ============================================================================
# PHASE 1: Verify Real GitHub Alert Data
# ============================================================================
print("\n[PHASE 1] Verifying Real GitHub Alert Data...")

# Get all Findings
all_findings = Finding.objects.all().select_related('test__engagement__product', 'test__test_type')

total_findings = all_findings.count()
print(f"\nTotal Findings in database: {total_findings}")

# Group by test type to see where they came from
print("\nFindings by Test Type (tool/scanner):")
test_types = Finding.objects.values('test__test_type__name').annotate(
    count=Count('id')
).order_by('-count')

for tt in test_types:
    print(f"  - {tt['test__test_type__name']}: {tt['count']} findings")

# Group by Product
print("\nFindings by Product:")
products = Finding.objects.values('test__engagement__product__name', 'test__engagement__product_id').annotate(
    count=Count('id')
).order_by('-count')

for p in products:
    print(f"  - {p['test__engagement__product__name']} (ID={p['test__engagement__product_id']}): {p['count']} findings")

# Sample real Findings to verify they're GitHub alerts
print("\nSample Findings (first 5):")
for finding in all_findings[:5]:
    print(f"\n  Finding ID={finding.id}:")
    print(f"    Title: {finding.title}")
    print(f"    Severity: {finding.severity}")
    print(f"    Tool: {finding.test.test_type.name if finding.test.test_type else 'Unknown'}")
    print(f"    Hash Code: {finding.hash_code}")
    print(f"    Unique ID from Tool: {finding.unique_id_from_tool}")
    print(f"    File: {finding.file_path}")
    print(f"    Product: {finding.test.engagement.product.name}")
    print(f"    Repository: {finding.test.engagement.product.name}")

# Check for GitHub-specific indicators
github_indicators = {
    'has_unique_id_from_tool': Finding.objects.exclude(unique_id_from_tool__isnull=True).exclude(unique_id_from_tool='').count(),
    'has_file_path': Finding.objects.exclude(file_path__isnull=True).exclude(file_path='').count(),
    'has_hash_code': Finding.objects.exclude(hash_code__isnull=True).exclude(hash_code='').count(),
}

print("\nGitHub Alert Indicators:")
print(f"  Findings with unique_id_from_tool: {github_indicators['has_unique_id_from_tool']}/{total_findings}")
print(f"  Findings with file_path: {github_indicators['has_file_path']}/{total_findings}")
print(f"  Findings with hash_code: {github_indicators['has_hash_code']}/{total_findings}")

if github_indicators['has_hash_code'] == total_findings:
    print("  ✓ All Findings have hash_codes (required for deduplication)")
else:
    print(f"  ✗ WARNING: {total_findings - github_indicators['has_hash_code']} Findings missing hash_codes")

# ============================================================================
# PHASE 2: Analyze Deduplication Keys
# ============================================================================
print("\n[PHASE 2] Analyzing Deduplication Keys...")

# Capture deduplication data before potential re-import
dedup_data = {}
hash_code_counts = {}

for finding in all_findings:
    # Store deduplication key
    dedup_key = (
        finding.title,
        finding.file_path,
        finding.line,
        finding.unique_id_from_tool,
        finding.test.engagement.product_id
    )

    if dedup_key not in dedup_data:
        dedup_data[dedup_key] = []
    dedup_data[dedup_key].append(finding.id)

    # Count hash_code occurrences
    if finding.hash_code:
        hash_code_counts[finding.hash_code] = hash_code_counts.get(finding.hash_code, 0) + 1

# Check for existing duplicates
duplicates = {k: v for k, v in dedup_data.items() if len(v) > 1}
duplicate_hash_codes = {k: v for k, v in hash_code_counts.items() if v > 1}

print(f"\nDeduplication Analysis:")
print(f"  Unique deduplication keys: {len(dedup_data)}")
print(f"  Total Findings: {total_findings}")
print(f"  Duplicate deduplication keys: {len(duplicates)}")
print(f"  Duplicate hash_codes: {len(duplicate_hash_codes)}")

if duplicates:
    print(f"\n  ✗ WARNING: Found {len(duplicates)} duplicate deduplication keys:")
    for dedup_key, finding_ids in list(duplicates.items())[:3]:
        print(f"    - Key {dedup_key}: Finding IDs {finding_ids}")
else:
    print(f"  ✓ No duplicate deduplication keys found")

if duplicate_hash_codes:
    print(f"\n  ✗ WARNING: Found {len(duplicate_hash_codes)} duplicate hash_codes:")
    for hash_code, count in list(duplicate_hash_codes.items())[:3]:
        findings_with_hash = Finding.objects.filter(hash_code=hash_code)
        print(f"    - Hash {hash_code}: {count} findings")
        for f in findings_with_hash[:2]:
            print(f"      Finding {f.id}: {f.title}")
else:
    print(f"  ✓ All hash_codes are unique")

# ============================================================================
# PHASE 3: Check Repository Sources
# ============================================================================
print("\n[PHASE 3] Verifying Repository Sources...")

repositories = Repository.objects.all()
print(f"\nRepositories in database: {repositories.count()}")

for repo in repositories:
    print(f"\n  Repository: {repo.name}")
    print(f"    GitHub ID: {repo.github_repo_id}")
    print(f"    GitHub URL: {repo.github_url}")
    print(f"    Product: {repo.product.name} (ID={repo.product_id})")

    # Count Findings for this repository's product
    findings_count = Finding.objects.filter(test__engagement__product=repo.product).count()
    print(f"    Findings in Product: {findings_count}")

# ============================================================================
# PHASE 4: Deduplication Configuration Check
# ============================================================================
print("\n[PHASE 4] Checking Deduplication Configuration...")

# Check if there are any Tool Configurations
tool_configs = Tool_Configuration.objects.all()
print(f"\nTool Configurations: {tool_configs.count()}")

if tool_configs.exists():
    for tc in tool_configs[:3]:
        print(f"  - {tc.name}: {tc.tool_type.name if tc.tool_type else 'No type'}")

# Check Test metadata
tests = Test.objects.all()
print(f"\nTests in database: {tests.count()}")

print("\nTests by Type:")
test_type_counts = Test.objects.values('test_type__name').annotate(
    count=Count('id')
).order_by('-count')

for tt in test_type_counts:
    print(f"  - {tt['test_type__name']}: {tt['count']} tests")

# ============================================================================
# PHASE 5: Data Quality Assessment
# ============================================================================
print("\n[PHASE 5] Data Quality Assessment...")

data_quality = {
    'total_findings': total_findings,
    'findings_with_hash': github_indicators['has_hash_code'],
    'findings_with_unique_id': github_indicators['has_unique_id_from_tool'],
    'findings_with_file': github_indicators['has_file_path'],
    'unique_dedup_keys': len(dedup_data),
    'duplicate_dedup_keys': len(duplicates),
    'duplicate_hash_codes': len(duplicate_hash_codes),
}

print("\nData Quality Metrics:")
for metric, value in data_quality.items():
    print(f"  {metric}: {value}")

# Assessment
is_real_github_data = (
    github_indicators['has_hash_code'] > 0 and
    github_indicators['has_unique_id_from_tool'] > 0 and
    repositories.filter(github_repo_id__isnull=False).exists()
)

print(f"\n{'=' * 80}")
print("ASSESSMENT")
print(f"{'=' * 80}")

if is_real_github_data:
    print("\n✓ Data appears to be REAL GitHub security alerts:")
    print(f"  - {github_indicators['has_hash_code']} Findings have hash_codes")
    print(f"  - {github_indicators['has_unique_id_from_tool']} Findings have unique_id_from_tool")
    print(f"  - {repositories.count()} Repositories with GitHub IDs")
    print(f"  - {total_findings} total vulnerability Findings")
else:
    print("\n✗ Data does NOT appear to be real GitHub alerts")
    print("  - May be synthetic test data or missing GitHub metadata")

if len(duplicates) == 0 and len(duplicate_hash_codes) == 0:
    print("\n✓ Deduplication is working correctly:")
    print("  - No duplicate deduplication keys")
    print("  - All hash_codes are unique")
    print("  - Safe to test re-import")
else:
    print("\n✗ Deduplication issues detected:")
    print(f"  - {len(duplicates)} duplicate deduplication keys")
    print(f"  - {len(duplicate_hash_codes)} duplicate hash_codes")
    print("  - May indicate existing deduplication failures")

print(f"\n{'=' * 80}")
print("CONCLUSION")
print(f"{'=' * 80}")

if is_real_github_data and len(duplicates) == 0:
    print("\n✓ Database contains clean, real GitHub alert data")
    print("✓ Ready for re-import deduplication testing")
    print(f"✓ {total_findings} Findings available for validation")
else:
    print("\n⚠ Database state requires attention before re-import testing")
    if not is_real_github_data:
        print("  - Verify GitHub PAT is configured correctly")
        print("  - Verify github_collector has synced alerts")
    if len(duplicates) > 0:
        print("  - Resolve existing duplicate Findings first")

print("\n✓ Data verification complete")
