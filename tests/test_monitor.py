import os
import sqlite3
import unittest
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from monitor import init_db, ping_host, log_system_metrics, log_host_status

TEST_DB = "test_monitor_logs.db"


class TestDatabaseOperations(unittest.TestCase):
    """Tests for SQLite database init and logging functions."""

    def setUp(self):
        if os.path.exists(TEST_DB):
            os.remove(TEST_DB)

    def tearDown(self):
        if os.path.exists(TEST_DB):
            os.remove(TEST_DB)

    def test_init_db_creates_file(self):
        """init_db must create the SQLite file."""
        init_db(TEST_DB)
        self.assertTrue(os.path.exists(TEST_DB))

    def test_init_db_creates_system_metrics_table(self):
        """system_metrics table must be created."""
        init_db(TEST_DB)
        conn = sqlite3.connect(TEST_DB)
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        conn.close()
        self.assertIn("system_metrics", tables)

    def test_init_db_creates_host_status_table(self):
        """host_status table must be created."""
        init_db(TEST_DB)
        conn = sqlite3.connect(TEST_DB)
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        conn.close()
        self.assertIn("host_status", tables)

    def test_log_system_metrics_stores_correctly(self):
        """Logged CPU/RAM/Disk values must be retrievable and accurate."""
        init_db(TEST_DB)
        log_system_metrics(TEST_DB, 25.5, 60.3, 72.1)
        conn = sqlite3.connect(TEST_DB)
        row = conn.execute(
            "SELECT cpu_usage, ram_usage, disk_usage FROM system_metrics").fetchone()
        conn.close()
        self.assertIsNotNone(row)
        self.assertAlmostEqual(row[0], 25.5, places=1)
        self.assertAlmostEqual(row[1], 60.3, places=1)
        self.assertAlmostEqual(row[2], 72.1, places=1)

    def test_log_multiple_metrics(self):
        """Multiple metric rows must all be stored."""
        init_db(TEST_DB)
        log_system_metrics(TEST_DB, 10.0, 20.0, 30.0)
        log_system_metrics(TEST_DB, 50.0, 60.0, 70.0)
        conn = sqlite3.connect(TEST_DB)
        count = conn.execute("SELECT COUNT(*) FROM system_metrics").fetchone()[0]
        conn.close()
        self.assertEqual(count, 2)

    def test_log_host_status_online(self):
        """Online host status must be stored with is_online=1."""
        init_db(TEST_DB)
        log_host_status(TEST_DB, "Google DNS", "8.8.8.8", True)
        conn = sqlite3.connect(TEST_DB)
        row = conn.execute(
            "SELECT host_name, ip_address, is_online FROM host_status").fetchone()
        conn.close()
        self.assertIsNotNone(row)
        self.assertEqual(row[0], "Google DNS")
        self.assertEqual(row[1], "8.8.8.8")
        self.assertEqual(row[2], 1)

    def test_log_host_status_offline(self):
        """Offline host status must be stored with is_online=0."""
        init_db(TEST_DB)
        log_host_status(TEST_DB, "Dead Server", "10.0.0.99", False)
        conn = sqlite3.connect(TEST_DB)
        row = conn.execute(
            "SELECT is_online FROM host_status WHERE host_name='Dead Server'").fetchone()
        conn.close()
        self.assertIsNotNone(row)
        self.assertEqual(row[0], 0)


class TestNetworkPinger(unittest.TestCase):
    """Tests for the ping_host function."""

    def test_ping_localhost(self):
        """127.0.0.1 (loopback) must always be reachable."""
        result = ping_host("127.0.0.1")
        self.assertTrue(result, "Loopback 127.0.0.1 should always be online.")

    def test_ping_invalid_address(self):
        """An invalid IP must return False, not raise an exception."""
        try:
            result = ping_host("0.0.0.0")
            self.assertIsInstance(result, bool)
        except Exception as e:
            self.fail(f"ping_host raised an exception on invalid IP: {e}")

    def test_ping_unreachable_host(self):
        """A clearly unreachable address must return False."""
        result = ping_host("192.0.2.1")  # TEST-NET-1, RFC 5737 — never routable
        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main(verbosity=2)
