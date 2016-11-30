pragma solidity ^0.4.4;
import "IOUToken.sol";
import "MoneyIOU.sol";
import "byte_set_lib.sol";
contract Market is IOUToken{

    using ItSet for ItSet.ByteSet;
    // holds the offerId -> Offer() mapping
    mapping (bytes32 => Offer) offers;

    struct Offer {

        uint energyUnits;
        int price;
        address seller;
    }
    // Holds set of all the offerIds
    ItSet.ByteSet offerIdSet;
    // Holds the reference to MoneyIOU contract used for token transfers
    MoneyIOU moneyIOU;

    // Initialized when the market contract is created on the blockchain
    uint marketStartTime;

    // The interval of time for which market can be used for trading
    uint interval;

    function Market(
        address moneyIOUAddress,
        uint128 _initialAmount,
        string _tokenName,
        uint8 _decimalUnits,
        string _tokenSymbol,
        uint _interval
    ) IOUToken(
        _initialAmount,
        _tokenName,
        _decimalUnits,
        _tokenSymbol) {

        moneyIOU = MoneyIOU(moneyIOUAddress);
        interval = _interval;
        marketStartTime = now;
    }

    // Temp storage for OfferIds
    bytes32[] tempOffersIds;

    // Events
    event OfferEvent(uint energyUnits, int price, address indexed seller, uint blocknumber);
    event CancelOffer(uint energyUnits, int price, address indexed seller);
    event Trade(address indexed buyer, address indexed seller, uint energyUnits, int price);

    /*
     * @notice The msg.sender is able to put new offers.
     * @param energyUnits the units of energy offered generally in KWh.
     * @param price the price of each unit.
     */
    function offer(uint energyUnits, int price) returns (bytes32 offerId) {

        if (energyUnits > 0 && price != 0) {
            offerId = sha3(energyUnits, price, msg.sender, block.number);
            Offer offer = offers[offerId];
            offer.energyUnits = energyUnits;
            offer.price = price;
            offer.seller = msg.sender;
            offerIdSet.insert(offerId);
            OfferEvent(offer.energyUnits, offer.price, offer.seller, block.number);
        }
        else {
            offerId = "";
        }
    }
    /*
     * @notice Only the offer seller is able to cancel the offer
     * @param offerId Id of the offer
     */
    function cancel(bytes32 offerId) returns (bool success) {
        Offer offer = offers[offerId];
        if (offer.seller == msg.sender) {
            offer.energyUnits = 0;
            offer.price = 0;
            offer.seller = 0;
            offerIdSet.remove(offerId);
            success = true;
            CancelOffer(offer.energyUnits, offer.price, offer.seller);
        }
        else {
          success = false;
        }
    }

    /*
     * @notice matches the existing offer with the Id
     * @notice adds the energyUnits to balance[buyer] and subtracts from balance[offer.seller]
     * @notice calls the MoneyIOU contract to transfer tokens from buyer to offer.seller
     * @notice market needs to be registered with MoneyIOU to transfer tokens
     * @notice market only runs for the "interval" amount of time from the
     *         from the "marketStartTime"
     */
    function trade(bytes32 offerId) returns (bool success) {
        Offer offer = offers[offerId];
        address buyer = msg.sender;

        if (offer.energyUnits > 0
            && offer.seller != address(0)
            && msg.sender != offer.seller
            && now-marketStartTime < interval) {
            balances[buyer] += int(offer.energyUnits);
            balances[offer.seller] -= int(offer.energyUnits);
            int cost = int(offer.energyUnits) * offer.price;
            success = moneyIOU.marketTransfer(buyer, offer.seller, cost);
            if (success) {
                Trade(buyer, offer.seller, offer.energyUnits, offer.price);
                offer.energyUnits = 0;
                offer.price = 0;
                offer.seller = 0;
                offerIdSet.remove(offerId);
                success = true;

            } else {
                throw;
            }
        } else {
            success = false;
        }
    }

    /*
     * @notice registers the market with the MoneyIOU contract for token transfers.
     * @notice For security the same user which makes the MoneyIOU contract calls
               this function to register the market.
     * @param _value the maximum amount that the market is allowed to transfer
     *        between the participants
     */
    function registerMarket(uint256 _value) returns (bool success) {
        success = moneyIOU.globallyApprove(_value);
    }

    /*
     * @notice Gets the Offer tuple if given a valid offerid
     */
    function getOffer(bytes32 offerId) constant returns (uint, int, address) {
        Offer offer = offers[offerId];
        return (offer.energyUnits, offer.price, offer.seller);
    }

    /*
     * Gets all OfferIds in the market
     */
    function getAllOffers() constant returns (bytes32[]) {
        return offerIdSet.list;
    }

    /*
     * Gets the address of the MoneyIOU contract that the market is registered with
     */
    function getMoneyIOUAddress() constant returns (address) {
        return address(moneyIOU);
    }

    /*
     * Gets all the offerids whose offer price is below _value
     */
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
