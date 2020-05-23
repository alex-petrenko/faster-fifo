[![Build Status](https://travis-ci.org/alex-petrenko/faster-fifo.svg?branch=master)](https://travis-ci.org/github/alex-petrenko/faster-fifo)
[![codecov](https://codecov.io/gh/alex-petrenko/faster-fifo/branch/master/graph/badge.svg)](https://codecov.io/gh/alex-petrenko/faster-fifo)

# Faster Fifo
Faster alternative to Python's multiprocessing.Queue (IPC FIFO queue)

## Build Instructions
```python setup.py build_ext --inplace```

## Comparison Table
|                                                     | Faster Fifo (consume 1) | Faster Fifo (consume 100) | Multiprocessing Queue (consume 1) |   |
|-----------------------------------------------------|:-----------------------:|:-------------------------:|:---------------------------------:|---|
|   1 producer 1 consumer (200000 msgs per producer)  |           2.09          |            2.2            |                7.86               |   |
|  1 producer 10 consumers (200000 msgs per producer) |           4.01          |            3.88           |               11.68               |   |
|  10 producers 1 consumer (100000 msgs per producer) |          16.68          |            5.98           |               44.48               |   |
| 3 producers 20 consumers (100000 msgs per producer) |           7.83          |            7.49           |               22.59               |   |
|  20 producers 3 consumers (50000 msgs per producer) |           22.3          |            6.35           |                66.3               |   |
| 20 producers 20 consumers (50000 msgs per producer) |          14.39          |           15.78           |               78.75               |   |

(All values are in seconds)

Configuration used to test the above:- 
* Intel(R) Core(TM) i5-4200U CPU @ 1.60GHz
* 6 GB RAM