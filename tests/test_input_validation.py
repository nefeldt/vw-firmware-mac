"""Validate disconnected/range handling before any actual guest input is emitted."""
from pathlib import Path
import sys
import unittest
import struct
from unittest.mock import mock_open, patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from mib_input import Hub
class InputValidation(unittest.TestCase):
    def test_tap_has_single_click_count(self):
        hub=Hub();hub.connected=True
        with patch.object(Path,'open',mock_open()):
            hub.submit({'type':'touch','phase':'up','x':250,'y':110})
        packet=hub.queue.get_nowait()[0]
        self.assertEqual(struct.unpack('<I',packet[:4])[0],52)
        payload=struct.unpack('<10i',packet[16:])
        self.assertEqual(payload,(13,1,0,0,250,110,1,0,1,1))
    def test_seat_menu_uses_front_keyboard(self):
        # Original P0480T HardKeyReader table: (keyboard13, key78) produces
        # MENU events320/319. Keyboard1 has no MENU entry.
        hub=Hub();hub.connected=True
        with patch.object(Path,'open',mock_open()):
            hub.submit({'type':'button','name':'MENU'})
        packets=hub.queue.get_nowait()
        self.assertEqual(len(packets),2)
        for packet,state in zip(packets,(1,0)):
            self.assertEqual(struct.unpack('<9I',packet),
                (32,0x0201d800,0xa63ff832,25,13,78,state,0,1))
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
