pragma solidity ^0.4.4;
import "IOUToken.sol";
import "MoneyIOU.sol";
import "byte_set_lib.sol";
contract Market is IOUToken{

    using ItSet for ItSet.ByteSet;

    mapping (bytes32 => Offer) offers;

    struct Offer {

        uint energyUnits;
        uint price;
        address seller;
        address buyer;
    }

    ItSet.ByteSet offerIdSet;

    MoneyIOU moneyIOU;

    function Market(address moneyIOUAddress) {
        moneyIOU = MoneyIOU(moneyIOUAddress);
    }


    function offer(uint energyUnits, uint price) returns (bytes32 offerId) {

        offerId = sha3(energyUnits, price, msg.sender);
        Offer offer = offers[offerId];
        offer.energyUnits = energyUnits;
        offer.price = price;
        offer.seller = msg.sender;
        offerIdSet.insert(offerId);
    }

    function cancel(bytes32 offerId) returns (bool success) {
        Offer offer = offers[offerId];
        if (offer.seller == msg.sender) {
          offer.energyUnits = 0;
          offer.price = 0;
          offer.seller = 0;
          offerIdSet.remove(offerId);
          success = true;
        }
        else {
          success = false;
        }
    }

    function trade(bytes32 offerId) returns (bool success) {
        Offer offer = offers[offerId];
        address buyer = msg.sender;
        if ( offer.energyUnits > 0 && offer.price > 0 && offer.seller != address(0)) {
            balances[msg.sender] += int(offer.energyUnits);
            balances[offer.seller] -= int(offer.energyUnits);
            uint cost = offer.energyUnits * offer.price;
            success = moneyIOU.transferFrom(buyer, offer.seller, cost);
            if (success) {
                offer.buyer = buyer;
            } else {
                throw;
            }
        } else {
            success = false;
        }
    }

    function registerMarket(uint256 _value) returns (bool success) {
        success = moneyIOU.globallyApprove(_value);
    }

    function getOffer(bytes32 offerId) constant returns(uint, uint, address, address) {
        Offer offer = offers[offerId];
        return (offer.energyUnits, offer.price, offer.seller, offer.buyer);
    }

    function getAllOffers() constant returns(bytes32[]) {
      return offerIdSet.list;
    }

}
