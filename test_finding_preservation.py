#!/usr/bin/env python3
"""Investigate Finding preservation issue after migration."""
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dojo.settings.settings")
import django
django.setup()

from dojo.models import Product, Engagement, Test, Finding, Repository

print("=== CRITICAL FINDING PRESERVATION ISSUE ===\n")

print("Data Model Chain: Repository → Product ← Engagement ← Test ← Finding")
print("Migration changes: Repository.product (moves repo)")
print("Finding linkage: Finding → Test → Engagement → Product (NOT moved!)\n")

print("=== Old Products (Archived) ===")
old_products = Product.objects.filter(is_repository_placeholder=True).order_by('id')
for old_product in old_products:
    repos = Repository.objects.filter(product=old_product)
    engagements = Engagement.objects.filter(product=old_product)
    findings = Finding.objects.filter(test__engagement__product=old_product)

    print(f"\n{old_product.name} (ID={old_product.id})")
    print(f"  Repositories: {repos.count()} (should be 0 after migration)")
    print(f"  Engagements: {engagements.count()}")
    print(f"  Findings: {findings.count()}")
    print(f"  Migrated to: Product ID {old_product.migrated_to_product_id}")

    if engagements.exists():
        print(f"  Engagement details:")
        for eng in engagements[:3]:
            tests = Test.objects.filter(engagement=eng)
            eng_findings = Finding.objects.filter(test__engagement=eng)
            print(f"    - {eng.name}: {tests.count()} tests, {eng_findings.count()} findings")

print("\n=== New Product (Consolidated) ===")
new_product = Product.objects.get(name="Vulnerable Apps Consolidated")
repos = Repository.objects.filter(product=new_product)
engagements = Engagement.objects.filter(product=new_product)
findings = Finding.objects.filter(test__engagement__product=new_product)

print(f"\n{new_product.name} (ID={new_product.id})")
print(f"  Repositories: {repos.count()} (should be 2 after migration)")
for r in repos:
    print(f"    - {r.name}")
print(f"  Engagements: {engagements.count()} (PROBLEM: should have engagements!)")
print(f"  Findings: {findings.count()} (PROBLEM: should be 133!)")

print("\n=== ANALYSIS ===")
print("✗ Migration only updates Repository.product ForeignKey")
print("✗ Engagements remain linked to OLD archived Products")
print("✗ All Findings (133) are 'orphaned' - still under archived Products")
print("✗ New GitHub alerts for migrated repos will create NEW Findings")
print("✗ This creates DUPLICATE vulnerability records!")

print("\n=== REQUIRED FIX ===")
print("Migration must ALSO move Engagements to the new consolidated Product:")
print("  1. Find all Engagements for old Products in the migration")
print("  2. Update Engagement.product to point to new consolidated Product")
print("  3. This preserves the Finding → Test → Engagement → Product chain")

print("\n=== VERIFICATION QUERY ===")
total_findings = Finding.objects.count()
findings_in_new = Finding.objects.filter(test__engagement__product=new_product).count()
findings_in_old = Finding.objects.filter(test__engagement__product__is_repository_placeholder=True).count()

print(f"Total Findings in DB: {total_findings}")
print(f"Findings under new Product: {findings_in_new}")
print(f"Findings under old Products: {findings_in_old}")
print(f"Data loss: {'YES - CRITICAL!' if findings_in_new < total_findings else 'No'}")

print("\n✓ Investigation complete")
