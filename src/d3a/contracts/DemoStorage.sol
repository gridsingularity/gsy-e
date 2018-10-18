pragma solidity 0.4.25;

contract DemoStorage {
    uint current_power;
    uint current_voltage;

    // Events
    event NewPower(uint energyUnits, address indexed seller);

    function set_power(uint x) {
        current_power = x;
        emit NewPower(x, msg.sender);

    }

    function set_voltage(uint y) {
        current_voltage = y;
    }

    function get_power() constant returns (uint) {
        return current_power;
    }

    function get_voltage() constant returns (uint) {
        return current_voltage;
    }
}
