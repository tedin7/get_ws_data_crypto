"""Exercise the collector run loop with controlled transport and clocks."""

import unittest

from probe_feed_stall import scenario


class FeedFreshnessTest(unittest.IsolatedAsyncioTestCase):
    async def test_residual_ticker_times_out_and_failed_flush_preserves_data(self):
        result = await scenario("residual_ticker")
        self.assertEqual(result["reconnect_close_at_s"], 65)
        self.assertEqual(result["buffered"], 1)
        self.assertTrue(result["failed_flush_reports_unsaved"])
        self.assertTrue(result["failed_flush_pending_batch"])
        self.assertEqual(result["failed_flush_buffered"], 1)
        self.assertEqual(result["retry_saved_prices"], [42])

    async def test_unchanged_valid_prices_keep_connection_fresh(self):
        result = await scenario("unchanged_price")
        self.assertIsNone(result["reconnect_close_at_s"])
        self.assertEqual(result["ticks"], 17)

    async def test_flush_does_not_extend_receive_deadline(self):
        result = await scenario("flush_only")
        self.assertEqual(result["reconnect_close_at_s"], 65)

    async def test_invalid_prices_do_not_extend_receive_deadline(self):
        result = await scenario("invalid_messages")
        self.assertEqual(result["reconnect_close_at_s"], 65)

    async def test_connection_without_first_callback_times_out(self):
        result = await scenario("no_callback")
        self.assertEqual(result["reconnect_close_at_s"], 65)

    async def test_first_ticker_replaces_initial_grace_deadline(self):
        result = await scenario("late_first_ticker")
        self.assertEqual(result["ticks"], 1)
        self.assertEqual(result["reconnect_close_at_s"], 85)

    async def test_valid_callbacks_from_another_thread_keep_feed_fresh(self):
        result = await scenario("threaded_price")
        self.assertEqual(result["ticks"], 17)
        self.assertIsNone(result["reconnect_close_at_s"])

    async def test_forward_wall_clock_jump_does_not_change_deadline(self):
        result = await scenario("residual_ticker", wall_shift=86400)
        self.assertEqual(result["reconnect_close_at_s"], 65)

    async def test_backward_wall_clock_jump_does_not_change_deadline(self):
        result = await scenario("residual_ticker", wall_shift=-86400)
        self.assertEqual(result["reconnect_close_at_s"], 65)


if __name__ == "__main__":
    unittest.main()
