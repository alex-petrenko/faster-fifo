# cython: language_level=3
# cython: boundscheck=False
# cython: infer_types=False

import ctypes
import multiprocessing

from ctypes import c_size_t
from multiprocessing import context
import threading
from queue import Full, Empty
from typing import Optional

_ForkingPickler = context.reduction.ForkingPickler

cimport faster_fifo_def as Q


DEFAULT_TIMEOUT = float(10)
DEFAULT_CIRCULAR_BUFFER_SIZE = 1000 * 1000  # 1 Mb
INITIAL_RECV_BUFFER_SIZE = 5000


class QueueError(Exception):
    pass


class TLSBuffer(threading.local):
    """Used for recv message buffers, prevents race condition in multithreading (not a problem with multiprocessing)."""
    def __init__(self, v=None):
        self.val = v

    def __getstate__(self):
        message_buffer_size = 0 if self.val is None else len(self.val)
        return message_buffer_size

    def __setstate__(self, message_buffer_size):
        if message_buffer_size == 0:
            self.val = None
        else:
            self.val = (ctypes.c_ubyte * message_buffer_size)()


cdef size_t caddr(buf):
    cdef size_t buffer_ptr = ctypes.addressof(buf)
    return buffer_ptr

cdef size_t q_addr(q):
    return caddr(q.queue_obj_buffer)

cdef size_t buf_addr(q):
    return caddr(q.shared_memory)

cdef size_t msg_buf_addr(q):
    return caddr(q.message_buffer.val)

cdef size_t bytes_to_ptr(b):
    ptr = ctypes.cast(b, ctypes.POINTER(ctypes.c_byte))
    return ctypes.addressof(ptr.contents)


class Queue:
    def __init__(self, max_size_bytes=DEFAULT_CIRCULAR_BUFFER_SIZE, maxsize=int(1e9), loads=None, dumps=None):
        self.max_size_bytes = max_size_bytes
        self.maxsize = maxsize  # default maxsize
        self.max_bytes_to_read = self.max_size_bytes  # by default, read the whole queue if necessary

        # allow per-instance serializer overriding
        if loads is not None:
            self.loads = loads
        if dumps is not None:
            self.dumps = dumps

        self.closed = multiprocessing.RawValue(ctypes.c_bool, False)

        queue_obj_size = Q.queue_object_size()
        self.queue_obj_buffer = multiprocessing.RawArray(ctypes.c_ubyte, queue_obj_size)
        self.shared_memory = multiprocessing.RawArray(ctypes.c_ubyte, max_size_bytes)

        Q.create_queue(<void *> q_addr(self), max_size_bytes, maxsize)

        self.message_buffer: TLSBuffer = TLSBuffer(None)

        self.last_error: Optional[str] = None

    def _error(self, message):
        self.last_error = message
        raise QueueError(message)

    # allow class level serializers
    def loads(self, msg_bytes):
        return _ForkingPickler.loads(msg_bytes)

    def dumps(self, obj):
        return _ForkingPickler.dumps(obj).tobytes()

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

    def put_many(self, xs, block=True, timeout=DEFAULT_TIMEOUT):
        if not isinstance(xs, (list, tuple)):
            self._error(f'put_many() expects a list or tuple, got {type(xs)}')

        xs = [self.dumps(ele) for ele in xs]

        _len = len
        msgs_buf = (c_size_t * _len(xs))()
        size_buf = (c_size_t * _len(xs))()

        for i, ele in enumerate(xs):
            msgs_buf[i] = bytes_to_ptr(ele)
            size_buf[i] = _len(ele)
        
        # explicitly convert all function parameters to corresponding C-types
        cdef void* c_q_addr = <void*>q_addr(self)
        cdef void* c_buf_addr = <void*>buf_addr(self)

        cdef const void** c_msgs_buf_addr = <const void**>caddr(msgs_buf)
        cdef const size_t* c_size_buff_addr = <const size_t*>caddr(size_buf)

        cdef size_t c_len_x = _len(xs)
        cdef int c_block = block
        cdef float c_timeout = timeout

        cdef int c_status = 0

        with nogil:
            c_status = Q.queue_put(
                c_q_addr, c_buf_addr, c_msgs_buf_addr, c_size_buff_addr, c_len_x,
                c_block, c_timeout,
            )

        status = c_status

        if status == Q.Q_SUCCESS:
            pass
        elif status == Q.Q_FULL:
            raise Full()
        else:
            raise Exception(f'Unexpected queue error {status}')

    def put(self, x, block=True, timeout=DEFAULT_TIMEOUT):
        status = self.put_many([x], block, timeout)
        if status == Q.Q_FULL:
            raise Full()
        return status

    def put_many_nowait(self, xs):
        status = self.put_many(xs, block=False)
        if status == Q.Q_FULL:
            raise Full()
        return status

    def put_nowait(self, x):
        status = self.put_many_nowait([x])
        if status == Q.Q_FULL:
            raise Full()
        return status


    def get_many(self, block=True, timeout=DEFAULT_TIMEOUT, max_messages_to_get=int(1e9)):
        if self.message_buffer.val is None:
            self.reallocate_msg_buffer(INITIAL_RECV_BUFFER_SIZE)  # initialize a small buffer at first, it will be increased later if needed

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
        cdef size_t c_len_message_buffer = len(self.message_buffer.val)

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
            if messages_read.value <= 0 or bytes_read.value <= 0:
                self._error(f'Expected to read at least 1 message, but got {messages_read.value} messages and {bytes_read.value} bytes')
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

    def get(self, block=True, timeout=DEFAULT_TIMEOUT):
        return self.get_many(block=block, timeout=timeout, max_messages_to_get=1)[0]

    def get_nowait(self):
        return self.get(block=False)

    def parse_messages(self, num_messages, total_bytes, msg_buffer):
        messages = [None] * num_messages

        offset = 0
        for msg_idx in range(num_messages):
            msg_size = c_size_t.from_buffer(msg_buffer.val, offset)
            offset += ctypes.sizeof(c_size_t)

            msg_bytes = memoryview(msg_buffer.val)[offset:offset + msg_size.value]
            #msg_bytes = msg_buffer.val[offset,msg_size.value] #memoryview(msg_buffer.val)[offset:offset + msg_size.value]
            offset += msg_size.value
            msg = self.loads(msg_bytes)
            messages[msg_idx] = msg

        if offset != total_bytes:
            self._error(f'Expected to read {total_bytes} bytes, but got {offset} bytes')
        return messages

    def reallocate_msg_buffer(self, new_size):
        new_size = max(INITIAL_RECV_BUFFER_SIZE, new_size)
        self.message_buffer.val = (ctypes.c_ubyte * new_size)()

    def qsize(self):
        return Q.get_queue_size(<void *>q_addr(self))

    def data_size(self):
        return Q.get_data_size(<void *>q_addr(self))

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
