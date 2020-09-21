# Scoring API

A small python API for calc scoring, and get client interests

## Installation

Python 3 required.
Tested on Python 3.7.3

## Usage

Run API server:

python api.py

## Testing

run docker container with Tarantool

docker run --name mytarantool -p3301:3301 -d tarantool/tarantool

And after that run tests:

python test.py

python test_integration.py
