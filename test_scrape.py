import tempfile
import os

import pytest
from bs4 import BeautifulSoup

from scrape import scrape_hn_table, replace_table_in_index_html, HN_BASE, HN_TABLE_SELECTOR


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------

class TestLinkRewriting:
    """Test that link rewriting handles relative vs absolute URLs correctly."""

    def _make_table_with_links(self, hrefs):
        """Build a minimal HTML table matching HN_TABLE_SELECTOR with given hrefs."""
        links = "".join(f'<a href="{h}">link</a>' for h in hrefs)
        html = (
            f'<table id="hnmain"><tr><td></td></tr><tr><td></td></tr>'
            f'<tr><td><table>{links}</table></td></tr></table>'
        )
        soup = BeautifulSoup(html, "html.parser")
        return soup.select_one(HN_TABLE_SELECTOR)

    def test_relative_link_gets_base_prepended(self):
        table = self._make_table_with_links(["item?id=123"])
        # Simulate the rewriting logic from scrape_hn_table
        for a in table.find_all("a", href=True):
            href = a["href"]
            if not href.startswith(("http://", "https://")):
                a["href"] = f"{HN_BASE}/{href.lstrip('/')}"
        assert table.find("a")["href"] == "https://news.ycombinator.com/item?id=123"

    def test_absolute_http_link_unchanged(self):
        table = self._make_table_with_links(["https://www.youtube.com/watch?v=abc"])
        for a in table.find_all("a", href=True):
            href = a["href"]
            if not href.startswith(("http://", "https://")):
                a["href"] = f"{HN_BASE}/{href.lstrip('/')}"
        assert table.find("a")["href"] == "https://www.youtube.com/watch?v=abc"

    def test_absolute_https_link_unchanged(self):
        table = self._make_table_with_links(["http://example.com/page"])
        for a in table.find_all("a", href=True):
            href = a["href"]
            if not href.startswith(("http://", "https://")):
                a["href"] = f"{HN_BASE}/{href.lstrip('/')}"
        assert table.find("a")["href"] == "http://example.com/page"

    def test_relative_link_with_leading_slash(self):
        table = self._make_table_with_links(["/newcomments"])
        for a in table.find_all("a", href=True):
            href = a["href"]
            if not href.startswith(("http://", "https://")):
                a["href"] = f"{HN_BASE}/{href.lstrip('/')}"
        assert table.find("a")["href"] == "https://news.ycombinator.com/newcomments"

    def test_mixed_links(self):
        hrefs = [
            "item?id=999",
            "https://github.com/foo/bar",
            "user?id=someone",
            "http://blog.example.com",
            "vote?id=999&how=up&goto=news",
        ]
        table = self._make_table_with_links(hrefs)
        for a in table.find_all("a", href=True):
            href = a["href"]
            if not href.startswith(("http://", "https://")):
                a["href"] = f"{HN_BASE}/{href.lstrip('/')}"

        results = [a["href"] for a in table.find_all("a", href=True)]
        assert results == [
            "https://news.ycombinator.com/item?id=999",
            "https://github.com/foo/bar",
            "https://news.ycombinator.com/user?id=someone",
            "http://blog.example.com",
            "https://news.ycombinator.com/vote?id=999&how=up&goto=news",
        ]


class TestReplaceTable:
    """Test that replace_table_in_index_html swaps the table correctly."""

    def _make_index_html(self, table_content="<tr><td>old</td></tr>"):
        return (
            f'<html><body><center>'
            f'<table id="hnmain"><tr><td></td></tr><tr><td></td></tr>'
            f'<tr><td><table>{table_content}</table></td></tr></table>'
            f'</center></body></html>'
        )

    def test_table_is_replaced(self, monkeypatch):
        fake_table_html = '<table><tr><td class="new">scraped</td></tr></table>'
        fake_table = BeautifulSoup(fake_table_html, "html.parser").find("table")

        monkeypatch.setattr("scrape.scrape_hn_table", lambda: fake_table)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False) as f:
            f.write(self._make_index_html())
            tmp_path = f.name

        try:
            replace_table_in_index_html(tmp_path)
            with open(tmp_path) as f:
                result = f.read()
            assert "scraped" in result
            assert "old" not in result
        finally:
            os.unlink(tmp_path)

    def test_no_crash_when_scrape_returns_none(self, monkeypatch, capsys):
        monkeypatch.setattr("scrape.scrape_hn_table", lambda: None)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False) as f:
            f.write(self._make_index_html())
            tmp_path = f.name

        try:
            replace_table_in_index_html(tmp_path)
            assert "Could not find the HN table" in capsys.readouterr().out
        finally:
            os.unlink(tmp_path)


# ---------------------------------------------------------------------------
# Integration tests (hit the real HN site)
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestIntegration:
    """These tests make real HTTP requests to news.ycombinator.com."""

    def test_scrape_returns_table(self):
        table = scrape_hn_table()
        assert table is not None
        assert table.name == "table"

    def test_scraped_links_are_absolute(self):
        table = scrape_hn_table()
        for a in table.find_all("a", href=True):
            href = a["href"]
            assert href.startswith("http://") or href.startswith("https://"), (
                f"Found non-absolute link: {href}"
            )

    def test_external_links_not_rewritten(self):
        table = scrape_hn_table()
        for a in table.find_all("a", href=True):
            href = a["href"]
            if "news.ycombinator.com" not in href:
                assert not href.startswith(HN_BASE), (
                    f"External link was incorrectly rewritten: {href}"
                )

    def test_no_double_base_url(self):
        table = scrape_hn_table()
        double_base = f"{HN_BASE}/{HN_BASE}"
        for a in table.find_all("a", href=True):
            assert double_base not in a["href"], (
                f"Double base URL found: {a['href']}"
            )
