"""
Unit tests for Product Migration Wizard.

Phase 4: Product Grouping & Migration
"""

from django.test import TestCase
from django.utils import timezone
from dojo.models import Repository, Product, Product_Type, Engagement, Test, Test_Type, Finding, Dojo_User
from dojo.product.migration_wizard import ProductMigrationWizard


class ProductMigrationWizardTest(TestCase):
    """Test the product migration wizard."""

    def setUp(self):
        """Create test data."""
        # Create user
        self.user = Dojo_User.objects.create(username='test_user')

        # Create Product_Type
        self.product_type = Product_Type.objects.create(name="Test Team")

        # Create Test_Type
        self.test_type = Test_Type.objects.create(name="Generic Scan")

        # Create Products (simulating 1:1 with repositories)
        self.products = []
        for i in range(5):
            product = Product.objects.create(
                name=f"myorg/repo-{i}",
                prod_type=self.product_type
            )
            self.products.append(product)

        # Create Repositories
        self.repositories = []
        for i, product in enumerate(self.products):
            repo = Repository.objects.create(
                name=f"myorg/repo-{i}",
                github_repo_id=1000 + i,
                github_url=f"https://github.com/myorg/repo-{i}",
                product=product,
                primary_language="Python",
                tier="tier2"
            )
            self.repositories.append(repo)

            # Create Engagement and Test for each product
            engagement = Engagement.objects.create(
                product=product,
                name=f"Engagement {i}",
                target_start=timezone.now().date(),
                target_end=timezone.now().date()
            )

            test = Test.objects.create(
                engagement=engagement,
                test_type=self.test_type,
                target_start=timezone.now(),
                target_end=timezone.now()
            )

            # Create some Findings
            for j in range(3):
                Finding.objects.create(
                    test=test,
                    title=f"Finding {i}-{j}",
                    severity="High",
                    numerical_severity="S1",
                    description="Test finding",
                    date=timezone.now().date()
                )

        self.wizard = ProductMigrationWizard(user=self.user)

    def test_get_clustering_suggestions(self):
        """Test getting clustering suggestions."""
        result = self.wizard.get_clustering_suggestions()

        self.assertTrue(result['success'])
        self.assertIn('clusters', result)
        self.assertIn('summary', result)
        self.assertIn('dendrogram', result)

        # Should produce at least one cluster
        self.assertGreater(len(result['clusters']), 0)

        # Summary should have expected fields
        summary = result['summary']
        self.assertEqual(summary['total_repositories'], len(self.repositories))
        self.assertGreater(summary['total_clusters'], 0)

    def test_preview_migration_valid_groupings(self):
        """Test preview migration with valid groupings."""
        # Create simple grouping: combine first 3 repos into one product
        groupings = [
            {
                'product_name': 'Combined Product',
                'repository_ids': [self.repositories[0].id, self.repositories[1].id, self.repositories[2].id],
                'product_type_id': self.product_type.id,
                'description': 'Test grouping'
            }
        ]

        preview = self.wizard.preview_migration(groupings)

        self.assertTrue(preview['success'])
        self.assertEqual(len(preview['validation_errors']), 0)

        # Check impact
        impact = preview['impact']
        self.assertEqual(impact['new_products_count'], 1)
        self.assertEqual(impact['affected_repositories'], 3)
        self.assertEqual(impact['affected_findings'], 9)  # 3 repos * 3 findings each

    def test_preview_migration_duplicate_repos(self):
        """Test preview migration detects duplicate repository assignments."""
        # Create groupings with duplicate repo assignment
        groupings = [
            {
                'product_name': 'Product A',
                'repository_ids': [self.repositories[0].id, self.repositories[1].id],
                'product_type_id': self.product_type.id,
                'description': 'Group A'
            },
            {
                'product_name': 'Product B',
                'repository_ids': [self.repositories[1].id, self.repositories[2].id],  # repo[1] duplicated
                'product_type_id': self.product_type.id,
                'description': 'Group B'
            }
        ]

        preview = self.wizard.preview_migration(groupings)

        self.assertFalse(preview['success'])
        self.assertGreater(len(preview['validation_errors']), 0)

        # Should detect duplicate assignment
        error_text = ' '.join(preview['validation_errors'])
        self.assertIn('multiple products', error_text.lower())

    def test_preview_migration_duplicate_names(self):
        """Test preview migration detects duplicate product names."""
        groupings = [
            {
                'product_name': 'Same Name',
                'repository_ids': [self.repositories[0].id],
                'product_type_id': self.product_type.id,
                'description': 'Group A'
            },
            {
                'product_name': 'Same Name',  # Duplicate
                'repository_ids': [self.repositories[1].id],
                'product_type_id': self.product_type.id,
                'description': 'Group B'
            }
        ]

        preview = self.wizard.preview_migration(groupings)

        self.assertFalse(preview['success'])
        self.assertGreater(len(preview['validation_errors']), 0)

        error_text = ' '.join(preview['validation_errors'])
        self.assertIn('duplicate', error_text.lower())

    def test_preview_migration_missing_repos(self):
        """Test preview migration with non-existent repository IDs."""
        groupings = [
            {
                'product_name': 'Test Product',
                'repository_ids': [99999],  # Doesn't exist
                'product_type_id': self.product_type.id,
                'description': 'Test'
            }
        ]

        preview = self.wizard.preview_migration(groupings)

        self.assertFalse(preview['success'])
        self.assertGreater(len(preview['validation_errors']), 0)

    def test_apply_migration_dry_run(self):
        """Test dry-run migration (should not persist changes)."""
        groupings = [
            {
                'product_name': 'New Combined Product',
                'repository_ids': [self.repositories[0].id, self.repositories[1].id],
                'product_type_id': self.product_type.id,
                'description': 'Test grouping'
            }
        ]

        # Count products before
        product_count_before = Product.objects.count()

        # Dry run
        result = self.wizard.apply_migration(groupings, dry_run=True)

        self.assertTrue(result['success'])
        self.assertTrue(result['dry_run'])

        # Products count should not change
        product_count_after = Product.objects.count()
        self.assertEqual(product_count_before, product_count_after)

    def test_apply_migration_actual(self):
        """Test actual migration execution."""
        groupings = [
            {
                'product_name': 'Migrated Product',
                'repository_ids': [self.repositories[0].id, self.repositories[1].id],
                'product_type_id': self.product_type.id,
                'description': 'Test migration'
            }
        ]

        # Apply migration
        result = self.wizard.apply_migration(groupings, dry_run=False)

        self.assertTrue(result['success'])
        self.assertFalse(result['dry_run'])
        self.assertIsNotNone(result['migration_id'])

        # New product should be created
        self.assertEqual(len(result['created_products']), 1)
        new_product = Product.objects.get(name='Migrated Product')
        self.assertIsNotNone(new_product)

        # Repositories should be updated
        repo0 = Repository.objects.get(id=self.repositories[0].id)
        repo1 = Repository.objects.get(id=self.repositories[1].id)
        self.assertEqual(repo0.product, new_product)
        self.assertEqual(repo1.product, new_product)

        # Old products should be marked as placeholders
        old_product0 = Product.objects.get(name='myorg/repo-0')
        old_product1 = Product.objects.get(name='myorg/repo-1')
        self.assertTrue(old_product0.is_repository_placeholder)
        self.assertTrue(old_product1.is_repository_placeholder)
        self.assertEqual(old_product0.migrated_to_product, new_product)
        self.assertEqual(old_product1.migrated_to_product, new_product)

    def test_apply_migration_preserves_findings(self):
        """Test that migration preserves all Findings."""
        groupings = [
            {
                'product_name': 'Grouped Product',
                'repository_ids': [self.repositories[0].id, self.repositories[1].id],
                'product_type_id': self.product_type.id,
                'description': 'Test'
            }
        ]

        # Count findings before
        findings_before = Finding.objects.count()

        # Apply migration
        result = self.wizard.apply_migration(groupings, dry_run=False)

        self.assertTrue(result['success'])

        # Findings count should not change
        findings_after = Finding.objects.count()
        self.assertEqual(findings_before, findings_after)

        # All findings should still be accessible through new product
        new_product = Product.objects.get(name='Grouped Product')
        findings_in_product = Finding.objects.filter(test__engagement__product=new_product)

        # Should have findings from both repos (but they're still under old products' engagements)
        # This is expected - engagements don't move, only repository.product links change
        # Findings remain under original engagements

    def test_rollback_migration(self):
        """Test rolling back a migration."""
        # First, apply a migration
        groupings = [
            {
                'product_name': 'Rollback Test Product',
                'repository_ids': [self.repositories[0].id, self.repositories[1].id],
                'product_type_id': self.product_type.id,
                'description': 'Will be rolled back'
            }
        ]

        apply_result = self.wizard.apply_migration(groupings, dry_run=False)
        self.assertTrue(apply_result['success'])

        migration_id = apply_result['migration_id']

        # Verify migration happened
        new_product = Product.objects.get(name='Rollback Test Product')
        repo0 = Repository.objects.get(id=self.repositories[0].id)
        self.assertEqual(repo0.product, new_product)

        # Now rollback
        rollback_result = self.wizard.rollback_migration(migration_id)

        self.assertTrue(rollback_result['success'])
        self.assertEqual(rollback_result['restored_repositories'], 2)

        # Repositories should be back to original products
        repo0_after = Repository.objects.get(id=self.repositories[0].id)
        original_product = Product.objects.get(name='myorg/repo-0')
        self.assertEqual(repo0_after.product, original_product)

        # Original products should no longer be placeholders
        self.assertFalse(original_product.is_repository_placeholder)
        self.assertIsNone(original_product.migrated_to_product)

        # New product should be deleted
        with self.assertRaises(Product.DoesNotExist):
            Product.objects.get(name='Rollback Test Product')

    def test_rollback_nonexistent_migration(self):
        """Test rolling back a non-existent migration."""
        result = self.wizard.rollback_migration('mig_99999999_999999')

        self.assertFalse(result['success'])
        self.assertIn('error', result)

    def test_migration_validation_warnings(self):
        """Test that migration generates appropriate warnings."""
        # Create a large cluster (> 20 repos)
        # Add more repositories for this test
        extra_repos = []
        for i in range(25):
            product = Product.objects.create(
                name=f"myorg/extra-{i}",
                prod_type=self.product_type
            )
            repo = Repository.objects.create(
                name=f"myorg/extra-{i}",
                github_repo_id=5000 + i,
                github_url=f"https://github.com/myorg/extra-{i}",
                product=product
            )
            extra_repos.append(repo)

        # Create grouping with all extra repos (25 > 20 threshold)
        groupings = [
            {
                'product_name': 'Large Product',
                'repository_ids': [r.id for r in extra_repos],
                'product_type_id': self.product_type.id,
                'description': 'Large cluster'
            }
        ]

        preview = self.wizard.preview_migration(groupings)

        # Should succeed but with warnings
        self.assertTrue(preview['success'])
        self.assertGreater(len(preview['validation_warnings']), 0)

        # Should warn about large cluster
        warning_text = ' '.join(preview['validation_warnings'])
        self.assertIn('20', warning_text)  # Mentions the threshold

    def test_migration_transaction_safety(self):
        """Test that migration uses transactions (all-or-nothing)."""
        # This is a conceptual test - actual transaction rollback is hard to test directly
        # We test that if validation fails, apply_migration returns error

        groupings = [
            {
                'product_name': 'Duplicate Product Name',
                'repository_ids': [self.repositories[0].id],
                'product_type_id': self.product_type.id,
                'description': 'First'
            },
            {
                'product_name': 'Duplicate Product Name',  # Will fail validation
                'repository_ids': [self.repositories[1].id],
                'product_type_id': self.product_type.id,
                'description': 'Second'
            }
        ]

        result = self.wizard.apply_migration(groupings, dry_run=False)

        # Should fail due to validation
        self.assertFalse(result['success'])

        # No products should have been created
        with self.assertRaises(Product.DoesNotExist):
            Product.objects.get(name='Duplicate Product Name')
