# bitrange

A tiny, dependency-free bitmap toolkit written in pure standard-library
Python.

## 现状

Today bitrange ships exactly one class: `FlatBits` in `bitrange/bits.py`. It
stores each bit as one character in a plain list. Setting or clearing a bit
touches a single character, and every range query -- whether a span is all
ones, all zeros, its one count, or the next zero/one after a position -- walks
the span bit by bit. There is no interval tree, no node bookkeeping and no
lazy tag.

## 目标（见任务描述）

Grow the toolkit beyond per-bit scanning into an interval-tree bitmap with
range all-one/all-zero queries, range assign/clear with lazy propagation,
next-zero/next-one search, span and global one counts, and correct boundaries.
The full requirements live in the task description.

## 运行

Run the demo:

    python3 demo.py

Run the test suite:

    python3 -m unittest discover -s tests -v

## 实现说明

（实现后补，10 行以内）
