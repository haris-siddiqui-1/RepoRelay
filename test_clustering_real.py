#!/usr/bin/env python3
"""Test clustering with real GitHub repository data."""
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dojo.settings.settings")
import django
django.setup()

from dojo.models import Repository
from dojo.github_collector.clustering import RepositoryClusteringEngine
from dojo.product.migration_wizard import ProductMigrationWizard
import json

# Verify repository data
repos = Repository.objects.all()
print("=== Repository Data ===")
print(f"Total repositories: {repos.count()}\n")

for repo in repos:
    print(f"{repo.name}:")
    print(f"  Last commit: {repo.days_since_last_commit} days ago")
    print(f"  Contributors: {repo.active_contributors_90d}")
    lang = repo.primary_language if repo.primary_language else "(none)"
    print(f"  Language: {lang}")
    print(f"  Has Dockerfile: {repo.has_dockerfile}")
    print(f"  Has CI/CD: {repo.has_ci_cd}")
    print()

# Test clustering
print("=== Testing Clustering ===")
wizard = ProductMigrationWizard()
result = wizard.get_clustering_suggestions()

print(f"\nClustering Success: {result['success']}")
if not result['success']:
    print(f"Error: {result.get('error')}")
else:
    print(f"\nSummary:")
    print(f"  Total repositories: {result['summary']['total_repositories']}")
    print(f"  Total clusters: {result['summary']['total_clusters']}")
    print(f"  High confidence clusters: {result['summary']['high_confidence_clusters']}")
    print(f"  Medium confidence clusters: {result['summary']['medium_confidence_clusters']}")
    print(f"  Low confidence clusters: {result['summary']['low_confidence_clusters']}")

    print(f"\nClusters:")
    for i, cluster in enumerate(result['clusters'], 1):
        print(f"\nCluster {i}:")
        print(f"  Suggested name: {cluster.get('suggested_product_name', 'N/A')}")
        print(f"  Confidence: {cluster['confidence_score']}")
        print(f"  Repository count: {cluster['repository_count']}")

        # Extract repository names from repositories list
        repo_names = [r['name'] for r in cluster.get('repositories', [])]
        repos_str = ", ".join(repo_names)
        print(f"  Repositories: {repos_str}")

        if 'common_features' in cluster:
            print(f"  Common features:")
            for key, value in cluster['common_features'].items():
                print(f"    {key}: {value}")

        if 'explanation' in cluster:
            print(f"  Explanation: {cluster['explanation']}")

print("\n✓ Clustering test complete")
