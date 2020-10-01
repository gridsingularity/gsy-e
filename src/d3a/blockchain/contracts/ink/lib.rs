
#![cfg_attr(not(feature = "std"), no_std)]

use ink_lang as ink;

#[ink::contract(version = "0.1.0")]
mod erc20 {
    use ink_core::storage;

    #[ink(storage)]
    struct Erc20 {
        /// The total supply.
        total_supply: storage::Value<Balance>,
        /// The balance of each user.
        balances: storage::HashMap<AccountId, Balance>,
        /// Approval spender on behalf of the message's sender.
        allowances: storage::HashMap<(AccountId, AccountId), Balance>,
        /// The balance of each user.
        trades: storage::HashMap<Hash, (AccountId, AccountId, Balance, i8)>,
    }

    #[ink(event)]
    struct Transfer {
        #[ink(topic)]
        from: Option<AccountId>,
        #[ink(topic)]
        to: Option<AccountId>,
        value: Balance,
    }

    #[ink(event)]
    struct Approval {
        #[ink(topic)]
        owner: Option<AccountId>,
        #[ink(topic)]
        spender: Option<AccountId>,
        #[ink(topic)]
        value: Balance,
    }

    #[ink(event)]
    struct Trade {
        hash: Hash,
        #[ink(topic)]
        buyer: Option<AccountId>,
        #[ink(topic)]
        seller: Option<AccountId>,
        value: Balance,
        rate: i8
    }

    impl Erc20 {
        #[ink(constructor)]
        fn new(&mut self, initial_supply: Balance) {
            self.total_supply.set(initial_supply);
            self.balances.insert(self.env().caller(), initial_supply);
            self.env().emit_event(
                Transfer {
                    from: None,
                    to: Some(self.env().caller()),
                    value: initial_supply,
                });
        }

        #[ink(message)]
        fn total_supply(&self) -> Balance {
            *self.total_supply.get()
        }

        #[ink(message)]
        fn balance_of(&self, owner: AccountId) -> Balance {
            self.balance_of_or_zero(&owner)
        }

        #[ink(message)]
        fn approve(&mut self, spender: AccountId, value: Balance) -> bool {
            let owner = self.env().caller();
            self.allowances.insert((owner, spender), value);
            self.env().emit_event(Approval {
                owner: Some(owner),
                spender: Some(spender),
                value: value,
            });
            true
        }

        #[ink(message)]
        fn allowance(&self, owner: AccountId, spender: AccountId) -> Balance {
            self.allowance_of_or_zero(&owner, &spender)
        }

        fn transfer_from(&mut self, from: AccountId, to: AccountId, value: Balance) -> bool {
            let caller = self.env().caller();
            let allowance = self.allowance_of_or_zero(&from, &caller);
            if allowance < value {
                return false
            }
            self.allowances.insert((from, caller), allowance - value);
            self.transfer_from_to(from, to, value);
            true
        }

        #[ink(message)]
        fn transfer(&mut self, to: AccountId, value: Balance) -> bool {
            let caller = self.env().caller();
            self.transfer_from_to(caller, to, value)
        }

        fn transfer_from_to(&mut self, from: AccountId, to: AccountId, value: Balance) -> bool {
            let from_balance = self.balance_of_or_zero(&from);
            let to_balance = self.balance_of_or_zero(&to);
            if from_balance < value {
                return false
            }
            self.balances.insert(from, from_balance - value);
            self.balances.insert(to, to_balance + value);
            self.env()
                .emit_event(
                    Transfer {
                        from: Some(from),
                        to: Some(to),
                        value,
                    });
            true
        }

        fn balance_of_or_zero(&self, owner: &AccountId) -> Balance {
            let balance = self.balances.get(owner).unwrap_or(&0);
            *balance
        }

        fn allowance_of_or_zero(&self, owner: &AccountId, spender: &AccountId) -> Balance {
            let allowance = self.allowances.get(&(*owner, *spender)).unwrap_or(&0);
            *allowance
        }

        #[ink(message)]
        fn trade(&mut self, id: u8, buyer: AccountId, seller: AccountId, value: Balance, rate: i8) -> bool {
            let buyer_balance = self.balance_of_or_zero(&buyer);
            let seller_balance = self.balance_of_or_zero(&seller);
            if seller_balance < value {
                return false
            }
            let hash = Hash::from([id; 32]);
            self.balances.insert(buyer, buyer_balance + value);
            self.balances.insert(seller, seller_balance - value);
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
            true
        }

        #[ink(message)]
        fn get_trades(&self, id: u8) -> (AccountId, AccountId, Balance, i8) {
            let hash = Hash::from([id; 32]);
            let default_tuple = (AccountId::default(), AccountId::default(), 0, 0);
            let trade = self.trades.get(&hash).unwrap_or(&default_tuple);
            *trade
        }
    }

    #[cfg(test)]
    mod tests {
        use super::*;

        #[test]
        fn new_works() {
            let contract = Erc20::new(777);
            assert_eq!(contract.total_supply(), 777);
        }

        #[test]
        fn balance_works() {
            let contract = Erc20::new(100);
            assert_eq!(contract.total_supply(), 100);
            assert_eq!(contract.balance_of(AccountId::from([0x1; 32])), 100);
            assert_eq!(contract.balance_of(AccountId::from([0x0; 32])), 0);
        }

        #[test]
        fn transfer_works() {
            let mut contract = Erc20::new(100);
            assert_eq!(contract.balance_of(AccountId::from([0x1; 32])), 100);
            assert!(contract.transfer(AccountId::from([0x0; 32]), 10));
            assert_eq!(contract.balance_of(AccountId::from([0x0; 32])), 10);
            assert!(!contract.transfer(AccountId::from([0x0; 32]), 100));
        }

        #[test]
        fn trade_works() {
            let mut contract = Erc20::new(100000);
            assert!(contract.trade(0, AccountId::from([0x0; 32]), AccountId::from([0x1; 32]), 20, 15));
            assert_eq!(Hash::default(), Hash::from([0; 32]));
        }
    }
}
