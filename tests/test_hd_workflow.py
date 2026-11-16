"""Offline mocks for HD billing boundaries and poll/download semantics."""
import unittest

from hd_workflow import (
    JobFailedError,
    JobQueryError,
    JobTimeoutError,
    china_hd_cost,
    overseas_hd_cost,
    poll_and_download,
    billable_seconds,
    fps_multiplier,
)


class BillingBoundaryTests(unittest.TestCase):
    def test_minimum_and_ceil(self):
        self.assertEqual(billable_seconds(12.34), 15)
        self.assertEqual(billable_seconds(14.1), 15)
        self.assertEqual(billable_seconds(15), 15)
        self.assertEqual(billable_seconds(15.0), 15)
        self.assertEqual(billable_seconds(15.1), 16)
        self.assertEqual(billable_seconds(30), 30)

    def test_fps_boundary(self):
        self.assertEqual(fps_multiplier(29.97), 1)
        self.assertEqual(fps_multiplier(30), 1)
        self.assertEqual(fps_multiplier(30.0), 1)
        self.assertEqual(fps_multiplier(30.01), 2)
        self.assertEqual(fps_multiplier(59.94), 2)

    def test_china_documented_example(self):
        self.assertAlmostEqual(china_hd_cost(30, 59.94, '4k'), 7.20)
        self.assertAlmostEqual(china_hd_cost(30, 59.94, '4k', discount=0.8), 5.76)
        self.assertAlmostEqual(china_hd_cost(12, 29.97, '1080p'), 15 * 0.04)

    def test_overseas_formula_uses_supplied_all_area_rate(self):
        # 0.01 is a test input, not a published overseas list price.
        rate = 0.01
        self.assertAlmostEqual(overseas_hd_cost(30, 29.97, '1080p', rate), 30 * rate)
        self.assertAlmostEqual(overseas_hd_cost(30, 29.97, '2k', rate), 30 * rate * 2)
        self.assertAlmostEqual(overseas_hd_cost(30, 59.94, '4k', rate), 30 * rate * 3 * 2)
        self.assertAlmostEqual(overseas_hd_cost(12.34, 29.97, '4k', rate, discount=0.8), 15 * rate * 3 * 0.8)


class PollWorkflowTests(unittest.TestCase):
    def test_success_downloads_result(self):
        calls = []
        jobs = [
            (200, {'status': 'processing'}, None),
            (200, {'status': 'succeeded', 'result': {'url': 'https://example.com/out.mp4'}}, None),
        ]

        def get_job(job_id):
            self.assertEqual(job_id, 'job_123')
            return jobs.pop(0)

        def download(url, path):
            calls.append((url, path))

        slept = []
        job = poll_and_download(
            'job_123', get_job, download, 'enhanced.mp4',
            max_attempts=5, interval=5, sleep=slept.append,
        )
        self.assertEqual(job['status'], 'succeeded')
        self.assertEqual(calls, [('https://example.com/out.mp4', 'enhanced.mp4')])
        self.assertEqual(slept, [5])

    def test_failed_job_does_not_download(self):
        downloaded = []

        def get_job(_job_id):
            return 200, {'status': 'failed', 'error': {'code': 'invalid_media', 'message': 'bad'}}, None

        with self.assertRaises(JobFailedError) as raised:
            poll_and_download('job_fail', get_job, lambda *_: downloaded.append(True), 'out.mp4', max_attempts=3)
        self.assertEqual(raised.exception.job_id, 'job_fail')
        self.assertEqual(downloaded, [])

    def test_timeout_keeps_job_id_and_does_not_cancel(self):
        canceled = []
        downloaded = []

        def get_job(_job_id):
            return 200, {'status': 'processing', 'id': 'job_pending'}, None

        with self.assertRaises(JobTimeoutError) as raised:
            poll_and_download(
                'job_pending', get_job,
                lambda *_: downloaded.append(True),
                'out.mp4',
                max_attempts=3,
                interval=1,
                sleep=lambda _s: None,
            )
        self.assertEqual(raised.exception.job_id, 'job_pending')
        self.assertIn('JOB_ID=job_pending', str(raised.exception))
        self.assertIn('was not canceled', str(raised.exception))
        self.assertEqual(downloaded, [])
        self.assertEqual(canceled, [])

    def test_429_honors_retry_after_then_succeeds(self):
        sequence = [
            (429, {}, {'Retry-After': '7'}),
            (200, {'status': 'succeeded', 'result': {'url': 'https://example.com/done.mp4'}}, None),
        ]
        slept = []
        downloaded = []

        def get_job(_job_id):
            return sequence.pop(0)

        job = poll_and_download(
            'job_429', get_job, lambda url, path: downloaded.append((url, path)),
            'done.mp4', max_attempts=4, interval=5, sleep=slept.append,
        )
        self.assertEqual(job['status'], 'succeeded')
        self.assertEqual(slept, [7])
        self.assertEqual(downloaded, [('https://example.com/done.mp4', 'done.mp4')])

    def test_non_200_query_error(self):
        def get_job(_job_id):
            return 500, {}, None

        with self.assertRaises(JobQueryError):
            poll_and_download('job_500', get_job, lambda *_: None, 'out.mp4', max_attempts=1)


if __name__ == '__main__':
    unittest.main()
