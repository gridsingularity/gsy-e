pragma solidity ^0.4.4;
import "IOUToken.sol";

contract MoneyIOU is IOUToken{
    address marketAddress;

    function globalApprove(){
        marketAddress = msg.sender;
    }

    function transferFrom(address _from, address _to, uint256 _value) returns (bool success) {
      if (msg.sender == marketAddress && _value > 0) {
          balances[_from] -= int(_value);
          balances[_to] += int(_value);
        } else {
            return false;
        }
    }

}
