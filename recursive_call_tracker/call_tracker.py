# This file is part of recursive-call-tracker. See __init__.py for more details.
# Copyright (C) 2022  Numerlor

from __future__ import annotations

import enum
import threading
import typing as t
from collections import abc, defaultdict
from functools import wraps

from recursive_call_tracker.utils import prettify_kwargs_repr

if t.TYPE_CHECKING:
    import typing_extensions as te

    P = te.ParamSpec("P")
    R = t.TypeVar("R")


class Uninitialized(enum.Enum):  # noqa: D101
    UNINITIALIZED = enum.auto()

    def __str__(self):
        return self._name_

    __repr__ = __str__


UNINITIALIZED = Uninitialized.UNINITIALIZED


class RecursiveCall:
    """
    A single recursive call.

    Recursive calls from within this call should be registered with the `add_callee` method.
    """

    def __init__(
        self,
        args: tuple[object, ...],
        kwargs: dict[str, object],
        caller: None | RecursiveCall = None,
    ):
        self.caller = caller
        self.callees: list[RecursiveCall] = []
        self.args = args
        self.kwargs = kwargs
        self.result: object | t.Literal[UNINITIALIZED] = UNINITIALIZED

    def add_callee(self, callee: RecursiveCall) -> None:
        """Add a callee to the `callees` attribute, and register self as its caller."""
        self.callees.append(callee)
        callee.caller = self

    def __repr__(self) -> str:
        return f"<RecursiveCall callees={self.callees} args={self.args} kwargs={self.kwargs} result={self.result})"

    def pretty_print(self, *, indent: int = 4) -> None:
        """Pretty print this call."""
        current = self
        depth = 0
        callee_iterators = {}

        while current is not None:
            if current not in callee_iterators:
                callee_iterators[current] = iter(current.callees)
                print(  # noqa: T201
                    f"{self._indent_from_depth(depth, indent=indent)}RecursiveCall"
                )
                hanging_indent = self._indent_from_depth(
                    depth, indent=indent, hanging=True
                )
                print(f"{hanging_indent}result={current.result!r}")  # noqa: T201
                print(f"{hanging_indent}args={current.args!r}")  # noqa: T201
                print(  # noqa: T201
                    f"{hanging_indent}kwargs={prettify_kwargs_repr(current.kwargs)})"
                )
                if not current.callees:
                    print(f"{hanging_indent}callees=[]")  # noqa: T201
                else:
                    print(f"{hanging_indent}callees=[")  # noqa: T201

            try:
                current = next(callee_iterators[current])
            except StopIteration:
                if current.callees:
                    print(  # noqa: T201
                        f"{self._indent_from_depth(depth, indent=indent, hanging=True)}],"
                    )
                depth -= 1
                current = current.caller
            else:
                depth += 1

    @staticmethod
    def _indent_from_depth(depth: int, *, indent: int, hanging: bool = False) -> str:
        """Get the spaces to indent for `depth`. If `hanging` is True, an additional indentation level is added."""
        if not depth:
            indent_width = 0
        else:
            # Each depth has base indent + hanging from callees
            indent_width = indent * depth * 2
        if hanging:
            indent_width += indent
        return " " * indent_width


class CallTracker:
    """
    Track all recursive calls of the wrapped function.

    The initial call for each recursive chain is stored in the `start_calls` attribute.
    """

    def __init__(self):
        self._call_stacks: defaultdict[int, list[RecursiveCall]] = defaultdict(list)
        self.start_calls: list[RecursiveCall] = []

    def __call__(self, func: abc.Callable[P, R]) -> abc.Callable[P, R]:
        """Wrap `func` to register calls to it in this tracker."""

        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            call = RecursiveCall(args, kwargs)
            call_stack = self._call_stacks[threading.get_ident()]

            if call_stack:
                call_stack[-1].add_callee(call)
            else:
                self.start_calls.append(call)

            call_stack.append(call)

            result = func(*args, **kwargs)

            call_stack.pop().result = result

            return result

        return wrapper
