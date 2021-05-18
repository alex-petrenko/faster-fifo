import setuptools
from Cython.Build import cythonize
from setuptools import setup, Extension


extensions = [
    Extension(
        name='faster_fifo',
        sources=['faster_fifo.pyx', 'cpp_faster_fifo/cpp_lib/faster_fifo.cpp'],
        language='c++',
        extra_compile_args=['-std=c++14'],
        include_dirs=['cpp_faster_fifo/cpp_lib'],
    ),
]

with open('README.md', 'r') as fh:
    long_description = fh.read()

setup(
    # Information
    name='faster-fifo',
    version='1.2.0',
    url='https://github.com/alex-petrenko/faster-fifo',
    author='Aleksei Petrenko & Tushar Kumar',
    license='MIT',
    keywords='multiprocessing data structures',
    description='A faster alternative to Python\'s standard multiprocessing.Queue (IPC FIFO queue)',
    long_description=long_description,
    long_description_content_type='text/markdown',

    # Build instructions
    ext_modules=cythonize(extensions),
    install_requires=['setuptools>=45.2.0', 'cython>=0.29'],
    python_requires='>=3.6',

    packages=setuptools.find_packages(where='./', include='faster_fifo*'),
    # install_requires=["pip>=19.3"],
)
