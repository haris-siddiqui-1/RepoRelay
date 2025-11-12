"""
README Summarization

Extracts and summarizes repository README files for quick context.
Provides simple extraction (first sentences) without requiring LLM integration.
"""

import logging
import re
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class ReadmeSummarizer:
    """
    Extracts key information from repository README files.

    Provides lightweight summarization without external dependencies:
    - Extracts first meaningful paragraph
    - Detects primary language and framework mentions
    - Computes README length metrics
    """

    # Common framework/technology patterns
    FRAMEWORK_PATTERNS = {
        # JavaScript/TypeScript
        'React': r'\b(React|ReactJS|react)\b',
        'Vue': r'\b(Vue|VueJS|vue)\b',
        'Angular': r'\b(Angular|angular)\b',
        'Next.js': r'\b(Next\.js|NextJS|next)\b',
        'Express': r'\b(Express|ExpressJS|express)\b',
        'Node.js': r'\b(Node\.js|NodeJS|node)\b',

        # Python
        'Django': r'\b(Django|django)\b',
        'Flask': r'\b(Flask|flask)\b',
        'FastAPI': r'\b(FastAPI|fastapi)\b',
        'Pandas': r'\b(Pandas|pandas)\b',
        'PyTorch': r'\b(PyTorch|pytorch)\b',
        'TensorFlow': r'\b(TensorFlow|tensorflow)\b',

        # Java
        'Spring': r'\b(Spring|SpringBoot|spring-boot)\b',
        'Hibernate': r'\b(Hibernate|hibernate)\b',

        # Go
        'Gin': r'\b(Gin|gin-gonic)\b',
        'Echo': r'\b(Echo|echo)\b',

        # Ruby
        'Rails': r'\b(Rails|Ruby on Rails|rails)\b',
        'Sinatra': r'\b(Sinatra|sinatra)\b',

        # PHP
        'Laravel': r'\b(Laravel|laravel)\b',
        'Symfony': r'\b(Symfony|symfony)\b',

        # Rust
        'Actix': r'\b(Actix|actix-web)\b',
        'Rocket': r'\b(Rocket|rocket)\b',

        # DevOps/Cloud
        'Docker': r'\b(Docker|docker)\b',
        'Kubernetes': r'\b(Kubernetes|K8s|k8s)\b',
        'Terraform': r'\b(Terraform|terraform)\b',
    }

    LANGUAGE_PATTERNS = {
        'Python': r'\b(Python|python|\.py)\b',
        'JavaScript': r'\b(JavaScript|javascript|JS|js|\.js)\b',
        'TypeScript': r'\b(TypeScript|typescript|TS|ts|\.ts)\b',
        'Java': r'\b(Java|java|\.java)\b',
        'Go': r'\b(Go|Golang|golang|go)\b',
        'Rust': r'\b(Rust|rust|\.rs)\b',
        'Ruby': r'\b(Ruby|ruby|\.rb)\b',
        'PHP': r'\b(PHP|php|\.php)\b',
        'C#': r'\b(C#|csharp|CSharp|\.cs)\b',
        'C++': r'\b(C\+\+|cpp|CPP|\.cpp)\b',
    }

    def __init__(self, repo):
        """
        Initialize summarizer with GitHub repository object.

        Args:
            repo: PyGithub Repository object
        """
        self.repo = repo

    def extract_and_summarize(self) -> Dict[str, any]:
        """
        Extract and summarize README content.

        Returns:
            Dictionary containing:
            - summary: String (max 500 chars) summary of README
            - length: Integer character count of full README
            - primary_language: String detected primary language
            - primary_framework: String detected primary framework
            - raw_content: String full README content (for further processing)
        """
        logger.info(f"Summarizing README for repository: {self.repo.full_name}")

        try:
            readme = self.repo.get_readme()
            content = readme.decoded_content.decode('utf-8')

            return {
                'summary': self._extract_summary(content),
                'length': len(content),
                'primary_language': self._detect_language(content),
                'primary_framework': self._detect_framework(content),
                'raw_content': content
            }
        except Exception as e:
            logger.warning(f"Could not extract README for {self.repo.full_name}: {e}")
            return {
                'summary': '',
                'length': 0,
                'primary_language': '',
                'primary_framework': '',
                'raw_content': ''
            }

    def _extract_summary(self, content: str, max_length: int = 500) -> str:
        """
        Extract meaningful summary from README.

        Strategy:
        1. Look for "About", "Overview", "What is" sections
        2. Fall back to first paragraph after title
        3. Clean badges/shields and formatting
        4. Truncate to max_length

        Args:
            content: Full README content
            max_length: Maximum summary length (default 500)

        Returns:
            Summary string
        """
        # Remove common badges/shields (markdown image links)
        content = re.sub(r'!\[.*?\]\(.*?\)', '', content)
        content = re.sub(r'\[!\[.*?\].*?\]', '', content)

        # Remove HTML comments
        content = re.sub(r'<!--.*?-->', '', content, flags=re.DOTALL)

        # Look for "About" or "Overview" section
        about_match = re.search(r'##?\s*(About|Overview|What is|Description)\s*\n+(.*?)(?=\n##|\Z)',
                               content,
                               re.IGNORECASE | re.DOTALL)

        if about_match:
            summary_text = about_match.group(2).strip()
        else:
            # Fall back to first paragraph after title (skip first # heading)
            lines = content.split('\n')
            summary_lines = []
            found_content = False

            for line in lines:
                line = line.strip()
                # Skip title lines
                if line.startswith('#'):
                    continue
                # Skip empty lines until we find content
                if not found_content and not line:
                    continue
                if line:
                    found_content = True
                    summary_lines.append(line)
                    # Stop at next heading or after 10 lines
                    if line.startswith('#') or len(summary_lines) >= 10:
                        break

            summary_text = ' '.join(summary_lines)

        # Clean up formatting
        summary_text = self._clean_markdown(summary_text)

        # Extract first 2-3 sentences
        sentences = re.split(r'[.!?]\s+', summary_text)
        summary_sentences = []
        current_length = 0

        for sentence in sentences[:5]:  # Max 5 sentences
            sentence = sentence.strip()
            if not sentence:
                continue

            sentence_length = len(sentence) + 2  # +2 for '. '

            if current_length + sentence_length > max_length:
                break

            summary_sentences.append(sentence)
            current_length += sentence_length

        summary = '. '.join(summary_sentences)
        if summary and not summary.endswith('.'):
            summary += '.'

        return summary[:max_length].strip()

    def _clean_markdown(self, text: str) -> str:
        """
        Remove markdown formatting for clean text.

        Args:
            text: Markdown text

        Returns:
            Plain text
        """
        # Remove code blocks
        text = re.sub(r'```.*?```', '', text, flags=re.DOTALL)
        text = re.sub(r'`[^`]+`', '', text)

        # Remove links but keep text
        text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)

        # Remove emphasis
        text = re.sub(r'[*_]{1,2}([^*_]+)[*_]{1,2}', r'\1', text)

        # Remove multiple spaces/newlines
        text = re.sub(r'\s+', ' ', text)

        return text.strip()

    def _detect_language(self, content: str) -> str:
        """
        Detect primary programming language from README mentions.

        Args:
            content: README content

        Returns:
            Language name or empty string
        """
        # Check against patterns
        language_scores = {}

        for language, pattern in self.LANGUAGE_PATTERNS.items():
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                # Weight by position (earlier mentions = higher score)
                first_pos = content.lower().find(matches[0].lower())
                score = len(matches) * (1000 - min(first_pos, 1000) / 1000)
                language_scores[language] = score

        if language_scores:
            return max(language_scores, key=language_scores.get)

        return ''

    def _detect_framework(self, content: str) -> str:
        """
        Detect primary framework from README mentions.

        Args:
            content: README content

        Returns:
            Framework name or empty string
        """
        framework_scores = {}

        for framework, pattern in self.FRAMEWORK_PATTERNS.items():
            matches = re.findall(pattern, content)
            if matches:
                # Weight by position
                first_pos = content.find(matches[0])
                score = len(matches) * (1000 - min(first_pos, 1000) / 1000)
                framework_scores[framework] = score

        if framework_scores:
            return max(framework_scores, key=framework_scores.get)

        return ''
