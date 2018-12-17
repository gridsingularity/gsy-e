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
import "StandardToken.sol";


// Since IOUToken inherits from StandardToken it has all functionalities of
// StandardToken
contract IOUToken is StandardToken {
    string public name;
    uint8 public decimals;
    string public symbol;

    constructor(
        uint128 _initialAmount,
        string memory _tokenName,
        uint8 _decimalUnits,
        string memory _tokenSymbol
    ) public {
        balances[msg.sender] = int(_initialAmount);          // Give the creator all initial tokens
        totalSupply = _initialAmount;                        // Update total supply
        name = _tokenName;                                   // Set the name for display purposes
        decimals = _decimalUnits;                            // Amount of decimals for display purposes
        symbol = _tokenSymbol;                               // Set the symbol for display purposes
    }

    function () external payable {
        // if ether is sent to this address, send it back.
        revert("Ether should never be sent to this address.");
    }

    /* Approves and then calls the receiving contract */
    function approveAndCall(address _spender, uint256 _value, bytes memory _extraData) public returns (bool success) {
        allowed[msg.sender][_spender] = _value;
        emit Approval(msg.sender, _spender, _value);

        // call the receiveApproval function on the contract you want to be notified.
        // This crafts the function signature manually so one doesn't have to include a contract in here just for this.
        // receiveApproval(address _from, uint256 _value, address _tokenContract, bytes _extraData)
        // it is assumed that when does this that the call *should* succeed, otherwise one would use
        // vanilla approve instead.
        (bool retVal, bytes memory data) = _spender.call(abi.encodeWithSignature(
            "receiveApproval(address,uint256,address,bytes)",
            msg.sender, _value, this, _extraData
        ));
        if (!retVal) {
            revert("Failed to call receiveApproval callback.");
        }
        return true;
    }
}
