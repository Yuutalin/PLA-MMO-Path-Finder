import importlib.util
import tempfile
import unittest
from pathlib import Path

HAS_FLASK = importlib.util.find_spec("flask") is not None
if HAS_FLASK:
    from app import create_app


@unittest.skipUnless(HAS_FLASK, "Flask is not installed in this isolated build environment")
class DiagnosticsEndpointTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.app = create_app({
            "TESTING": True,
            "DATA_DIR": str(Path(self.tempdir.name) / "data"),
        })
        self.client = self.app.test_client()

    def tearDown(self):
        self.tempdir.cleanup()

    def test_diagnostics_endpoint_returns_copyable_report(self):
        response = self.client.get("/api/diagnostics")
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertTrue(body["ok"])
        self.assertIn("PLA MMO 闪光路径助手 - 诊断报告", body["report"])
        self.assertIn("Python：", body["report"])
        self.assertIn("runtime_errors.log", body["report"])
        self.assertIn("offline_engine_setup.log", body["report"])
        self.assertIn("用户配置状态：", body["report"])

    def test_health_version_is_current(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["version"], "0.7.3")

    def test_index_displays_author_and_current_version(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("君粒&amp;GPT".encode("utf-8"), response.data)
        self.assertIn(b"v0.7.3", response.data)

    def test_user_asset_route_serves_images_from_user_data_directory(self):
        import base64
        assets = self.app.extensions["pla_pokemon_assets"]
        image = assets.custom_dir / "c_712.png"
        image.write_bytes(base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADUlEQVR4nGP4z8AAAAMBAQDJ/pLvAAAAAElFTkSuQmCC"))
        # send_file() streams a file handle on Windows. Always close every
        # test response explicitly so TemporaryDirectory cleanup does not hit
        # WinError 32 when the test client still owns the image stream.
        response = self.client.get("/user-assets/custom/c_712.png")
        try:
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.mimetype, "image/png")
            self.assertTrue(response.data.startswith(b"\x89PNG\r\n\x1a\n"))
        finally:
            response.close()

        traversal_response = self.client.get("/user-assets/custom/../settings.json")
        try:
            self.assertEqual(traversal_response.status_code, 404)
        finally:
            traversal_response.close()

    def test_history_api_is_removed(self):
        self.assertEqual(self.client.get("/api/history").status_code, 404)
        self.assertEqual(self.client.get("/api/history/1").status_code, 404)


if __name__ == "__main__":
    unittest.main()
