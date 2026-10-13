import unittest

import pandas as pd

from src.openalex_dashboard.views.explorer import (
    _add_funding_summary,
    _add_roster_summary,
    _add_topic_keyword_summary,
    _grouped_text,
)


class ExplorerSummaryTests(unittest.TestCase):
    def test_unique_text_keeps_order_and_exact_truncation_count(self):
        frame = pd.DataFrame({
            "work_id": ["w1"] * 9 + ["w2", "w3", None],
            "text": [" B ", "A", "B", "", None, "nan", "C", "D", "E", None, " ", "ignored"],
        })
        original = frame.copy(deep=True)
        result = _grouped_text(frame, "text", limit=3)
        self.assertEqual(result.to_dict(), {"w1": "B; A; C; +2 more", "w2": "", "w3": ""})
        pd.testing.assert_frame_equal(frame, original)

    def test_confidence_order_scores_and_unmatched_publication(self):
        works = pd.DataFrame({"work_id": ["w2", "w1", "w3"]})
        roster = pd.DataFrame({
            "work_id": ["w1", "w1", "w1", "w1", "w2"],
            "paper_confidence": [" LOW ", "HIGH", "medium", "high", None],
            "paper_confidence_score": [0.1, 0.9, 0.5, 0.8, None],
            "paper_confidence_reasons": ["R", "R", "S", None, None],
            "staff_name": ["B", "A", "B", "C", "D"],
        })
        original = roster.copy(deep=True)
        result = _add_roster_summary(works, roster).set_index("work_id")
        self.assertEqual(result.index.tolist(), ["w2", "w1", "w3"])
        self.assertEqual(result.loc["w1", "paper_confidence"], "high; medium; low")
        self.assertEqual(result.loc["w1", "paper_confidence_score_min"], 0.1)
        self.assertEqual(result.loc["w1", "paper_confidence_score_max"], 0.9)
        self.assertEqual(result.loc["w1", "linked_staff"], "B; A; C")
        self.assertEqual(result.loc["w1", "paper_confidence_reasons"], "R; S")
        self.assertEqual(result.loc["w2", "paper_confidence"], "")
        self.assertTrue(pd.isna(result.loc["w3", "linked_staff"]))
        pd.testing.assert_frame_equal(roster, original)

    def test_optional_topic_schema_and_existing_funding(self):
        works = pd.DataFrame({"work_id": ["w1"], "funder_names": ["Existing"]})
        topics = pd.DataFrame({"work_id": ["w1", "w1"], "field_name": ["F", "F"]})
        result = _add_topic_keyword_summary(works, topics, pd.DataFrame())
        self.assertEqual(result.loc[0, "openalex_topics"], "F")
        self.assertEqual(result.loc[0, "openalex_subfields"], "")
        funding = pd.DataFrame({"work_id": ["w1", "w1"], "funder_name": ["Other", "Other"], "award_id": ["2", "1"]})
        result = _add_funding_summary(result, funding)
        self.assertEqual(result.loc[0, "funder_names"], "Existing")
        self.assertEqual(result.loc[0, "award_ids"], "2; 1")

    def test_empty_and_null_work_ids(self):
        works = pd.DataFrame({"work_id": ["w1"]})
        pd.testing.assert_frame_equal(_add_roster_summary(works, pd.DataFrame()), works)
        roster = pd.DataFrame({"work_id": [None], "staff_name": ["A"]})
        result = _add_roster_summary(works, roster)
        self.assertTrue(pd.isna(result.loc[0, "linked_staff"]))


if __name__ == "__main__":
    unittest.main()
