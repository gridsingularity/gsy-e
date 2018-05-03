pragma solidity ^0.4.20;

import "./Owned.sol";


contract Mortal is Owned {
    function kill() public {
        if (msg.sender == owner)
            selfdestruct(owner);
    }
}
