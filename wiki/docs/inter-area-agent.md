The Inter-Area Agent (IAA) plays a crucial role in the architecture of D3A.
It is created for each area class (for nodes such as Houses, streets, etc. that do not have configured strategies) and mainly deals with forwarding offers and bids between markets of different hierarchy levels. 
The IAA class accounts for the direction of the offer, meaning whether the offer is sent from a lower to a higher hierarchy layer or the other way around.
This is achieved by creating two separate IAA Engines for each direction.

**Sample grid setup and the role of the IAA in the hierarchy if nodes, leafs and markets (this scheme only applies for one time slot)**:

![img](img/inter-area-agent-1.png)

The Inter-Area Agent is responsible for modeling the inter-area operations for an area. The main functionalities of an inter-area agent can be summarized to these points:

- Forwarding offers from a lower hierarchy (market) to an upper hierarchy.
- Forwarding bids, in the same fashion as offers
- Keeping track of the aforementioned forwarded bids and offers
- Reacting to events coming from neighbouring inter-area agents, in order to propagate the event for an offer/bid that has been forwarded from this IAA.
- Triggering the matching of offers and bids for the two sided market.