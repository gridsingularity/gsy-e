pragma solidity 0.4.25;

import "./Owned.sol";


contract Mortal is Owned {
    function kill() public {
        if (msg.sender == owner)
            selfdestruct(owner);
    }
}
