import os
import sqlite3
import unittest
from monitor import init_db, ping_host, log_system_metrics, log_host_status

TEST_DB = "test_monitor_logs.db"

class TestNetworkSystemMonitor(unittest.TestCase):
    def setUp(self):
        if os.path.exists(TEST_DB):
            os.remove(TEST_DB)
            
    def tearDown(self):
        if os.path.exists(TEST_DB):
            os.remove(TEST_DB)

    def test_ping_local_loopback(self):
        # 127.0.0.1 should always be online
        result = ping_host("127.0.0.1")
        self.assertTrue(result)

    def test_database_logging(self):
        # Initialize test database
        init_db(TEST_DB)
        self.assertTrue(os.path.exists(TEST_DB))

        # Log system metrics
        log_system_metrics(TEST_DB, 15.5, 45.2, 60.1)
        
        # Log host status
        log_host_status(TEST_DB, "Google DNS", "8.8.8.8", True)

        # Query database and verify
        conn = sqlite3.connect(TEST_DB)
        cursor = conn.cursor()
        
        cursor.execute("SELECT cpu_usage, ram_usage, disk_usage FROM system_metrics")
        metrics = cursor.fetchone()
        self.assertIsNotNone(metrics)
        self.assertEqual(metrics[0], 15.5)
        self.assertEqual(metrics[1], 45.2)
        
        cursor.execute("SELECT host_name, ip_address, is_online FROM host_status")
        host = cursor.fetchone()
        self.assertIsNotNone(host)
        self.assertEqual(host[0], "Google DNS")
        self.assertEqual(host[1], "8.8.8.8")
        self.assertEqual(host[2], 1)
        
        conn.close()

if __name__ == "__main__":
    unittest.main()
