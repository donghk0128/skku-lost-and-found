from uuid import uuid4

import pytest

from app.matching.evaluation import ranking_metrics


def test_ranking_metrics_recall_and_mrr() -> None:
    source, positive, negative = uuid4(), uuid4(), uuid4()
    result = ranking_metrics({source: [negative, positive]}, {source: {positive}})
    assert result == {"recall_at_1": 0.0, "recall_at_5": 1.0, "mrr": 0.5}


def test_ranking_metrics_require_truth() -> None:
    source = uuid4()
    with pytest.raises(ValueError):
        ranking_metrics({source: []}, {source: set()})
