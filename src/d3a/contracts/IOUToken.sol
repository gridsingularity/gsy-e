pragma solidity ^0.4.4;
import "StandardToken.sol";

contract IOUToken is StandardToken{


    string public name;
    uint8 public decimals;
    string public symbol;


    function () {
        //if ether is sent to this address, send it back.
        throw;
    }

    function IOUToken(
      uint256 _initialAmount,
      string _tokenName,
      uint8 _decimalUnits,
      string _tokenSymbol
      ) {
      balances[msg.sender] = int(_initialAmount);               // Give the creator all initial tokens
      totalSupply = _initialAmount;                        // Update total supply
      name = _tokenName;                                   // Set the name for display purposes
      decimals = _decimalUnits;                            // Amount of decimals for display purposes
      symbol = _tokenSymbol;                               // Set the symbol for display purposes
    }

}
