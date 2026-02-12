#!/usr/bin/env bash

python setup.py sdist build

twine upload --disable-proxy dist/*
