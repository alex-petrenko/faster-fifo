#include <array>
#include <vector>

#include "gtest/gtest.h"

#include "faster_fifo.hpp"


template<size_t SIZE> using arr = std::array<uint8_t, SIZE>;
template<size_t SIZE1, size_t SIZE2> using arr2D = std::array<arr<SIZE2>, SIZE1>;
template<size_t SIZE=1> using sz_arr = std::array<size_t, SIZE>;

#pragma clang diagnostic push
#pragma ide diagnostic ignored "cert-err58-cpp"
TEST(fast_queue, queue_test) {
    const auto q_size = queue_object_size();
    std::vector<uint8_t> q_buffer(q_size);  // allocate memory for the queue object (normally would be Python shared memory)
    void *q = q_buffer.data();

    constexpr float tm = 1.0;
    constexpr size_t max_size_bytes = 100;
    create_queue(q, max_size_bytes);

    arr<max_size_bytes> buffer{};  // memory for the circular buffer

    // adding messages to the queue
    arr2D<1, 5> msg0{0, 1, 2, 3, 42};
    const void *ptr = msg0[0].data();
    sz_arr<> sizes{sizeof(msg0)};
    auto status = queue_put(q, buffer.data(), &ptr, sizes.data(), 1, false, tm);
    EXPECT_EQ(status, Q_SUCCESS);

    arr2D<1, 80> msg1{};
    sizes[0] = sizeof(msg1);
    ptr = msg1[0].data();
    status = queue_put(q, buffer.data(), &ptr, sizes.data(), 1, true, tm);
    EXPECT_EQ(status, Q_FULL);

    arr2D<1, 79> msg2{};
    msg2[0][1] = 0xff;
    msg2[0][78] = 0xee;
    sizes[0] = sizeof(msg2);
    ptr = msg2[0].data();
    status = queue_put(q, buffer.data(), &ptr, sizes.data(), 1, true, tm);
    EXPECT_EQ(status, Q_SUCCESS);

    uint8_t msg3;
    sizes[0] = sizeof(msg3);
    ptr = &msg3;
    status = queue_put(q, buffer.data(), &ptr, sizes.data(), 1, true, tm);
    EXPECT_EQ(status, Q_FULL);

    // reading messages from the queue
    size_t msgs_read, bytes_read, msgs_size;

    // try to read one message, while providing insufficient buffer size
    arr<10> msg_buffer10{};
    status = queue_get(q, buffer.data(), msg_buffer10.data(), sizeof(msg_buffer10), 1, 100, &msgs_read, &bytes_read, &msgs_size, true, tm);
    EXPECT_EQ(status, Q_MSG_BUFFER_TOO_SMALL);
    EXPECT_EQ(msgs_read, 0);
    EXPECT_EQ(bytes_read, 0);
    EXPECT_EQ(msgs_size, sizeof(msgs_size) + sizeof(msg0));

    // allocate a bigger buffer that fits the first message + message size
    arr<13> msg_buffer13{};
    status = queue_get(q, buffer.data(), msg_buffer13.data(), sizeof(msg_buffer13), 1, 100, &msgs_read, &bytes_read, &msgs_size, true, tm);
    EXPECT_EQ(status, Q_SUCCESS);
    EXPECT_EQ(msgs_read, 1);
    EXPECT_EQ(bytes_read, sizeof(msg_buffer13));
    EXPECT_EQ(msgs_size, sizeof(msgs_size) + sizeof(msg0));  // we read as many messages as we wanted, so this is just equal to bytes_read
    EXPECT_EQ(*(size_t *)msg_buffer13.data(), sizeof(msg0));  // first 8 bytes of the message should contain the size of the message
    EXPECT_EQ(memcmp(msg_buffer13.data() + sizeof(size_t), msg0.data(), sizeof(msg0)), 0);  // the message we read is identical to the message we put in a queue

    // attempt to read the next (big) message using small buffer
    status = queue_get(q, buffer.data(), msg_buffer13.data(), sizeof(msg_buffer13), 100, 100, &msgs_read, &bytes_read, &msgs_size, true, tm);
    EXPECT_EQ(status, Q_MSG_BUFFER_TOO_SMALL);
    EXPECT_EQ(msgs_read, 0);
    EXPECT_EQ(bytes_read, 0);
    EXPECT_EQ(msgs_size, sizeof(msgs_size) + sizeof(msg2));  // this is how many bytes we need to actually read the next message

    // allocate a bigger buffer and read the next message
    arr<max_size_bytes> msg_buffer100{};
    status = queue_get(q, buffer.data(), msg_buffer100.data(), sizeof(msg_buffer100), 100, 100, &msgs_read, &bytes_read, &msgs_size, true, tm);
    EXPECT_EQ(status, Q_SUCCESS);
    EXPECT_EQ(msgs_read, 1);
    EXPECT_EQ(bytes_read, sizeof(msgs_size) + sizeof(msg2));
    EXPECT_EQ(msgs_size, bytes_read);
    EXPECT_EQ(memcmp(msg_buffer100.data() + sizeof(size_t), msg2.data(), sizeof(msg2)), 0);  // the message we read is identical to the message we put in a queue

    // at this point the queue is empty, any attempt to read messages will be unsuccessful
    status = queue_get(q, buffer.data(), msg_buffer100.data(), sizeof(msg_buffer100), 100, 100, &msgs_read, &bytes_read, &msgs_size, true, tm);
    EXPECT_EQ(status, Q_EMPTY);
    EXPECT_EQ(msgs_read, 0);
    EXPECT_EQ(bytes_read, 0);
    EXPECT_EQ(msgs_size, 0);
    status = queue_get(q, buffer.data(), msg_buffer100.data(), sizeof(msg_buffer100), 1, 1, &msgs_read, &bytes_read, &msgs_size, true, tm);
    EXPECT_EQ(status, Q_EMPTY);
}

TEST(fast_queue, test_many) {
    const auto q_size = queue_object_size();
    std::vector<uint8_t> q_buffer(q_size);  // allocate memory for the queue object (normally would be Python shared memory)
    void *q = q_buffer.data();

    constexpr float tm = 1.0;
    constexpr size_t max_size_bytes = 100;
    create_queue(q, max_size_bytes);

    arr<max_size_bytes> buffer{};  // memory for the circular buffer

    constexpr auto num_msgs = 3, msg_size = 5, msg_bytes = num_msgs * msg_size;
    arr2D<num_msgs, msg_size> msgs = {{{1, 2, 3, 4, 5}, {6, 7, 8, 9, 10}, {0, 0, 0, 0, 255}}};
    sz_arr<num_msgs> sizes;
    sizes.fill(msg_size);
    arr<msg_size> *msg_ptrs[num_msgs];
    for (auto i = 0; i < num_msgs; ++i)
        msg_ptrs[i] = &msgs[i];

    auto status = queue_put(q, buffer.data(), (const void **)(&msg_ptrs), sizes.data(), num_msgs, true, 0.1);
    EXPECT_EQ(status, Q_SUCCESS);

    // try to read one message, while providing insufficient buffer size
    arr<10> msg_buffer10{};
    size_t msgs_read, bytes_read, msgs_size;
    status = queue_get(
        q, buffer.data(), msg_buffer10.data(), sizeof(msg_buffer10),
        num_msgs, msg_bytes, &msgs_read, &bytes_read,
        &msgs_size, true, tm
    );

    EXPECT_EQ(status, Q_MSG_BUFFER_TOO_SMALL);
    EXPECT_EQ(msgs_read, 0);
    EXPECT_EQ(bytes_read, 0);

    // allocate a bigger buffer and read all messages
    arr<100> msg_buffer100{};
    size_t expected_bytes = msg_bytes + sizeof(size_t) * num_msgs;
    status = queue_get(
        q, buffer.data(), msg_buffer100.data(), sizeof(msg_buffer100),
        num_msgs, expected_bytes, &msgs_read, &bytes_read,
        &msgs_size, true, tm
    );

    EXPECT_EQ(status, Q_SUCCESS);
    EXPECT_EQ(msgs_read, num_msgs);
    EXPECT_EQ(bytes_read, expected_bytes);
    for (auto i = 0; i < num_msgs; ++i) {
        const auto ofs = i * (sizeof(size_t) + msg_size) + sizeof(size_t);
        EXPECT_EQ(memcmp(msg_buffer100.data() + ofs, msgs[i].data(), msg_size), 0);
    }
}
#pragma clang diagnostic pop
