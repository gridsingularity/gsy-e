/*
You should inherit from StandardToken or, for a token like you would want to
deploy in something like Mist, see HumanStandardToken.sol.
(This implements ONLY the standard functions and NOTHING else.
If you deploy this, you won't have anything useful.)

Implements ERC 20 Token standard: https://github.com/ethereum/EIPs/issues/20
.*/

pragma solidity 0.4.25;
import "./Token.sol";


contract StandardToken is Token {

    /*
     * @notice StandardToken can  have negative value of tokens
     * @param _to address to which tokens are to be transferred
     * @param _value of tokens that needs to be transferred
     */
    function transfer(address _to, uint256 _value) public returns (bool success) {

        if (_value > 0) {
            balances[msg.sender] -= int(_value);
            balances[_to] += int(_value);
            emit Transfer(msg.sender, _to, _value);
            return true;
        } else {
            return false;
        }
    }

    /*
     * @notice transfers _value  from the _from address to the _to address
     */
    function transferFrom(address _from, address _to, uint256 _value) public returns (bool success) {

        if (allowed[_from][msg.sender] >= _value && _value > 0) {
            balances[_to] += int(_value);
            balances[_from] -= int(_value);
            allowed[_from][msg.sender] -= _value;
            emit Transfer(_from, _to, _value);
            return true;
        } else {
            return false;
        }
    }

    /*
     * @notice Gets the token balance of _ownner
     */
     //@faizan: might be better to use msg.sender rather than _owner
    function balanceOf(address _owner) public view returns (int256 balance) {
        return balances[_owner];
    }

    /*
     * @notice msg.sender can approve _spender to spend _value tokens
     * on its behalf
     */
    function approve(address _spender, uint256 _value) public returns (bool success) {
        allowed[msg.sender][_spender] = _value;
        emit Approval(msg.sender, _spender, _value);
        return true;
    }

    /*
     * @notice Gets the amounts of tokens _owner has authorised _spender to
     * spend on its behalf
     */
    function allowance(address _owner, address _spender) public view returns (uint256 remaining) {
        return allowed[_owner][_spender];
    }

    // Balances can be negative hence mapping from address to int256 type
    mapping (address => int256) internal balances;
    mapping (address => mapping (address => uint256)) internal allowed;
}
