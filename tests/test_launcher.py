import os
import socket
import unittest
from unittest.mock import patch

from pla_mmo.launcher import choose_local_port


class LocalPortSelectionTests(unittest.TestCase):
    def test_uses_preferred_port_when_available(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        self.assertEqual(choose_local_port(preferred=port, attempts=1), port)

    def test_skips_a_port_owned_by_an_old_instance(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as occupied:
            occupied.bind(("127.0.0.1", 0))
            occupied.listen(1)
            old_port = occupied.getsockname()[1]
            selected = choose_local_port(preferred=old_port, attempts=5)
            self.assertNotEqual(selected, old_port)
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as verify:
                verify.bind(("127.0.0.1", selected))

    def test_honors_pla_port_when_available(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        with patch.dict(os.environ, {"PLA_PORT": str(port)}):
            self.assertEqual(choose_local_port(attempts=1), port)

    def test_rejects_invalid_pla_port(self):
        with patch.dict(os.environ, {"PLA_PORT": "not-a-port"}):
            with self.assertRaises(ValueError):
                choose_local_port()


if __name__ == "__main__":
    unittest.main()
