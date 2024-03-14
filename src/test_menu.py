import os
import unittest
from unittest.mock import patch, MagicMock
from menu import MenuApp

DB_PATH='test_db.db'

class TestManageResume(unittest.TestCase):
    @patch('menu.curses')
    @patch('menu.os.getenv')
    
    def test_manage_resume(self, mock_getenv, mock_curses):
        # Mock environment variables
        mock_getenv.side_effect = lambda x: {'OPENAI_API_KEY': 'test_key', 'BASE_RESUME_PATH': 'temp_base_resume.txt', 'HN_START_URL': 'test_url', 'COMMANDJOBS_LISTINGS_PER_BATCH': '10', 'OPENAI_GPT_MODEL': 'gpt-3.5'}.get(x, None)
                
        # Mock stdscr object
        mock_stdscr = MagicMock()
        mock_curses.initscr.return_value = mock_stdscr
        mock_stdscr.getmaxyx.return_value = (200, 200)  # Example values for a terminal size
        
        # Mock user input sequence for getch and get_wch
        test_resume_text = ''
        with open('config/base_resume.sample', 'r') as file:
            test_resume_text = file.read()

        # This is testing when the resume file doesn't exist
        # Remove test resume file, to make sure it doesn't exist
        temp_test_resume_path = os.getenv('BASE_RESUME_PATH')
        if os.path.exists(temp_test_resume_path):
            os.remove(temp_test_resume_path)
        
        # Presses Enter (10) to go into Paste Resume option
        mock_stdscr.getch.side_effect = [10]
        
        # And then paste the resume text + Esc ('\x1b'), to save the resume
        mock_stdscr.get_wch.side_effect = list(test_resume_text) + ['\x1b']
        
        # Initialize Menu with mocked stdscr and logger
        logger = MagicMock()
        with patch.object(MenuApp, 'run', return_value=None):
            menu = MenuApp(mock_stdscr, logger)
        
        # Simulate calling capture_text_with_scrolling
        exit_message = menu.manage_resume(mock_stdscr)
        
        # Verify we got a success message
        self.assertEqual(exit_message, f'Resume saved to {temp_test_resume_path}')
        
        # Verify the text was saved to base_resume.txt
        with open(temp_test_resume_path, 'r') as file:
            saved_text = file.read()

        self.assertEqual(saved_text, test_resume_text)
        
        # Remove temp test resume file
        if os.path.exists(temp_test_resume_path):
            os.remove(temp_test_resume_path)
        
        temp_test_db_path = DB_PATH
        if os.path.exists(temp_test_db_path):
            os.remove(temp_test_db_path)

if __name__ == '__main__':
    unittest.main()
