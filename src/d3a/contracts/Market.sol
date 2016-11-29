pragma solidity ^0.4.4;
import "IOUToken.sol";
import "MoneyIOU.sol";
import "byte_set_lib.sol";
contract Market is IOUToken{

    using ItSet for ItSet.ByteSet;

    mapping (bytes32 => Offer) offers;

    struct Offer {

        uint energyUnits;
        int price;
        address seller;
    }

    ItSet.ByteSet offerIdSet;

    MoneyIOU moneyIOU;

    function Market(
        address moneyIOUAddress,
        uint128 _initialAmount,
        string _tokenName,
        uint8 _decimalUnits,
        string _tokenSymbol
    ) IOUToken(
        _initialAmount,
        _tokenName,
        _decimalUnits,
        _tokenSymbol) {

        moneyIOU = MoneyIOU(moneyIOUAddress);
    }

    bytes32[] tempOffersIds;

    function offer(uint energyUnits, int price) returns (bytes32 offerId) {

        if (energyUnits > 0) {
            offerId = sha3(energyUnits, price, msg.sender, block.number);
            Offer offer = offers[offerId];
            offer.energyUnits = energyUnits;
            offer.price = price;
            offer.seller = msg.sender;
            offerIdSet.insert(offerId);
        }
        else {
            offerId = "";
        }
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

        if (offer.energyUnits > 0
            && offer.seller != address(0)
            && msg.sender != offer.seller) {
            balances[buyer] += int(offer.energyUnits);
            balances[offer.seller] -= int(offer.energyUnits);
            int cost = int(offer.energyUnits) * offer.price;
            success = moneyIOU.marketTransfer(buyer, offer.seller, cost);
            if (success) {
                success = true;
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

    function getOffer(bytes32 offerId) constant returns (uint, int, address) {
        Offer offer = offers[offerId];
        return (offer.energyUnits, offer.price, offer.seller);
    }

    function getAllOffers() constant returns (bytes32[]) {
        return offerIdSet.list;
    }

    function getMoneyIOUAddress() constant returns (address) {
        return address(moneyIOU);
    }

    function getOffersIdsBelow(int _value) constant returns (bytes32[]) {
        delete tempOffersIds;
        uint j = 0;
        for (uint i = 0; i < offerIdSet.size(); i++) {
            Offer offer = offers[offerIdSet.list[i]];
            if (offer.energyUnits > 0
                && offer.price < _value
                && offer.seller != address(0)) {

                tempOffersIds.push(offerIdSet.list[i]);
                j += 1;
            }
        }
        return tempOffersIds;
    }
}
