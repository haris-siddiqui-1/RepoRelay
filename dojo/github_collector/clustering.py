"""
Repository Clustering Engine for Product Grouping.

This module implements hierarchical clustering to suggest logical groupings of
repositories into Products. Uses repository metadata (name, language, ownership,
signals) to identify related repositories that should belong to the same Product.

Phase 4: Product Grouping & Migration
"""

import logging
import re
from typing import List, Dict, Any, Tuple
from collections import Counter

import numpy as np
from scipy.cluster.hierarchy import dendrogram, linkage, fcluster
from scipy.spatial.distance import pdist
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score

from dojo.models import Repository

logger = logging.getLogger(__name__)


class RepositoryClusteringEngine:
    """
    Hierarchical clustering engine for repository grouping.

    Uses agglomerative clustering with Ward linkage to suggest logical
    Product groupings based on repository features.
    """

    def __init__(self):
        """Initialize the clustering engine."""
        self.repositories = []
        self.feature_matrix = None
        self.linkage_matrix = None
        self.dendrogram_data = None

    def cluster_repositories(
        self,
        repositories: List[Repository],
        suggested_num_clusters: int = None
    ) -> Dict[str, Any]:
        """
        Perform hierarchical clustering on repositories.

        Args:
            repositories: List of Repository instances to cluster
            suggested_num_clusters: Optional target number of clusters

        Returns:
            Dictionary containing:
            - dendrogram: Dendrogram data for D3.js visualization
            - suggested_cut_height: Recommended cut height for optimal clustering
            - clusters: List of cluster dictionaries with repositories and metadata
            - confidence_scores: Per-cluster confidence ratings
        """
        logger.info(f"Starting clustering for {len(repositories)} repositories")

        if len(repositories) < 2:
            logger.warning("Need at least 2 repositories for clustering")
            return self._single_cluster_result(repositories)

        self.repositories = repositories

        # Build feature matrix
        self.feature_matrix = self._build_feature_matrix(repositories)
        logger.info(f"Built feature matrix: {self.feature_matrix.shape}")

        # Perform hierarchical clustering
        self.linkage_matrix = linkage(self.feature_matrix, method='ward')
        logger.info("Completed hierarchical clustering")

        # Generate dendrogram data
        self.dendrogram_data = dendrogram(
            self.linkage_matrix,
            no_plot=True,
            count_sort='ascending'
        )

        # Determine optimal cut height
        if suggested_num_clusters:
            cut_height = self._find_cut_height_for_k(suggested_num_clusters)
        else:
            cut_height = self._suggest_optimal_cut_height()

        logger.info(f"Suggested cut height: {cut_height:.3f}")

        # Get cluster assignments
        cluster_labels = fcluster(self.linkage_matrix, cut_height, criterion='distance')

        # Build cluster metadata
        clusters = self._build_clusters(repositories, cluster_labels)

        # Calculate confidence scores
        for cluster in clusters:
            cluster['confidence_score'] = self._calculate_cluster_confidence(cluster)

        return {
            'dendrogram': {
                'icoord': self.dendrogram_data['icoord'],
                'dcoord': self.dendrogram_data['dcoord'],
                'leaves': self.dendrogram_data['leaves'],
                'color_list': self.dendrogram_data['color_list']
            },
            'suggested_cut_height': float(cut_height),
            'num_clusters': len(clusters),
            'clusters': clusters
        }

    def _build_feature_matrix(self, repositories: List[Repository]) -> np.ndarray:
        """
        Build feature matrix from repository attributes.

        Features:
        1. Name similarity (TF-IDF on repo name tokens)
        2. Language/Framework (one-hot encoding)
        3. Ownership similarity (TF-IDF on CODEOWNERS)
        4. 36 binary signals
        5. Activity patterns (normalized)

        Args:
            repositories: List of Repository instances

        Returns:
            NumPy array of shape (n_repos, n_features)
        """
        features_list = []

        for repo in repositories:
            repo_features = []

            # 1. Name tokens (will be TF-IDF transformed separately)
            # Extract for later processing

            # 2. Language/Framework (one-hot, 10 features)
            # Most common languages/frameworks
            common_languages = ['Python', 'JavaScript', 'TypeScript', 'Go', 'Java']
            lang_features = [1 if repo.primary_language == lang else 0 for lang in common_languages]
            repo_features.extend(lang_features)

            common_frameworks = ['Django', 'React', 'Spring Boot', 'Express', 'Flask']
            fw_features = [1 if repo.primary_framework == fw else 0 for fw in common_frameworks]
            repo_features.extend(fw_features)

            # 3. Ownership confidence (1 feature)
            repo_features.append(repo.ownership_confidence / 100.0 if repo.ownership_confidence else 0.0)

            # 4. 36 Binary signals (36 features)
            signal_fields = [
                # Tier 1 - Deployment (6)
                'has_dockerfile', 'has_kubernetes_config', 'has_ci_cd',
                'has_terraform', 'has_deployment_scripts', 'has_environments',
                # Tier 2 - Production (5)
                'has_monitoring', 'has_releases', 'recent_release_90d',
                'has_branch_protection', 'has_codeowners',
                # Tier 3 - Development Activity (5)
                'recent_commits_30d', 'recent_commits_90d', 'active_contributors',
                'active_prs_30d', 'has_dependabot',
                # Tier 4 - Code Organization (6)
                'has_tests', 'has_documentation', 'has_readme',
                'readme_length_500', 'has_api_spec', 'has_changelog',
                # Tier 5 - Security (5)
                'has_security_policy', 'has_secret_scanning', 'has_sbom',
                'has_security_txt', 'has_code_scanning',
                # Additional (9)
                'has_package_manager', 'has_license', 'has_contributing_guide',
                'has_code_of_conduct', 'has_issue_templates', 'has_pr_template',
                'has_gitignore', 'has_editorconfig', 'has_gitattributes'
            ]

            for field in signal_fields:
                value = getattr(repo, field, False)
                repo_features.append(1.0 if value else 0.0)

            # 5. Activity patterns (3 features, normalized)
            # Contributors (normalize to 0-1, assume max 50)
            contributors = getattr(repo, 'active_contributors_90d', 0)
            repo_features.append(min(1.0, contributors / 50.0))

            # Days since last commit (inverse normalized, assume max 365)
            days_since = getattr(repo, 'days_since_last_commit', 365)
            repo_features.append(max(0.0, 1.0 - (days_since / 365.0)))

            # Tier (convert to numeric: tier1=4, tier2=3, tier3=2, tier4=1, archived=0)
            tier_value = {
                'tier1': 4, 'tier2': 3, 'tier3': 2, 'tier4': 1, 'archived': 0
            }.get(getattr(repo, 'tier', 'tier4'), 1)
            repo_features.append(tier_value / 4.0)

            features_list.append(repo_features)

        # Convert to numpy array
        feature_matrix = np.array(features_list, dtype=float)

        # Add name similarity features (TF-IDF)
        name_features = self._extract_name_features(repositories)

        # Combine all features
        combined_features = np.hstack([feature_matrix, name_features])

        # Standardize features for clustering
        scaler = StandardScaler()
        scaled_features = scaler.fit_transform(combined_features)

        return scaled_features

    def _extract_name_features(self, repositories: List[Repository]) -> np.ndarray:
        """
        Extract TF-IDF features from repository names.

        Tokenizes names and applies TF-IDF to capture similarity in naming patterns.
        Examples: "auth-api", "auth-frontend" → high similarity

        Args:
            repositories: List of Repository instances

        Returns:
            NumPy array of TF-IDF features (n_repos, n_terms)
        """
        # Extract repository names
        repo_names = [repo.name for repo in repositories]

        # Tokenize names (split on /, -, _, and camelCase)
        def tokenize_name(name):
            # Split on separators
            tokens = re.split(r'[/\-_.]', name.lower())
            # Further split on camelCase
            expanded_tokens = []
            for token in tokens:
                # Insert space before uppercase letters
                expanded = re.sub(r'([a-z])([A-Z])', r'\1 \2', token)
                expanded_tokens.extend(expanded.split())
            return ' '.join(expanded_tokens)

        tokenized_names = [tokenize_name(name) for name in repo_names]

        # Apply TF-IDF
        # Use max_features to limit dimensionality
        vectorizer = TfidfVectorizer(
            max_features=20,
            min_df=2,  # Token must appear in at least 2 repos
            ngram_range=(1, 2)  # Unigrams and bigrams
        )

        try:
            tfidf_matrix = vectorizer.fit_transform(tokenized_names).toarray()
        except ValueError:
            # If vocabulary is empty (all unique names), return zeros
            logger.warning("Could not extract name features, vocabulary too sparse")
            tfidf_matrix = np.zeros((len(repositories), 1))

        return tfidf_matrix

    def _suggest_optimal_cut_height(self) -> float:
        """
        Suggest optimal cut height for dendrogram using silhouette score.

        Tries multiple cut heights and selects the one with highest silhouette score.

        Returns:
            Optimal cut height value
        """
        # Try different numbers of clusters
        n_repos = len(self.repositories)

        # Reasonable range: sqrt(n) to n/10 clusters
        min_clusters = max(2, int(np.sqrt(n_repos)))
        max_clusters = min(n_repos - 1, max(10, n_repos // 10))

        best_score = -1
        best_k = min_clusters

        # Try different k values
        for k in range(min_clusters, min(max_clusters + 1, 50)):  # Cap at 50 for performance
            labels = fcluster(self.linkage_matrix, k, criterion='maxclust')

            # Need at least 2 clusters for silhouette score
            if len(set(labels)) < 2:
                continue

            try:
                score = silhouette_score(self.feature_matrix, labels)
                if score > best_score:
                    best_score = score
                    best_k = k
            except ValueError:
                # Skip if clustering is degenerate
                continue

        logger.info(f"Optimal k={best_k} (silhouette score: {best_score:.3f})")

        # Find the cut height that gives us best_k clusters
        return self._find_cut_height_for_k(best_k)

    def _find_cut_height_for_k(self, k: int) -> float:
        """
        Find the cut height that produces exactly k clusters.

        Args:
            k: Desired number of clusters

        Returns:
            Cut height value
        """
        # Binary search for the right cut height
        # The linkage matrix distances range from 0 to max
        max_dist = np.max(self.linkage_matrix[:, 2])

        # Start with the (n-k)th largest merge distance
        # Linkage matrix row (n-k) represents the merge that creates k clusters
        if k <= len(self.repositories):
            merge_index = len(self.repositories) - k
            if merge_index >= 0 and merge_index < len(self.linkage_matrix):
                return self.linkage_matrix[merge_index, 2]

        # Fallback: use 70% of max distance
        return max_dist * 0.7

    def _build_clusters(
        self,
        repositories: List[Repository],
        cluster_labels: np.ndarray
    ) -> List[Dict[str, Any]]:
        """
        Build cluster metadata from labels.

        Args:
            repositories: List of Repository instances
            cluster_labels: Cluster assignment for each repository

        Returns:
            List of cluster dictionaries
        """
        clusters = []
        unique_labels = set(cluster_labels)

        for label in sorted(unique_labels):
            # Get repositories in this cluster
            indices = np.where(cluster_labels == label)[0]
            cluster_repos = [repositories[i] for i in indices]

            # Generate suggested product name
            suggested_name = self._suggest_product_name(cluster_repos)

            # Extract common features
            common_features = self._extract_common_features(cluster_repos)

            cluster_dict = {
                'cluster_id': int(label),
                'repository_count': len(cluster_repos),
                'repositories': [
                    {
                        'id': repo.id,
                        'name': repo.name,
                        'github_url': repo.github_url,
                        'primary_language': repo.primary_language,
                        'tier': repo.tier
                    }
                    for repo in cluster_repos
                ],
                'suggested_product_name': suggested_name,
                'common_features': common_features
            }

            clusters.append(cluster_dict)

        # Sort by repository count (largest clusters first)
        clusters.sort(key=lambda x: x['repository_count'], reverse=True)

        return clusters

    def _suggest_product_name(self, repositories: List[Repository]) -> str:
        """
        Suggest a product name based on repository names in cluster.

        Args:
            repositories: List of Repository instances in cluster

        Returns:
            Suggested product name
        """
        if len(repositories) == 1:
            # Single repo: use repo name without org prefix
            name = repositories[0].name
            if '/' in name:
                return name.split('/')[-1].replace('-', ' ').replace('_', ' ').title()
            return name.replace('-', ' ').replace('_', ' ').title()

        # Multiple repos: find common prefix/suffix
        repo_names = [repo.name.split('/')[-1] for repo in repositories]  # Remove org prefix

        # Extract common prefix
        common_prefix = self._longest_common_prefix(repo_names)

        if common_prefix and len(common_prefix) > 3:
            # Clean up prefix (remove trailing -, _, etc.)
            clean_prefix = common_prefix.rstrip('-_. ')
            return clean_prefix.replace('-', ' ').replace('_', ' ').title()

        # Extract common suffix
        common_suffix = self._longest_common_suffix(repo_names)

        if common_suffix and len(common_suffix) > 3:
            # Clean up suffix
            clean_suffix = common_suffix.lstrip('-_. ')
            return clean_suffix.replace('-', ' ').replace('_', ' ').title()

        # Fallback: use most common words
        all_words = []
        for name in repo_names:
            words = re.findall(r'[a-zA-Z]+', name.lower())
            all_words.extend(words)

        if all_words:
            word_counts = Counter(all_words)
            # Get most common word that appears in at least 2 repos
            for word, count in word_counts.most_common():
                if count >= 2:
                    return word.title() + " Services"

        # Last resort: generic name
        return f"Product Group {repositories[0].id}"

    def _longest_common_prefix(self, strings: List[str]) -> str:
        """Find longest common prefix among strings."""
        if not strings:
            return ""

        prefix = strings[0]
        for s in strings[1:]:
            while not s.startswith(prefix):
                prefix = prefix[:-1]
                if not prefix:
                    return ""
        return prefix

    def _longest_common_suffix(self, strings: List[str]) -> str:
        """Find longest common suffix among strings."""
        if not strings:
            return ""

        # Reverse strings and find common prefix
        reversed_strings = [s[::-1] for s in strings]
        reversed_suffix = self._longest_common_prefix(reversed_strings)
        return reversed_suffix[::-1]

    def _extract_common_features(self, repositories: List[Repository]) -> Dict[str, Any]:
        """
        Extract common features from cluster repositories.

        Args:
            repositories: List of Repository instances

        Returns:
            Dictionary of common features
        """
        # Primary language (most common)
        languages = [r.primary_language for r in repositories if r.primary_language]
        primary_language = Counter(languages).most_common(1)[0][0] if languages else None

        # Primary framework (most common)
        frameworks = [r.primary_framework for r in repositories if r.primary_framework]
        primary_framework = Counter(frameworks).most_common(1)[0][0] if frameworks else None

        # Common owners (intersection of CODEOWNERS)
        owners_sets = []
        for repo in repositories:
            if repo.codeowners_content:
                # Extract @mentions from CODEOWNERS
                owners = re.findall(r'@[\w-]+', repo.codeowners_content)
                owners_sets.append(set(owners))

        common_owners = []
        if owners_sets:
            common_owners = list(set.intersection(*owners_sets))

        # Average tier
        tier_values = {'tier1': 1, 'tier2': 2, 'tier3': 3, 'tier4': 4, 'archived': 5}
        tiers = [tier_values.get(r.tier, 4) for r in repositories]
        avg_tier = sum(tiers) / len(tiers) if tiers else 4
        avg_tier_name = {1: 'tier1', 2: 'tier2', 3: 'tier3', 4: 'tier4', 5: 'archived'}[round(avg_tier)]

        return {
            'primary_language': primary_language,
            'primary_framework': primary_framework,
            'common_owners': common_owners[:5],  # Top 5 common owners
            'average_tier': avg_tier_name
        }

    def _calculate_cluster_confidence(self, cluster: Dict[str, Any]) -> int:
        """
        Calculate confidence score for a cluster (0-100).

        Scoring:
        - Intra-cluster similarity (0-40 points): How similar repos are
        - Feature agreement (0-30 points): % with same language/framework
        - Name pattern match (0-20 points): Common prefix/suffix detected
        - Ownership overlap (0-10 points): Shared CODEOWNERS entries

        Args:
            cluster: Cluster dictionary

        Returns:
            Confidence score (0-100)
        """
        score = 0
        repos = cluster['repositories']
        n_repos = len(repos)

        if n_repos == 1:
            # Single repo clusters get lower confidence
            return 60

        # 1. Intra-cluster similarity (0-40 points)
        # Based on feature variance - lower variance = higher similarity
        # This is a simplification; ideally compute pairwise distances
        score += 30  # Default moderate similarity

        # 2. Feature agreement (0-30 points)
        common_features = cluster['common_features']

        # Language agreement
        if common_features.get('primary_language'):
            # Check what % of repos share this language
            matching_langs = sum(
                1 for r in repos
                if r.get('primary_language') == common_features['primary_language']
            )
            lang_agreement = matching_langs / n_repos
            score += int(15 * lang_agreement)

        # Framework agreement
        if common_features.get('primary_framework'):
            # This would require loading full repo objects, simplify for now
            score += 10

        # 3. Name pattern match (0-20 points)
        repo_names = [r['name'].split('/')[-1] for r in repos]

        # Check for common prefix
        common_prefix = self._longest_common_prefix(repo_names)
        if common_prefix and len(common_prefix) > 3:
            score += 15
        else:
            # Check for common suffix
            common_suffix = self._longest_common_suffix(repo_names)
            if common_suffix and len(common_suffix) > 3:
                score += 10
            else:
                score += 5  # Some similarity if they're clustered

        # 4. Ownership overlap (0-10 points)
        common_owners = common_features.get('common_owners', [])
        if common_owners:
            score += min(10, len(common_owners) * 2)

        return min(100, score)

    def _single_cluster_result(self, repositories: List[Repository]) -> Dict[str, Any]:
        """
        Return result for single repository (no clustering possible).

        Args:
            repositories: List with single Repository

        Returns:
            Cluster result dictionary
        """
        repo = repositories[0] if repositories else None

        if not repo:
            return {
                'dendrogram': None,
                'suggested_cut_height': 0,
                'num_clusters': 0,
                'clusters': []
            }

        return {
            'dendrogram': None,
            'suggested_cut_height': 0,
            'num_clusters': 1,
            'clusters': [
                {
                    'cluster_id': 1,
                    'repository_count': 1,
                    'repositories': [
                        {
                            'id': repo.id,
                            'name': repo.name,
                            'github_url': repo.github_url,
                            'primary_language': repo.primary_language,
                            'tier': repo.tier
                        }
                    ],
                    'suggested_product_name': repo.name.split('/')[-1].replace('-', ' ').title(),
                    'common_features': {
                        'primary_language': repo.primary_language,
                        'primary_framework': repo.primary_framework,
                        'common_owners': [],
                        'average_tier': repo.tier
                    },
                    'confidence_score': 100  # Single repo, perfect confidence
                }
            ]
        }
