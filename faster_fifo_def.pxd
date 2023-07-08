# cython: language_level=3
# cython: boundscheck=False
from libcpp cimport bool
cdef extern from 'cpp_faster_fifo/cpp_lib/faster_fifo.hpp':
    int Q_SUCCESS = 0, Q_EMPTY = -1, Q_FULL = -2, Q_MSG_BUFFER_TOO_SMALL = -3;

    size_t queue_object_size();
    void create_queue(void *queue_obj_memory, size_t max_size_bytes, size_t maxsize);

    int queue_put(void *queue_obj, void *buffer, const void **msgs_data, const size_t *msg_sizes, size_t num_msgs, int block, float timeout) nogil;
    int queue_get(void *queue_obj, void *buffer,
                  void *msg_buffer, size_t msg_buffer_size,
                  size_t max_messages_to_get, size_t max_bytes_to_get,
                  size_t *messages_read, size_t *bytes_read, size_t *messages_size, int block, float timeout) nogil;
    size_t get_queue_size(void *queue_obj);
    size_t get_data_size(void *queue_obj);
    bool is_queue_full(void *queue_obj);
