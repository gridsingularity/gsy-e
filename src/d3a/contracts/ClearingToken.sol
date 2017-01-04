pragma solidity ^0.4.4;
import "IOUToken.sol";


contract ClearingToken is IOUToken {

    // Approves Clearing Members to be registered with this contract
    // Initialized while making the contract
    address approver;

    // Mapping of the clearing member which is allowed to transfer IOU's
    //between any accounts. These could also be market contracts.
    mapping (address => uint256) clearingMemberAmount;

    // list of all the clearing members
    address[] clearingMembers;

    function ClearingToken(
        uint128 _initialAmount,
        string _tokenName,
        uint8 _decimalUnits,
        string _tokenSymbol
    ) IOUToken(
        _initialAmount,
        _tokenName,
        _decimalUnits,
        _tokenSymbol
    ) {

        approver = msg.sender;
    }

    // event
    event ApproveClearingMember(address indexed market, address indexed approver);

    /*
     * @notice transfers _value tokens from the _from to _to address.
     * @notice the market needs to be registered for the transfer.
     */
    function marketTransfer(address _from, address _to, int256 _value) returns (bool success) {
        // 1st condition checks whether market is registered and
        // second condition checks whether _value is below the allowed value for transfers
        if (clearingMemberAmount[msg.sender] > 0 && _value < int(clearingMemberAmount[msg.sender])) {
            balances[_to] += int(_value);
            balances[_from] -= int(_value);
            success = true;
        } else {
            success = false;
        }
    }

    /*
     * @notice Approves a market to make the token transfers between participants
     * @param _value Maximum amount allowed to be transferred between the participants
     */
    function globallyApprove(address clearingMember, uint _value) returns (bool success) {
        if (msg.sender == approver && _value > 0) {
            clearingMemberAmount[clearingMember] = _value;
            clearingMembers.push(clearingMember);
            success = true;
            ApproveClearingMember(clearingMember, approver);
        } else {
            success = false;
        }
    }

    /*
     * @notice Status whether Market is registered
     */
    function isGloballyApproved(address clearingMember) constant returns (bool) {
        return clearingMemberAmount[clearingMember] > 0;
    }

    /*
     * @notice Gets the owner which approves cleaing members of the contract
     */
    function getApprover() constant returns (address) {
        return approver;
    }

    /*
     * @notice Gets all approved markets in the contracts
     */
    function getApprovedMarkets() constant returns (address[]) {
        return clearingMembers;
    }

}
