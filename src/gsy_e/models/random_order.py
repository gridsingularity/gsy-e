"""
Copyright 2018 Grid Singularity
This file is part of Grid Singularity Exchange.

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

import hashlib
from typing import Callable, Iterable, List, Sequence, TypeVar

from numpy import random

import gsy_e.constants

T = TypeVar("T")

_seed = 0


def set_seed(seed: int) -> None:
    """Set the run seed that item-hash ordering is derived from."""
    global _seed  # pylint: disable=global-statement
    _seed = int(seed)


def _digest(salt: str, key: str) -> bytes:
    return hashlib.blake2b(f"{_seed}|{salt}|{key}".encode(), digest_size=8).digest()


def shuffled(items: Iterable[T], salt: Callable[[], str], key: Callable[[T], str]) -> List[T]:
    """Return the items in a fair random order.

    By default the order comes from the global numpy stream, as gsy-e has always done. With
    ORDER_BY_ITEM_HASH set, each item is ranked on a hash of the run seed, the salt and its own
    key, so removing one item leaves the relative order of the others unchanged.
    """
    if not gsy_e.constants.ORDER_BY_ITEM_HASH:
        return sorted(items, key=lambda _: random.random())
    salt_text = salt()
    return sorted(items, key=lambda item: _digest(salt_text, key(item)))


def choice(items: Sequence[T], salt: Callable[[], str], key: Callable[[T], str]) -> T:
    """Return one item at random, with the same two modes as shuffled."""
    if not gsy_e.constants.ORDER_BY_ITEM_HASH:
        return random.choice(items)
    return shuffled(items, salt, key)[0]
