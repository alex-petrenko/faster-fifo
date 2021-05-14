#include <mutex>
#include <cassert>
#include <cstring>
#include <iostream>

#include <pthread.h>
#include <sys/time.h>

#include "faster_fifo.hpp"


struct Queue {
    explicit Queue(size_t max_size_bytes) : max_size_bytes(max_size_bytes) {
        pthread_mutexattr_init(&mutex_attr);
        pthread_mutexattr_setpshared(&mutex_attr, PTHREAD_PROCESS_SHARED);
        pthread_mutex_init(&mutex, &mutex_attr);

        pthread_condattr_init(&cond_attr);
        pthread_condattr_setpshared(&cond_attr, PTHREAD_PROCESS_SHARED);

        pthread_cond_init(&not_empty, &cond_attr);
        pthread_cond_init(&not_full, &cond_attr);
    }

    ~Queue() = default;

    size_t get_max_buffer_size() const {
        return max_size_bytes;
    }

    bool can_fit(size_t data_size) const {
        return size + data_size <= max_size_bytes;
    }

    /// This function does not check if there is enough space in the circular buffer, assuming the check
    /// has been performed.
    void circular_buffer_write(uint8_t *buffer, const uint8_t *data, const size_t data_size) {
        if (tail + data_size < max_size_bytes) {
            // all data fits before the wrapping point
            memcpy(buffer + tail, data, data_size);
            tail += data_size;
        } else {
            const auto before_wrap = max_size_bytes - tail, after_wrap = data_size - before_wrap;
            memcpy(buffer + tail, data, before_wrap);  // put portion of data to the end of the buffer
            memcpy(buffer, data + before_wrap, after_wrap);
            tail = after_wrap;  // new tail position
        }

        size += data_size;

        assert(size <= max_size_bytes);
        assert(tail < max_size_bytes);
    }

    void circular_buffer_read(uint8_t *buffer, uint8_t *data, size_t read_size, bool pop_message) {
        size_t new_head;

        if (head + read_size < max_size_bytes) {
            // read a segment without wrapping
            memcpy(data, buffer + head, read_size);
            new_head = head + read_size;
        } else {
            const auto before_wrap = max_size_bytes - head, after_wrap = read_size - before_wrap;
            memcpy(data, buffer + head, before_wrap);
            memcpy(data + before_wrap, buffer, after_wrap);
            new_head = after_wrap;
        }

        const auto new_size = size - read_size;

        assert(new_head < max_size_bytes);
        assert(new_size >= 0 && new_size < max_size_bytes);

        if (pop_message) {
            head = new_head;
            size = new_size;
        }
    }

public:
    // 9 bytes is the min message size.  8 bytes for the size
    // and 1 for the message
    static const size_t MIN_MSG_SIZE = 9;
    size_t max_size_bytes;
    size_t head = 0, tail = 0, size = 0;
    size_t num_elem = 0;

    pthread_mutexattr_t mutex_attr{};
    pthread_mutex_t mutex{};

    pthread_condattr_t cond_attr{};
    int not_empty_n_waiters = 0, not_full_n_waiters = 0;
    pthread_cond_t not_empty{}, not_full{};
};


struct LockGuard {
    explicit LockGuard(pthread_mutex_t *m) : m(m) {
        pthread_mutex_lock(m);
    }

    ~LockGuard() {
        pthread_mutex_unlock(m);
    }

private:
    pthread_mutex_t *m;
};


size_t queue_object_size() {
    return sizeof(Queue);
}

void create_queue(void *queue_obj_memory, size_t max_size_bytes) {
    new(queue_obj_memory) Queue(max_size_bytes);  // placement new
}

struct timeval float_seconds_to_timeval(float seconds) {
    struct timeval wait_timeval{};

    constexpr uint64_t million = 1000000UL;
    const auto wait_us = uint64_t(seconds * million);
    wait_timeval.tv_sec = wait_us / million;
    wait_timeval.tv_usec = wait_us % million;

    return wait_timeval;
}

struct timeval wait(struct timeval wait_time, pthread_cond_t *cond, pthread_mutex_t *mutex, int *waiter_count) {
    struct timeval now{}, wait_until{};
    gettimeofday(&now, nullptr);

    timeradd(&now, &wait_time, &wait_until);

    struct timespec wait_until_ts{};
    wait_until_ts.tv_sec = wait_until.tv_sec;
    wait_until_ts.tv_nsec = wait_until.tv_usec * 1000UL;

    ++(*waiter_count);
    pthread_cond_timedwait(cond, mutex, &wait_until_ts);
    --(*waiter_count);

    gettimeofday(&now, nullptr);
    struct timeval remaining{};
    timersub(&wait_until, &now, &remaining);
    return remaining;
}

bool timer_positive(const struct timeval &timer) {
    return (timer.tv_sec > 0) || (timer.tv_sec == 0 && timer.tv_usec > 0);
}

int queue_put(void *queue_obj, void *buffer, const void **msgs_data, const size_t *msg_sizes, const size_t num_msgs, const int block, const float timeout) {
    auto q = (Queue *)queue_obj;
    LockGuard lock(&q->mutex);

    {
        size_t total_size = num_msgs * sizeof(size_t);
        for (size_t i = 0; i < num_msgs; ++i)
            total_size += msg_sizes[i];

        auto wait_remaining = float_seconds_to_timeval(timeout);
        while (!q->can_fit(total_size)) {
            if (!block || !timer_positive(wait_remaining))
                return Q_FULL;

            // If there are any consumers waiting, wake them up!
            if (q->not_empty_n_waiters > 0)
                pthread_cond_signal(&q->not_empty);

            wait_remaining = wait(wait_remaining, &q->not_full, &q->mutex, &q->not_full_n_waiters);
        }
    }

    for (size_t i = 0; i < num_msgs; ++i) {
        // write the size to the circular buffer
        q->circular_buffer_write((uint8_t *)buffer, reinterpret_cast<const uint8_t *>(msg_sizes + i), sizeof(size_t));

        // write the message to the circular buffer
        q->circular_buffer_write((uint8_t *)buffer, reinterpret_cast<const uint8_t *>(msgs_data[i]), msg_sizes[i]);

        // Increment count by one as one element has been added
        ++q->num_elem;
    }
    
    if (q->not_empty_n_waiters > 0)
        pthread_cond_signal(&q->not_empty);
    else if (q->not_full_n_waiters && q->can_fit(Queue::MIN_MSG_SIZE)) {
        // In the case of many producers and one batched consumer, producers
        // should wake each other up as the batched consumer is only guaranteed to
        // wake up 1 producer its pthread_cond_signal(&q->not_full).

        pthread_cond_signal(&q->not_full);
    }

    return Q_SUCCESS;
}

int queue_get(void *queue_obj, void *buffer,
              void *msg_buffer, size_t msg_buffer_size,
              size_t max_messages_to_get, size_t max_bytes_to_get,
              size_t *messages_read, size_t *bytes_read, size_t *messages_size,
              int block, float timeout) {

    auto q = (Queue *)queue_obj;
    *messages_read = *bytes_read = *messages_size = 0;

    LockGuard lock(&q->mutex);

    auto wait_remaining = float_seconds_to_timeval(timeout);
    while (q->size <= 0) {
        if (!block || !timer_positive(wait_remaining))
            return Q_EMPTY;

        wait_remaining = wait(wait_remaining, &q->not_empty, &q->mutex, &q->not_empty_n_waiters);
    }

    auto status = Q_SUCCESS;
    while (*messages_read < max_messages_to_get && *bytes_read < max_bytes_to_get) {
        // read the size of the next message
        size_t msg_size;
        q->circular_buffer_read((uint8_t *)buffer, (uint8_t *)&msg_size, sizeof(msg_size), false);

        // this is how many bytes we need for another message
        *messages_size += sizeof(msg_size) + msg_size;

        if (msg_buffer_size < *messages_size) {
            status = Q_MSG_BUFFER_TOO_SMALL;  // caller didn't provide enough space to read all messages
            break;
        }

        assert(q->size >= sizeof(msg_size) + msg_size);

        // actually read the message, while also removing it from the queue
        const auto read_num_bytes = sizeof(msg_size) + msg_size;
        q->circular_buffer_read((uint8_t *)buffer, (uint8_t *)msg_buffer + *bytes_read, read_num_bytes, true);

        *bytes_read += read_num_bytes;
        *messages_read += 1;
        --q->num_elem;

        if (q->size <= 0) {
            // we want to read more messages, but the queue does not have any
            break;
        }
    }

    if (*messages_read > 0 && q->not_full_n_waiters > 0)
        pthread_cond_signal(&q->not_full);
    else if (q->size > 0 && q->not_empty_n_waiters > 0) {
        // In the case of many consumers and a single batched producer,
        // consumers need to wake each other up as the producer is only
        // guaranteed to wake up 1 consumer with its pthread_cond_signal(&q->not_empty).
        // Only send this signal if we didn't signal
        // not_full as this would just create lock contention otherwise

        pthread_cond_signal(&q->not_empty);
    }

    // we managed to read as many messages as we wanted and they all fit into the buffer!
    return status;
}

size_t get_queue_size(void *queue_obj) {
    auto q = (Queue *)queue_obj;
    return q->num_elem;
}

bool is_queue_full(void *queue_obj) {
    auto q = (Queue *)queue_obj;
    constexpr size_t min_message_size = 1;
    return !q->can_fit(min_message_size + sizeof(min_message_size));
}
