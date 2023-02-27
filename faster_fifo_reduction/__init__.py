"""
Old workaround for threading.local not being picklable.
Solved now by overriding __getstate__ and __setstate__ in TLSBuffer.

Keeping this file around for now so that user code that imports this module
doesn't break. Should be deprecated in the future.
"""

# from multiprocessing import context
#
# import faster_fifo
#
# _ForkingPickler = context.reduction.ForkingPickler
#
#
# def rebuild_queue(newstate, message_buffer_size):
#     q = faster_fifo.Queue.__new__(faster_fifo.Queue)
#     q.__dict__.update(newstate)
#     q.message_buffer = faster_fifo.TLSBuffer(None)
#     q.reallocate_msg_buffer(message_buffer_size)
#     return q
#
#
# def reduce_queue(q):
#     state = q.__dict__.copy()
#     message_buffer_size = 0 if q.message_buffer.val is None else len(q.message_buffer.val)
#     state['message_buffer'] = None
#     return rebuild_queue, (state, message_buffer_size)
#
#
# _ForkingPickler.register(faster_fifo.Queue, reduce_queue)
