from multiprocessing import context

import faster_fifo

_ForkingPickler = context.reduction.ForkingPickler


def rebuild_queue(newstate, message_buffer_size):
    q = faster_fifo.Queue.__new__(faster_fifo.Queue)
    q.__dict__.update(newstate)
    q.reallocate_msg_buffer(message_buffer_size)
    return q


def reduce_queue(q):
    state = q.__dict__.copy()
    message_buffer_size = 0 if q.message_buffer is None else len(q.message_buffer)
    state['message_buffer'] = None
    state['message_buffer_memview'] = None
    return rebuild_queue, (state, message_buffer_size)


_ForkingPickler.register(faster_fifo.Queue, reduce_queue)
