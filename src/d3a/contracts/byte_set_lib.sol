pragma solidity ^0.4.4;
library ItSet {
    struct SetEntry {
        uint idx;
    }

    struct ByteSet {
        mapping(bytes32=>SetEntry) entries;
        bytes32[] list;
    }

    function insert(ByteSet storage self, bytes32 k) internal {
        var entry = self.entries[k];
        if(entry.idx == 0) {
            entry.idx = self.list.length + 1;
            self.list.push(k);
        }
    }

    function contains(ByteSet storage self, bytes32 k) internal constant returns (bool) {
        return self.entries[k].idx > 0;
    }

    function remove(ByteSet storage self, bytes32 k) internal {
        var entry = self.entries[k];
        if(entry.idx > 0) {
            var otherkey = self.list[self.list.length - 1];
            self.list[entry.idx - 1] = otherkey;
            self.list.length -= 1;

            self.entries[otherkey].idx = entry.idx;
            entry.idx = 0;
        }
    }

    function size(ByteSet storage self) internal constant returns (uint) {
        return self.list.length;
    }
}
