pragma solidity ^0.4.23;
import "./IOUToken.sol";

contract ClearingToken is IOUToken {

    // Approves Clearing Members to be registered with this contract
    // Initialized while making the contract
    address approver;

    // Mapping of the clearing member which is allowed to transfer IOU's
    //between any accounts. These could also be market contracts.
    mapping (address => uint256) clearingMemberAmount;

    // list of all the clearing members
    address[] clearingMembers;

    constructor(
        uint128 _initialAmount,
        string _tokenName,
        uint8 _decimalUnits,
        string _tokenSymbol
    ) IOUToken(
        _initialAmount,
        _tokenName,
        _decimalUnits,
        _tokenSymbol
    ) public {

        approver = msg.sender;
    }

    // event
    event ApproveClearingMember(address indexed market, address indexed approver);

    /*
     * @notice transfers _value tokens from the _from to _to address.
     * @notice the clearing member needs to be registered for the transfer.
     */
    function clearingTransfer(address _from, address _to, int256 _value) public returns (bool success) {
        // 1st condition checks whether market is registered and
        // second condition checks whether _value is below the allowed value for transfers
        if (clearingMemberAmount[msg.sender] > 0 && _value < int(clearingMemberAmount[msg.sender])) {
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
    function globallyApprove(address clearingMember, uint _value) public returns (bool success) {
        // Only the approver can call this function to add a clearingMember
        if (msg.sender == approver && _value > 0) {
            clearingMemberAmount[clearingMember] = _value;
            clearingMembers.push(clearingMember);
            success = true;
            emit ApproveClearingMember(clearingMember, approver);
        } else {
            success = false;
        }
    }

    /*
     * @notice Status whether Market is registered
     */
    function isGloballyApproved(address clearingMember) public constant returns (bool) {
        return clearingMemberAmount[clearingMember] > 0;
    }

    /*
     * @notice Gets the owner which approves cleaing members of the contract
     */
    function getApprover() public constant returns (address) {
        return approver;
    }

    /*
     * @notice Gets all approved markets in the contracts
     */
    function getApprovedMarkets() public constant returns (address[]) {
        return clearingMembers;
    }

}
