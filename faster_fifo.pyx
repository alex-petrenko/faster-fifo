# cython: language_level=3
# cython: boundscheck=False
# cython: infer_types=False

import ctypes
import multiprocessing
import time

from ctypes import c_size_t
from multiprocessing import context
from queue import Full, Empty

_ForkingPickler = context.reduction.ForkingPickler

cimport faster_fifo_def as Q


cdef size_t q_addr(q):
    cdef size_t obj_buffer_ptr = ctypes.addressof(q.queue_obj_buffer)
    return obj_buffer_ptr


cdef size_t buf_addr(q):
    cdef size_t buffer_ptr = ctypes.addressof(q.shared_memory)
    return buffer_ptr


cdef size_t msg_buf_addr(q):
    cdef size_t buffer_ptr = ctypes.addressof(q.message_buffer)
    return buffer_ptr


cdef size_t bytes_to_ptr(b):
    ptr = ctypes.cast(b, ctypes.POINTER(ctypes.c_byte))
    return ctypes.addressof(ptr.contents)

class Queue:
    def __init__(self, max_size_bytes=200000):
        self.max_size_bytes = max_size_bytes
        self.max_bytes_to_read = self.max_size_bytes  # by default, read the whole queue if necessary

        self.closed = multiprocessing.RawValue(ctypes.c_bool, False)

        queue_obj_size = Q.queue_object_size()
        self.queue_obj_buffer = multiprocessing.RawArray(ctypes.c_ubyte, queue_obj_size)
        self.shared_memory = multiprocessing.RawArray(ctypes.c_ubyte, max_size_bytes)

        Q.create_queue(<void *> q_addr(self), max_size_bytes)

        self.message_buffer = None
        self.message_buffer_memview = None

    def close(self):
        """
        This is not atomic by any means, but using locks is expensive. So this should be preferably called by
        only one process, e.g. main process.
        """
        self.closed.value = True

    def is_closed(self):
        """
        This 'closed' variable is not atomic, so changes may not immediately propagate between processes.
        This should be okay for most usecases, but if 100% reliability is required perhaps another mechanism is needed.
        """
        return self.closed.value

    def put(self, x, block=True, timeout=float(1e3)):
        x = _ForkingPickler.dumps(x).tobytes()

        # explicitly convert all function parameters to corresponding C-types
        cdef void* c_q_addr = <void*>q_addr(self)
        cdef void* c_buf_addr = <void*>buf_addr(self)
        cdef void* c_x_ptr = <void*>bytes_to_ptr(x)

        cdef size_t c_len_x = len(x)
        cdef int c_block = block
        cdef float c_timeout = timeout

        cdef int c_status = 0

        with nogil:
            c_status = Q.queue_put(
                c_q_addr, c_buf_addr, c_x_ptr, c_len_x,
                c_block, c_timeout,
            )

        status = c_status

        if status == Q.Q_SUCCESS:
            pass
        elif status == Q.Q_FULL:
            raise Full()
        else:
            raise Exception(f'Unexpected queue error {status}')

    def put_nowait(self, x):
        return self.put(x, block=False)

    def get_many(self, block=True, timeout=float(1e3), max_messages_to_get=int(1e9)):
        if self.message_buffer is None:
            self.reallocate_msg_buffer(10)  # initialize a small buffer at first, it will be increased later

        messages_read = ctypes.c_size_t(0)
        cdef size_t messages_read_ptr = ctypes.addressof(messages_read)

        bytes_read = ctypes.c_size_t(0)
        cdef size_t bytes_read_ptr = ctypes.addressof(bytes_read)

        messages_size = ctypes.c_size_t(0)  # this is how much memory we need to allocate to read more messages
        cdef size_t messages_size_ptr = ctypes.addressof(messages_size)

        # explicitly convert all function parameters to corresponding C-types
        cdef void* c_q_addr = <void*>q_addr(self)
        cdef void* c_buf_addr = <void*>buf_addr(self)
        cdef void* c_msg_buf_addr = <void*>msg_buf_addr(self)

        cdef int c_block = block
        cdef float c_timeout = timeout
        cdef size_t c_max_messages_to_get = max_messages_to_get
        cdef size_t c_max_bytes_to_read = self.max_bytes_to_read
        cdef size_t c_len_message_buffer = len(self.message_buffer)

        cdef int c_status = 0

        with nogil:
            c_status = Q.queue_get(
                c_q_addr, c_buf_addr, c_msg_buf_addr, c_len_message_buffer,
                c_max_messages_to_get, c_max_bytes_to_read,
                <size_t *>messages_read_ptr,
                <size_t *>bytes_read_ptr,
                <size_t *>messages_size_ptr,
                c_block, c_timeout,
            )

        status = c_status

        if status == Q.Q_MSG_BUFFER_TOO_SMALL and messages_read.value <= 0:
            # could not read any messages because msg buffer was too small
            # reallocate the buffer and try again
            self.reallocate_msg_buffer(int(messages_size.value * 1.5))
            return self.get_many_nowait(max_messages_to_get)
        elif status == Q.Q_SUCCESS or status == Q.Q_MSG_BUFFER_TOO_SMALL:
            # we definitely managed to read something!
            assert messages_read.value >= 1
            assert bytes_read.value >= 1
            messages = self.parse_messages(messages_read.value, bytes_read.value, self.message_buffer)

            if status == Q.Q_MSG_BUFFER_TOO_SMALL:
                # we could not read as many messages as we wanted
                # allocate a bigger buffer so next time we can read more
                self.reallocate_msg_buffer(int(messages_size.value * 1.5))

            return messages

        elif status == Q.Q_EMPTY:
            raise Empty()
        else:
            raise Exception(f'Unexpected queue error {status}')

    def get_many_nowait(self, max_messages_to_get=int(1e9)):
        return self.get_many(block=False, max_messages_to_get=max_messages_to_get)

    def get(self, block=True, timeout=float(1e3)):
        return self.get_many(block=block, timeout=timeout, max_messages_to_get=1)[0]

    def get_nowait(self):
        return self.get(block=False)

    def parse_messages(self, num_messages, total_bytes, msg_buffer):
        messages = [None] * num_messages

        offset = 0
        for msg_idx in range(num_messages):
            msg_size = c_size_t.from_buffer(msg_buffer, offset)
            offset += ctypes.sizeof(c_size_t)

            msg_bytes = self.message_buffer_memview[offset:offset + msg_size.value]
            offset += msg_size.value
            msg = _ForkingPickler.loads(msg_bytes)
            messages[msg_idx] = msg

        assert total_bytes == offset
        return messages

    def reallocate_msg_buffer(self, new_size):
        # log.info('Reallocating msg buffer size: %d', new_size)
        self.message_buffer = (ctypes.c_ubyte * new_size)()
        self.message_buffer_memview = memoryview(self.message_buffer)

    def qsize(self):
        return Q.get_queue_size(<void *>q_addr(self))

    def empty(self):
        """
        Return True if the queue is empty, False otherwise. 
        If empty() returns True it doesn’t guarantee that a subsequent call to put() will not block. 
        Similarly, if empty() returns False it doesn’t guarantee that a subsequent call to get() will not block.
        """
        return self.qsize() == 0
    
    def full(self):
        """
        Return True if the queue is full, False otherwise. 
        If full() returns True it doesn’t guarantee that a subsequent call to get() will not block. 
        Similarly, if full() returns False it doesn’t guarantee that a subsequent call to put() will not block.
        """
        return Q.is_queue_full(<void *>q_addr(self))

    def join_thread(self):
        """This is not implemented as this implementation does not use a background thread"""
        pass

    def cancel_join_thread(self):
        """This is not implemented as this implementation does not use a background thread"""
        pass