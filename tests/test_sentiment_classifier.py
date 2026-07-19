"""Tests for SentimentClassifier class."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import torch

from resources import SentimentClassifier, SentimentResult


@pytest.fixture
def mock_model():
    """Mock FinBERT model and tokenizer."""
    with (
        patch("resources.sentiment_classifier.AutoTokenizer"),
        patch("resources.sentiment_classifier.AutoModelForSequenceClassification"),
    ):
        classifier = SentimentClassifier()
        return classifier


def test_classifier_initialization():
    """Test SentimentClassifier initializes with correct model."""
    with (
        patch("resources.sentiment_classifier.AutoTokenizer") as mock_tokenizer,
        patch(
            "resources.sentiment_classifier.AutoModelForSequenceClassification"
        ) as mock_model,
    ):
        classifier = SentimentClassifier()

        assert classifier.model_name == "ProsusAI/finbert"
        assert classifier.labels == ["positive", "negative", "neutral"]
        assert classifier.device in ["cuda", "cpu"]
        mock_tokenizer.from_pretrained.assert_called_once()
        mock_model.from_pretrained.assert_called_once()


def test_classifier_with_cache_dir():
    """Test classifier uses cache directory."""
    cache_dir = Path("/tmp/test_cache")

    with (
        patch("resources.sentiment_classifier.AutoTokenizer") as mock_tokenizer,
        patch(
            "resources.sentiment_classifier.AutoModelForSequenceClassification"
        ) as mock_model,
    ):
        classifier = SentimentClassifier(model_cache_dir=cache_dir)

        mock_tokenizer.from_pretrained.assert_called_with(
            "ProsusAI/finbert", cache_dir=str(cache_dir)
        )
        mock_model.from_pretrained.assert_called_with(
            "ProsusAI/finbert", cache_dir=str(cache_dir)
        )


@patch("resources.sentiment_classifier.AutoTokenizer")
@patch("resources.sentiment_classifier.AutoModelForSequenceClassification")
def test_classify_positive(mock_model_class, mock_tokenizer_class):
    """Test classifying positive sentiment."""
    mock_tokenizer = MagicMock()
    mock_tokenizer.return_value = {"input_ids": torch.tensor([[1, 2, 3]])}
    mock_tokenizer_class.from_pretrained.return_value = mock_tokenizer

    mock_model = MagicMock()
    mock_output = MagicMock()
    mock_output.logits = torch.tensor([[2.0, -1.0, -1.0]])
    mock_model.return_value = mock_output
    mock_model.eval.return_value = None
    mock_model.to.return_value = mock_model
    mock_model_class.from_pretrained.return_value = mock_model

    classifier = SentimentClassifier()
    result = classifier.classify("Stock price surges to all-time high")

    assert isinstance(result, SentimentResult)
    assert result.label == "positive"
    assert 0 <= result.score <= 1
    assert "positive" in result.label_scores
    assert "negative" in result.label_scores
    assert "neutral" in result.label_scores


@patch("resources.sentiment_classifier.AutoTokenizer")
@patch("resources.sentiment_classifier.AutoModelForSequenceClassification")
def test_classify_negative(mock_model_class, mock_tokenizer_class):
    """Test classifying negative sentiment."""
    mock_tokenizer = MagicMock()
    mock_tokenizer.return_value = {"input_ids": torch.tensor([[1, 2, 3]])}
    mock_tokenizer_class.from_pretrained.return_value = mock_tokenizer

    mock_model = MagicMock()
    mock_output = MagicMock()
    mock_output.logits = torch.tensor([[-1.0, 2.0, -1.0]])
    mock_model.return_value = mock_output
    mock_model.eval.return_value = None
    mock_model.to.return_value = mock_model
    mock_model_class.from_pretrained.return_value = mock_model

    classifier = SentimentClassifier()
    result = classifier.classify("Company faces major lawsuit")

    assert result.label == "negative"
    assert result.score > 0.5


@patch("resources.sentiment_classifier.AutoTokenizer")
@patch("resources.sentiment_classifier.AutoModelForSequenceClassification")
def test_classify_neutral(mock_model_class, mock_tokenizer_class):
    """Test classifying neutral sentiment."""
    mock_tokenizer = MagicMock()
    mock_tokenizer.return_value = {"input_ids": torch.tensor([[1, 2, 3]])}
    mock_tokenizer_class.from_pretrained.return_value = mock_tokenizer

    mock_model = MagicMock()
    mock_output = MagicMock()
    mock_output.logits = torch.tensor([[-1.0, -1.0, 2.0]])
    mock_model.return_value = mock_output
    mock_model.eval.return_value = None
    mock_model.to.return_value = mock_model
    mock_model_class.from_pretrained.return_value = mock_model

    classifier = SentimentClassifier()
    result = classifier.classify("Company announces quarterly report")

    assert result.label == "neutral"


@patch("resources.sentiment_classifier.AutoTokenizer")
@patch("resources.sentiment_classifier.AutoModelForSequenceClassification")
def test_classify_batch(mock_model_class, mock_tokenizer_class):
    """Test batch classification."""
    mock_tokenizer = MagicMock()
    mock_tokenizer.return_value = {"input_ids": torch.tensor([[1, 2, 3]])}
    mock_tokenizer_class.from_pretrained.return_value = mock_tokenizer

    mock_model = MagicMock()
    mock_output = MagicMock()
    mock_output.logits = torch.tensor([[2.0, -1.0, -1.0]])
    mock_model.return_value = mock_output
    mock_model.eval.return_value = None
    mock_model.to.return_value = mock_model
    mock_model_class.from_pretrained.return_value = mock_model

    classifier = SentimentClassifier()
    texts = ["Positive news", "Negative news", "Neutral news"]
    results = classifier.classify_batch(texts)

    assert len(results) == 3
    assert all(isinstance(r, SentimentResult) for r in results)


@patch("resources.sentiment_classifier.AutoTokenizer")
@patch("resources.sentiment_classifier.AutoModelForSequenceClassification")
def test_is_relevant_positive(mock_model_class, mock_tokenizer_class):
    """Test relevance check for positive sentiment."""
    mock_tokenizer = MagicMock()
    mock_tokenizer.return_value = {"input_ids": torch.tensor([[1, 2, 3]])}
    mock_tokenizer_class.from_pretrained.return_value = mock_tokenizer

    mock_model = MagicMock()
    mock_output = MagicMock()
    mock_output.logits = torch.tensor([[3.0, -2.0, -1.0]])
    mock_model.return_value = mock_output
    mock_model.eval.return_value = None
    mock_model.to.return_value = mock_model
    mock_model_class.from_pretrained.return_value = mock_model

    classifier = SentimentClassifier()

    assert classifier.is_relevant("Stock surges", threshold=0.5) is True


@patch("resources.sentiment_classifier.AutoTokenizer")
@patch("resources.sentiment_classifier.AutoModelForSequenceClassification")
def test_is_relevant_neutral(mock_model_class, mock_tokenizer_class):
    """Test relevance check for neutral sentiment."""
    mock_tokenizer = MagicMock()
    mock_tokenizer.return_value = {"input_ids": torch.tensor([[1, 2, 3]])}
    mock_tokenizer_class.from_pretrained.return_value = mock_tokenizer

    mock_model = MagicMock()
    mock_output = MagicMock()
    mock_output.logits = torch.tensor([[-1.0, -1.0, 2.0]])
    mock_model.return_value = mock_output
    mock_model.eval.return_value = None
    mock_model.to.return_value = mock_model
    mock_model_class.from_pretrained.return_value = mock_model

    classifier = SentimentClassifier()

    assert classifier.is_relevant("Neutral headline", threshold=0.5) is False


@patch("resources.sentiment_classifier.AutoTokenizer")
@patch("resources.sentiment_classifier.AutoModelForSequenceClassification")
def test_is_relevant_low_confidence(mock_model_class, mock_tokenizer_class):
    """Test relevance check with low confidence."""
    mock_tokenizer = MagicMock()
    mock_tokenizer.return_value = {"input_ids": torch.tensor([[1, 2, 3]])}
    mock_tokenizer_class.from_pretrained.return_value = mock_tokenizer

    mock_model = MagicMock()
    mock_output = MagicMock()
    mock_output.logits = torch.tensor([[0.3, 0.2, 0.1]])
    mock_model.return_value = mock_output
    mock_model.eval.return_value = None
    mock_model.to.return_value = mock_model
    mock_model_class.from_pretrained.return_value = mock_model

    classifier = SentimentClassifier()

    assert classifier.is_relevant("Weak signal", threshold=0.8) is False


def test_sentiment_result_dataclass():
    """Test SentimentResult dataclass."""
    result = SentimentResult(
        label="positive",
        score=0.95,
        label_scores={"positive": 0.95, "negative": 0.03, "neutral": 0.02},
    )

    assert result.label == "positive"
    assert result.score == 0.95
    assert result.label_scores["positive"] == 0.95
    assert sum(result.label_scores.values()) == pytest.approx(1.0)
