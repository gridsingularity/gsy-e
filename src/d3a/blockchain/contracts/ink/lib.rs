// Copyright 2018 Grid Singularity
// This file is part of D3A.
// This program is free software: you can redistribute it and/or modify
// it under the terms of the GNU General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
// This program is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU General Public License for more details.
// You should have received a copy of the GNU General Public License
// along with this program.  If not, see <http://www.gnu.org/licenses/>.

#![cfg_attr(not(feature = "std"), no_std)]

use ink_lang as ink;

#[ink::contract]
mod trade_storage {
    #[cfg(not(feature = "ink-as-dependency"))]
    use ink_storage::{
        collections::HashMap as StorageHashMap,
    };

    /// A simple ERC-20 contract.
    #[ink(storage)]
    pub struct TradeStorage {
        /// The trades stored in the contract.
        trades: StorageHashMap<Hash, (AccountId, AccountId, Balance, i8)>,
        area_market_id: StorageHashMap<u128, (u128, u32)>,
    }

    /// Storing a trade by a call from d3a
    #[ink(event)]
    pub struct Trade {
        hash: Hash,
        #[ink(topic)]
        buyer: Option<AccountId>,
        #[ink(topic)]
        seller: Option<AccountId>,
        value: Balance,
        rate: i8
    }

    /// The contract error types.
    #[derive(Debug, PartialEq, Eq, scale::Encode)]
    #[cfg_attr(feature = "std", derive(scale_info::TypeInfo))]
    pub enum Error {
        /// Returned if not enough balance to fulfill a request is available.
        InsufficientBalance,
    }

    /// The contract result type.
    pub type Result<T> = core::result::Result<T, Error>;

    impl TradeStorage {
        /// Creates a contract that stores trade data.
        #[ink(constructor)]
        pub fn new(simulation_id: u128, area_id: u128, timestamp: u32) -> Self {
            let trades = StorageHashMap::new();
            let mut area_market_id = StorageHashMap::new();
            area_market_id.insert(simulation_id, (area_id, timestamp));
            let instance = Self {
                trades, area_market_id,
            };
            instance
        }

        #[ink(message)]
        pub fn trade(
            &mut self,
            id: u8,
            buyer: AccountId,
            seller: AccountId,
            value: Balance,
            rate: i8
        ) -> Result<()> {
            let hash = Hash::from([id; 32]);
            self.env()
                .emit_event(
                    Trade {
                        hash,
                        buyer: Some(buyer),
                        seller: Some(seller),
                        value,
                        rate
                    });
            self.trades.insert(hash, (buyer, seller, value, rate));
            Ok(())
        }

        #[ink(message)]
        pub fn get_trades(&self, id: u8) -> (AccountId, AccountId, Balance, i8) {
            let hash = Hash::from([id; 32]);
            let default_tuple = (AccountId::default(), AccountId::default(), 0, 0);
            let trade = self.trades.get(&hash).copied().unwrap_or(default_tuple);
            trade
        }

        #[ink(message)]
        pub fn get_contract_identity(&self, id: u128) -> (u128, u32) {
            self.area_market_id[&id]
        }
    }
}
