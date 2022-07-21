import logging
import multiprocessing
from queue import Full, Empty
from time import time
from unittest import TestCase
import ctypes

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


def consume_msgs(q, p_idx, all_msgs_sent, consume_many=1):
    num_received = 0
    while True:
        try:
            if consume_many == 1:
                msg = q.get(timeout=0.01)
                msgs = [msg]
            else:
                msgs = q.get_many(timeout=0.01, max_messages_to_get=consume_many)

            for msg in msgs:
                if msg[0] % 50000 == 0:
                    log.info('Consume: %r %d num_msgs: %d total received: %d', msg, p_idx, len(msgs), num_received)
                num_received += 1

        except Empty:
            if all_msgs_sent.value:
                break
        except Exception as exc:
            log.exception(exc)


def run_test(queue_cls, num_producers, num_consumers, msgs_per_prod, consume_many):
    start_time = time()
    q = queue_cls(100000)

    producers = []
    consumers = []
    all_msgs_sent = multiprocessing.RawValue(ctypes.c_bool, False)
    for j in range(num_producers):
        p = multiprocessing.Process(target=produce_msgs, args=(q, j, msgs_per_prod))
        producers.append(p)
    for j in range(num_consumers):
        p = multiprocessing.Process(target=consume_msgs, args=(q, j, all_msgs_sent, consume_many))
        consumers.append(p)
    for p in producers:
        p.start()
    for c in consumers:
        c.start()
    for p in producers:
        p.join()
    all_msgs_sent.value = True
    for c in consumers:
        c.join()
    q.close()
    log.info('Exiting queue type %s', queue_cls.__module__ + '.' + queue_cls.__name__)
    end_time = time()
    time_taken = end_time - start_time
    log.info('Time taken by queue type %s is %.5f', queue_cls.__module__ + '.' + queue_cls.__name__, time_taken)
    return time_taken


class ComparisonTestCase(TestCase):
    @staticmethod
    def comparison(n_prod, n_con, n_msgs):
        n_msgs += 1  # +1 here to make sure the last log line will be printed
        time_ff = run_test(Queue, num_producers=n_prod, num_consumers=n_con, msgs_per_prod=n_msgs, consume_many=1)
        time_ff_many = run_test(Queue, num_producers=n_prod, num_consumers=n_con, msgs_per_prod=n_msgs,
                                consume_many=100)
        time_mp = run_test(multiprocessing.Queue, num_producers=n_prod, num_consumers=n_con, msgs_per_prod=n_msgs,
                           consume_many=1)

        if time_ff > time_mp:
            log.warning(f'faster-fifo took longer than mp.Queue ({time_ff=} vs {time_mp=}) on configuration ({n_prod}, {n_con}, {n_msgs})')
        if time_ff_many > time_mp:
            log.warning(f'faster-fifo get_many() took longer than mp.Queue ({time_ff_many=} vs {time_mp=}) on configuration ({n_prod}, {n_con}, {n_msgs})')

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


# i9-7900X (10-core CPU)
# [2020-05-16 03:24:26,548][30412] Configuration (1, 1, 200000), timing [ff: 0.92s, ff_many: 0.93s, mp.queue: 2.83s]
# [2020-05-16 03:24:26,548][30412] Configuration (1, 10, 200000), timing [ff: 1.43s, ff_many: 1.40s, mp.queue: 7.60s]
# [2020-05-16 03:24:26,548][30412] Configuration (10, 1, 100000), timing [ff: 4.95s, ff_many: 1.40s, mp.queue: 12.24s]
# [2020-05-16 03:24:26,548][30412] Configuration (3, 20, 100000), timing [ff: 2.29s, ff_many: 2.25s, mp.queue: 13.25s]
# [2020-05-16 03:24:26,548][30412] Configuration (20, 3, 50000), timing [ff: 3.19s, ff_many: 1.12s, mp.queue: 29.07s]
# [2020-05-16 03:24:26,548][30412] Configuration (20, 20, 50000), timing [ff: 1.65s, ff_many: 4.14s, mp.queue: 46.71s]

# With Erik's changes to prevent stale (version 1.1.2)
# [2021-05-14 00:51:46,237][25370] Configuration (1, 1, 200000), timing [ff: 1.05s, ff_many: 1.10s, mp.queue: 2.32s]
# [2021-05-14 00:51:46,237][25370] Configuration (1, 10, 200000), timing [ff: 1.49s, ff_many: 1.51s, mp.queue: 3.31s]
# [2021-05-14 00:51:46,237][25370] Configuration (10, 1, 100000), timing [ff: 6.07s, ff_many: 0.97s, mp.queue: 12.92s]
# [2021-05-14 00:51:46,237][25370] Configuration (3, 20, 100000), timing [ff: 2.27s, ff_many: 2.19s, mp.queue: 6.55s]
# [2021-05-14 00:51:46,237][25370] Configuration (20, 3, 50000), timing [ff: 7.65s, ff_many: 0.70s, mp.queue: 15.40s]
# [2021-05-14 00:51:46,237][25370] Configuration (20, 20, 50000), timing [ff: 1.82s, ff_many: 4.14s, mp.queue: 31.65s]
# Ran 1 test in 103.115s

# Ubuntu 20, Python 3.9, version 1.3.1
# For some reason (10, 1) configuration became 2x slower. This does not seem to be any kind of regression in the code
# because it also reproduces in older versions on my new system. Seems to be caused by Python environment/Linux version/compiler?
# [2022-03-31 02:28:18,986][549096] Configuration (1, 1, 200000), timing [ff: 1.06s, ff_many: 1.06s, mp.queue: 2.10s]
# [2022-03-31 02:28:18,986][549096] Configuration (1, 10, 200000), timing [ff: 1.51s, ff_many: 1.52s, mp.queue: 2.96s]
# [2022-03-31 02:28:18,986][549096] Configuration (10, 1, 100000), timing [ff: 13.10s, ff_many: 0.99s, mp.queue: 11.54s]
# [2022-03-31 02:28:18,987][549096] Configuration (3, 20, 100000), timing [ff: 3.04s, ff_many: 2.22s, mp.queue: 7.19s]
# [2022-03-31 02:28:18,987][549096] Configuration (20, 3, 50000), timing [ff: 14.80s, ff_many: 0.67s, mp.queue: 15.29s]
# [2022-03-31 02:28:18,987][549096] Configuration (20, 20, 50000), timing [ff: 1.33s, ff_many: 3.91s, mp.queue: 21.46s]
# Ran 1 test in 105.765s

# Ubuntu 20, Python 3.8, version 1.4.1
# [2022-07-21 01:32:09,831][2374340] Configuration (1, 1, 200000), timing [ff: 1.13s, ff_many: 1.10s, mp.queue: 2.20s]
# [2022-07-21 01:32:09,831][2374340] Configuration (1, 10, 200000), timing [ff: 1.72s, ff_many: 1.69s, mp.queue: 3.51s]
# [2022-07-21 01:32:09,831][2374340] Configuration (10, 1, 100000), timing [ff: 13.71s, ff_many: 1.28s, mp.queue: 12.16s]
# [2022-07-21 01:32:09,831][2374340] Configuration (3, 20, 100000), timing [ff: 3.18s, ff_many: 2.29s, mp.queue: 7.81s]
# [2022-07-21 01:32:09,831][2374340] Configuration (20, 3, 50000), timing [ff: 15.47s, ff_many: 0.75s, mp.queue: 17.52s]
# [2022-07-21 01:32:09,831][2374340] Configuration (20, 20, 50000), timing [ff: 1.26s, ff_many: 3.74s, mp.queue: 27.82s]
# Ran 1 test in 118.350s


# i5-4200U (dual-core CPU)
# [2020-05-22 18:03:55,061][09146] Configuration (1, 1, 200000), timing [ff: 2.09s, ff_many: 2.20s, mp.queue: 7.86s]
# [2020-05-22 18:03:55,061][09146] Configuration (1, 10, 200000), timing [ff: 4.01s, ff_many: 3.88s, mp.queue: 11.68s]
# [2020-05-22 18:03:55,061][09146] Configuration (10, 1, 100000), timing [ff: 16.68s, ff_many: 5.98s, mp.queue: 44.48s]
# [2020-05-22 18:03:55,061][09146] Configuration (3, 20, 100000), timing [ff: 7.83s, ff_many: 7.49s, mp.queue: 22.59s]
# [2020-05-22 18:03:55,061][09146] Configuration (20, 3, 50000), timing [ff: 22.30s, ff_many: 6.35s, mp.queue: 66.30s]
# [2020-05-22 18:03:55,061][09146] Configuration (20, 20, 50000), timing [ff: 14.39s, ff_many: 15.78s, mp.queue: 78.75s]
