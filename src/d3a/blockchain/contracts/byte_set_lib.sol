//Copyright 2018 Grid Singularity
//This file is part of D3A.
//
//This program is free software: you can redistribute it and/or modify
//it under the terms of the GNU General Public License as published by
//the Free Software Foundation, either version 3 of the License, or
//(at your option) any later version.
//
//This program is distributed in the hope that it will be useful,
//but WITHOUT ANY WARRANTY; without even the implied warranty of
//MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
//GNU General Public License for more details.
//
//You should have received a copy of the GNU General Public License
//along with this program.  If not, see <http://www.gnu.org/licenses/>.
pragma solidity 0.5.1;


library ItSet {
    struct SetEntry {
        uint idx;
    }

    struct ByteSet {
        mapping(bytes32=>SetEntry) entries;
        bytes32[] list;
    }

    function insert(ByteSet storage self, bytes32 k) internal {
        if (self.entries[k].idx == 0) {
            self.entries[k].idx = self.list.length + 1;
            self.list.push(k);
        }
    }

    function contains(ByteSet storage self, bytes32 k) internal view returns (bool) {
        return self.entries[k].idx > 0;
    }

    function remove(ByteSet storage self, bytes32 k) internal {
        var entry = self.entries[k];
        if (entry.idx > 0) {
            var otherkey = self.list[self.list.length - 1];
            self.list[entry.idx - 1] = otherkey;
            self.list.length -= 1;

            self.entries[otherkey].idx = entry.idx;
            entry.idx = 0;
        }
    }

    function size(ByteSet storage self) internal view returns (uint) {
        return self.list.length;
    }
}
