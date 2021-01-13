#!/bin/bash

if [ $TRAVIS_OS_NAME = 'osx' ]; then
    export CC=gcc-9
    export CXX=g++-9
    case "${TOXENV}" in
        py36)
            eval "$(pyenv init -)"
            pyenv install 3.6.2
            pyenv global 3.6.2
            pip3 install setuptools==45.2.0 --force-reinstall
            pip3 install --upgrade pip
            ;;
        py38)
            eval "$(pyenv init -)"
            pyenv install 3.8.0
            pyenv global 3.8.0
            ;;
        py39)
            eval "$(pyenv init -)"
            pyenv install 3.9.0
            pyenv global 3.9.0
            ;;
    esac
    pip3 install cython
    pip3 install coverage
    pip3 install faster-fifo
else
    pip install cython
    pip install coverage
    pip install faster-fifo
fi