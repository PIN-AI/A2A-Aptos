 #[test_only]
module aptos_task_manager::match_system_tests {
    use std::signer;
    use std::string;
    use aptos_framework::coin;
    use aptos_framework::aptos_coin::{Self, AptosCoin};
    use aptos_framework::timestamp;
    use aptos_framework::account;
    use aptos_task_manager::match_system;
    use aptos_task_manager::task_manager;

    const MINIMUM_ORDER_AMOUNT: u64 = 1000;
    const TEST_TASK_PAYMENT: u64 = 100000000; // 1 APT
    const TEST_DEADLINE_SECONDS: u64 = 86400; // 24 hours

    // Test: Initialize market
    #[test(framework = @0x1, market_admin = @0x12345)]
    fun test_initialize_market(framework: &signer, market_admin: &signer) {
        // Setup environment
        timestamp::set_time_has_started_for_testing(framework);
        let (burn_cap, mint_cap) = aptos_coin::initialize_for_test(framework);
        
        let market_addr = signer::address_of(market_admin);
        account::create_account_for_test(market_addr);
        
        let coins = coin::mint<AptosCoin>(1000000000, &mint_cap);
        coin::deposit(market_addr, coins);
        
        // Initialize Match Engine
        match_system::initialize_market(market_admin);
        
        // Verify market status
        let status = match_system::get_market_status(market_addr);
        assert!(status == 1, 1); // Should be MARKET_STATUS_OPEN
        
        // Verify initial order book stats
        let (total_task_orders, total_service_orders, best_task_price, best_service_price) = 
            match_system::get_order_book_stats(market_addr);
        assert!(total_task_orders == 0, 2);
        assert!(total_service_orders == 0, 3);
        assert!(best_task_price == 0, 4);
        assert!(best_service_price == 0, 5);
        
        // Verify initial market stats
        let (total_matches, total_volume, total_fees) = match_system::get_market_stats(market_addr);
        assert!(total_matches == 0, 6);
        assert!(total_volume == 0, 7);
        assert!(total_fees == 0, 8);
        
        // Cleanup
        coin::destroy_burn_cap(burn_cap);
        coin::destroy_mint_cap(mint_cap);
    }

    // Test: Publish task to market
    #[test(framework = @0x1, market_admin = @0x12345, task_agent = @0x23456, service_agent = @0x34567)]
    fun test_publish_task_to_market(
        framework: &signer, 
        market_admin: &signer, 
        task_agent: &signer, 
        service_agent: &signer
    ) {
        // Setup environment
        timestamp::set_time_has_started_for_testing(framework);
        let (burn_cap, mint_cap) = aptos_coin::initialize_for_test(framework);
        
        let market_addr = signer::address_of(market_admin);
        let task_addr = signer::address_of(task_agent);
        let service_addr = signer::address_of(service_agent);
        
        account::create_account_for_test(market_addr);
        account::create_account_for_test(task_addr);
        account::create_account_for_test(service_addr);
        
        let task_coins = coin::mint<AptosCoin>(TEST_TASK_PAYMENT * 2, &mint_cap);
        coin::deposit(task_addr, task_coins);
        
        // Initialize systems
        task_manager::initialize(task_agent);
        match_system::initialize_market(market_admin);
        
        let task_id = b"test_task_001";
        
        // Create a task first
        task_manager::create_task(
            task_agent,
            task_id,
            service_addr,
            TEST_TASK_PAYMENT,
            TEST_DEADLINE_SECONDS,
            string::utf8(b"Test task description")
        );
        
        // Publish task to market
        match_system::publish_task_to_market(
            task_agent,
            market_addr,
            task_id,
            TEST_TASK_PAYMENT,
            TEST_DEADLINE_SECONDS,
            string::utf8(b"Test task for market publication")
        );
        
        // Verify order book stats updated
        let (total_task_orders, _total_service_orders, best_task_price, _best_service_price) = 
            match_system::get_order_book_stats(market_addr);
        assert!(total_task_orders == 1, 1);
        assert!(best_task_price == TEST_TASK_PAYMENT, 2);
        
        // Cleanup
        coin::destroy_burn_cap(burn_cap);
        coin::destroy_mint_cap(mint_cap);
    }

    // Test: Place service bid
    #[test(framework = @0x1, market_admin = @0x12345, service_agent = @0x34567)]
    fun test_place_service_bid(
        framework: &signer, 
        market_admin: &signer, 
        service_agent: &signer
    ) {
        // Setup environment
        timestamp::set_time_has_started_for_testing(framework);
        let (burn_cap, mint_cap) = aptos_coin::initialize_for_test(framework);
        
        let market_addr = signer::address_of(market_admin);
        let service_addr = signer::address_of(service_agent);
        
        account::create_account_for_test(market_addr);
        account::create_account_for_test(service_addr);
        
        // Initialize market
        match_system::initialize_market(market_admin);
        
        let task_id = b"test_task_002";
        let bid_price = TEST_TASK_PAYMENT / 2; // Bid lower than max price
        
        // Place service bid
        match_system::place_service_bid(
            service_agent,
            market_addr,
            task_id,
            bid_price,
            TEST_DEADLINE_SECONDS,
            string::utf8(b"Service bid for test task")
        );
        
        // Verify order book stats updated
        let (_total_task_orders, total_service_orders, _best_task_price, best_service_price) = 
            match_system::get_order_book_stats(market_addr);
        assert!(total_service_orders == 1, 1);
        assert!(best_service_price == bid_price, 2);
        
        // Cleanup
        coin::destroy_burn_cap(burn_cap);
        coin::destroy_mint_cap(mint_cap);
    }

    // Test: Error cases - Market not initialized
    #[test(framework = @0x1, task_agent = @0x23456)]
    #[expected_failure(abort_code = 100, location = aptos_task_manager::match_system)]
    fun test_market_not_initialized(framework: &signer, task_agent: &signer) {
        // Setup basic environment but don't initialize market
        timestamp::set_time_has_started_for_testing(framework);
        let (burn_cap, mint_cap) = aptos_coin::initialize_for_test(framework);
        
        let fake_market_addr = @0x99999;
        let task_id = b"test_task";
        
        // Try to publish to uninitialized market
        match_system::publish_task_to_market(
            task_agent,
            fake_market_addr,
            task_id,
            TEST_TASK_PAYMENT,
            TEST_DEADLINE_SECONDS,
            string::utf8(b"Task for uninitialized market")
        );
        
        // Cleanup
        coin::destroy_burn_cap(burn_cap);
        coin::destroy_mint_cap(mint_cap);
    }
}