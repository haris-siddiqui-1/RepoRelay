"""
Test script for GitHub GraphQL migration

Tests:
1. GraphQL client initialization
2. Single repository query cost
3. Organization batch query cost
4. Incremental sync filtering
5. Signal detection from GraphQL data
6. Data consistency vs REST API
"""

import os
import sys
import django
from datetime import datetime, timedelta

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dojo.settings.settings')
django.setup()

from dojo.github_collector.graphql_client import GitHubGraphQLClient
from dojo.github_collector.collector import GitHubRepositoryCollector
from django.conf import settings
from django.utils import timezone


def test_graphql_client_init():
    """Test 1: GraphQL client initialization"""
    print("\n" + "="*70)
    print("TEST 1: GraphQL Client Initialization")
    print("="*70)

    try:
        token = getattr(settings, 'DD_GITHUB_TOKEN', os.getenv('DD_GITHUB_TOKEN'))
        if not token:
            print("❌ SKIP: DD_GITHUB_TOKEN not configured")
            return False

        client = GitHubGraphQLClient(token)
        print("✅ GraphQL client initialized successfully")
        return True
    except Exception as e:
        print(f"❌ FAILED: {e}")
        return False


def test_single_repo_query_cost():
    """Test 2: Single repository query cost measurement"""
    print("\n" + "="*70)
    print("TEST 2: Single Repository Query Cost")
    print("="*70)

    try:
        token = getattr(settings, 'DD_GITHUB_TOKEN', os.getenv('DD_GITHUB_TOKEN'))
        org = getattr(settings, 'DD_GITHUB_ORG', os.getenv('DD_GITHUB_ORG'))

        if not token or not org:
            print("❌ SKIP: DD_GITHUB_TOKEN or DD_GITHUB_ORG not configured")
            return False

        client = GitHubGraphQLClient(token)

        # Query single repo (use DefectDojo itself as test)
        repo_data = client.get_repository_data("DefectDojo", "django-DefectDojo")

        if repo_data:
            print("✅ Successfully fetched repository data")
            print(f"   Repository: {repo_data.get('nameWithOwner')}")
            print(f"   Description: {repo_data.get('description', 'N/A')[:80]}...")
            print(f"   Stars: {repo_data.get('diskUsage', 0)} KB")
            print(f"   Primary Language: {repo_data.get('primaryLanguage', 'N/A')}")

            commits = repo_data.get('commits', {})
            print(f"   Total Commits: {commits.get('totalCount', 0)}")
            print(f"   Contributors (90d): {commits.get('contributorCount', 0)}")

            file_tree = repo_data.get('fileTree', [])
            print(f"   Files in root: {len(file_tree)}")

            print("\n💡 CHECK LOGS ABOVE for rate limit cost!")
            print("   Look for: 'Rate limit: cost=XX, remaining=XXXX'")
            return True
        else:
            print("❌ FAILED: No data returned")
            return False

    except Exception as e:
        print(f"❌ FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_organization_query():
    """Test 3: Organization batch query (limit to 10 repos for testing)"""
    print("\n" + "="*70)
    print("TEST 3: Organization Batch Query (10 repos)")
    print("="*70)

    try:
        token = getattr(settings, 'DD_GITHUB_TOKEN', os.getenv('DD_GITHUB_TOKEN'))
        org = getattr(settings, 'DD_GITHUB_ORG', os.getenv('DD_GITHUB_ORG'))

        if not token or not org:
            print("❌ SKIP: DD_GITHUB_TOKEN or DD_GITHUB_ORG not configured")
            return False

        client = GitHubGraphQLClient(token)

        # Fetch first 10 repos
        repos = client.get_organization_repositories(org, limit=10)

        if repos:
            print(f"✅ Successfully fetched {len(repos)} repositories")
            for i, repo in enumerate(repos[:5], 1):
                print(f"   {i}. {repo.get('nameWithOwner')} - {repo.get('primaryLanguage', 'N/A')}")

            if len(repos) > 5:
                print(f"   ... and {len(repos) - 5} more")

            print("\n💡 CHECK LOGS ABOVE for rate limit cost PER PAGE!")
            print("   Each page fetches 100 repos (or less if limit set)")
            return True
        else:
            print("❌ FAILED: No repositories returned")
            return False

    except Exception as e:
        print(f"❌ FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_incremental_sync_filter():
    """Test 4: Incremental sync filtering logic"""
    print("\n" + "="*70)
    print("TEST 4: Incremental Sync Filtering")
    print("="*70)

    try:
        token = getattr(settings, 'DD_GITHUB_TOKEN', os.getenv('DD_GITHUB_TOKEN'))
        org = getattr(settings, 'DD_GITHUB_ORG', os.getenv('DD_GITHUB_ORG'))

        if not token or not org:
            print("❌ SKIP: DD_GITHUB_TOKEN or DD_GITHUB_ORG not configured")
            return False

        client = GitHubGraphQLClient(token)

        # Test with updated_since = 7 days ago
        updated_since = timezone.now() - timedelta(days=7)
        print(f"   Filtering for repos updated after: {updated_since}")

        repos = client.get_organization_repositories(
            org,
            updated_since=updated_since,
            limit=10
        )

        print(f"✅ Found {len(repos)} repositories updated in last 7 days")

        if repos:
            for repo in repos[:5]:
                print(f"   - {repo.get('nameWithOwner')} (updated: {repo.get('updatedAt')})")

        return True

    except Exception as e:
        print(f"❌ FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_signal_detection_from_graphql():
    """Test 5: Signal detection from GraphQL data"""
    print("\n" + "="*70)
    print("TEST 5: Signal Detection from GraphQL Data")
    print("="*70)

    try:
        token = getattr(settings, 'DD_GITHUB_TOKEN', os.getenv('DD_GITHUB_TOKEN'))

        if not token:
            print("❌ SKIP: DD_GITHUB_TOKEN not configured")
            return False

        collector = GitHubRepositoryCollector(token, use_graphql=True)
        client = collector.graphql_client

        # Fetch test repo
        repo_data = client.get_repository_data("DefectDojo", "django-DefectDojo")

        if not repo_data:
            print("❌ FAILED: Could not fetch test repository")
            return False

        # Detect signals
        signals = collector._detect_signals_from_graphql(repo_data)

        print(f"✅ Detected {sum(signals.values())}/36 binary signals")

        # Group by category
        deployment_signals = ['has_dockerfile', 'has_kubernetes_config', 'has_ci_cd', 'has_terraform', 'has_deployment_scripts', 'has_environments']
        production_signals = ['has_monitoring', 'has_releases', 'recent_release_90d', 'has_branch_protection', 'has_codeowners']
        development_signals = ['recent_commits_30d', 'recent_commits_90d', 'active_contributors', 'active_prs_30d', 'has_dependabot']

        print("\n   Deployment Signals (Tier 1):")
        for signal in deployment_signals:
            value = signals.get(signal, False)
            icon = "✓" if value else "✗"
            print(f"      [{icon}] {signal}")

        print("\n   Production Signals (Tier 2):")
        for signal in production_signals:
            value = signals.get(signal, False)
            icon = "✓" if value else "✗"
            print(f"      [{icon}] {signal}")

        print("\n   Development Signals (Tier 3):")
        for signal in development_signals:
            value = signals.get(signal, False)
            icon = "✓" if value else "✗"
            print(f"      [{icon}] {signal}")

        return True

    except Exception as e:
        print(f"❌ FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_full_sync_simulation():
    """Test 6: Simulate incremental sync (10 repos)"""
    print("\n" + "="*70)
    print("TEST 6: Incremental Sync Simulation (10 repos)")
    print("="*70)

    try:
        token = getattr(settings, 'DD_GITHUB_TOKEN', os.getenv('DD_GITHUB_TOKEN'))
        org = getattr(settings, 'DD_GITHUB_ORG', os.getenv('DD_GITHUB_ORG'))

        if not token or not org:
            print("❌ SKIP: DD_GITHUB_TOKEN or DD_GITHUB_ORG not configured")
            return False

        # Initialize collector with GraphQL
        collector = GitHubRepositoryCollector(token, org, use_graphql=True)

        print("   Running incremental sync with 10 repo limit...")
        print("   ⚠️  This will CREATE/UPDATE Products in database!")

        # Fetch and process 10 repos
        updated_since = timezone.now() - timedelta(days=30)
        repos_data = collector.graphql_client.get_organization_repositories(
            org,
            updated_since=updated_since,
            limit=10
        )

        print(f"\n   Found {len(repos_data)} repos updated in last 30 days")

        success_count = 0
        error_count = 0

        for repo_data in repos_data:
            try:
                repo_name = repo_data.get('nameWithOwner', 'unknown')
                was_created = collector._sync_repository_from_graphql(repo_data)

                status = "CREATED" if was_created else "UPDATED"
                print(f"   ✅ {status}: {repo_name}")
                success_count += 1

            except Exception as e:
                error_count += 1
                print(f"   ❌ ERROR: {repo_name} - {e}")

        print(f"\n✅ Sync completed: {success_count} success, {error_count} errors")
        return error_count == 0

    except Exception as e:
        print(f"❌ FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("\n" + "="*70)
    print("GitHub GraphQL Migration Test Suite")
    print("="*70)

    tests = [
        ("GraphQL Client Init", test_graphql_client_init),
        ("Single Repo Query Cost", test_single_repo_query_cost),
        ("Organization Query", test_organization_query),
        ("Incremental Sync Filter", test_incremental_sync_filter),
        ("Signal Detection", test_signal_detection_from_graphql),
        ("Full Sync Simulation", test_full_sync_simulation),
    ]

    results = []
    for name, test_func in tests:
        result = test_func()
        results.append((name, result))

    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All tests passed!")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")

    print("\n💡 NEXT STEPS:")
    print("   1. Review rate limit costs in logs above")
    print("   2. Verify signal detection matches REST API")
    print("   3. Run full incremental sync: python manage.py sync_github_repos")
    print("="*70)


if __name__ == "__main__":
    main()
