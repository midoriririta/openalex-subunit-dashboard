import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest


class ExplorerRefreshTests(unittest.TestCase):
    def test_sidebar_change_refreshes_the_fragment_input(self):
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=120)
        app.query_params["dataset"] = "demography"
        app.session_state["main_tabs_demography"] = "Publications Explorer"
        app.run()
        self.assertFalse(app.exception)
        initial = app.dataframe[0].value
        expected = initial[initial["is_oa"] == True]["work_id"].tolist()

        next(widget for widget in app.checkbox if widget.label == "Open access only").check()
        app.run()
        self.assertFalse(app.exception)
        self.assertCountEqual(app.dataframe[0].value["work_id"].tolist(), expected)

        next(widget for widget in app.text_input if widget.label == "Search visible table").input("genetic")
        app.run()
        self.assertFalse(app.exception)
        rows = app.dataframe[0].value
        self.assertGreater(len(rows), 0)
        self.assertTrue(rows["is_oa"].all())
        self.assertTrue(rows.astype(str).apply(lambda col: col.str.contains("genetic", case=False)).any(axis=1).all())


if __name__ == "__main__":
    unittest.main()
