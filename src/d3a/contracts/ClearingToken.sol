pragma solidity 0.4.25;
import "IOUToken.sol";
import "Mortal.sol";


contract ClearingToken is IOUToken, Owned {

    // Mapping of the clearing member which is allowed to transfer IOU's
    //between any accounts. These could also be market contracts.
    mapping (address => int256) public clearingMemberAmount;

    // list of all the clearing members
    address[] public clearingMembers;

    constructor(
        uint128 _initialAmount,
        string _tokenName,
        uint8 _decimalUnits,
        string _tokenSymbol
    ) public IOUToken(
        _initialAmount,
        _tokenName,
        _decimalUnits,
        _tokenSymbol
    ) {
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
    function getApprovedMarkets() public view returns (address[]) {
        return clearingMembers;
    }

}
