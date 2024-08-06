The main goal of an electricity market exchange is to balance the grid in terms of demand and supply. Since efficient storage of large quantities of energy is currently not economically feasible and electrical current varies within seconds, a market mechanism that efficiently accounts for the physical energy production and consumption is required. Generally, trading occurs in three types of markets with different time intervals:

1. **Spot market**: short-term trades for immediate or near-term delivery. Energy transactions are divided into small time blocks (typically 15 minute slots) that can either be traded on the Day-ahead or in the Intraday market.
2. **Balancing market**: imbalances that occur due to deviations between energy traded in the spot market and actual energy consumption and production are absorbed by balance responsible parties (BRP) that are reimbursed for their service with a fee based on the energy deviation.
3. **Futures market**: trades for the longer term future consumption and production of energy are agreed in advance. This market is currently outside the scope of Grid Singularity energy exchange implementation.

![alt_text](img/markets-1.png)

The current implementation of Grid Singularity software focuses on the spot and balancing markets. [Balancing markets](market-types.md#balancing-market) take place immediately after each spot market slot (if enabled). The duration of the markets can be configured. Currently, three spot market types are implemented:

1. [One-sided Pay-as-Offer](market-types.md#one-sided-pay-as-offer-market)
2. [Two-sided Pay-as-Bid](market-types.md#two-sided-pay-as-bid-market)
3. [Two-sided Pay-as-Clear](market-types.md#two-sided-pay-as-clear-market)

##Market Slots

The energy spot market is broken into time slots, with the default set to 15 minutes of simulated time. For a one-day simulation, 96 market slots would occur with the default setting. Learn how to adjust market slot length [here](general-settings.md).

Depending on the market type, bids and offers are either matched within or at the end of each slot. Bids and offers that remain unmatched at the end of a market slot are annulled, and assets may be penalised for any energy they physically produce or consume that is not transacted for.

##Market Ticks

Each slot is further segmented into ticks. The default setting for a tick is 15 seconds of simulated time (simulated time is the time unit within a simulation as opposed to real-time which is the real-life time that the simulation takes; e.g. a simulation can simulate 7 days of trading in minutes or hours), and this configuration may be changed. The default 15 minute market slot is made up of 60 15-second ticks.

In a pay-as-bid market, the market is cleared at the end of each tick. If an order is not matched, it is propagated to all adjacent markets by a [Market Agent](trading-agents-and-strategies.md) after two ticks. If an order is not matched at the end of two next ticks, it is further propagated to connected markets in the subsequent ticks following the same logic.
