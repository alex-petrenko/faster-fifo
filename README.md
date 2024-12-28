[![tests](https://github.com/alex-petrenko/faster-fifo/actions/workflows/test-ci.yml/badge.svg)](https://github.com/alex-petrenko/faster-fifo/actions/workflows/test-ci.yml)
[![Downloads](https://pepy.tech/badge/faster-fifo)](https://pepy.tech/project/faster-fifo)
[<img src="https://img.shields.io/discord/987232982798598164?label=discord">](https://discord.gg/d9VZmMWejh)

<!-- [![codecov](https://codecov.io/gh/alex-petrenko/faster-fifo/branch/master/graph/badge.svg)](https://codecov.io/gh/alex-petrenko/faster-fifo) -->

# faster-fifo

Faster alternative to Python's standard multiprocessing.Queue (IPC FIFO queue). Up to 30x faster in some configurations.

Implemented in C++ using POSIX mutexes with PTHREAD_PROCESS_SHARED attribute. Based on a circular buffer, low footprint, brokerless.

Adds `get_many()` and `put_many()` methods to receive/send multiple messages at once for the price of a single lock.

## Requirements 

- Linux or MacOS
- Python 3.6 or newer
- GCC 4.9.0 or newer

## Installation

```pip install faster-fifo```

(on a fresh Linux installation you might need some basic compiling tools `sudo apt install --reinstall build-essential gcc g++`)

## Manual build instructions

```
pip install Cython
python setup.py build_ext --inplace
pip install -e .
```

## Usage example

```Python
from faster_fifo import Queue
from queue import Full, Empty

q = Queue(1000 * 1000)  # specify the size of the circular buffer in the ctor

# any pickle-able Python object can be added to the queue
py_obj = dict(a=42, b=33, c=(1, 2, 3), d=[1, 2, 3], e='123', f=b'kkk')
q.put(py_obj)
assert q.qsize() == 1

retrieved = q.get()
assert q.empty()
assert py_obj == retrieved

for i in range(100):
    try:
        q.put(py_obj, timeout=0.1)
    except Full:
        log.debug('Queue is full!')

num_received = 0
while num_received < 100:
    # get multiple messages at once, returns a list of messages for better performance in many-to-few scenarios
    # get_many does not guarantee that all max_messages_to_get will be received on the first call, in fact
    # no such guarantee can be made in multiprocessing systems.
    # get_many() will retrieve as many messages as there are available AND can fit in the pre-allocated memory
    # buffer. The size of the buffer is increased gradually to match demand.
    messages = q.get_many(max_messages_to_get=100)
    num_received += len(messages)

try:
    q.get(timeout=0.1)
    assert True, 'This won\'t be called'
except Empty:
    log.debug('Queue is empty')

```

## Performance comparison (faster-fifo vs multiprocessing.Queue)

##### System #1 (Intel(R) Core(TM) i9-7900X CPU @ 3.30GHz, 10 cores, Ubuntu 18.04)

*(measured execution times in seconds)*

|                                                   | multiprocessing.Queue |   faster-fifo, get()    |  faster-fifo, get_many()  |
|---------------------------------------------------|:---------------------:|:-----------------------:|:-------------------------:|
|   1 producer 1 consumer (200K msgs per producer)  |         2.54          |          0.86           |           0.92            |
|  1 producer 10 consumers (200K msgs per producer) |         4.00          |          1.39           |           1.36            |           
|  10 producers 1 consumer (100K msgs per producer) |         13.19         |          6.74           |           0.94            |
| 3 producers 20 consumers (100K msgs per producer) |         9.30          |          2.22           |           2.17            |
|  20 producers 3 consumers (50K msgs per producer) |         18.62         |          7.41           |           0.64            |
| 20 producers 20 consumers (50K msgs per producer) |         36.51         |          1.32           |           3.79            |


##### System #2 (Intel(R) Core(TM) i5-4200U CPU @ 1.60GHz, 2 cores, Ubuntu 18.04)

*(measured execution times in seconds)*

|                                                   | multiprocessing.Queue |   faster-fifo, get()    |  faster-fifo, get_many()  |
|---------------------------------------------------|:---------------------:|:-----------------------:|:-------------------------:|
|   1 producer 1 consumer (200K msgs per producer)  |         7.86          |          2.09           |            2.2            |
|  1 producer 10 consumers (200K msgs per producer) |         11.68         |          4.01           |           3.88            |           
|  10 producers 1 consumer (100K msgs per producer) |         44.48         |          16.68          |           5.98            |
| 3 producers 20 consumers (100K msgs per producer) |         22.59         |          7.83           |           7.49            |
|  20 producers 3 consumers (50K msgs per producer) |         66.3          |          22.3           |           6.35            |
| 20 producers 20 consumers (50K msgs per producer) |         78.75         |          14.39          |           15.78           |

## Run tests

```
pip install numpy
python -m unittest
```

(there are also C++ unit tests, should run them if C++ code was altered)

## Recent PyPI releases

##### v1.5.2

* Fixing some dependencies and distribution issues

##### v1.5.0

* Build/publish binary wheels with cibuildwheel. Thank you [zbowling](https://github.com/zbowling)!

##### v1.4.7

* Added missing `<new>` header. Thank you [mxilinas](https://github.com/mxilinas)!

##### v1.4.6

* Added missing `<cstdio>` causing issues with newer g++. Thank you [mesaglio](https://github.com/mesaglio)!

##### v1.4.5

* Added method `data_size()` to query the total size of the messages in queue (in bytes). Thank you [@LucaNicosia](https://github.com/LucaNicosia)!

##### v1.4.4

* Fixed an obscure issue with the TLSBuffer ctor being called without arguments (guessing it's Cython's weirdness)

##### v1.4.3

* Simplified usage with "spawn" multiprocessing context. No need to use `faster_fifo_reduction` anymore. Thank you [@MosBas](https://github.com/MosBas)!

##### v1.4.2

* Fixed an issue with the custom Queue pickler

##### v1.4.1

* Fixed multithreading issues using threading.local for message recv buffer (huge thanks to [@brianmacy](https://github.com/brianmacy)!)
* Better error reporting in Cython and C++
* Added threading tests

##### v1.4.0

* Increase default receive buffer size from 10 bytes to 5000 bytes.

##### v1.3.1

* Minor change: better debugging messages + improved C++ tests

##### v1.3.0
* Now support custom serializers and deserializers instead of Pickle (thank you [@beasteers](https://github.com/beasteers)!):
```Python
q = Queue(max_size_bytes=100000, loads=custom_deserializer, dumps=custom_serializer)
```

## Footnote

Originally designed for SampleFactory, a high-throughput asynchronous RL codebase https://github.com/alex-petrenko/sample-factory.

Programmed by [Aleksei Petrenko](https://alex-petrenko.github.io/) and Tushar Kumar at [USC RESL](https://robotics.usc.edu/resl/people/).

Developed under MIT License, feel free to use for any purpose, commercial or not, at your own risk.

If you wish to cite this repository:

```
@misc{faster-fifo,
    author={Petrenko, Aleksei and Kumar, Tushar},
    title={A Faster Alternative to Python's multiprocessing.Queue},
    publisher={GitHub},
    journal = {GitHub repository},
    howpublished = {\url{https://github.com/alex-petrenko/faster-fifo}},
    year={2020},
}
```
