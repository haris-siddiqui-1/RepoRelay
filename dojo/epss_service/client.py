"""
EPSS API Client

Interfaces with FIRST.org EPSS API to fetch exploit prediction scores for CVEs.

API Documentation: https://www.first.org/epss/api
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class EPSSClient:
    """
    Client for FIRST.org EPSS API.

    The EPSS (Exploit Prediction Scoring System) provides probability scores
    (0.0-1.0) indicating likelihood of exploitation in the next 30 days.
    """

    DEFAULT_API_URL = 'https://api.first.org/data/v1/epss'
    MAX_CVES_PER_REQUEST = 100  # API limit

    def __init__(self, api_url: Optional[str] = None):
        """
        Initialize EPSS client.

        Args:
            api_url: EPSS API base URL (defaults to FIRST.org)
        """
        self.api_url = api_url or getattr(settings, 'DD_EPSS_API_URL', self.DEFAULT_API_URL)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'DefectDojo-Enterprise/1.0',
            'Accept': 'application/json'
        })

    def get_scores(self, cves: List[str]) -> Dict[str, Dict]:
        """
        Fetch EPSS scores for list of CVEs.

        Args:
            cves: List of CVE IDs (e.g., ['CVE-2021-44228', 'CVE-2022-1234'])

        Returns:
            Dictionary mapping CVE ID to score data:
            {
                'CVE-2021-44228': {
                    'cve': 'CVE-2021-44228',
                    'epss': 0.97480,
                    'percentile': 0.99990,
                    'date': '2024-01-15'
                },
                ...
            }
        """
        if not cves:
            return {}

        # Remove duplicates and normalize
        cves = list(set(cve.strip().upper() for cve in cves if cve))

        if not cves:
            return {}

        logger.info(f'Fetching EPSS scores for {len(cves)} CVEs')

        # Process in batches
        all_scores = {}
        for i in range(0, len(cves), self.MAX_CVES_PER_REQUEST):
            batch = cves[i:i + self.MAX_CVES_PER_REQUEST]
            batch_scores = self._fetch_batch(batch)
            all_scores.update(batch_scores)

        logger.info(f'Retrieved EPSS scores for {len(all_scores)}/{len(cves)} CVEs')
        return all_scores

    def _fetch_batch(self, cves: List[str]) -> Dict[str, Dict]:
        """
        Fetch EPSS scores for a batch of CVEs.

        Args:
            cves: List of CVE IDs (max 100)

        Returns:
            Dictionary mapping CVE ID to score data
        """
        try:
            # Build request parameters
            params = {
                'cve': ','.join(cves)
            }

            response = self.session.get(self.api_url, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()

            # Parse response
            scores = {}
            if 'data' in data:
                for item in data['data']:
                    cve_id = item.get('cve', '').upper()
                    if cve_id:
                        scores[cve_id] = {
                            'cve': cve_id,
                            'epss': float(item.get('epss', 0.0)),
                            'percentile': float(item.get('percentile', 0.0)),
                            'date': item.get('date', datetime.now().strftime('%Y-%m-%d'))
                        }

            return scores

        except requests.exceptions.RequestException as e:
            logger.error(f'EPSS API request failed for batch: {e}')
            return {}
        except (ValueError, KeyError) as e:
            logger.error(f'Failed to parse EPSS API response: {e}')
            return {}

    def get_score(self, cve: str) -> Optional[Dict]:
        """
        Fetch EPSS score for a single CVE.

        Args:
            cve: CVE ID (e.g., 'CVE-2021-44228')

        Returns:
            Score data dictionary or None if not found
        """
        scores = self.get_scores([cve])
        return scores.get(cve.upper())

    def get_latest_scores(self, limit: Optional[int] = None) -> Dict[str, Dict]:
        """
        Fetch latest EPSS scores (all CVEs with scores from latest data).

        Note: This can return a large dataset. Use with caution.

        Args:
            limit: Optional limit on number of CVEs to return

        Returns:
            Dictionary mapping CVE ID to score data
        """
        try:
            params = {}
            if limit:
                params['limit'] = limit

            response = self.session.get(self.api_url, params=params, timeout=60)
            response.raise_for_status()

            data = response.json()

            scores = {}
            if 'data' in data:
                for item in data['data'][:limit] if limit else data['data']:
                    cve_id = item.get('cve', '').upper()
                    if cve_id:
                        scores[cve_id] = {
                            'cve': cve_id,
                            'epss': float(item.get('epss', 0.0)),
                            'percentile': float(item.get('percentile', 0.0)),
                            'date': item.get('date', datetime.now().strftime('%Y-%m-%d'))
                        }

            logger.info(f'Retrieved {len(scores)} latest EPSS scores')
            return scores

        except requests.exceptions.RequestException as e:
            logger.error(f'EPSS API request failed: {e}')
            return {}
        except (ValueError, KeyError) as e:
            logger.error(f'Failed to parse EPSS API response: {e}')
            return {}

    def check_api_status(self) -> bool:
        """
        Check if EPSS API is accessible.

        Returns:
            True if API is reachable and responding
        """
        try:
            # Fetch a known CVE to test connectivity
            response = self.session.get(
                self.api_url,
                params={'cve': 'CVE-2021-44228'},
                timeout=10
            )
            return response.status_code == 200
        except requests.exceptions.RequestException:
            return False
