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
            pass
        except Exception as exc:
            log.exception(exc)
    log.info('Done producing! %d', p_idx)


def consume_msgs(q, p_idx, consume_many=1):
    while True:
        try:
            if consume_many == 1:
                msg = q.get()
                msgs = [msg]
            else:
                msgs = q.get_many(max_messages_to_get=consume_many)
            if any(m is None for m in msgs):
                break
        except Empty:
            pass
        except Exception as exc:
            log.exception(exc)
    log.info('Done consuming! %d', p_idx)


def process_prod_and_cons(queue_cls, num_producers, num_consumers, msgs_per_prod, consume_many=1):
    start_time = time()
    q = queue_cls(20000000)
    producers = []
    consumers = []
    for j in range(num_producers):
        p = multiprocessing.Process(target=produce_msgs, args=(q, j, msgs_per_prod))
        producers.append(p)
    for j in range(num_consumers):
        p = multiprocessing.Process(target=consume_msgs, args=(q, j, consume_many))
        consumers.append(p)
    for p in producers:
        p.start()
    for c in consumers:
        c.start()
    for p in producers:
        p.join()
    for j in range(num_consumers * consume_many):
        q.put(None)
    for c in consumers:
        c.join()
    q.close()
    log.info('Exiting queue type %s', queue_cls.__module__ + '.' + queue_cls.__name__)
    end_time = time()
    time_taken = end_time - start_time
    log.info('Time taken by queue type %s is %.5f', queue_cls.__module__ + '.' + queue_cls.__name__, time_taken)
    return time_taken


class ComparisonTestCase(TestCase):

    def test_one_prod_to_one_cons(self):
        time_ff = process_prod_and_cons(Queue, num_producers=1, num_consumers=1, msgs_per_prod=500000,
                                        consume_many=1)
        time_mp = process_prod_and_cons(multiprocessing.Queue, num_producers=1, num_consumers=1,
                                        msgs_per_prod=500000, consume_many=1)
        self.assertLess(time_ff, time_mp)

    def test_one_prod_to_ten_cons(self):
        time_ff = process_prod_and_cons(Queue, num_producers=1, num_consumers=10, msgs_per_prod=500000,
                                        consume_many=1)
        time_mp = process_prod_and_cons(multiprocessing.Queue, num_producers=1, num_consumers=10, msgs_per_prod=500000,
                                        consume_many=1)
        self.assertLess(time_ff, time_mp)

    def test_ten_prod_to_one_cons(self):
        time_ff = process_prod_and_cons(Queue, num_producers=10, num_consumers=1, msgs_per_prod=50000,
                                        consume_many=1)
        time_mp = process_prod_and_cons(multiprocessing.Queue, num_producers=10, num_consumers=1, msgs_per_prod=50000,
                                        consume_many=1)
        self.assertLess(time_ff, time_mp)

    def test_three_prod_to_twenty_cons(self):
        time_ff = process_prod_and_cons(Queue, num_producers=3, num_consumers=20, msgs_per_prod=100000,
                                        consume_many=1)
        time_mp = process_prod_and_cons(multiprocessing.Queue, num_producers=3, num_consumers=20, msgs_per_prod=100000,
                                        consume_many=1)
        self.assertLess(time_ff, time_mp)

    def test_twenty_prod_to_three_cons(self):
        time_ff = process_prod_and_cons(Queue, num_producers=20, num_consumers=3, msgs_per_prod=25000,
                                        consume_many=1)
        time_mp = process_prod_and_cons(multiprocessing.Queue, num_producers=20, num_consumers=3, msgs_per_prod=25000,
                                        consume_many=1)
        self.assertLess(time_ff, time_mp)

    def test_twenty_prod_to_twenty_cons(self):
        time_ff = process_prod_and_cons(Queue, num_producers=20, num_consumers=20, msgs_per_prod=25000,
                                        consume_many=1)
        time_mp = process_prod_and_cons(multiprocessing.Queue, num_producers=20, num_consumers=20, msgs_per_prod=25000,
                                        consume_many=1)
        self.assertLess(time_ff, time_mp)

    def test_one_prod_to_one_cons_consume_multiple(self):
        time_ff_many = process_prod_and_cons(Queue, num_producers=1, num_consumers=1, msgs_per_prod=500000,
                                             consume_many=100)
        time_mp = process_prod_and_cons(multiprocessing.Queue, num_producers=1, num_consumers=1, msgs_per_prod=500000,
                                        consume_many=1)
        self.assertLess(time_ff_many, time_mp)

    def test_one_prod_to_ten_cons_consume_multiple(self):
        time_ff_many = process_prod_and_cons(Queue, num_producers=1, num_consumers=10, msgs_per_prod=500000,
                                             consume_many=100)
        time_mp = process_prod_and_cons(multiprocessing.Queue, num_producers=1, num_consumers=10, msgs_per_prod=500000,
                                        consume_many=1)
        self.assertLess(time_ff_many, time_mp)

    def test_ten_prod_to_one_cons_consume_multiple(self):
        time_ff_many = process_prod_and_cons(Queue, num_producers=10, num_consumers=1, msgs_per_prod=50000,
                                             consume_many=100)
        time_mp = process_prod_and_cons(multiprocessing.Queue, num_producers=10, num_consumers=1, msgs_per_prod=50000,
                                        consume_many=1)
        self.assertLess(time_ff_many, time_mp)

    def test_three_prod_to_twenty_cons_consume_multiple(self):
        time_ff_many = process_prod_and_cons(Queue, num_producers=3, num_consumers=20, msgs_per_prod=100000,
                                             consume_many=100)
        time_mp = process_prod_and_cons(multiprocessing.Queue, num_producers=3, num_consumers=20, msgs_per_prod=100000,
                                        consume_many=1)
        self.assertLess(time_ff_many, time_mp)

    def test_twenty_prod_to_three_cons_consume_multiple(self):
        time_ff_many = process_prod_and_cons(Queue, num_producers=20, num_consumers=3, msgs_per_prod=25000,
                                             consume_many=100)
        time_mp = process_prod_and_cons(multiprocessing.Queue, num_producers=20, num_consumers=3, msgs_per_prod=25000,
                                        consume_many=1)
        self.assertLess(time_ff_many, time_mp)

    def test_twenty_prod_to_twenty_cons_consume_multiple(self):
        time_ff_many = process_prod_and_cons(Queue, num_producers=20, num_consumers=20, msgs_per_prod=25000,
                                             consume_many=100)
        time_mp = process_prod_and_cons(multiprocessing.Queue, num_producers=20, num_consumers=20, msgs_per_prod=25000,
                                        consume_many=1)
        self.assertLess(time_ff_many, time_mp)
