In the one sided market, loads buy the cheapest offers available to them. However, they can also set a limit to the maximum price they are willing to pay. To configure a load, the user can input the following parameters:

- `avg_power_W`: average consuming power of the load. Unit is Watts. This is a required parameter.
- `hrs_of_day`: list representing a daily schedule that contains the hours where the load is allowed to consume energy. Default value is `None`, meaning that the load is allowed to consume energy during every hour of the day. See addendum below for more information.
- `hrs_per_day`: number of hours per day that the load is consuming power. The initial value is `None`, meaning that the load will consume energy for all the hours listed in the `hrs_of_day` parameter. See addendum below for more information.
- `update_interval`: time after which the rate should be updated (type: pendulum duration object). Range → `[1:(slot_length_minute-1)]`
- `initial_buying_rate`: initial rate in ct/kWh.
- `final_buying_rate`: final rate in ct/kWh.
- `use_market_maker_rate:` If this flag is set `True`, then agent's `final_buying_rate` would be overwritten with [Market Maker Strategy](market-maker-strategy.md)'s defined `energy_rate.`
- `energy_rate_increase_per_update`: explicit rate decrease increment in cents.
- `fit_to_limit:` derive bidding behaviour from a linear fitted curve of a buying rate between `initial_buying_rate` and `final_buying_rate` (boolean value) within the bidding interval. If activated, `energy_rate_increase_per_update = (final_buying_rate - initial_buying_rate) / max(int((slot_length / update_interval) -1), 1)`

In order to enable the load to participate in balancing market, a prerequisite is to add the load device in "[Device Registry](https://gridsingularity.atlassian.net/wiki/spaces/D3A/pages/23887933/Markets+-+balancing+market)" and set the following parameters:

- `balancing_energy_ratio`: tuple with 2 values. The first value dictates the ratio of energy to be demanded in balancing market, i.e. committing to voluntary ramping-up consumption. The second value dictates the ratio of energy to be supplied in balancing market, i.e. committing to voluntary ramping down of consumption (default value: tuple(0.1, 0.1)).

The Load will increase its acceptable energy rate linearly in the frame of a market slot of a one-sided market. It will start at the `initial_buying_rate` and end at `final_buying_rate`.

Corresponding code: src/`3a/models/strategy/load_hours.py`

How to add load device to setup-file:

```python
Area('Load', strategy=LoadHoursStrategy(avg_power_W=200,
                                        hrs_per_day=6,
                                        hrs_of_day=list(range(12, 18)),
                                        initial_buying_rate=0,
                                        final_buying_rate=35),
             appliance=SwitchableAppliance())
```



------

**Addendum: `hrs_of_day` and `hrs_per_day`**

`hrs_of_day` defines the allowed time-window in which the load has to consume for a time defined by `hrs_per_day`.

For example, a user can input 5 `hrs_per_day`, for example and give a wider range for `hrs_of_day` like (2,18). The 5 programmed hours will be consumed "greedily" during this period, meaning that the Load will try to consume as fast as possible if there are any offered energy to purchase within the limits of `initial_buying_rate` and `final_buying_rate set parameters`.

- So if there is sufficient energy with affordable rates, the load will consume in the hours first 5 hours, i.e. from 02:00 until 07:00, with no energy demand being unmatched.
- In case energy prices would be too high during the time-interval from 04:00 to 16:00, the load will consume from 02:00 until 04:00, turn off, and consume from 16:00 until 18:00, resulting in 1 hour of energy demand being unmatched.

------



For information on buying rate decrease behaviour, please see: [Energy Rate Settings and Behaviour](https://gridsingularity.atlassian.net/wiki/spaces/D3AD/pages/1342668821/Energy+Rate+Settings+and+Behaviour). 

#### Relation of different parameters for energy pricing

Let's assume the user has configured its *LoadStrategy* with these parameters `(initial_buying_rate=0, final_buying_rate=30, fit_to_limit=True, update_interval=5mins)` and `slot_length=15min`. At the start of market, LOAD would place its initial bid at the rate of `initial_buying_rate`. If `fit_to_limit` is set to `True`, it will gradually increase its `bid_rate` linearly such that its `final_bid` before the end of `market_slot` should be equal to `final_buying_rate`. Number of available updates in such a case is `(slot_length / update_interval) -1) → (15/5 -1)=2`. Therefore, it is possible for a user to update its offer two times inside the same `market_slot`. The first update would happen at 5mins. The calculated `energy_rate_decrease_per_update → (30 - 0) / 2 → 15`. So, the Load will increase its `buying_rate` at the 5th min from 0 to 15 cts/kWh and at the 10th min from 15 to 30 cts/kWh.

![img](https://gridsingularity.atlassian.net/wiki/download/thumbnails/855015429/image2019-10-24_16-52-34.png?version=1&modificationDate=1571928755789&cacheVersion=1&api=v2&width=428&height=250)