#[test_only]
module aptos_task_manager::bidding_system_test {
    use aptos_task_manager::bidding_system;
    use aptos_framework::coin;
    use aptos_framework::aptos_coin::{Self, AptosCoin};
    use aptos_framework::timestamp;
    use aptos_framework::account;
    use std::signer;
    use std::string;
    use std::vector;

    // Test constants
    const PLATFORM_ADDR: address = @0x1;
    const CREATOR_ADDR: address = @0x2;
    const BIDDER1_ADDR: address = @0x3;
    const BIDDER2_ADDR: address = @0x4;
    
    const TASK_ID: vector<u8> = b"test_task_001";
    const MAX_BUDGET: u64 = 10000;
    const DEADLINE_SECONDS: u64 = 3600;
    const BID_PRICE_1: u64 = 8000;
    const BID_PRICE_2: u64 = 7000;
    const REPUTATION_SCORE: u64 = 100;

    // Test setup helper
    fun setup_test_environment(): (signer, signer, signer, signer) {
        let platform = account::create_account_for_test(PLATFORM_ADDR);
        let creator = account::create_account_for_test(CREATOR_ADDR);
        let bidder1 = account::create_account_for_test(BIDDER1_ADDR);
        let bidder2 = account::create_account_for_test(BIDDER2_ADDR);
        
        // Initialize AptosCoin for testing
        let (burn_cap, mint_cap) = aptos_coin::initialize_for_test(&platform);
        
        // Fund accounts
        coin::deposit(CREATOR_ADDR, coin::mint(MAX_BUDGET * 2, &mint_cap));
        coin::deposit(BIDDER1_ADDR, coin::mint(1000, &mint_cap));
        coin::deposit(BIDDER2_ADDR, coin::mint(1000, &mint_cap));
        
        // Clean up capabilities
        coin::destroy_mint_cap(mint_cap);
        coin::destroy_burn_cap(burn_cap);
        
        // Set timestamp for tests
        timestamp::set_time_has_started_for_testing(&platform);
        timestamp::update_global_time_for_test(1000000);
        
        (platform, creator, bidder1, bidder2)
    }

    #[test]
    fun test_platform_initialization() {
        let (platform, _creator, _bidder1, _bidder2) = setup_test_environment();
        
        // Initialize platform
        bidding_system::initialize(&platform);
        
        // Verify platform statistics
        let (total_tasks, completed_tasks, cancelled_tasks) = bidding_system::get_platform_stats(PLATFORM_ADDR);
        assert!(total_tasks == 0, 1);
        assert!(completed_tasks == 0, 2);
        assert!(cancelled_tasks == 0, 3);
    }

    #[test]
    fun test_task_publication() {
        let (platform, creator, _bidder1, _bidder2) = setup_test_environment();
        
        // Initialize platform
        bidding_system::initialize(&platform);
        
        // Publish task
        bidding_system::publish_task(
            &creator,
            PLATFORM_ADDR,
            TASK_ID,
            string::utf8(b"Test task description"),
            MAX_BUDGET,
            DEADLINE_SECONDS,
        );
        
        // Verify task was created
        assert!(bidding_system::task_exists(PLATFORM_ADDR, TASK_ID), 1);
        
        // Verify task details
        let (task_id, creator, max_budget, deadline, status) = bidding_system::get_task_info(PLATFORM_ADDR, TASK_ID);
        assert!(task_id == TASK_ID, 2);
        assert!(creator == CREATOR_ADDR, 3);
        assert!(max_budget == MAX_BUDGET, 4);
        assert!(status == 1, 5); // STATUS_PUBLISHED
        assert!(vector::length(&bidding_system::get_task_bids(PLATFORM_ADDR, TASK_ID)) == 0, 6);
        
        // Verify platform statistics
        let (total_tasks, completed_tasks, cancelled_tasks) = bidding_system::get_platform_stats(PLATFORM_ADDR);
        assert!(total_tasks == 1, 7);
        assert!(completed_tasks == 0, 8);
        assert!(cancelled_tasks == 0, 9);
    }

    #[test]
    fun test_bid_placement() {
        let (platform, creator, bidder1, bidder2) = setup_test_environment();
        
        // Initialize platform
        bidding_system::initialize(&platform);
        
        // Publish task
        bidding_system::publish_task(
            &creator,
            PLATFORM_ADDR,
            TASK_ID,
            string::utf8(b"Test task description"),
            MAX_BUDGET,
            DEADLINE_SECONDS,
        );
        
        // Place bids
        bidding_system::place_bid(
            &bidder1,
            PLATFORM_ADDR,
            TASK_ID,
            BID_PRICE_1,
            REPUTATION_SCORE,
        );
        
        bidding_system::place_bid(
            &bidder2,
            PLATFORM_ADDR,
            TASK_ID,
            BID_PRICE_2,
            REPUTATION_SCORE + 50,
        );
        
        // Verify bids were placed
        let bids = bidding_system::get_task_bids(PLATFORM_ADDR, TASK_ID);
        assert!(vector::length(&bids) == 2, 1);
        
        // Note: We can't access bid fields directly due to Move's privacy model
        // The fact that we got 2 bids confirms they were placed correctly
    }

    #[test]
    fun test_winner_selection() {
        let (platform, creator, bidder1, bidder2) = setup_test_environment();
        
        // Initialize platform
        bidding_system::initialize(&platform);
        
        // Publish task
        bidding_system::publish_task(
            &creator,
            PLATFORM_ADDR,
            TASK_ID,
            string::utf8(b"Test task description"),
            MAX_BUDGET,
            DEADLINE_SECONDS,
        );
        
        // Place bids (bidder2 has lower price)
        bidding_system::place_bid(
            &bidder1,
            PLATFORM_ADDR,
            TASK_ID,
            BID_PRICE_1,
            REPUTATION_SCORE,
        );
        
        bidding_system::place_bid(
            &bidder2,
            PLATFORM_ADDR,
            TASK_ID,
            BID_PRICE_2,
            REPUTATION_SCORE,
        );
        
        // Select winner
        bidding_system::select_winner(
            &creator,
            PLATFORM_ADDR,
            TASK_ID,
        );
        
        // Verify winner selection
        assert!(bidding_system::get_task_status(PLATFORM_ADDR, TASK_ID) == 2, 1); // STATUS_ASSIGNED
        assert!(bidding_system::get_task_winner(PLATFORM_ADDR, TASK_ID) == BIDDER2_ADDR, 2); // Lower price wins
        assert!(bidding_system::get_task_winning_price(PLATFORM_ADDR, TASK_ID) == BID_PRICE_2, 3);
        
        // Verify bids were cleared
        assert!(bidding_system::get_task_bid_count(PLATFORM_ADDR, TASK_ID) == 0, 4);
    }

    #[test]
    fun test_task_completion() {
        let (platform, creator, bidder1, bidder2) = setup_test_environment();
        
        // Initialize platform
        bidding_system::initialize(&platform);
        
        // Publish task
        bidding_system::publish_task(
            &creator,
            PLATFORM_ADDR,
            TASK_ID,
            string::utf8(b"Test task description"),
            MAX_BUDGET,
            DEADLINE_SECONDS,
        );
        
        // Place bid
        bidding_system::place_bid(
            &bidder1,
            PLATFORM_ADDR,
            TASK_ID,
            BID_PRICE_1,
            REPUTATION_SCORE,
        );
        
        // Select winner
        bidding_system::select_winner(
            &creator,
            PLATFORM_ADDR,
            TASK_ID,
        );
        
        // Get balances before completion
        let creator_balance_before = coin::balance<AptosCoin>(CREATOR_ADDR);
        let bidder_balance_before = coin::balance<AptosCoin>(BIDDER1_ADDR);
        
        // Complete task
        bidding_system::complete_task(
            &bidder1,
            PLATFORM_ADDR,
            TASK_ID,
        );
        
        // Verify task completion
        assert!(bidding_system::get_task_status(PLATFORM_ADDR, TASK_ID) == 3, 1); // STATUS_COMPLETED
        assert!(bidding_system::get_task_completed_at(PLATFORM_ADDR, TASK_ID) > 0, 2);
        
        // Verify fund transfers
        let creator_balance_after = coin::balance<AptosCoin>(CREATOR_ADDR);
        let bidder_balance_after = coin::balance<AptosCoin>(BIDDER1_ADDR);
        
        // Creator should receive refund (max_budget - winning_price)
        let expected_refund = MAX_BUDGET - BID_PRICE_1;
        assert!(creator_balance_after == creator_balance_before + expected_refund, 3);
        
        // Bidder should receive their bid amount
        assert!(bidder_balance_after == bidder_balance_before + BID_PRICE_1, 4);
        
        // Verify platform statistics
        let (total_tasks, completed_tasks, cancelled_tasks) = bidding_system::get_platform_stats(PLATFORM_ADDR);
        assert!(total_tasks == 1, 5);
        assert!(completed_tasks == 1, 6);
        assert!(cancelled_tasks == 0, 7);
    }

    #[test]
    fun test_task_cancellation() {
        let (platform, creator, bidder1, _bidder2) = setup_test_environment();
        
        // Initialize platform
        bidding_system::initialize(&platform);
        
        // Publish task
        bidding_system::publish_task(
            &creator,
            PLATFORM_ADDR,
            TASK_ID,
            string::utf8(b"Test task description"),
            MAX_BUDGET,
            DEADLINE_SECONDS,
        );
        
        // Place bid
        bidding_system::place_bid(
            &bidder1,
            PLATFORM_ADDR,
            TASK_ID,
            BID_PRICE_1,
            REPUTATION_SCORE,
        );
        
        // Get creator balance before cancellation
        let creator_balance_before = coin::balance<AptosCoin>(CREATOR_ADDR);
        
        // Cancel task
        bidding_system::cancel_task(
            &creator,
            PLATFORM_ADDR,
            TASK_ID,
        );
        
        // Verify task cancellation
        assert!(bidding_system::get_task_status(PLATFORM_ADDR, TASK_ID) == 4, 1); // STATUS_CANCELLED
        assert!(bidding_system::get_task_bid_count(PLATFORM_ADDR, TASK_ID) == 0, 2);
        
        // Verify full refund
        let creator_balance_after = coin::balance<AptosCoin>(CREATOR_ADDR);
        assert!(creator_balance_after == creator_balance_before + MAX_BUDGET, 3);
        
        // Verify platform statistics
        let (total_tasks, completed_tasks, cancelled_tasks) = bidding_system::get_platform_stats(PLATFORM_ADDR);
        assert!(total_tasks == 1, 4);
        assert!(completed_tasks == 0, 5);
        assert!(cancelled_tasks == 1, 6);
    }

    #[test]
    #[expected_failure(abort_code = 110)] // EALREADY_BIDDED
    fun test_duplicate_bid_failure() {
        let (platform, creator, bidder1, _bidder2) = setup_test_environment();
        
        // Initialize platform
        bidding_system::initialize(&platform);
        
        // Publish task
        bidding_system::publish_task(
            &creator,
            PLATFORM_ADDR,
            TASK_ID,
            string::utf8(b"Test task description"),
            MAX_BUDGET,
            DEADLINE_SECONDS,
        );
        
        // Place first bid
        bidding_system::place_bid(
            &bidder1,
            PLATFORM_ADDR,
            TASK_ID,
            BID_PRICE_1,
            REPUTATION_SCORE,
        );
        
        // Try to place second bid (should fail)
        bidding_system::place_bid(
            &bidder1,
            PLATFORM_ADDR,
            TASK_ID,
            BID_PRICE_2,
            REPUTATION_SCORE,
        );
    }

    #[test]
    #[expected_failure(abort_code = 106)] // EINVALID_BID_PRICE
    fun test_bid_exceeds_budget_failure() {
        let (platform, creator, bidder1, _bidder2) = setup_test_environment();
        
        // Initialize platform
        bidding_system::initialize(&platform);
        
        // Publish task
        bidding_system::publish_task(
            &creator,
            PLATFORM_ADDR,
            TASK_ID,
            string::utf8(b"Test task description"),
            MAX_BUDGET,
            DEADLINE_SECONDS,
        );
        
        // Try to place bid exceeding budget (should fail)
        bidding_system::place_bid(
            &bidder1,
            PLATFORM_ADDR,
            TASK_ID,
            MAX_BUDGET + 1000,
            REPUTATION_SCORE,
        );
    }

    #[test]
    #[expected_failure(abort_code = 109)] // ENO_BIDS_PLACED
    fun test_select_winner_no_bids_failure() {
        let (platform, creator, _bidder1, _bidder2) = setup_test_environment();
        
        // Initialize platform
        bidding_system::initialize(&platform);
        
        // Publish task
        bidding_system::publish_task(
            &creator,
            PLATFORM_ADDR,
            TASK_ID,
            string::utf8(b"Test task description"),
            MAX_BUDGET,
            DEADLINE_SECONDS,
        );
        
        // Try to select winner without bids (should fail)
        bidding_system::select_winner(
            &creator,
            PLATFORM_ADDR,
            TASK_ID,
        );
    }
}