from Cython.Build import cythonize
from setuptools import setup, Extension


extensions = [
    Extension(
        name='faster_fifo',
        sources=['faster_fifo.pyx', 'cpp_faster_fifo/cpp_lib/faster_fifo.cpp'],
        language='c++',
        include_dirs=['cpp_faster_fifo/cpp_lib'],
    ),
]

setup(
    # Information
    name='faster-fifo',
    version='0.0.1',
    url='https://github.com/alex-petrenko/faster-fifo',
    author='Aleksei Petrenko & Tushar Kumar',
    license='MIT',
    keywords='multiprocessing data structures',

    # Build instructions
    ext_modules=cythonize(extensions),

    setup_requires=['setuptools>=45.2.0', 'cython>=0.29'],
)
