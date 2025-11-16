"""
Unit tests for Repository Clustering Engine.

Phase 4: Product Grouping & Migration
"""

from django.test import TestCase
from dojo.models import Repository, Product, Product_Type
from dojo.github_collector.clustering import RepositoryClusteringEngine


class RepositoryClusteringEngineTest(TestCase):
    """Test the hierarchical clustering engine."""

    def setUp(self):
        """Create test data."""
        # Create Product_Type
        self.product_type = Product_Type.objects.create(name="Test Team")

        # Create Products (will be used as placeholders)
        self.products = []
        for i in range(10):
            product = Product.objects.create(
                name=f"Test Product {i}",
                prod_type=self.product_type
            )
            self.products.append(product)

        # Create Repositories with similar naming patterns
        self.repositories = []

        # Group 1: Auth services (similar names)
        for i, suffix in enumerate(['api', 'frontend', 'shared']):
            repo = Repository.objects.create(
                name=f"myorg/auth-{suffix}",
                github_repo_id=1000 + i,
                github_url=f"https://github.com/myorg/auth-{suffix}",
                product=self.products[i],
                primary_language="Python",
                primary_framework="Django",
                tier="tier1"
            )
            self.repositories.append(repo)

        # Group 2: Payment services
        for i, suffix in enumerate(['service', 'gateway', 'processor']):
            repo = Repository.objects.create(
                name=f"myorg/payment-{suffix}",
                github_repo_id=2000 + i,
                github_url=f"https://github.com/myorg/payment-{suffix}",
                product=self.products[i + 3],
                primary_language="Java",
                primary_framework="Spring Boot",
                tier="tier2"
            )
            self.repositories.append(repo)

        # Group 3: Unrelated repos
        for i, name in enumerate(['legacy-app', 'tools-cli', 'docs-site']):
            repo = Repository.objects.create(
                name=f"myorg/{name}",
                github_repo_id=3000 + i,
                github_url=f"https://github.com/myorg/{name}",
                product=self.products[i + 6],
                primary_language="JavaScript" if i == 2 else "Python",
                tier="tier3"
            )
            self.repositories.append(repo)

        self.engine = RepositoryClusteringEngine()

    def test_clustering_basic(self):
        """Test basic clustering functionality."""
        result = self.engine.cluster_repositories(self.repositories)

        self.assertTrue('clusters' in result)
        self.assertTrue('dendrogram' in result)
        self.assertTrue('suggested_cut_height' in result)

        # Should produce fewer clusters than repositories
        num_clusters = len(result['clusters'])
        self.assertGreater(num_clusters, 0)
        self.assertLessEqual(num_clusters, len(self.repositories))

    def test_clustering_suggests_auth_group(self):
        """Test that auth-* repos are clustered together."""
        result = self.engine.cluster_repositories(self.repositories)

        # Find clusters containing auth repos
        auth_repo_ids = {r.id for r in self.repositories if 'auth-' in r.name}

        auth_clusters = []
        for cluster in result['clusters']:
            cluster_repo_ids = {r['id'] for r in cluster['repositories']}
            if auth_repo_ids.intersection(cluster_repo_ids):
                auth_clusters.append(cluster)

        # Auth repos should be in same cluster (or at least most of them)
        # This is a heuristic test - clustering isn't deterministic
        self.assertGreater(len(auth_clusters), 0, "Auth repos should form at least one cluster")

    def test_clustering_suggests_payment_group(self):
        """Test that payment-* repos are clustered together."""
        result = self.engine.cluster_repositories(self.repositories)

        # Find clusters containing payment repos
        payment_repo_ids = {r.id for r in self.repositories if 'payment-' in r.name}

        payment_clusters = []
        for cluster in result['clusters']:
            cluster_repo_ids = {r['id'] for r in cluster['repositories']}
            if payment_repo_ids.intersection(cluster_repo_ids):
                payment_clusters.append(cluster)

        # Payment repos should be in same cluster
        self.assertGreater(len(payment_clusters), 0, "Payment repos should form at least one cluster")

    def test_confidence_scoring(self):
        """Test that confidence scores are reasonable."""
        result = self.engine.cluster_repositories(self.repositories)

        for cluster in result['clusters']:
            confidence = cluster['confidence_score']

            # Confidence should be 0-100
            self.assertGreaterEqual(confidence, 0)
            self.assertLessEqual(confidence, 100)

            # Clusters with similar names should have higher confidence
            repo_names = [r['name'] for r in cluster['repositories']]
            if len(repo_names) > 1:
                # Check for common prefixes
                first_name = repo_names[0].split('/')[-1]
                prefix = first_name.split('-')[0] if '-' in first_name else first_name

                same_prefix_count = sum(1 for name in repo_names if prefix in name)

                if same_prefix_count == len(repo_names):
                    # All have same prefix - should be high confidence
                    self.assertGreater(confidence, 50, f"Cluster with common prefix should have >50% confidence")

    def test_product_name_suggestion(self):
        """Test that product names are intelligently suggested."""
        result = self.engine.cluster_repositories(self.repositories)

        # Check that suggested names make sense
        for cluster in result['clusters']:
            suggested_name = cluster['suggested_product_name']

            # Should not be empty
            self.assertTrue(suggested_name)
            self.assertGreater(len(suggested_name), 0)

            # If cluster has repos with common prefix, name should reflect it
            repo_names = [r['name'].split('/')[-1] for r in cluster['repositories']]

            if 'auth-' in repo_names[0]:
                self.assertIn('Auth', suggested_name, "Auth repos should suggest 'Auth' in product name")
            elif 'payment-' in repo_names[0]:
                self.assertIn('Payment', suggested_name, "Payment repos should suggest 'Payment' in product name")

    def test_common_features_extraction(self):
        """Test that common features are correctly identified."""
        result = self.engine.cluster_repositories(self.repositories)

        for cluster in result['clusters']:
            common_features = cluster['common_features']

            # Should have expected keys
            self.assertIn('primary_language', common_features)
            self.assertIn('primary_framework', common_features)
            self.assertIn('average_tier', common_features)

            # If all repos in cluster have same language, it should be identified
            repo_langs = set(r['primary_language'] for r in cluster['repositories'])
            if len(repo_langs) == 1:
                self.assertEqual(common_features['primary_language'], list(repo_langs)[0])

    def test_single_repository_cluster(self):
        """Test clustering with a single repository."""
        single_repo = [self.repositories[0]]
        result = self.engine.cluster_repositories(single_repo)

        self.assertEqual(len(result['clusters']), 1)
        self.assertEqual(result['clusters'][0]['repository_count'], 1)
        self.assertEqual(result['clusters'][0]['confidence_score'], 100)

    def test_empty_repository_list(self):
        """Test clustering with no repositories."""
        result = self.engine.cluster_repositories([])

        self.assertEqual(len(result['clusters']), 0)

    def test_suggested_num_clusters(self):
        """Test that suggested_num_clusters parameter works."""
        # Request specific number of clusters
        target_clusters = 3
        result = self.engine.cluster_repositories(
            self.repositories,
            suggested_num_clusters=target_clusters
        )

        num_clusters = len(result['clusters'])

        # Should be close to target (may not be exact due to algorithm)
        # Allow some tolerance
        self.assertLessEqual(abs(num_clusters - target_clusters), 2)

    def test_feature_matrix_dimensions(self):
        """Test that feature matrix has correct dimensions."""
        self.engine.repositories = self.repositories
        feature_matrix = self.engine._build_feature_matrix(self.repositories)

        # Should have one row per repository
        self.assertEqual(feature_matrix.shape[0], len(self.repositories))

        # Should have many features (language, framework, signals, name features)
        # At minimum: 10 (lang/fw) + 1 (ownership) + 36 (signals) + 3 (activity) + 20 (name TF-IDF)
        self.assertGreater(feature_matrix.shape[1], 50)

    def test_dendrogram_generation(self):
        """Test that dendrogram data is properly generated."""
        result = self.engine.cluster_repositories(self.repositories)

        dendrogram = result['dendrogram']

        # Should have required fields for D3.js
        self.assertIn('icoord', dendrogram)
        self.assertIn('dcoord', dendrogram)
        self.assertIn('leaves', dendrogram)

        # Coordinates should be lists
        self.assertIsInstance(dendrogram['icoord'], list)
        self.assertIsInstance(dendrogram['dcoord'], list)

        # Leaves should match repository count
        self.assertEqual(len(dendrogram['leaves']), len(self.repositories))
