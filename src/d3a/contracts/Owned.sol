pragma solidity 0.4.25;


contract Owned {
    address owner;

    modifier onlyowner() {
        if (msg.sender == owner) {
            _;
        }
    }

    constructor () public {
        owner = msg.sender;
    }
}
