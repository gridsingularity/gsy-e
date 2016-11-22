pragma solidity ^0.4.4;
import "IOUToken.sol";

contract MoneyIOU is IOUToken{
    address owner;
    address marketAddress;

    function MoneyIOU(){
        address owner = msg.sender;
    }

    function globalApprove() returns (bool success) {
        if (tx.origin == owner) {
            marketAddress = msg.sender;
            success = true;
        } else {
            success = false;
        }

    }

    function transferFrom(address _from, address _to, uint256 _value) returns (bool success) {
        if (msg.sender == marketAddress && _value > 0) {
            balances[_from] -= int(_value);
            balances[_to] += int(_value);
        } else {
              return false;
        }
    }

    function getOwner() constant returns (address) {
        return owner;
    }

    function getMarketAddress() constant returns (address) {
        return marketAddress;
    }
}
