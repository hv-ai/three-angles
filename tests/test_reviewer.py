import tempfile
from pathlib import Path
import unittest
from research import ResearchError
from reviewer import ReviewerAccess

ENV={'REVIEW_ACCESS_CODE':'test-review-code-long','NEBIUS_API_KEY':'model-test-only',
     'TAVILY_API_KEY':'search-test-only','REVIEW_EXPIRES':'2099-01-01T00:00:00+00:00',
     'REVIEW_ACTION_UNITS':'3'}

class ReviewerTests(unittest.TestCase):
    def test_grant_budget_and_restart(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'review.sqlite3';access=ReviewerAccess(path,ENV)
            with self.assertRaises(ResearchError):access.run('visitor',3,lambda c:None)
            with self.assertRaises(ResearchError):access.authorize('visitor','wrong',True)
            with self.assertRaises(ResearchError):access.authorize('visitor',ENV['REVIEW_ACCESS_CODE'],False)
            access.authorize('visitor',ENV['REVIEW_ACCESS_CODE'],True)
            result=access.run('visitor',3,lambda c:c['provider'])
            self.assertEqual(result,'nebius')
            restored=ReviewerAccess(path,ENV)
            with self.assertRaises(ResearchError):restored.run('visitor',1,lambda c:None)
            raw=path.read_bytes()
            self.assertNotIn(b'model-test-only',raw);self.assertNotIn(b'search-test-only',raw)
            self.assertNotIn(b'test-review-code-long',raw)
    def test_disabled_expired_and_failed_attempt_still_bounded(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertFalse(ReviewerAccess(Path(folder)/'off.sqlite3',{}).available())
            expired=ReviewerAccess(Path(folder)/'expired.sqlite3',{**ENV,'REVIEW_EXPIRES':'2000-01-01T00:00:00+00:00'})
            with self.assertRaises(ResearchError):expired.authorize('visitor',ENV['REVIEW_ACCESS_CODE'],True)
            access=ReviewerAccess(Path(folder)/'failed.sqlite3',ENV)
            access.authorize('visitor',ENV['REVIEW_ACCESS_CODE'],True)
            def fail(c):raise ResearchError('Controlled failure')
            with self.assertRaises(ResearchError):access.run('visitor',3,fail)
            with self.assertRaises(ResearchError):access.run('visitor',1,lambda c:None)

if __name__=='__main__':unittest.main()
