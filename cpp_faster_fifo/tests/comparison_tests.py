import logging
import multiprocessing
from queue import Full, Empty
from time import time
from unittest import TestCase

from faster_fifo import Queue

ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)

fmt = logging.Formatter('[%(asctime)s][%(process)05d] %(message)s')
ch.setFormatter(fmt)

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
            if i % 50000 == 0:
                log.info('Produce: %d %d', i, p_idx)
            i += 1
        except Full:
            pass
        except Exception as exc:
            log.exception(exc)


def consume_msgs(q, p_idx, consume_many=1):
    num_received = 0

    while True:
        try:
            if consume_many == 1:
                msg = q.get(timeout=0.01)
                msgs = [msg]
            else:
                msgs = q.get_many(timeout=0.01, max_messages_to_get=10)

            if any(m is None for m in msgs):
                break

            for msg in msgs:
                if msg[0] % 50000 == 0:
                    log.info('Consume: %r %d num_msgs: %d total received: %d', msg, p_idx, len(msgs), num_received)
                num_received += 1

        except Empty:
            pass
        except Exception as exc:
            log.exception(exc)


def run_test(queue_cls, num_producers, num_consumers, msgs_per_prod, consume_many):
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
    def comparison(self, n_prod, n_con, n_msgs):
        n_msgs += 1  # +1 here to make sure the last log line will be printed
        time_ff = run_test(Queue, num_producers=n_prod, num_consumers=n_con, msgs_per_prod=n_msgs, consume_many=1)
        time_ff_many = run_test(Queue, num_producers=n_prod, num_consumers=n_con, msgs_per_prod=n_msgs, consume_many=100)
        time_mp = run_test(multiprocessing.Queue, num_producers=n_prod, num_consumers=n_con, msgs_per_prod=n_msgs, consume_many=1)
        self.assertLess(time_ff, time_mp)
        self.assertLess(time_ff_many, time_mp)
        return time_ff, time_ff_many, time_mp

    def test_all_configurations(self):
        configurations = (
            (1, 1, 200000),
            (1, 10, 200000),
            (10, 1, 100000),
            (3, 20, 100000),
            (20, 3, 50000),
            (20, 20, 50000),
        )

        results = []
        for c in configurations:
            results.append(self.comparison(*c))

        log.info('\nResults:\n')
        for c, r in zip(configurations, results):
            log.info('Configuration %r, timing [ff: %.2fs, ff_many: %.2fs, mp.queue: %.2fs]', c, *r)


# [2020-05-16 03:24:26,548][30412] Configuration (1, 1, 200000), timing [ff: 0.92s, ff_many: 0.93s, mp.queue: 2.83s]
# [2020-05-16 03:24:26,548][30412] Configuration (1, 10, 200000), timing [ff: 1.43s, ff_many: 1.40s, mp.queue: 7.60s]
# [2020-05-16 03:24:26,548][30412] Configuration (10, 1, 100000), timing [ff: 4.95s, ff_many: 1.40s, mp.queue: 12.24s]
# [2020-05-16 03:24:26,548][30412] Configuration (3, 20, 100000), timing [ff: 2.29s, ff_many: 2.25s, mp.queue: 13.25s]
# [2020-05-16 03:24:26,548][30412] Configuration (20, 3, 50000), timing [ff: 3.19s, ff_many: 1.12s, mp.queue: 29.07s]
# [2020-05-16 03:24:26,548][30412] Configuration (20, 20, 50000), timing [ff: 1.65s, ff_many: 4.14s, mp.queue: 46.71s]
