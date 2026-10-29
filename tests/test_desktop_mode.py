import os
import sys
import tempfile
import threading
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import app


class DesktopModeSelectionTests(unittest.TestCase):
    def test_frozen_build_defaults_to_native_desktop_window(self):
        with patch.object(app.sys, "frozen", True, create=True), patch.dict(os.environ, {}, clear=True):
            self.assertTrue(app._desktop_mode_enabled())

    def test_source_run_keeps_browser_mode_unless_explicitly_enabled(self):
        with patch.object(app.sys, "frozen", False, create=True), patch.dict(os.environ, {}, clear=True):
            self.assertFalse(app._desktop_mode_enabled())
        with patch.dict(os.environ, {"PLA_DESKTOP": "1"}, clear=True):
            self.assertTrue(app._desktop_mode_enabled())

    def test_local_server_is_stopped_when_desktop_window_closes(self):
        class FakeServer:
            def __init__(self):
                self.stop_event = threading.Event()
                self.thread = None
                self.shutdown_calls = 0
                self.close_calls = 0

            def serve_forever(self):
                self.thread = threading.current_thread()
                self.stop_event.wait(timeout=5)

            def shutdown(self):
                self.shutdown_calls += 1
                self.stop_event.set()

            def server_close(self):
                self.close_calls += 1

        class FakeEvent:
            def __iadd__(self, callback):
                self.callback = callback
                return self

        class FakeEvents:
            def __init__(self):
                self.shown = FakeEvent()

        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            server = FakeServer()
            fake_window = types.SimpleNamespace(events=FakeEvents())
            fake_webview = types.SimpleNamespace(
                create_window=Mock(return_value=fake_window),
                start=Mock(return_value=None),
            )
            with (
                patch("werkzeug.serving.make_server", return_value=server),
                patch.dict(sys.modules, {"webview": fake_webview}),
                patch("app._wait_for_local_server", return_value=True),
                patch("pla_mmo.settings.get_data_dir", return_value=data_dir),
                patch.dict(os.environ, {"WEBVIEW2_USER_DATA_FOLDER": str(data_dir / "webview")}),
            ):
                flask_app = app.create_app({"TESTING": True, "DATA_DIR": str(data_dir / "data")})
                app._run_desktop_window(flask_app, "http://127.0.0.1:5050", 5050)

            self.assertEqual(server.shutdown_calls, 1)
            self.assertEqual(server.close_calls, 1)
            self.assertIsNotNone(server.thread)
            self.assertFalse(server.thread.is_alive())
            fake_webview.start.assert_called_once()


if __name__ == "__main__":
    unittest.main()
