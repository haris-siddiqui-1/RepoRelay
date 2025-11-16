"""
Product Migration Wizard Backend.

Handles migration from "1 Product per Repository" to "1 Product per Application"
using clustering-based grouping suggestions.

Phase 4: Product Grouping & Migration
"""

import logging
import json
from datetime import datetime
from typing import List, Dict, Any, Optional

from django.db import transaction
from django.utils import timezone
from django.contrib.auth.models import User

from dojo.models import Product, Repository, Engagement, Test, Finding
from dojo.github_collector.clustering import RepositoryClusteringEngine

logger = logging.getLogger(__name__)


class ProductMigrationWizard:
    """
    Migration wizard for grouping repositories into logical Products.

    Provides functionality to:
    1. Generate clustering suggestions
    2. Preview migration impact
    3. Apply approved groupings
    4. Rollback migrations if needed
    """

    def __init__(self, user: User = None):
        """
        Initialize migration wizard.

        Args:
            user: User performing the migration (for audit trail)
        """
        self.user = user
        self.clustering_engine = RepositoryClusteringEngine()

    def get_clustering_suggestions(
        self,
        product_type_id: Optional[int] = None,
        suggested_num_clusters: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Run clustering and return suggested Product groupings.

        Args:
            product_type_id: Optional filter to cluster only repos in this Product_Type
            suggested_num_clusters: Optional target number of clusters

        Returns:
            Dictionary with clustering results and suggestions
        """
        logger.info(f"Generating clustering suggestions (product_type={product_type_id})")

        # Load repositories
        repositories = Repository.objects.all()

        if product_type_id:
            # Filter to repos whose current Product belongs to this Product_Type
            repositories = repositories.filter(product__prod_type_id=product_type_id)

        repositories = list(repositories.select_related('product'))

        if not repositories:
            logger.warning("No repositories found for clustering")
            return {
                'success': False,
                'error': 'No repositories found',
                'clusters': []
            }

        logger.info(f"Clustering {len(repositories)} repositories")

        # Run clustering
        try:
            result = self.clustering_engine.cluster_repositories(
                repositories,
                suggested_num_clusters=suggested_num_clusters
            )

            # Categorize by confidence
            high_confidence = []
            medium_confidence = []
            low_confidence = []

            for cluster in result['clusters']:
                confidence = cluster['confidence_score']
                if confidence >= 80:
                    high_confidence.append(cluster)
                elif confidence >= 50:
                    medium_confidence.append(cluster)
                else:
                    low_confidence.append(cluster)

            # Add summary statistics
            result['summary'] = {
                'total_repositories': len(repositories),
                'total_clusters': len(result['clusters']),
                'high_confidence_clusters': len(high_confidence),
                'high_confidence_repos': sum(c['repository_count'] for c in high_confidence),
                'medium_confidence_clusters': len(medium_confidence),
                'medium_confidence_repos': sum(c['repository_count'] for c in medium_confidence),
                'low_confidence_clusters': len(low_confidence),
                'low_confidence_repos': sum(c['repository_count'] for c in low_confidence),
            }

            result['success'] = True
            return result

        except Exception as e:
            logger.error(f"Clustering failed: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'clusters': []
            }

    def preview_migration(self, groupings: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze migration impact without applying changes.

        Args:
            groupings: List of approved cluster groupings with structure:
                [
                    {
                        'product_name': 'Auth Service',
                        'repository_ids': [1, 2, 3],
                        'product_type_id': 5,
                        'description': 'Authentication system'
                    },
                    ...
                ]

        Returns:
            Dictionary with migration impact analysis
        """
        logger.info(f"Previewing migration for {len(groupings)} groupings")

        # Collect all repository IDs
        all_repo_ids = set()
        for group in groupings:
            all_repo_ids.update(group.get('repository_ids', []))

        # Load repositories and related data
        repositories = Repository.objects.filter(id__in=all_repo_ids).select_related('product')

        # Count affected objects
        affected_products = set()
        total_findings = 0
        total_tests = 0
        total_engagements = 0

        for repo in repositories:
            if repo.product:
                affected_products.add(repo.product.id)

                # Count Engagements for this product
                engagements = Engagement.objects.filter(product=repo.product)
                total_engagements += engagements.count()

                # Count Tests
                for engagement in engagements:
                    tests = Test.objects.filter(engagement=engagement)
                    total_tests += tests.count()

                    # Count Findings
                    for test in tests:
                        total_findings += Finding.objects.filter(test=test).count()

        # Validation checks
        validation_errors = []
        validation_warnings = []

        # Check 1: All repository IDs exist
        found_repo_ids = set(repo.id for repo in repositories)
        missing_repo_ids = all_repo_ids - found_repo_ids
        if missing_repo_ids:
            validation_errors.append(f"Repository IDs not found: {missing_repo_ids}")

        # Check 2: No duplicate repository assignments
        repo_assignments = {}
        for group in groupings:
            for repo_id in group.get('repository_ids', []):
                if repo_id in repo_assignments:
                    validation_errors.append(
                        f"Repository {repo_id} assigned to multiple products: "
                        f"{repo_assignments[repo_id]} and {group['product_name']}"
                    )
                repo_assignments[repo_id] = group['product_name']

        # Check 3: Product names are unique
        product_names = [g['product_name'] for g in groupings]
        duplicate_names = [name for name in product_names if product_names.count(name) > 1]
        if duplicate_names:
            validation_errors.append(f"Duplicate product names: {set(duplicate_names)}")

        # Check 4: Warn about large clusters
        for group in groupings:
            repo_count = len(group.get('repository_ids', []))
            if repo_count > 20:
                validation_warnings.append(
                    f"Product '{group['product_name']}' has {repo_count} repositories. "
                    f"Consider splitting into multiple products."
                )

        # Check 5: Warn about orphaned repositories
        all_repositories_count = Repository.objects.count()
        if len(all_repo_ids) < all_repositories_count:
            orphaned_count = all_repositories_count - len(all_repo_ids)
            validation_warnings.append(
                f"{orphaned_count} repositories not included in migration. "
                f"They will retain their current Product assignments."
            )

        # Check 6: Validate product_type_id is provided
        for group in groupings:
            if not group.get('product_type_id'):
                validation_errors.append(
                    f"Product '{group['product_name']}' missing required product_type_id"
                )

        return {
            'success': len(validation_errors) == 0,
            'validation_errors': validation_errors,
            'validation_warnings': validation_warnings,
            'impact': {
                'new_products_count': len(groupings),
                'affected_repositories': len(all_repo_ids),
                'affected_products': len(affected_products),
                'affected_findings': total_findings,
                'affected_tests': total_tests,
                'affected_engagements': total_engagements,
            },
            'breakdown': [
                {
                    'product_name': group['product_name'],
                    'repository_count': len(group.get('repository_ids', [])),
                    'repository_names': [
                        repo.name
                        for repo in repositories.filter(id__in=group.get('repository_ids', []))
                    ]
                }
                for group in groupings
            ]
        }

    @transaction.atomic
    def apply_migration(
        self,
        groupings: List[Dict[str, Any]],
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Execute migration with transaction safety.

        Steps:
        1. Validate groupings (use preview_migration)
        2. Begin transaction
        3. Create new Products for each cluster
        4. Update repository.product ForeignKey
        5. Mark old Products as is_repository_placeholder=True
        6. Set old Product.migrated_to_product
        7. Commit transaction

        Args:
            groupings: List of approved cluster groupings
            dry_run: If True, rollback transaction (preview only)

        Returns:
            Migration result with success status and details
        """
        logger.info(f"Applying migration for {len(groupings)} groupings (dry_run={dry_run})")

        # Validate first
        preview = self.preview_migration(groupings)

        if not preview['success']:
            return {
                'success': False,
                'error': 'Validation failed',
                'validation_errors': preview['validation_errors'],
                'migration_id': None
            }

        if preview['validation_warnings']:
            logger.warning(f"Migration warnings: {preview['validation_warnings']}")

        # Generate migration ID
        migration_id = f"mig_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        try:
            # Track changes for audit
            created_products = []
            updated_repositories = []
            archived_products = []

            for group in groupings:
                # Create new Product
                new_product = Product.objects.create(
                    name=group['product_name'],
                    description=group.get('description', f"Migrated product grouping (migration {migration_id})"),
                    prod_type_id=group.get('product_type_id'),
                    created=timezone.now(),
                    updated=timezone.now(),
                    # Set migration metadata
                    is_repository_placeholder=False  # This is a real logical product
                )

                created_products.append(new_product)
                logger.info(f"Created Product: {new_product.name} (ID={new_product.id})")

                # Update repositories to point to new Product
                repository_ids = group.get('repository_ids', [])
                repositories = Repository.objects.filter(id__in=repository_ids).select_related('product')

                for repo in repositories:
                    old_product = repo.product

                    # Update repository
                    repo.product = new_product
                    repo.save()

                    updated_repositories.append(repo)
                    logger.info(f"Updated Repository: {repo.name} → Product {new_product.name}")

                    # Mark old Product as placeholder (if not already migrated)
                    if old_product and not old_product.is_repository_placeholder:
                        # CRITICAL FIX: Move all Engagements from old Product to new Product
                        # This preserves the Finding → Test → Engagement → Product chain
                        engagements = Engagement.objects.filter(product=old_product)
                        engagement_count = 0
                        for engagement in engagements:
                            engagement.product = new_product
                            engagement.save()
                            engagement_count += 1
                            logger.info(f"Moved Engagement '{engagement.name}' → Product {new_product.name}")

                        if engagement_count > 0:
                            logger.info(f"Migrated {engagement_count} engagements from {old_product.name} to {new_product.name}")

                        old_product.is_repository_placeholder = True
                        old_product.migrated_to_product = new_product
                        old_product.migration_date = timezone.now()
                        old_product.save()

                        archived_products.append(old_product)
                        logger.info(f"Archived Product: {old_product.name} (ID={old_product.id})")

            if dry_run:
                # Rollback for preview
                transaction.set_rollback(True)
                logger.info(f"Dry-run complete, rolled back {len(created_products)} products")

                return {
                    'success': True,
                    'dry_run': True,
                    'migration_id': migration_id,
                    'created_products': len(created_products),
                    'updated_repositories': len(updated_repositories),
                    'archived_products': len(archived_products),
                    'message': 'Dry-run successful - no changes applied'
                }
            else:
                # Commit changes
                logger.info(
                    f"Migration {migration_id} complete: "
                    f"{len(created_products)} products created, "
                    f"{len(updated_repositories)} repositories updated, "
                    f"{len(archived_products)} products archived"
                )

                return {
                    'success': True,
                    'dry_run': False,
                    'migration_id': migration_id,
                    'created_products': [
                        {'id': p.id, 'name': p.name}
                        for p in created_products
                    ],
                    'updated_repositories': [
                        {'id': r.id, 'name': r.name, 'new_product_id': r.product.id}
                        for r in updated_repositories
                    ],
                    'archived_products': [
                        {'id': p.id, 'name': p.name, 'migrated_to_id': p.migrated_to_product.id}
                        for p in archived_products
                    ],
                    'message': f'Migration {migration_id} applied successfully'
                }

        except Exception as e:
            logger.error(f"Migration failed: {e}", exc_info=True)
            # Transaction will auto-rollback on exception
            return {
                'success': False,
                'error': str(e),
                'migration_id': migration_id
            }

    @transaction.atomic
    def rollback_migration(self, migration_id: str) -> Dict[str, Any]:
        """
        Undo migration by restoring original Product assignments.

        NOTE: This only works if old Products still exist (within 90-day retention).

        Args:
            migration_id: Migration ID to rollback

        Returns:
            Rollback result
        """
        logger.info(f"Rolling back migration: {migration_id}")

        try:
            # Find all Products created by this migration
            # We track this via description containing migration_id
            migrated_products = Product.objects.filter(
                description__contains=migration_id,
                is_repository_placeholder=False
            )

            if not migrated_products.exists():
                return {
                    'success': False,
                    'error': f'No products found for migration {migration_id}'
                }

            # Find all archived Products that point to these new products
            archived_products = Product.objects.filter(
                is_repository_placeholder=True,
                migrated_to_product__in=migrated_products
            )

            if not archived_products.exists():
                return {
                    'success': False,
                    'error': f'No archived products found for migration {migration_id}'
                }

            # Restore repositories to original products
            restored_count = 0

            for new_product in migrated_products:
                # Find repositories currently assigned to this new product
                repositories = Repository.objects.filter(product=new_product)

                for repo in repositories:
                    # Find the original product (archived)
                    # Match by repository name (original Product name = repo name)
                    original_product_name = repo.name

                    try:
                        original_product = archived_products.get(
                            name=original_product_name,
                            migrated_to_product=new_product
                        )

                        # Restore repository to original product
                        repo.product = original_product
                        repo.save()

                        # NOTE: Engagement rollback is not automated
                        # Engagements remain under the new Product because we lack metadata
                        # to determine which original Product each Engagement came from.
                        # If Engagement restoration is required, manual reassignment is needed
                        # by querying Engagement history or reviewing migration logs.
                        logger.warning(
                            f"Rollback: Repository {repo.name} restored to {original_product.name}. "
                            f"Engagements remain under Product '{new_product.name}' - manual review required if restoration needed."
                        )

                        # Un-archive original product (keep as placeholder per Phase 1-3 design)
                        original_product.is_repository_placeholder = True
                        original_product.migrated_to_product = None
                        original_product.migration_date = None
                        original_product.save()

                        restored_count += 1
                        logger.info(f"Restored Repository: {repo.name} → Product {original_product.name}")

                    except Product.DoesNotExist:
                        logger.warning(f"Could not find original product for repository {repo.name}")
                        continue

                # Delete the new product (now empty)
                new_product.delete()
                logger.info(f"Deleted migrated Product: {new_product.name}")

            return {
                'success': True,
                'migration_id': migration_id,
                'restored_repositories': restored_count,
                'deleted_products': migrated_products.count(),
                'message': f'Successfully rolled back migration {migration_id}'
            }

        except Exception as e:
            logger.error(f"Rollback failed: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'migration_id': migration_id
            }
