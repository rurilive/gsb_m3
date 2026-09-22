"""串行 Session 的基线测试，锁住现有请求-响应语义。"""

import unittest

from linkmux.errors import StreamReset, StreamStateError
from linkmux.frame import Frame, FrameBuffer, KIND_DATA, KIND_FIN, KIND_PING, KIND_RESET
from linkmux.session import Message, Session, pump_all
from linkmux.transport import ManualClock, MemoryLink


class SessionTestCase(unittest.TestCase):
    def setUp(self):
        self.a, self.b = MemoryLink.pair(clock=ManualClock(), names=("client", "server"))
        self.client, self.server = Session(self.a), Session(self.b)

    def exchange(self, payload, response=None):
        stream_id = self.client.send_request(payload)
        pump_all(self.client, self.server)
        request = self.server.take_request()
        self.assertIsNotNone(request)
        self.server.send_response(request.stream_id, request.payload if response is None else response)
        pump_all(self.client, self.server)
        return stream_id, self.client.take_response()


class RoundTripTest(SessionTestCase):
    def test_echo_round_trip_empty_payload_stream_ids_and_ping(self):
        stream_id, response = self.exchange(b"ping")
        self.assertEqual(response, Message(stream_id, b"ping"))
        self.assertEqual(self.exchange(b"")[1], Message(3, b""))
        self.assertEqual((self.exchange(b"one")[0], self.exchange(b"two")[0]), (5, 7))
        self.b.send_frame(Frame(0, KIND_PING, b"tick"))
        self.assertEqual(self.client.pump(), 1)
        self.assertIsNone(self.client.take_response())

    def test_server_can_answer_different_payload_in_few_rounds(self):
        self.client.send_request(b"q")
        self.assertLessEqual(pump_all(self.client, self.server), 4)
        request = self.server.take_request()
        self.server.send_response(request.stream_id, b"answer")
        pump_all(self.client, self.server)
        self.assertEqual(self.client.take_response().payload, b"answer")


class FragmentationTest(SessionTestCase):
    def rebuild(self, limit):
        self.client, self.server = Session(self.a, frame_limit=limit), Session(self.b, frame_limit=limit)

    def test_large_payload_is_split_within_limit(self):
        self.rebuild(limit=16)
        payload = bytes(range(40))
        self.client.send_request(payload)
        buffer = FrameBuffer()
        buffer.feed(self.b.recv())
        frames = buffer.drain()
        data = [f for f in frames if f.kind == KIND_DATA]
        self.assertEqual(len(data), 3)
        self.assertTrue(all(len(f.payload) <= 16 for f in data))
        self.assertEqual((frames[-1].kind, b"".join(f.payload for f in data)), (KIND_FIN, payload))
        self.rebuild(limit=7)
        long_payload = b"abcdefghijklmnopqrstuvwxyz0123456789"
        self.assertEqual(self.exchange(long_payload)[1].payload, long_payload)

    def test_frame_limit_out_of_range_rejected(self):
        for limit in (0, 4096):
            with self.assertRaises(ValueError):
                Session(self.a, frame_limit=limit)


class GuardAndResetTest(SessionTestCase):
    def test_second_request_and_double_response_rejected(self):
        self.client.send_request(b"first")
        with self.assertRaises(StreamStateError):
            self.client.send_request(b"second")
        pump_all(self.client, self.server)
        request = self.server.take_request()
        self.server.send_response(request.stream_id, b"ok")
        with self.assertRaises(StreamStateError):
            self.server.send_response(request.stream_id, b"again")

    def test_reset_during_flight_and_reset_of_unknown_stream(self):
        stream_id = self.client.send_request(b"q")
        self.b.send_frame(Frame(stream_id, KIND_RESET))
        self.b.send_frame(Frame(101, KIND_RESET))
        self.assertEqual(self.client.pump(), 2)
        with self.assertRaises(StreamReset) as caught:
            self.client.take_response()
        self.assertEqual(caught.exception.stream_id, stream_id)
        self.assertIsNone(self.client.take_response())


if __name__ == "__main__":
    unittest.main()
