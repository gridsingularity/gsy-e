pragma solidity ^0.4.4;
import "IOUToken.sol";


contract MoneyIOU is IOUToken {

    // Approves the Market to be registered with this contract
    // Initialized while making the contract
    address approver;

    mapping (address => uint256) allowedMarkets;

    address[] markets;

    function MoneyIOU(
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
    event ApproveMarket(address indexed market, address indexed approver);

    /*
     * @notice transfers _value tokens from the _from to _to address.
     * @notice the market needs to be registered for the transfer.
     */
    function marketTransfer(address _from, address _to, int256 _value) returns (bool success) {
        // 1st condition checks whether market is registered and
        // second condition checks whether _value is below the allowed value for transfers
        if (allowedMarkets[msg.sender] > 0 && _value < int(allowedMarkets[msg.sender])) {
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
    function globallyApprove(uint _value) returns (bool success) {
        if (tx.origin == approver && _value > 0) {
            allowedMarkets[msg.sender] = _value;
            markets.push(msg.sender);
            success = true;
            ApproveMarket(msg.sender, approver);
        } else {
            success = false;
        }
    }

    /*
     * @notice Tells whethe Market is registered
     */
    function isGloballyApproved(address _market) constant returns (bool) {
        return allowedMarkets[_market] > 0;
    }

    function getApprover() constant returns (address) {
        return approver;
    }

    /*
     * @notice Gets all approved markets in the contracts
     */
    function getApprovedMarkets() constant returns (address[]) {
        return markets;
    }

}
