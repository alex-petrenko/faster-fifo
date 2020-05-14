import multiprocessing
from unittest import TestCase
from faster_fifo import Queue
from time import time
from queue import Full, Empty
import logging

ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)

log = logging.getLogger('rl')
log.setLevel(logging.DEBUG)
log.handlers = []  # No duplicated handlers
log.propagate = False  # workaround for duplicated logs in ipython
log.addHandler(ch)

MSG_SIZE = 5


def make_msg(msg_idx):
    return (msg_idx,) * MSG_SIZE


def produce_msgs(q, p_idx, num_messages):
    i = 0
    while i < num_messages:
        try:
            q.put(make_msg(i), timeout=0.01)
            if i % 100000 == 0:
                log.info('Produce: %d %d', i, p_idx)
            i += 1
        except Full:
            # time.sleep(0.001)
            pass
        except Exception as exc:
            log.exception(exc)
    log.info('Done producing! %d', p_idx)


def consume_msgs(q, queue_type, p_idx, consume_many=None, total_num_messages=int(1e9)):
    messages_received = 0
    while True:
        try:
            msgs = q.get_many(timeout=0.01, max_messages_to_get=consume_many) if queue_type == 'ff' else q.get()
            if queue_type == 'mp' and msgs is None:
                break
            messages_received += len(msgs) if queue_type == 'ff' else 1
            if messages_received >= total_num_messages:
                break
        except Empty:
            if q.empty():
                break
        except Exception as exc:
            log.exception(exc)
    log.info('Done consuming! %d', p_idx)


def process_prod_and_cons(queue_type, num_producers, num_consumers, msgs_per_prod, consume_many=None):
    start_time = time()
    q = Queue(max_size_bytes=20000000) if queue_type == 'ff' else multiprocessing.Queue()
    producers = []
    consumers = []
    for j in range(num_producers):
        p = multiprocessing.Process(target=produce_msgs, args=(q, j, msgs_per_prod))
        producers.append(p)
    for j in range(num_consumers):
        p = multiprocessing.Process(target=consume_msgs, args=(q, queue_type, j, consume_many))
        consumers.append(p)
    for p in producers:
        p.start()
    for c in consumers:
        c.start()
    for p in producers:
        p.join()
    if queue_type == 'mp':
        for j in range(num_consumers):
            q.put(None)
    for c in consumers:
        c.join()
    q.close()
    log.info('Exiting queue type ' + queue_type)
    end_time = time()
    return round(end_time - start_time, 5)


class ComparisonTestsWithConsumeManyAtOne(TestCase):

    def test_one_prod_to_one_cons(self):
        time_ff = process_prod_and_cons(queue_type='ff', num_producers=1, num_consumers=1, msgs_per_prod=500000,
                                        consume_many=1)
        time_mp = process_prod_and_cons(queue_type='mp', num_producers=1, num_consumers=1, msgs_per_prod=500000,
                                        consume_many=None)
        self.assertLess(time_ff, time_mp)

    def test_one_prod_to_ten_cons(self):
        time_ff = process_prod_and_cons(queue_type='ff', num_producers=1, num_consumers=10, msgs_per_prod=500000,
                                        consume_many=1)
        time_mp = process_prod_and_cons(queue_type='mp', num_producers=1, num_consumers=10, msgs_per_prod=500000,
                                        consume_many=None)
        self.assertLess(time_ff, time_mp)

    def test_ten_prod_to_one_cons(self):
        time_ff = process_prod_and_cons(queue_type='ff', num_producers=10, num_consumers=1, msgs_per_prod=50000,
                                        consume_many=1)
        time_mp = process_prod_and_cons(queue_type='mp', num_producers=10, num_consumers=1, msgs_per_prod=50000,
                                        consume_many=None)
        self.assertLess(time_ff, time_mp)

    def test_three_prod_to_twenty_cons(self):
        time_ff = process_prod_and_cons(queue_type='ff', num_producers=3, num_consumers=20, msgs_per_prod=100000,
                                        consume_many=1)
        time_mp = process_prod_and_cons(queue_type='mp', num_producers=3, num_consumers=20, msgs_per_prod=100000,
                                        consume_many=None)
        self.assertLess(time_ff, time_mp)

    def test_twenty_prod_to_three_cons(self):
        time_ff = process_prod_and_cons(queue_type='ff', num_producers=20, num_consumers=3, msgs_per_prod=25000,
                                        consume_many=1)
        time_mp = process_prod_and_cons(queue_type='mp', num_producers=20, num_consumers=3, msgs_per_prod=25000,
                                        consume_many=None)
        self.assertLess(time_ff, time_mp)

    def test_twenty_prod_to_twenty_cons(self):
        time_ff = process_prod_and_cons(queue_type='ff', num_producers=20, num_consumers=20, msgs_per_prod=25000,
                                        consume_many=1)
        time_mp = process_prod_and_cons(queue_type='mp', num_producers=20, num_consumers=20, msgs_per_prod=25000,
                                        consume_many=None)
        self.assertLess(time_ff, time_mp)


class ComparisonTestsWithConsumeManyAtHundred(TestCase):

    def test_one_prod_to_one_cons(self):
        time_ff = process_prod_and_cons(queue_type='ff', num_producers=1, num_consumers=1, msgs_per_prod=500000,
                                        consume_many=100)
        time_mp = process_prod_and_cons(queue_type='mp', num_producers=1, num_consumers=1, msgs_per_prod=500000,
                                        consume_many=None)
        self.assertLess(time_ff, time_mp)

    def test_one_prod_to_ten_cons(self):
        time_ff = process_prod_and_cons(queue_type='ff', num_producers=1, num_consumers=10, msgs_per_prod=500000,
                                        consume_many=100)
        time_mp = process_prod_and_cons(queue_type='mp', num_producers=1, num_consumers=10, msgs_per_prod=500000,
                                        consume_many=None)
        self.assertLess(time_ff, time_mp)

    def test_ten_prod_to_one_cons(self):
        time_ff = process_prod_and_cons(queue_type='ff', num_producers=10, num_consumers=1, msgs_per_prod=50000,
                                        consume_many=100)
        time_mp = process_prod_and_cons(queue_type='mp', num_producers=10, num_consumers=1, msgs_per_prod=50000,
                                        consume_many=None)
        self.assertLess(time_ff, time_mp)

    def test_three_prod_to_twenty_cons(self):
        time_ff = process_prod_and_cons(queue_type='ff', num_producers=3, num_consumers=20, msgs_per_prod=100000,
                                        consume_many=100)
        time_mp = process_prod_and_cons(queue_type='mp', num_producers=3, num_consumers=20, msgs_per_prod=100000,
                                        consume_many=None)
        self.assertLess(time_ff, time_mp)

    def test_twenty_prod_to_three_cons(self):
        time_ff = process_prod_and_cons(queue_type='ff', num_producers=20, num_consumers=3, msgs_per_prod=25000,
                                        consume_many=100)
        time_mp = process_prod_and_cons(queue_type='mp', num_producers=20, num_consumers=3, msgs_per_prod=25000,
                                        consume_many=None)
        self.assertLess(time_ff, time_mp)

    def test_twenty_prod_to_twenty_cons(self):
        time_ff = process_prod_and_cons(queue_type='ff', num_producers=20, num_consumers=20, msgs_per_prod=25000,
                                        consume_many=100)
        time_mp = process_prod_and_cons(queue_type='mp', num_producers=20, num_consumers=20, msgs_per_prod=25000,
                                        consume_many=None)
        self.assertLess(time_ff, time_mp)
