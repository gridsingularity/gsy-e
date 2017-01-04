pragma solidity ^0.4.4;
import "IOUToken.sol";
import "ClearingToken.sol";


contract Market is IOUToken {

    // holds the offerId -> Offer() mapping
    mapping (bytes32 => Offer) offers;

    struct Offer {

        uint energyUnits;
        int price;
        address seller;
    }


    // Holds the reference to clearingToken contract used for token transfers
    ClearingToken clearingToken;

    // Initialized when the market contract is created on the blockchain
    uint marketStartTime;

    // The interval of time for which market can be used for trading
    uint interval;

    function Market(
        address clearingTokenAddress,
        uint128 _initialAmount,
        string _tokenName,
        uint8 _decimalUnits,
        string _tokenSymbol,
        uint _interval
    ) IOUToken(
        _initialAmount,
        _tokenName,
        _decimalUnits,
        _tokenSymbol ) {

        clearingToken = ClearingToken(clearingTokenAddress);
        interval = _interval;
        marketStartTime = now;
    }

    // Temp storage for OfferIds
    bytes32[] tempOffersIds;

    // Events
    event OfferEvent(bytes32 offerId, uint energyUnits, int price, address indexed seller);
    event CancelOffer(uint energyUnits, int price, address indexed seller);
    event Trade(address indexed buyer, address indexed seller, uint energyUnits, int price);
    event OfferChanged(bytes32 oldOfferId, uint energyUnits, int price, address indexed seller);
    /*
     * @notice The msg.sender is able to put new offers.
     * @param energyUnits the units of energy offered generally in KWh.
     * @param price the price of each unit.
     */
    function offer(uint energyUnits, int price) returns (bytes32 offerId) {

        if (energyUnits > 0) {
            offerId = sha3(energyUnits, price, msg.sender, block.number);
            Offer offer = offers[offerId];
            offer.energyUnits = energyUnits;
            offer.price = price;
            offer.seller = msg.sender;
            OfferEvent(offerId, offer.energyUnits, offer.price, offer.seller);
        } else {
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
            CancelOffer(offer.energyUnits, offer.price, offer.seller);
            offer.energyUnits = 0;
            offer.price = 0;
            offer.seller = 0;
            success = true;
        } else {
          success = false;
        }
    }

    /*
     * @notice matches the existing offer with the Id
     * @notice adds the energyUnits to balance[buyer] and subtracts from balance[offer.seller]
     * @notice calls the ClearingToken contract to transfer tokens from buyer to offer.seller
     * @notice market needs to be registered with ClearingToken to transfer tokens
     * @notice market only runs for the "interval" amount of time from the
     *         from the "marketStartTime"
     */
    function trade(bytes32 offerId, uint tradedEnergyUnits) returns (bool success, bytes32 newOfferId) {
        Offer offer = offers[offerId];
        address buyer = msg.sender;
        if (offer.energyUnits > 0
            && offer.seller != address(0)
            && msg.sender != offer.seller
            && now-marketStartTime < interval
            && withinRange(tradedEnergyUnits, 0, offer.energyUnits)) {
            // Allow Partial Trading, if tradedEnergyUnits  are less than the
            // energyUnits in the offer. Make a new offer with the remaining energyUnits
            // and the same price. Also emit OfferChanged event with old offerId
            // and new Offer values.
            if (tradedEnergyUnits < offer.energyUnits) {
                uint newEnergyUnits = offer.energyUnits - tradedEnergyUnits;
                newOfferId = partialOffer(newEnergyUnits, offer.price, offer.seller);
                OfferChanged(offerId, newEnergyUnits, offer.price, offer.seller);
            }
            // Record exchange of energy between buyer and seller
            balances[buyer] += int(tradedEnergyUnits);
            balances[offer.seller] -= int(tradedEnergyUnits);
            if (offer.price != 0) {
                int cost = int(tradedEnergyUnits) * offer.price;
                success = clearingToken.clearingTransfer(buyer, offer.seller, cost);
            }
            if (success || offer.price == 0) {
                Trade(buyer, offer.seller, tradedEnergyUnits, offer.price);
                offer.energyUnits = 0;
                offer.price = 0;
                offer.seller = 0;
                success = true;
            } else {
                throw;
            }
        } else {
            success = false;
        }
    }

    /*
     * @notice Gets the Offer tuple if given a valid offerid
     */
    function getOffer(bytes32 offerId) constant returns (uint, int, address) {
        Offer offer = offers[offerId];
        return (offer.energyUnits, offer.price, offer.seller);
    }

    /*
     * Gets the address of the ClearingToken contract that the market is registered with
     */
    function getClearingTokenAddress() constant returns (address) {
        return address(clearingToken);
    }

    function partialOffer(uint energyUnits, int price, address seller)
    private returns (bytes32 offerId) {
      offerId = sha3(energyUnits, price, seller, block.number);
      Offer offer = offers[offerId];
      offer.energyUnits = energyUnits;
      offer.price = price;
      offer.seller = seller;
      OfferEvent(offerId, offer.energyUnits, offer.price, offer.seller);
    }

    function withinRange(uint value, uint lower, uint upper) private constant returns (bool) {
        return value > lower && value <= upper;
    }
}
