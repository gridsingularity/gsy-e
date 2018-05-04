pragma solidity ^0.4.23;
import "./ClearingToken.sol";
import "./Mortal.sol";

contract Market is Mortal {

    // holds the offerId -> Offer() mapping
    mapping (bytes32 => Offer) offers;

    // Nonce counter to ensure unique offer ids
    uint offerNonce;

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

    constructor (address clearingTokenAddress, uint _interval) public {

        clearingToken = ClearingToken(clearingTokenAddress);
        interval = _interval;
        marketStartTime = block.timestamp;
    }


    // Events
    event NewOffer(bytes32 offerId, uint energyUnits, int price, address indexed seller);
    event CancelOffer(uint energyUnits, int price, address indexed seller);
    event Trade(bytes32 tradeId, address indexed buyer, address indexed seller, uint energyUnits, int price);
    event OfferChanged(bytes32 oldOfferId, bytes32 newOfferId, uint energyUnits, int price,
    address indexed seller);

    /*
     * @notice The msg.sender is able to introduce new offers.
     * @param energyUnits the units of energy offered generally in KWh.
     * @param price the price of each unit.
     */
    function offer(uint energyUnits, int price) public returns (bytes32 offerId) {
        bool success;
        bytes32 id;
        (success, id) = _offer(energyUnits, price, msg.sender);
        if (success) emit NewOffer(id, energyUnits, price, msg.sender);
        offerId = id;
    }

    function _offer(uint energyUnits, int price, address seller)
    private returns (bool success, bytes32 offerId) {

        if (energyUnits > 0) {
            offerId = keccak256(energyUnits, price, seller, block.number, offerNonce++);
            offers[offerId].energyUnits = energyUnits;
            offers[offerId].price = price;
            offers[offerId].seller = seller;
            success = true;
        } else {
            success = false;
            offerId = 0x0;
        }
    }

    /*
     * @notice Only the offer seller is able to cancel the offer
     * @param offerId Id of the offer
     */
    function cancel(bytes32 offerId) public returns (bool success) {
        if (offers[offerId].seller == msg.sender) {
            emit CancelOffer(offers[offerId].energyUnits, offers[offerId].price, offers[offerId].seller);
            offers[offerId].energyUnits = 0;
            offers[offerId].price = 0;
            offers[offerId].seller = 0;
            success = true;
        }
        else {
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
    function trade(bytes32 offerId, uint tradedEnergyUnits) public returns (bool success, bytes32 newOfferId, bytes32 tradeId) {
        if ((offers[offerId].energyUnits > 0)&&
        (offers[offerId].seller != address(0))&&
        (msg.sender != offers[offerId].seller)&&
        (block.timestamp-marketStartTime < interval)&&
        (tradedEnergyUnits > 0)&&
        (tradedEnergyUnits <= offers[offerId].energyUnits)) {
            // Allow Partial Trading, if tradedEnergyUnits  are less than the
            // energyUnits in the offer, make a new offer with the remaining energyUnits
            // and the same price. Also emit OfferChanged event with old offerId
            // and new Offer values.
            if (tradedEnergyUnits < offers[offerId].energyUnits) {
                uint newEnergyUnits = offers[offerId].energyUnits - tradedEnergyUnits;
                (success, newOfferId) = _offer(newEnergyUnits, offers[offerId].price, offers[offerId].seller);
                emit OfferChanged(offerId, newOfferId, newEnergyUnits, offers[offerId].price, offers[offerId].seller);
            }
            // Record exchange of energy between buyer and seller
            balances[msg.sender] += int(tradedEnergyUnits);
            balances[offers[offerId].seller] -= int(tradedEnergyUnits);
            // if the offer price is either positive or negative there has to be
            // a clearingTransfer to transfer Tokens from buyer to seller or
            // vice versa
            if (offers[offerId].price != 0) {
                success = clearingToken.clearingTransfer(msg.sender, offers[offerId].seller, int(tradedEnergyUnits) * offers[offerId].price);
            }
            if (success || offers[offerId].price == 0) {
                tradeId = keccak256(offerId, msg.sender);
                emit Trade(tradeId, msg.sender, offers[offerId].seller, tradedEnergyUnits, offers[offerId].price);
                offers[offerId].energyUnits = 0;
                offers[offerId].price = 0;
                offers[offerId].seller = 0;
                success = true;
            } else {
                revert();
            }
        } else {
            success = false;
        }
    }

    /*
     * @notice Gets the Offer tuple if given a valid offerid
     */
    function getOffer(bytes32 offerId) public view returns (uint, int, address) {
        return (offers[offerId].energyUnits, offers[offerId].price, offers[offerId].seller);
    }

    /*
     * @notice Gets the address of the ClearingToken contract
     */
    function getClearingTokenAddress() public view returns (address) {
        return address(clearingToken);
    }

    /*
     * @notice Gets the energy balance of _owner
     */
    function balanceOf(address _owner) public view returns (int256 balance) {
        return balances[_owner];
    }

}
