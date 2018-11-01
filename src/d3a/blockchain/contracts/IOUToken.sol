pragma solidity 0.4.25;
import "StandardToken.sol";


// Since IOUToken inherits from StandardToken it has all functionalities of
// StandardToken
contract IOUToken is StandardToken {
    string public name;
    uint8 public decimals;
    string public symbol;

    constructor(
        uint128 _initialAmount,
        string _tokenName,
        uint8 _decimalUnits,
        string _tokenSymbol
    ) public {
        balances[msg.sender] = int(_initialAmount);          // Give the creator all initial tokens
        totalSupply = _initialAmount;                        // Update total supply
        name = _tokenName;                                   // Set the name for display purposes
        decimals = _decimalUnits;                            // Amount of decimals for display purposes
        symbol = _tokenSymbol;                               // Set the symbol for display purposes
    }

    function () public payable {
        // if ether is sent to this address, send it back.
        revert("Ether should never be sent to this address.");
    }

    /* Approves and then calls the receiving contract */
    function approveAndCall(address _spender, uint256 _value, bytes _extraData) public returns (bool success) {
        allowed[msg.sender][_spender] = _value;
        emit Approval(msg.sender, _spender, _value);

        // call the receiveApproval function on the contract you want to be notified.
        // This crafts the function signature manually so one doesn't have to include a contract in here just for this.
        // receiveApproval(address _from, uint256 _value, address _tokenContract, bytes _extraData)
        // it is assumed that when does this that the call *should* succeed, otherwise one would use
        // vanilla approve instead.
        if (!_spender.call(bytes4(keccak256("receiveApproval(address,uint256,address,bytes)")),
            msg.sender, _value, this, _extraData)) {
            revert("Failed to call receiveApproval callback.");
        }
        return true;
    }
}
