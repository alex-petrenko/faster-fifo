import logging
import multiprocessing
from queue import Full, Empty
from unittest import TestCase

from faster_fifo import Queue
import faster_fifo_reduction


ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)

log = logging.getLogger('rl')
log.setLevel(logging.DEBUG)
log.handlers = []  # No duplicated handlers
log.propagate = False  # workaround for duplicated logs in ipython
log.addHandler(ch)

MSG_SIZE = 5


# I think we don't need this anymore (check!)
# if sys.version_info >= (3, 8) and sys.platform == 'darwin':
#     multiprocessing.set_start_method('fork')


def make_msg(msg_idx):
    return (msg_idx,) * MSG_SIZE


def produce(q, p_idx, num_messages):
    i = 0
    while i < num_messages:
        try:
            q.put(make_msg(i), timeout=0.01)
            if i % 50000 == 0:
                log.info('Produce: %d %d', i, p_idx)
            i += 1
        except Full:
            # time.sleep(0.001)
            pass
        except Exception as exc:
            log.exception(exc)
    log.info('Done! %d', p_idx)


def consume(q, p_idx, consume_many, total_num_messages=int(1e9)):
    messages_received = 0
    while True:
        try:
            msgs = q.get_many(timeout=0.01, max_messages_to_get=consume_many)
            for msg in msgs:
                messages_received += 1
                if msg[0] % 50000 == 0:
                    log.info('Consume: %r %d num_msgs: %d', msg, p_idx, len(msgs))
            if messages_received >= total_num_messages:
                break
        except Empty:
            if q.is_closed():
                break
        except Exception as exc:
            log.exception(exc)
    log.info('Done! %d', p_idx)


class TestFastQueue(TestCase):
    def test_singleproc(self):
        q = Queue()
        produce(q, 0, num_messages=20)
        consume(q, 0, consume_many=2, total_num_messages=20)
        q.close()

    def test_multiproc(self):
        q = Queue()
        consume_many = 1000
        producers = []
        consumers = []
        for j in range(20):
            p = multiprocessing.Process(target=produce, args=(q, j, 1000001))
            producers.append(p)
        for j in range(3):
            p = multiprocessing.Process(target=consume, args=(q, j, consume_many))
            consumers.append(p)
        for c in consumers:
            c.start()
        for p in producers:
            p.start()
        for p in producers:
            p.join()
        q.close()
        for c in consumers:
            c.join()
        log.info('Exit...')

    def test_msg(self):
        q = Queue(max_size_bytes=1000)

        py_obj = dict(a=42, b=33, c=(1, 2, 3), d=[1, 2, 3], e='123', f=b'kkk')
        q.put_nowait(py_obj)
        res = q.get_nowait()
        log.debug('got object %r', res)
        self.assertEqual(py_obj, res)

    def test_msg_many(self):
        q = Queue(max_size_bytes=100000)

        py_objs = [dict(a=42, b=33, c=(1, 2, 3), d=[1, 2, 3], e='123', f=b'kkk') for _ in range(5)]
        q.put_many_nowait(py_objs)
        res = q.get_many_nowait()

        while not q.empty():
            res.extend(q.get_many_nowait())

        log.debug('Got object %r', res)
        self.assertEqual(py_objs, res)

        q.put_nowait(py_objs)
        res = q.get_nowait()
        self.assertEqual(py_objs, res)

    def test_queue_size(self):
        q = Queue(max_size_bytes=1000)
        py_obj_1 = dict(a=10, b=20)
        py_obj_2 = dict(a=30, b=40)
        q.put_nowait(py_obj_1)
        q.put_nowait(py_obj_2)
        q_size_bef = q.qsize()
        log.debug('Queue size after put -  %d', q_size_bef)
        num_messages = 0
        want_to_read = 2
        while num_messages < want_to_read:
            msgs = q.get_many()
            print(msgs)
            num_messages += len(msgs)
        self.assertEqual(type(q_size_bef), int)
        q_size_af = q.qsize()
        log.debug('Queue size after get -  %d', q_size_af)
        self.assertEqual(q_size_af, 0)

    def test_queue_empty(self):
        q = Queue(max_size_bytes=1000)
        self.assertTrue(q.empty())
        py_obj = dict(a=42, b=33, c=(1, 2, 3), d=[1, 2, 3], e='123', f=b'kkk')
        q.put_nowait(py_obj)
        q_empty = q.empty()
        self.assertFalse(q_empty)

    def test_queue_full(self):
        q = Queue(max_size_bytes=60)
        self.assertFalse(q.full())
        py_obj = (1, 2)
        while True:
            try:
                q.put_nowait(py_obj)
            except Full:
                self.assertTrue(q.full())
                break

    def test_queue_usage(self):
        q = Queue(1000 * 1000)  # specify the size of the circular buffer in the ctor

        # any pickle-able Python object can be added to the queue
        py_obj = dict(a=42, b=33, c=(1, 2, 3), d=[1, 2, 3], e='123', f=b'kkk')
        q.put(py_obj)
        assert q.qsize() == 1

        retrieved = q.get()
        assert q.empty()
        assert py_obj == retrieved

        for i in range(100):
            try:
                q.put(py_obj, timeout=0.1)
            except Full:
                log.debug('Queue is full!')

        num_received = 0
        while num_received < 100:
            # get multiple messages at once, returns a list of messages for better performance in many-to-few scenarios
            # get_many does not guarantee that all max_messages_to_get will be received on the first call, in fact
            # no such guarantee can be made in multiprocessing systems.
            # get_many() will retrieve as many messages as there are available AND can fit in the pre-allocated memory
            # buffer. The size of the buffer is increased gradually to match demand.
            messages = q.get_many(max_messages_to_get=100)
            num_received += len(messages)

        try:
            q.get(timeout=0.1)
            assert True, 'This won\'t be called'
        except Empty:
            log.debug('Queue is empty')


def spawn_producer(data_q_):
    for i in range(10):
        data = [1, 2, 3, i]
        data_q_.put(data)


def spawn_consumer(data_q_):
    i = 0
    while True:
        try:
            data = data_q_.get(timeout=0.5)
            print(data)
            i += 1
        except Empty:
            print('Read', i, 'messages')
            break


class TestSpawn(TestCase):
    def test_spawn_ctx(self):
        ctx = multiprocessing.get_context('spawn')
        data_q = Queue(1000 * 1000)
        procs = [
            ctx.Process(target=spawn_producer, args=(data_q,)) for _ in range(2)
        ]
        procs.append(ctx.Process(target=spawn_consumer, args=(data_q,)))

        # add data to the queue and read some of it back to make sure all buffers are initialized before
        # the new process is spawned (such that we need to pickle everything)
        for i in range(10):
            data_q.put(self.test_spawn_ctx.__name__)
        msgs = data_q.get_many(max_messages_to_get=2)
        print(msgs)

        for p in procs:
            p.start()
        for p in procs:
            p.join()
