"""Check native SQLite validation against closed WAL libraries."""
import hashlib
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import unittest


class WorkspaceValidationTests(unittest.TestCase):
    def test_closed_wal_and_delete_libraries_keep_data(self):
        with tempfile.TemporaryDirectory() as temporary:
            for mode in ('WAL', 'DELETE'):
                database = Path(temporary) / (mode + ' library #1.sqlite3')
                connection = sqlite3.connect(database)
                connection.execute('PRAGMA journal_mode=' + mode)
                for name in ('records', 'projects', 'jobs', 'settings'):
                    connection.execute('CREATE TABLE ' + name + '(id TEXT)')
                connection.execute("INSERT INTO records VALUES ('preserved result')")
                connection.commit()
                connection.close()
                before = hashlib.sha256(database.read_bytes()).hexdigest()
                command = ['/usr/bin/sqlite3', '-cmd', 'PRAGMA query_only=ON;', database.as_uri() + '?mode=rw']
                check = subprocess.run(command + ["SELECT count(*) FROM sqlite_master WHERE type='table' AND name IN ('records','projects','jobs','settings');"], text=True, capture_output=True)
                self.assertEqual((check.returncode, check.stdout.strip()), (0, '4'), check.stderr)
                write = subprocess.run(command + ["INSERT INTO records VALUES ('must fail');"], text=True, capture_output=True)
                self.assertNotEqual(write.returncode, 0)
                self.assertIn('readonly', write.stderr)
                self.assertEqual(hashlib.sha256(database.read_bytes()).hexdigest(), before)
                connection = sqlite3.connect(database)
                self.assertEqual(connection.execute('SELECT id FROM records').fetchall(), [('preserved result',)])
                connection.close()

    def test_missing_library_is_not_created(self):
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / 'missing.sqlite3'
            check = subprocess.run(['/usr/bin/sqlite3', '-cmd', 'PRAGMA query_only=ON;', database.as_uri() + '?mode=rw', 'SELECT 1;'], text=True, capture_output=True)
            self.assertNotEqual(check.returncode, 0)
            self.assertFalse(database.exists())
