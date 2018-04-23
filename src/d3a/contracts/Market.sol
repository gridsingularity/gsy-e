pragma solidity ^0.4.4;
import "ClearingToken.sol";
import "github.com/ethereum/solidity/std/mortal.sol";


contract Market is mortal {

    // holds the offerId -> Offer() mapping
    mapping (bytes32 => Offer) offers;

    //mapping of the energy balances for market participants
    mapping (address => int256) balances;

    //Container to hold the details of the Offer
    struct Offer {

        uint energyUnits;
        int price;
        address seller;
    }


    // Holds the reference to ClearingToken contract used for token transfers
    ClearingToken clearingToken;

    // Initialized when the market contract is created on the blockchain
    uint marketStartTime;

    // The interval of time for which market can be used for trading
    uint interval;

    function Market(address clearingTokenAddress, uint _interval) {

        clearingToken = ClearingToken(clearingTokenAddress);
        interval = _interval;
        marketStartTime = now;
    }


    // Events
    event NewOffer(bytes32 offerId, uint energyUnits, int price, address indexed seller);
    event CancelOffer(uint energyUnits, int price, address indexed seller);
    event Trade(address indexed buyer, address indexed seller, uint energyUnits, int price);
    event OfferChanged(bytes32 oldOfferId, bytes32 newOfferId, uint energyUnits, int price,
      address indexed seller);

    /*
     * @notice The msg.sender is able to introduce new offers.
     * @param energyUnits the units of energy offered generally in KWh.
     * @param price the price of each unit.
     */
    function offer(uint energyUnits, int price) returns (bytes32 offerId) {
        var (success, id) = _offer(energyUnits, price, msg.sender);
        if (success) NewOffer(id, energyUnits, price, msg.sender);
        offerId = id;
    }

    function _offer(uint energyUnits, int price, address seller)
    private returns (bool success, bytes32 offerId) {

        if (energyUnits > 0) {
            offerId = sha3(energyUnits, price, seller, block.number);
            Offer offer = offers[offerId];
            offer.energyUnits = energyUnits;
            offer.price = price;
            offer.seller = seller;
            success = true;
        } else {
            success = false;
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
     * @ tradedEnergyUnits Allows for partial trading of energyUnits from an offer
     */
    function trade(bytes32 offerId, uint tradedEnergyUnits) returns (bool success, bytes32 newOfferId) {
        Offer offer = offers[offerId];
        address buyer = msg.sender;
        if (offer.energyUnits > 0
            && offer.seller != address(0)
            && msg.sender != offer.seller
            && now-marketStartTime < interval
            && tradedEnergyUnits > 0
            && tradedEnergyUnits <= offer.energyUnits) {
            // Allow Partial Trading, if tradedEnergyUnits  are less than the
            // energyUnits in the offer, make a new offer with the remaining energyUnits
            // and the same price. Also emit OfferChanged event with old offerId
            // and new Offer values.
            if (tradedEnergyUnits < offer.energyUnits) {
                uint newEnergyUnits = offer.energyUnits - tradedEnergyUnits;
                (success, newOfferId) = _offer(newEnergyUnits, offer.price, offer.seller);
                OfferChanged(offerId, newOfferId, newEnergyUnits, offer.price, offer.seller);
            }
            // Record exchange of energy between buyer and seller
            balances[buyer] += int(tradedEnergyUnits);
            balances[offer.seller] -= int(tradedEnergyUnits);
            // if the offer price is either positive or negative there has to be
            // a clearingTransfer to transfer Tokens from buyer to seller or
            // vice versa
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
     * @notice Gets the address of the ClearingToken contract
     */
    function getClearingTokenAddress() constant returns (address) {
        return address(clearingToken);
    }

    /*
     * @notice Gets the energy balance of _owner
     */
    function balanceOf(address _owner) constant returns (int256 balance) {
        return balances[_owner];
    }

}
