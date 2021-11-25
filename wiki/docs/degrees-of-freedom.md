Bids and offers for energy include a set of attributes (e.g. encrypted unique asset ID, asset location, type of energy produced e.g. solar energy or membership in energy club) and diverse requirements that reflect trading preferences, such as energy quantity, price range, energy source, geographic distance, or preferred trading partner.

Intelligent agents managed by aggregators make algorithmic trading decisions on behalf of participants, translating energy asset information and prosumer trading preferences into a requirements function. Bids and offers are submitted through Grid Singularity’s existing [Asset API](asset-api-template-script.md), modified to include attributes and requirements for each submitted order. Each market then stores the list of attributed bids and offers in the exchange’s open order book to be matched.

Below, an example of a bid and offer with attributes and requirements. The bid submits three sets of conditions. As the second condition is fulfilled by the offer, the two orders are successfully matched, in this case for 0.8 kWh of photovoltaic (PV) energy (at a price between 21 and 25 cents as determined by the matching algorithm). A verification function performs this check. The function accepts a bid / offer pair as input, returns a <True> (green check) if there is a valid match, and returns a <False> (red x) if requirements are not met. If the function returns <True>, a trade is created. In a near-term centralised implementation, this verification function is integrated into the exchange code. In a blockchain implementation, it is to be deployed as a module of the parachain’s protocol.

![alt_text](img/degrees-of-freedom.png)

***Figure 3.22***. *Example of a bid and offer with attributes and requirements.*
