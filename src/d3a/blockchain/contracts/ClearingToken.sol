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
import "IOUToken.sol";
import "Mortal.sol";


contract ClearingToken is IOUToken, Owned {

    // Mapping of the clearing member which is allowed to transfer IOU's
    //between any accounts. These could also be market contracts.
    mapping (address => int256) public clearingMemberAmount;

    // list of all the clearing members
    address[] public clearingMembers;

    uint256 private offerNonce;

    constructor(
        uint128 _initialAmount,
        string memory _tokenName,
        uint8 _decimalUnits,
        string memory _tokenSymbol
    ) public IOUToken(
        _initialAmount,
        _tokenName,
        _decimalUnits,
        _tokenSymbol
    ) {
        offerNonce = 0;
    }

    //Added here to generate unique OfferID
    function getAndIncreaseNonce() public returns (uint256 nonce) {
        return offerNonce++;
    }

    // event
    event ApproveClearingMember(address indexed market, address indexed approver);

    /*
     * @notice transfers _value tokens from the _from to _to address.
     * @notice the clearing member needs to be registered for the transfer.
     */
    function clearingTransfer(address _from, address _to, int256 _value) public payable returns (bool success) {
        // 1st condition checks whether market is registered and
        // second condition checks whether _value is below the allowed value for transfers
        if (isGloballyApproved(msg.sender)) {
             // balance mapping has been passed on from
             // StandardToken -> IOUToken -> ClearingToken
             // balance could be negative
            balances[_to] += int(_value);
            balances[_from] -= int(_value);
            success = true;
        } else {
            success = false;
        }
    }

    /*
     * @notice Approves a clearing member to make the token transfers between participants
     * @param clearingMember an address which is allowed to transfer the specified
     * _value token between any accounts
     * @param _value Maximum amount allowed to be transferred between the participants
     */
    function globallyApprove(address clearingMember, int256 _value) public onlyowner returns (bool success) {
        // Only the approver can call this function to add a clearingMember
        if (_value > 0) {
            clearingMemberAmount[clearingMember] = _value;
            clearingMembers.push(clearingMember);
            success = true;
            emit ApproveClearingMember(clearingMember, owner);
        } else {
            success = false;
        }
    }

    /*
     * @notice Status whether Market is registered
     */
    function isGloballyApproved(address clearingMember) public view returns (bool) {
        return clearingMemberAmount[clearingMember] > 0;
    }

    /*
     * @notice Gets the owner which approves cleaing members of the contract
     */
    function getApprover() public view returns (address) {
        return owner;
    }

    /*
     * @notice Gets all approved markets in the contracts
     */
    function getApprovedMarkets() public view returns (address[] memory) {
        return clearingMembers;
    }

}
