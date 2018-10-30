pragma solidity 0.4.25;
import "ClearingToken.sol";


contract Market is Mortal {

    // holds the offerId -> Offer() mapping
    mapping (bytes32 => Offer) private offers;

    // Nonce counter to ensure unique offer ids
    uint private offerNonce = 0;

    //mapping of the energy balances for market participants
    mapping (address => int256) private balances;

    //Container to hold the details of the Offer
    struct Offer {

        uint energyUnits;
        int price;
        address seller;
    }

    // Holds the reference to ClearingToken contract used for token transfers
    ClearingToken private clearingToken;

    // Initialized when the market contract is created on the blockchain
    uint private marketStartTime;

    // The interval of time for which market can be used for trading
    uint private interval;

    constructor(address clearingTokenAddress, uint _interval) public {
        clearingToken = ClearingToken(clearingTokenAddress);
        interval = _interval;
        marketStartTime = block.timestamp;
    }

    // Events
    event NewOffer(bytes32 offerId, uint energyUnits, int price, address indexed seller);

    event CancelOffer(uint energyUnits, int price, address indexed seller);

    event NewTrade(bytes32 tradeId, address indexed buyer, address indexed seller,
    uint energyUnits, int price, bool success);

    event OfferChanged(bytes32 oldOfferId, bytes32 newOfferId,
    uint energyUnits, int price, address indexed seller, bool success);

    /*
     * @notice The msg.sender is able to introduce new offers.
     * @param energyUnits the units of energy offered generally in KWh.
     * @param price the price of each unit.
     */
    function offer(uint energyUnits, int price) public {
        (
        bool success,
        bytes32 id) = _offer(energyUnits, price, msg.sender);
        if (success) {
            emit NewOffer(id, energyUnits, price, msg.sender);
        }
    }

    /*
     * @notice Only the offer seller is able to cancel the offer
     * @param offerId Id of the offer
     */
    function cancel(bytes32 offerId) public returns (bool success) {
        Offer storage cancelledOffer = offers[offerId];
        if (cancelledOffer.seller == msg.sender) {
            emit CancelOffer(cancelledOffer.energyUnits, cancelledOffer.price, cancelledOffer.seller);
            cancelledOffer.energyUnits = 0;
            cancelledOffer.price = 0;
            cancelledOffer.seller = 0;
            success = true;
        } else {
            success = false;
        }
    }

    /*
     * @notice matches the existing offer with the Id
     * @notice adds the energyUnits to balance[buyer] and subtracts from balance[tradedOffer.seller]
     * @notice calls the ClearingToken contract to transfer tokens from buyer to tradedOffer.seller
     * @notice market needs to be registered with ClearingToken to transfer tokens
     * @notice market only runs for the "interval" amount of time from the
     *         from the "marketStartTime"
     * @ tradedEnergyUnits Allows for partial trading of energyUnits from an offer
     */
    function trade(bytes32 offerId, uint tradedEnergyUnits) public returns (bool success,
        bytes32 newOfferId, bytes32 tradeId) {
        Offer storage tradedOffer = offers[offerId];
        address buyer = msg.sender;
        if (
        tradedOffer.energyUnits > 0 &&
        tradedOffer.seller != address(0) &&
        msg.sender != tradedOffer.seller &&
//        "Needs to be uncommented once network latency issue is solved"
//        block.timestamp-marketStartTime < interval &&
        tradedEnergyUnits > 0 &&
        tradedEnergyUnits <= tradedOffer.energyUnits
        ) {
            success = true;
            // Allow Partial Trading, if tradedEnergyUnits  are less than the
            // energyUnits in the offer, make a new offer with the remaining energyUnits
            // and the same price. Also emit OfferChanged event with old offerId
            // and new Offer values.

            if (tradedEnergyUnits < tradedOffer.energyUnits) {
                uint newEnergyUnits = tradedOffer.energyUnits - tradedEnergyUnits;
                (success, newOfferId) = _offer(newEnergyUnits, tradedOffer.price, tradedOffer.seller);
                emit OfferChanged(offerId, newOfferId, newEnergyUnits, tradedOffer.price, tradedOffer.seller, success);
            }
            // Record exchange of energy between buyer and seller
            balances[buyer] += int(tradedEnergyUnits);
            balances[tradedOffer.seller] -= int(tradedEnergyUnits);
            // if the offer price is either positive or negative there has to be
            // a clearingTransfer to transfer Tokens from buyer to seller or
            // vice versa
            if (tradedOffer.price != 0) {
                int256 cost = int256(tradedEnergyUnits) * tradedOffer.price;
                success = clearingToken.clearingTransfer(buyer, tradedOffer.seller, cost);
            }
            if (success || tradedOffer.price == 0) {
                tradeId = keccak256(
                    abi.encodePacked(offerId, buyer)
                );
                emit NewTrade(tradeId, buyer, tradedOffer.seller, tradedEnergyUnits, tradedOffer.price, true);
                tradedOffer.energyUnits = 0;
                tradedOffer.price = 0;
                tradedOffer.seller = 0;
                success = true;
            } else {
                emit NewTrade(offerId, buyer, tradedOffer.seller, tradedEnergyUnits, tradedOffer.price, false);
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

    function _offer(uint energyUnits, int price, address seller)
    private returns (bool success, bytes32 offerId) {

        if (energyUnits > 0) {
            offerId = keccak256(
                abi.encode(energyUnits, price, seller, offerNonce++)
            );
            offers[offerId] = Offer(energyUnits, price, msg.sender);
            offers[offerId].energyUnits = energyUnits;
            offers[offerId].price = price;
            offers[offerId].seller = seller;
            success = true;
        } else {
            success = false;
            offerId = bytes32(0);
        }
    }
}