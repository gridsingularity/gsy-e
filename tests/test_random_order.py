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

import pytest
from numpy import random

import gsy_e.constants
from gsy_e.models import random_order

NAMES = [f"asset {index}" for index in range(12)]


@pytest.fixture(name="item_hash_order")
def fixture_item_hash_order(monkeypatch):
    monkeypatch.setattr(gsy_e.constants, "ORDER_BY_ITEM_HASH", True)
    random_order.set_seed(0)
    yield
    random_order.set_seed(0)


def _order(items, salt="salt"):
    return random_order.shuffled(items, salt=lambda: salt, key=str)


def test_default_order_draws_from_the_numpy_stream_as_before():
    random.seed(3)
    expected = sorted(NAMES, key=lambda _: random.random())
    random.seed(3)
    assert _order(NAMES) == expected


def test_default_choice_draws_from_the_numpy_stream_as_before():
    random.seed(3)
    expected = random.choice(NAMES)
    random.seed(3)
    assert random_order.choice(NAMES, salt=lambda: "salt", key=str) == expected


@pytest.mark.usefixtures("item_hash_order")
def test_removing_an_item_keeps_the_relative_order_of_the_rest():
    without_one = _order([name for name in NAMES if name != "asset 5"])
    assert without_one == [name for name in _order(NAMES) if name != "asset 5"]


@pytest.mark.usefixtures("item_hash_order")
def test_item_hash_order_ignores_the_numpy_stream_and_input_order():
    reference = _order(NAMES)
    random.random()
    assert _order(list(reversed(NAMES))) == reference


@pytest.mark.usefixtures("item_hash_order")
def test_item_hash_order_changes_with_the_seed_and_the_salt():
    reference = _order(NAMES)
    assert _order(NAMES, salt="other salt") != reference
    random_order.set_seed(1)
    assert _order(NAMES) != reference


@pytest.mark.usefixtures("item_hash_order")
def test_item_hash_choice_is_the_first_of_the_order():
    assert random_order.choice(NAMES, salt=lambda: "salt", key=str) == _order(NAMES)[0]
