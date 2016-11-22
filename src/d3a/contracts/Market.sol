pragma solidity ^0.4.4;
import "IOUToken.sol";
import "MoneyIOU.sol";
contract Market is IOUToken{

mapping (bytes32 => Offer) offers;

struct Offer {

    uint energyUnits;

    uint price;

    address seller;
}

mapping (address => uint) energyBalances;

MoneyIOU moneyIOU;

function Market(address moneyIOUAddress){
    moneyIOU = MoneyIOU(moneyIOUAddress);
}

function offer(uint energyUnits, uint price) returns (bytes32 offerId) {

    offerId = sha3(energyUnits, price, msg.sender);
    Offer offer = offers[offerId];
    offer.energyUnits = energyUnits;
    offer.price = price;
    offer.seller = msg.sender;

}

function cancel(bytes32 offerId) returns (bool success) {
    Offer offer = offers[offerId];
    if (offer.seller == msg.sender) {
      offer.energyUnits = 0;
      offer.price = 0;
      offer.seller = 0;
      success = true;
    }
    else {
      success = false;
    }
}

function trade(bytes32 offerId) returns (bool success) {
    Offer offer = offers[offerId];
    address buyer = msg.sender;
    if ( offer.energyUnits != 0 && offer.price != 0 && offer.seller != address(0)) {
        energyBalances[msg.sender] += offer.energyUnits;
        energyBalances[offer.seller] -= offer.energyUnits;
        uint cost = offer.energyUnits * offer.price;
        moneyIOU.transferFrom(buyer, offer.seller, cost);
    }
    else {

    }
}

function registerMarket(){
    moneyIOU.globalApprove();
}


}
