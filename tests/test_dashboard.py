"""Tests for the Flask dashboard."""

import unittest

from dashboard.app import create_app


class DashboardTest(unittest.TestCase):
    """HTTP-level checks using Flask's test client."""

    def setUp(self) -> None:
        self.client = create_app().test_client()

    def test_index_shows_title(self) -> None:
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"SOC Monitor", response.data)

    def test_stylesheet_is_served_locally(self) -> None:
        response = self.client.get("/static/style.css")
        self.assertEqual(response.status_code, 200)
        response.close()


if __name__ == "__main__":
    unittest.main()
