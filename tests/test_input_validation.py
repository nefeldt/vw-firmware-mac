"""Validate disconnected/range handling before any actual guest input is emitted."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from mib_input import Hub
class InputValidation(unittest.TestCase):
    def test_disconnected_does_not_queue(self):
        hub=Hub()
        with self.assertRaises(ConnectionError):hub.submit({'type':'button','name':'MENU'})
        self.assertTrue(hub.queue.empty())
    def test_outside_display_rejected(self):
        hub=Hub();hub.connected=True
        for x,y in [(-1,0),(800,0),(0,-1),(0,480)]:
            with self.assertRaises(ValueError):hub.submit({'type':'touch','phase':'down','x':x,'y':y})
        self.assertTrue(hub.queue.empty())
    def test_unknown_control_rejected(self):
        hub=Hub();hub.connected=True
        with self.assertRaises(KeyError):hub.submit({'type':'button','name':'UNKNOWN'})
        with self.assertRaises(ValueError):hub.submit({'type':'encoder','name':'TUNE','delta':1000})
        self.assertTrue(hub.queue.empty())
if __name__=='__main__':unittest.main()
