"""Sentiment Classifier - FinBERT-based news sentiment analysis.

Data flow:
  News headline → FinBERT tokenizer → Model inference → Sentiment label + score
"""

from dataclasses import dataclass
from pathlib import Path

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer


@dataclass
class SentimentResult:
    """Sentiment analysis result."""

    label: str
    score: float
    label_scores: dict[str, float]


class SentimentClassifier:
    """Classify financial news sentiment using FinBERT."""

    def __init__(self, model_cache_dir: Path | None = None):
        """Initialize FinBERT sentiment classifier.

        Args:
            model_cache_dir: Directory to cache the model (optional).
        """
        self.model_name = "ProsusAI/finbert"
        self.device = "cuda" if torch.cuda.is_available() else "cpu"

        cache_dir_str = str(model_cache_dir) if model_cache_dir else None

        self.tokenizer = AutoTokenizer.from_pretrained(
            self.model_name, cache_dir=cache_dir_str
        )

        self.model = AutoModelForSequenceClassification.from_pretrained(
            self.model_name, cache_dir=cache_dir_str
        )

        self.model.to(self.device)
        self.model.eval()

        self.labels = ["positive", "negative", "neutral"]

    def classify(self, text: str) -> SentimentResult:
        """Classify sentiment of financial text.

        Args:
            text: News headline or text to classify.

        Returns:
            SentimentResult with label, score, and all label scores.
        """
        inputs = self.tokenizer(
            text, return_tensors="pt", truncation=True, max_length=512, padding=True
        )

        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        with torch.no_grad():
            outputs = self.model(**inputs)
            logits = outputs.logits

        probabilities = torch.nn.functional.softmax(logits, dim=-1)
        probabilities = probabilities.cpu().numpy()[0]

        label_scores = {
            self.labels[i]: float(probabilities[i]) for i in range(len(self.labels))
        }

        predicted_idx = probabilities.argmax()
        predicted_label = self.labels[predicted_idx]
        predicted_score = float(probabilities[predicted_idx])

        return SentimentResult(
            label=predicted_label, score=predicted_score, label_scores=label_scores
        )

    def classify_batch(self, texts: list[str]) -> list[SentimentResult]:
        """Classify sentiment for multiple texts.

        Args:
            texts: List of news headlines or texts.

        Returns:
            List of SentimentResult objects.
        """
        results = []

        for text in texts:
            result = self.classify(text)
            results.append(result)

        return results

    def is_relevant(self, text: str, threshold: float = 0.5) -> bool:
        """Determine if news is relevant (not neutral).

        Args:
            text: News headline or text.
            threshold: Minimum confidence threshold for positive/negative.

        Returns:
            True if news is positive or negative with confidence >= threshold.
        """
        result = self.classify(text)

        if result.label == "neutral":
            return False

        return result.score >= threshold


if __name__ == "__main__":
    """Example usage of SentimentClassifier."""
    print("Loading FinBERT model...")
    classifier = SentimentClassifier()

    test_headlines = [
        "Apple stock surges to all-time high on strong earnings beat",
        "Microsoft faces major lawsuit over antitrust violations",
        "Google announces new AI features for search engine",
        "Tesla recalls 100,000 vehicles due to safety concerns",
        "Amazon reports revenue growth in Q4 earnings",
    ]

    print("\nClassifying news headlines:\n")

    for headline in test_headlines:
        result = classifier.classify(headline)
        print(f"Headline: {headline}")
        print(f"Sentiment: {result.label.upper()} ({result.score:.2%})")
        print(f"Scores: {result.label_scores}")
        print(f"Relevant: {classifier.is_relevant(headline)}")
        print()
