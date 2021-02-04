The Inter-Area Agent (IAA) plays a crucial role in the communication architecture of Grid Singularity’s exchange engine (D3A), allowing different markets in the hierarchy to interact and trade with each other. IAA is created for each market (households/buildings, streets, etc. that do not have preset trading strategies) and mainly deals with forwarding bids and offers  markets of different hierarchy levels. 

The following illustration shows a sample grid setup and the role of the IAA in the market hierarchy during one time slot:

![alt_text](images/image1.png "image_tooltip")

The IAA is responsible for modelling hierarchical market operations, as follows:

*   **Forwarding** bids and offers from a lower hierarchy (market) to an upper hierarchy.
*   **Reacting** to bids, offers and trades reported by IAAs in connected markets, in order to propagate the event for an offer/bid that has been forwarded from this IAA.
*   Triggering the **matching** of bids and offers for the two-sided market.

To prioritize local trades, IAAs forward bids and offers to higher/lower markets with a **two-tick delay**. 
