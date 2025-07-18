/// A2A-Aptos Bidding System
/// 
/// This module implements a complete bidding system for AI Agent task management.
/// It allows Personal Agents to publish tasks and receive bids from multiple Service Agents,
/// with automatic winner selection based on price and reputation.
/// 
/// Key Features:
/// - Task publishing with escrow mechanism
/// - Multi-agent bidding system
/// - Reputation-based winner selection
/// - Automatic fund settlement
/// - Complete event tracking
module aptos_task_manager::bidding_system {
    use std::signer;
    use std::string::{Self, String};
    use std::vector;
    use aptos_framework::coin::{Self, Coin};
    use aptos_framework::aptos_coin::AptosCoin;
    use aptos_framework::timestamp;
    use aptos_framework::event::{Self, EventHandle};
    use aptos_framework::account;
    use aptos_std::smart_table::{Self, SmartTable};

    // Task Status Constants
    const STATUS_PUBLISHED: u8 = 1;    // Task is open for bidding
    const STATUS_ASSIGNED: u8 = 2;     // Winner selected, pending completion
    const STATUS_COMPLETED: u8 = 3;    // Task completed, funds settled
    const STATUS_CANCELLED: u8 = 4;    // Task cancelled by creator

    // Business Constants
    const MINIMUM_TASK_DURATION: u64 = 3600;     // 1 hour minimum
    const MAXIMUM_TASK_DURATION: u64 = 7776000;   // 90 days maximum
    const MINIMUM_PAY_AMOUNT: u64 = 1000;         // 0.00001 APT minimum

    // Error Codes
    const EPLATFORM_NOT_INITIALIZED: u64 = 101;
    const ETASK_NOT_FOUND: u64 = 102;
    const ETASK_ID_ALREADY_EXISTS: u64 = 103;
    const EUNAUTHORIZED: u64 = 104;
    const EWRONG_TASK_STATUS: u64 = 105;
    const EINVALID_BID_PRICE: u64 = 106;
    const EINVALID_DEADLINE: u64 = 107;
    const EINVALID_PAY_AMOUNT: u64 = 108;
    const ENO_BIDS_PLACED: u64 = 109;
    const EALREADY_BIDDED: u64 = 110;
    const EBIDDING_PERIOD_EXPIRED: u64 = 111;
    const EINVALID_WINNER_SELECTION: u64 = 112;

    // Core Data Structures

    /// Represents a bid from a Service Agent
    struct Bid has store, copy, drop {
        bidder: address,
        price: u64,
        timestamp: u64,
        reputation_score: u64,    // Future: reputation-based matching
    }

    /// Main Task structure containing all task information and state
    struct Task has store, copy, drop {
        id: vector<u8>,
        creator: address,
        description: String,
        max_budget: u64,
        deadline: u64,
        status: u8,
        created_at: u64,
        
        // Bidding information
        bids: vector<Bid>,
        
        // Winner information (set after selection)
        winner: address,
        winning_price: u64,
        completed_at: u64,
    }

    /// Central platform resource managing all tasks and escrows
    struct BiddingPlatform has key {
        tasks: SmartTable<vector<u8>, Task>,
        escrow: SmartTable<vector<u8>, Coin<AptosCoin>>,
        
        // Platform statistics
        total_tasks: u64,
        completed_tasks: u64,
        cancelled_tasks: u64,
        
        // Event handles
        task_published_events: EventHandle<TaskPublishedEvent>,
        bid_placed_events: EventHandle<BidPlacedEvent>,
        winner_selected_events: EventHandle<WinnerSelectedEvent>,
        task_completed_events: EventHandle<TaskCompletedEvent>,
        task_cancelled_events: EventHandle<TaskCancelledEvent>,
    }

    // Event Structures

    struct TaskPublishedEvent has drop, store {
        task_id: vector<u8>,
        creator: address,
        max_budget: u64,
        deadline: u64,
        description: String,
    }

    struct BidPlacedEvent has drop, store {
        task_id: vector<u8>,
        bidder: address,
        price: u64,
        reputation_score: u64,
    }

    struct WinnerSelectedEvent has drop, store {
        task_id: vector<u8>,
        creator: address,
        winner: address,
        winning_price: u64,
        total_bids: u64,
    }

    struct TaskCompletedEvent has drop, store {
        task_id: vector<u8>,
        creator: address,
        winner: address,
        paid_amount: u64,
        creator_refund: u64,
    }

    struct TaskCancelledEvent has drop, store {
        task_id: vector<u8>,
        creator: address,
        refunded_amount: u64,
        total_bids: u64,
    }

    // Initialization

    /// Initialize the bidding platform (called once by deployer)
    public entry fun initialize(deployer: &signer) {
        let deployer_addr = signer::address_of(deployer);
        assert!(!exists<BiddingPlatform>(deployer_addr), EPLATFORM_NOT_INITIALIZED);

        move_to(deployer, BiddingPlatform {
            tasks: smart_table::new(),
            escrow: smart_table::new(),
            total_tasks: 0,
            completed_tasks: 0,
            cancelled_tasks: 0,
            task_published_events: account::new_event_handle<TaskPublishedEvent>(deployer),
            bid_placed_events: account::new_event_handle<BidPlacedEvent>(deployer),
            winner_selected_events: account::new_event_handle<WinnerSelectedEvent>(deployer),
            task_completed_events: account::new_event_handle<TaskCompletedEvent>(deployer),
            task_cancelled_events: account::new_event_handle<TaskCancelledEvent>(deployer),
        });
    }

    // Core Functions - will be implemented in next steps

    /// Personal Agent publishes a task and escrows maximum budget
    public entry fun publish_task(
        creator: &signer,
        platform_addr: address,
        task_id: vector<u8>,
        description: String,
        max_budget: u64,
        deadline_seconds: u64,
    ) acquires BiddingPlatform {
        let creator_addr = signer::address_of(creator);
        assert!(exists<BiddingPlatform>(platform_addr), EPLATFORM_NOT_INITIALIZED);
        
        let platform = borrow_global_mut<BiddingPlatform>(platform_addr);
        
        // Validate task doesn't already exist
        assert!(!smart_table::contains(&platform.tasks, task_id), ETASK_ID_ALREADY_EXISTS);
        
        // Validate task parameters
        validate_task_params(max_budget, deadline_seconds);
        
        let current_time = timestamp::now_seconds();
        let deadline = current_time + deadline_seconds;
        
        // Escrow the maximum budget from creator
        let escrow_payment = coin::withdraw<AptosCoin>(creator, max_budget);
        
        // Create new task
        let new_task = Task {
            id: copy task_id,
            creator: creator_addr,
            description: copy description,
            max_budget,
            deadline,
            status: STATUS_PUBLISHED,
            created_at: current_time,
            bids: vector::empty<Bid>(),
            winner: @0x0,
            winning_price: 0,
            completed_at: 0,
        };
        
        // Store task and escrow
        smart_table::add(&mut platform.tasks, copy task_id, new_task);
        smart_table::add(&mut platform.escrow, copy task_id, escrow_payment);
        
        // Update platform statistics
        platform.total_tasks = platform.total_tasks + 1;
        
        // Emit event
        event::emit_event(&mut platform.task_published_events, TaskPublishedEvent {
            task_id,
            creator: creator_addr,
            max_budget,
            deadline,
            description,
        });
    }

    /// Service Agent places a bid on a published task
    public entry fun place_bid(
        bidder: &signer,
        platform_addr: address,
        task_id: vector<u8>,
        bid_price: u64,
        reputation_score: u64,
    ) acquires BiddingPlatform {
        let bidder_addr = signer::address_of(bidder);
        assert!(exists<BiddingPlatform>(platform_addr), EPLATFORM_NOT_INITIALIZED);
        
        let platform = borrow_global_mut<BiddingPlatform>(platform_addr);
        
        // Validate task exists
        assert!(smart_table::contains(&platform.tasks, task_id), ETASK_NOT_FOUND);
        
        let task = smart_table::borrow_mut(&mut platform.tasks, task_id);
        
        // Validate task status and timing
        assert!(task.status == STATUS_PUBLISHED, EWRONG_TASK_STATUS);
        assert!(timestamp::now_seconds() < task.deadline, EBIDDING_PERIOD_EXPIRED);
        
        // Validate bid price
        assert!(bid_price > 0, EINVALID_BID_PRICE);
        assert!(bid_price <= task.max_budget, EINVALID_BID_PRICE);
        
        // Validate bidder is not task creator
        assert!(task.creator != bidder_addr, EUNAUTHORIZED);
        
        // Check if bidder already placed a bid
        assert!(!has_bidder_already_bid(&task.bids, bidder_addr), EALREADY_BIDDED);
        
        // Create and add new bid
        let new_bid = Bid {
            bidder: bidder_addr,
            price: bid_price,
            timestamp: timestamp::now_seconds(),
            reputation_score,
        };
        
        vector::push_back(&mut task.bids, new_bid);
        
        // Emit event
        event::emit_event(&mut platform.bid_placed_events, BidPlacedEvent {
            task_id,
            bidder: bidder_addr,
            price: bid_price,
            reputation_score,
        });
    }

    /// Executor selects winner based on price and reputation
    public entry fun select_winner(
        executor: &signer,
        platform_addr: address,
        task_id: vector<u8>,
    ) acquires BiddingPlatform {
        let executor_addr = signer::address_of(executor);
        assert!(exists<BiddingPlatform>(platform_addr), EPLATFORM_NOT_INITIALIZED);
        
        let platform = borrow_global_mut<BiddingPlatform>(platform_addr);
        
        // Validate task exists
        assert!(smart_table::contains(&platform.tasks, task_id), ETASK_NOT_FOUND);
        
        let task = smart_table::borrow_mut(&mut platform.tasks, task_id);
        
        // Validate task status
        assert!(task.status == STATUS_PUBLISHED, EWRONG_TASK_STATUS);
        
        // Validate executor authority (MVP: only task creator can select winner)
        assert!(task.creator == executor_addr, EUNAUTHORIZED);
        
        // Validate there are bids to select from
        assert!(vector::length(&task.bids) > 0, ENO_BIDS_PLACED);
        
        // Find best bid using our algorithm (price + reputation + time)
        let best_bid_index = find_best_bid_index(&task.bids);
        let winning_bid = *vector::borrow(&task.bids, best_bid_index);
        
        // Update task state
        task.status = STATUS_ASSIGNED;
        task.winner = winning_bid.bidder;
        task.winning_price = winning_bid.price;
        
        // Store total bids count before clearing
        let total_bids = vector::length(&task.bids);
        
        // Clear bids to save storage space after selection
        task.bids = vector::empty<Bid>();
        
        // Emit event
        event::emit_event(&mut platform.winner_selected_events, WinnerSelectedEvent {
            task_id,
            creator: task.creator,
            winner: winning_bid.bidder,
            winning_price: winning_bid.price,
            total_bids,
        });
    }

    /// Winner completes task and receives payment
    public entry fun complete_task(
        winner: &signer,
        platform_addr: address,
        task_id: vector<u8>,
    ) acquires BiddingPlatform {
        let winner_addr = signer::address_of(winner);
        assert!(exists<BiddingPlatform>(platform_addr), EPLATFORM_NOT_INITIALIZED);
        
        let platform = borrow_global_mut<BiddingPlatform>(platform_addr);
        
        // Validate task exists
        assert!(smart_table::contains(&platform.tasks, task_id), ETASK_NOT_FOUND);
        
        let task = smart_table::borrow_mut(&mut platform.tasks, task_id);
        
        // Validate task status and winner
        assert!(task.status == STATUS_ASSIGNED, EWRONG_TASK_STATUS);
        assert!(task.winner == winner_addr, EUNAUTHORIZED);
        
        // Update task state
        task.status = STATUS_COMPLETED;
        task.completed_at = timestamp::now_seconds();
        
        // Get escrow and calculate payments
        let total_escrow = smart_table::remove(&mut platform.escrow, task_id);
        let winning_amount = task.winning_price;
        let creator_refund_amount = task.max_budget - winning_amount;
        
        // Pay winner their bid price (key optimization from V2 document)
        let payment_to_winner = coin::extract(&mut total_escrow, winning_amount);
        coin::deposit(winner_addr, payment_to_winner);
        
        // Refund the saved amount to task creator
        if (creator_refund_amount > 0) {
            coin::deposit(task.creator, total_escrow);
        } else {
            // If refund is 0, we still need to destroy the empty coin
            coin::destroy_zero(total_escrow);
        };
        
        // Update platform statistics
        platform.completed_tasks = platform.completed_tasks + 1;
        
        // Emit event
        event::emit_event(&mut platform.task_completed_events, TaskCompletedEvent {
            task_id,
            creator: task.creator,
            winner: winner_addr,
            paid_amount: winning_amount,
            creator_refund: creator_refund_amount,
        });
    }

    /// Creator cancels task and receives refund
    public entry fun cancel_task(
        creator: &signer,
        platform_addr: address,
        task_id: vector<u8>,
    ) acquires BiddingPlatform {
        let creator_addr = signer::address_of(creator);
        assert!(exists<BiddingPlatform>(platform_addr), EPLATFORM_NOT_INITIALIZED);
        
        let platform = borrow_global_mut<BiddingPlatform>(platform_addr);
        
        // Validate task exists
        assert!(smart_table::contains(&platform.tasks, task_id), ETASK_NOT_FOUND);
        
        let task = smart_table::borrow_mut(&mut platform.tasks, task_id);
        
        // Validate task status and creator
        assert!(task.status == STATUS_PUBLISHED, EWRONG_TASK_STATUS);
        assert!(task.creator == creator_addr, EUNAUTHORIZED);
        
        // Update task state
        task.status = STATUS_CANCELLED;
        
        // Store bids count before clearing
        let total_bids = vector::length(&task.bids);
        
        // Clear bids
        task.bids = vector::empty<Bid>();
        
        // Refund full amount to creator
        let refund = smart_table::remove(&mut platform.escrow, task_id);
        let refund_amount = coin::value(&refund);
        coin::deposit(creator_addr, refund);
        
        // Update platform statistics
        platform.cancelled_tasks = platform.cancelled_tasks + 1;
        
        // Emit event
        event::emit_event(&mut platform.task_cancelled_events, TaskCancelledEvent {
            task_id,
            creator: creator_addr,
            refunded_amount: refund_amount,
            total_bids,
        });
    }

    // View Functions

    /// Get task information
    #[view]
    public fun get_task(platform_addr: address, task_id: vector<u8>): Task acquires BiddingPlatform {
        let platform = borrow_global<BiddingPlatform>(platform_addr);
        assert!(smart_table::contains(&platform.tasks, task_id), ETASK_NOT_FOUND);
        *smart_table::borrow(&platform.tasks, task_id)
    }

    /// Get task status
    #[view]
    public fun get_task_status(platform_addr: address, task_id: vector<u8>): u8 acquires BiddingPlatform {
        let task = get_task(platform_addr, task_id);
        task.status
    }

    /// Get task winner
    #[view]
    public fun get_task_winner(platform_addr: address, task_id: vector<u8>): address acquires BiddingPlatform {
        let task = get_task(platform_addr, task_id);
        task.winner
    }

    /// Get task winning price
    #[view]
    public fun get_task_winning_price(platform_addr: address, task_id: vector<u8>): u64 acquires BiddingPlatform {
        let task = get_task(platform_addr, task_id);
        task.winning_price
    }

    /// Get task completed timestamp
    #[view]
    public fun get_task_completed_at(platform_addr: address, task_id: vector<u8>): u64 acquires BiddingPlatform {
        let task = get_task(platform_addr, task_id);
        task.completed_at
    }

    /// Get task basic info
    #[view]
    public fun get_task_info(platform_addr: address, task_id: vector<u8>): (vector<u8>, address, u64, u64, u8) acquires BiddingPlatform {
        let task = get_task(platform_addr, task_id);
        (task.id, task.creator, task.max_budget, task.deadline, task.status)
    }

    /// Get all bids for a task
    #[view]
    public fun get_task_bids(platform_addr: address, task_id: vector<u8>): vector<Bid> acquires BiddingPlatform {
        let task = get_task(platform_addr, task_id);
        task.bids
    }

    /// Get bid count for a task
    #[view]
    public fun get_task_bid_count(platform_addr: address, task_id: vector<u8>): u64 acquires BiddingPlatform {
        let task = get_task(platform_addr, task_id);
        vector::length(&task.bids)
    }

    /// Get platform statistics
    #[view]
    public fun get_platform_stats(platform_addr: address): (u64, u64, u64) acquires BiddingPlatform {
        let platform = borrow_global<BiddingPlatform>(platform_addr);
        (platform.total_tasks, platform.completed_tasks, platform.cancelled_tasks)
    }

    /// Check if task exists
    #[view]
    public fun task_exists(platform_addr: address, task_id: vector<u8>): bool acquires BiddingPlatform {
        if (!exists<BiddingPlatform>(platform_addr)) {
            return false
        };
        let platform = borrow_global<BiddingPlatform>(platform_addr);
        smart_table::contains(&platform.tasks, task_id)
    }

    // Helper Functions

    /// Validate task parameters
    fun validate_task_params(max_budget: u64, deadline_seconds: u64) {
        assert!(max_budget >= MINIMUM_PAY_AMOUNT, EINVALID_PAY_AMOUNT);
        assert!(deadline_seconds >= MINIMUM_TASK_DURATION, EINVALID_DEADLINE);
        assert!(deadline_seconds <= MAXIMUM_TASK_DURATION, EINVALID_DEADLINE);
    }

    /// Check if bidder already placed a bid
    fun has_bidder_already_bid(bids: &vector<Bid>, bidder_addr: address): bool {
        let i = 0;
        while (i < vector::length(bids)) {
            let bid = vector::borrow(bids, i);
            if (bid.bidder == bidder_addr) {
                return true
            };
            i = i + 1;
        };
        false
    }

    /// Find best bid index based on price and reputation
    fun find_best_bid_index(bids: &vector<Bid>): u64 {
        assert!(vector::length(bids) > 0, ENO_BIDS_PLACED);
        
        let best_index = 0;
        let i = 1;
        
        while (i < vector::length(bids)) {
            let current_bid = vector::borrow(bids, i);
            let best_bid = vector::borrow(bids, best_index);
            
            // Primary criteria: lowest price
            if (current_bid.price < best_bid.price) {
                best_index = i;
            } else if (current_bid.price == best_bid.price) {
                // Secondary criteria: higher reputation
                if (current_bid.reputation_score > best_bid.reputation_score) {
                    best_index = i;
                } else if (current_bid.reputation_score == best_bid.reputation_score) {
                    // Tertiary criteria: earlier timestamp
                    if (current_bid.timestamp < best_bid.timestamp) {
                        best_index = i;
                    };
                };
            };
            i = i + 1;
        };
        
        best_index
    }
}