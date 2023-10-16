The main goal of an electricity market exchange is to balance the grid in terms of demand and supply. Since efficient storage of large quantities of energy is currently not economically feasible and electrical current varies within seconds, a market mechanism that efficiently accounts for the physical energy production and consumption is required. Generally, trading occurs in three types of markets with different time intervals:

1. **[Spot market](spot-market-types.md)**: short-term trades for immediate or near-term delivery. Energy transactions are divided into small time blocks (typically 15 minute slots) that can either be traded on the Day-ahead or in the Intraday market.
2. **[Balancing market](balancing-market.md)**: balancing capacity and reserves purchased by the balancing responsible parties (BRP) or other local balancing agents to be deployed for future grid imbalances.
3. **[Settlement market](settlement-market-structure.md)**: post-delivery trades of deviations between energy physically produced/consumed and energy purchased in the spot or futures market to settle imbalances locally before BRP billing.
4. **Futures market**: Trades for the longer term future consumption and production of energy are agreed in advance. This market is currently in development of Grid Singularity energy exchange implementation.

<figure markdown>
  ![alt_text](img/market-types.png){:text-align:center"}
  <figcaption><b>Figure 4.1</b>: Market Types implemented in Grid Singularity Exchange.
</figcaption>
</figure>

### Market Slots

The energy spot market is broken into time slots, with the default set to 15 minutes of simulated time. For a one-day simulation, 96 market slots would occur with the default setting. Learn how to adjust market slot length [here](community-settings.md).

Depending on the market type, bids and offers are either matched within or at the end of each slot. Bids and offers that remain unmatched at the end of a market slot are annulled, and assets may be penalised for any energy they physically produce or consume that is not transacted for.

### Market Ticks

Each slot is further segmented into ticks. The default setting for a tick is 15 seconds of simulated time (simulated time is the time unit within a simulation as opposed to real-time which is the real-life time that the simulation takes; e.g. a simulation can simulate 7 days of trading in minutes or hours), and this configuration may be changed. The default 15 minute market slot is made up of 60 15-second ticks.

In a pay-as-bid market, for instance, the market is cleared at the end of each tick. If an order is not matched, it is [propagated to all adjacent markets](market-agent.md) by a MarketAgent after two ticks (explained in more detail [below](two-sided-pay-as-bid.md)). If an order is not matched at the end of two next ticks, it is further propagated to connected markets in the subsequent ticks following the same logic.

The current implementation of Grid Singularity exchange currently focuses on the spot and balancing markets. Balancing markets take place immediately after each spot market slot (if enabled). The duration of the markets can be configured.
