# commitx

A tiny, dependency-free commit toolkit written in pure standard-library
Python.

## 现状

Today commitx ships exactly one class: `LocalCommit` in `commitx/commit.py`. It
is a single-node committer. A call to `apply` mutates the local state in place,
and that is the whole story: there is no coordinator, no participants, no
voting, no prepare phase and no recovery log. Because nothing is ever split
across nodes, a change can never be partial, so there is nothing to recover and
nothing to coordinate.

## 目标（见任务描述）

Grow commitx from the single-node committer into a full two-phase commit
protocol: a coordinator that prepares all participants and collects their
votes, participants that commit or roll back on instruction, atomic
all-or-nothing outcomes, crash recovery from a persisted phase log, blocking
and timeout handling, and idempotent log replay. Everything stays inside the
commitx package, stays pure standard library, and is driven through injectable
deterministic simulation objects so that every run is reproducible. The full
requirements live in the task description.

## 运行

Run the demo:

    python3 demo.py

Run the test suite:

    python3 -m unittest discover -s tests -v

## 实现说明

（实现后补，10 行以内）
