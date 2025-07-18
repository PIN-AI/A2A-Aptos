module aptos_task_manager::task_manager {
    use std::signer;
    use std::string::{Self, String};
    use aptos_framework::coin::{Self, Coin};
    use aptos_framework::aptos_coin::AptosCoin;
    use aptos_framework::timestamp;
    use aptos_framework::event::{Self, EventHandle};
    use aptos_framework::account;
    use aptos_std::smart_table::{Self, SmartTable};

    // Constants
    const MINIMUM_TASK_DURATION: u64 = 3600; // 1 hour minimum
    const MAXIMUM_TASK_DURATION: u64 = 7776000; // 90 days maximum
    const MINIMUM_PAY_AMOUNT: u64 = 1000; // 0.00001 APT minimum

    // Error codes (Enhanced error system)
    const ETASK_MANAGER_NOT_INITIALIZED: u64 = 1;
    const ETASK_NOT_FOUND: u64 = 2;
    const ETASK_ALREADY_COMPLETED: u64 = 3;
    const EUNAUTHORIZED: u64 = 4;
    const EINSUFFICIENT_PAYMENT: u64 = 5;
    const ETASK_EXPIRED: u64 = 6;
    const ETASK_ALREADY_CANCELLED: u64 = 7;
    const EINVALID_DEADLINE: u64 = 8;
    const EINVALID_PAY_AMOUNT: u64 = 9;
    const ETASK_STILL_ACTIVE: u64 = 10;
    const ECANNOT_CANCEL_COMPLETED_TASK: u64 = 11;
    const ETASK_ID_ALREADY_EXISTS: u64 = 12;

    // Task structure with enhanced security fields
    struct Task has store, copy, drop {
        task_id: vector<u8>,
        task_agent: address,        // task creator
        service_agent: address,     // service provider
        pay_amount: u64,           // payment amount in APT
        created_at: u64,           // creation timestamp
        deadline: u64,             // task deadline
        is_completed: bool,        // completion status
        is_cancelled: bool,        // cancellation status
        description: String,       // task description
    }

    // TaskManager resource with SmartTable for better performance
    struct TaskManager has key {
        tasks: SmartTable<vector<u8>, Task>,
        escrow_coins: SmartTable<vector<u8>, Coin<AptosCoin>>,  // escrowed payments
        task_counter: u64,
        cancelled_task_count: u64, // track cancelled tasks
        completed_task_count: u64, // track completed tasks
        task_created_events: EventHandle<TaskCreatedEvent>,
        task_completed_events: EventHandle<TaskCompletedEvent>,
        task_cancelled_events: EventHandle<TaskCancelledEvent>,
        task_refunded_events: EventHandle<TaskRefundedEvent>,
    }

    // Enhanced Events
    struct TaskCreatedEvent has drop, store {
        task_id: vector<u8>,
        task_agent: address,
        service_agent: address,
        pay_amount: u64,
        deadline: u64,
        description: String,
    }

    struct TaskCompletedEvent has drop, store {
        task_id: vector<u8>,
        task_agent: address,
        service_agent: address,
        pay_amount: u64,
    }

    struct TaskCancelledEvent has drop, store {
        task_id: vector<u8>,
        task_agent: address,
        service_agent: address,
        refund_amount: u64,
        cancelled_at: u64,
    }

    struct TaskRefundedEvent has drop, store {
        task_id: vector<u8>,
        task_agent: address,
        refund_amount: u64,
        reason: String,
    }

    // Initialize TaskManager for an account
    public entry fun initialize(account: &signer) {
        let account_addr = signer::address_of(account);
        assert!(!exists<TaskManager>(account_addr), ETASK_MANAGER_NOT_INITIALIZED);
        
        move_to(account, TaskManager {
            tasks: smart_table::new(),
            escrow_coins: smart_table::new(),
            task_counter: 0,
            cancelled_task_count: 0,
            completed_task_count: 0,
            task_created_events: account::new_event_handle<TaskCreatedEvent>(account),
            task_completed_events: account::new_event_handle<TaskCompletedEvent>(account),
            task_cancelled_events: account::new_event_handle<TaskCancelledEvent>(account),
            task_refunded_events: account::new_event_handle<TaskRefundedEvent>(account),
        });
    }

    // Create a new task with enhanced validation
    public entry fun create_task(
        task_agent: &signer,
        task_id: vector<u8>,
        service_agent: address,
        pay_amount: u64,
        deadline_seconds: u64,
        description: String,
    ) acquires TaskManager {
        let task_agent_addr = signer::address_of(task_agent);
        assert!(exists<TaskManager>(task_agent_addr), ETASK_MANAGER_NOT_INITIALIZED);
        
        let task_manager = borrow_global_mut<TaskManager>(task_agent_addr);
        assert!(!smart_table::contains(&task_manager.tasks, task_id), ETASK_ID_ALREADY_EXISTS);
        
        // Enhanced validation
        assert!(pay_amount >= MINIMUM_PAY_AMOUNT, EINVALID_PAY_AMOUNT);
        assert!(deadline_seconds >= MINIMUM_TASK_DURATION, EINVALID_DEADLINE);
        assert!(deadline_seconds <= MAXIMUM_TASK_DURATION, EINVALID_DEADLINE);
        assert!(task_agent_addr != service_agent, EUNAUTHORIZED);
        
        // Withdraw payment from task agent
        let payment = coin::withdraw<AptosCoin>(task_agent, pay_amount);
        
        task_manager.task_counter = task_manager.task_counter + 1;
        
        let current_time = timestamp::now_seconds();
        let deadline = current_time + deadline_seconds;
        
        let task = Task {
            task_id,
            task_agent: task_agent_addr,
            service_agent,
            pay_amount,
            created_at: current_time,
            deadline,
            is_completed: false,
            is_cancelled: false,
            description,
        };
        
        // Store task and escrow payment
        smart_table::add(&mut task_manager.tasks, task_id, task);
        smart_table::add(&mut task_manager.escrow_coins, task_id, payment);
        
        // Emit event
        event::emit_event(&mut task_manager.task_created_events, TaskCreatedEvent {
            task_id,
            task_agent: task_agent_addr,
            service_agent,
            pay_amount,
            deadline,
            description,
        });
    }

    // Complete a task with enhanced security
    public entry fun complete_task(
        service_agent: &signer,
        task_agent_addr: address,
        task_id: vector<u8>,
    ) acquires TaskManager {
        assert!(exists<TaskManager>(task_agent_addr), ETASK_MANAGER_NOT_INITIALIZED);
        
        let task_manager = borrow_global_mut<TaskManager>(task_agent_addr);
        assert!(smart_table::contains(&task_manager.tasks, task_id), ETASK_NOT_FOUND);
        
        let task = smart_table::borrow_mut(&mut task_manager.tasks, task_id);
        assert!(!task.is_completed, ETASK_ALREADY_COMPLETED);
        assert!(!task.is_cancelled, ETASK_ALREADY_CANCELLED);
        assert!(task.service_agent == signer::address_of(service_agent), EUNAUTHORIZED);
        
        // Check if task has expired
        let current_time = timestamp::now_seconds();
        assert!(current_time <= task.deadline, ETASK_EXPIRED);
        
        // Mark task as completed
        task.is_completed = true;
        task_manager.completed_task_count = task_manager.completed_task_count + 1;
        
        // Release payment to service agent
        let payment = smart_table::remove(&mut task_manager.escrow_coins, task_id);
        coin::deposit(task.service_agent, payment);
        
        // Emit event
        event::emit_event(&mut task_manager.task_completed_events, TaskCompletedEvent {
            task_id,
            task_agent: task.task_agent,
            service_agent: task.service_agent,
            pay_amount: task.pay_amount,
        });
    }

    // Cancel a task (NEW SECURITY FEATURE)
    public entry fun cancel_task(
        task_agent: &signer,
        task_id: vector<u8>,
    ) acquires TaskManager {
        let task_agent_addr = signer::address_of(task_agent);
        assert!(exists<TaskManager>(task_agent_addr), ETASK_MANAGER_NOT_INITIALIZED);
        
        let task_manager = borrow_global_mut<TaskManager>(task_agent_addr);
        assert!(smart_table::contains(&task_manager.tasks, task_id), ETASK_NOT_FOUND);
        
        let task = smart_table::borrow_mut(&mut task_manager.tasks, task_id);
        assert!(task.task_agent == task_agent_addr, EUNAUTHORIZED);
        assert!(!task.is_completed, ECANNOT_CANCEL_COMPLETED_TASK);
        assert!(!task.is_cancelled, ETASK_ALREADY_CANCELLED);
        
        // Mark task as cancelled
        task.is_cancelled = true;
        task_manager.cancelled_task_count = task_manager.cancelled_task_count + 1;
        
        // Refund payment to task agent
        let payment = smart_table::remove(&mut task_manager.escrow_coins, task_id);
        let refund_amount = coin::value(&payment);
        coin::deposit(task_agent_addr, payment);
        
        let current_time = timestamp::now_seconds();
        
        // Emit events
        event::emit_event(&mut task_manager.task_cancelled_events, TaskCancelledEvent {
            task_id,
            task_agent: task_agent_addr,
            service_agent: task.service_agent,
            refund_amount,
            cancelled_at: current_time,
        });
    }

    // Automatic refund for expired tasks (NEW SECURITY FEATURE)
    public entry fun claim_expired_task_refund(
        task_agent: &signer,
        task_id: vector<u8>,
    ) acquires TaskManager {
        let task_agent_addr = signer::address_of(task_agent);
        assert!(exists<TaskManager>(task_agent_addr), ETASK_MANAGER_NOT_INITIALIZED);
        
        let task_manager = borrow_global_mut<TaskManager>(task_agent_addr);
        assert!(smart_table::contains(&task_manager.tasks, task_id), ETASK_NOT_FOUND);
        
        let task = smart_table::borrow_mut(&mut task_manager.tasks, task_id);
        assert!(task.task_agent == task_agent_addr, EUNAUTHORIZED);
        assert!(!task.is_completed, ECANNOT_CANCEL_COMPLETED_TASK);
        assert!(!task.is_cancelled, ETASK_ALREADY_CANCELLED);
        
        // Check if task has expired
        let current_time = timestamp::now_seconds();
        assert!(current_time > task.deadline, ETASK_STILL_ACTIVE);
        
        // Mark as cancelled and refund
        task.is_cancelled = true;
        task_manager.cancelled_task_count = task_manager.cancelled_task_count + 1;
        
        let payment = smart_table::remove(&mut task_manager.escrow_coins, task_id);
        let refund_amount = coin::value(&payment);
        coin::deposit(task_agent_addr, payment);
        
        // Emit refund event
        event::emit_event(&mut task_manager.task_refunded_events, TaskRefundedEvent {
            task_id,
            task_agent: task_agent_addr,
            refund_amount,
            reason: string::utf8(b"Task expired"),
        });
    }

    // Get a specific task by ID
    #[view]
    public fun get_task(task_agent_addr: address, task_id: vector<u8>): Task acquires TaskManager {
        assert!(exists<TaskManager>(task_agent_addr), ETASK_MANAGER_NOT_INITIALIZED);
        let task_manager = borrow_global<TaskManager>(task_agent_addr);
        assert!(smart_table::contains(&task_manager.tasks, task_id), ETASK_NOT_FOUND);
        *smart_table::borrow(&task_manager.tasks, task_id)
    }

    // Get total number of tasks created by an agent
    #[view]
    public fun get_total_tasks_created(task_agent_addr: address): u64 acquires TaskManager {
        assert!(exists<TaskManager>(task_agent_addr), ETASK_MANAGER_NOT_INITIALIZED);
        borrow_global<TaskManager>(task_agent_addr).task_counter
    }

    // Get detailed task stats for an agent
    #[view]
    public fun get_task_stats(task_agent_addr: address): (u64, u64, u64) acquires TaskManager {
        assert!(exists<TaskManager>(task_agent_addr), ETASK_MANAGER_NOT_INITIALIZED);
        let task_manager = borrow_global<TaskManager>(task_agent_addr);
        (
            task_manager.task_counter,
            task_manager.completed_task_count,
            task_manager.cancelled_task_count
        )
    }

    // Get detailed information for a specific task
    #[view]
    public fun get_task_info(task_agent_addr: address, task_id: vector<u8>): (address, address, u64, u64, u64, bool, bool, String) acquires TaskManager {
        let task = get_task(task_agent_addr, task_id);
        (
            task.task_agent,
            task.service_agent,
            task.pay_amount,
            task.created_at,
            task.deadline,
            task.is_completed,
            task.is_cancelled,
            task.description
        )
    }

    // Check if a task is expired
    #[view]
    public fun is_task_expired(task_agent_addr: address, task_id: vector<u8>): bool acquires TaskManager {
        let task = get_task(task_agent_addr, task_id);
        timestamp::now_seconds() > task.deadline
    }

    // Note: Direct field accessors removed to avoid transaction parameter type issues
    // Use get_task_info() and get_task() functions instead for accessing task fields

    // Integration Functions for match_system.move

    /// Check if a task exists (used by match_system for validation)
    #[view]
    public fun task_exists(task_agent_addr: address, task_id: vector<u8>): bool acquires TaskManager {
        if (!exists<TaskManager>(task_agent_addr)) {
            return false
        };
        let task_manager = borrow_global<TaskManager>(task_agent_addr);
        smart_table::contains(&task_manager.tasks, task_id)
    }

    /// Complete a task from market match (called by match_system)
    public entry fun complete_task_from_market(
        task_agent_addr: address,
        service_agent_addr: address,
        task_id: vector<u8>,
        final_amount: u64,
    ) acquires TaskManager {
        assert!(exists<TaskManager>(task_agent_addr), ETASK_MANAGER_NOT_INITIALIZED);
        
        let task_manager = borrow_global_mut<TaskManager>(task_agent_addr);
        assert!(smart_table::contains(&task_manager.tasks, task_id), ETASK_NOT_FOUND);
        
        let task = smart_table::borrow_mut(&mut task_manager.tasks, task_id);
        assert!(!task.is_completed, ETASK_ALREADY_COMPLETED);
        assert!(!task.is_cancelled, ETASK_ALREADY_CANCELLED);
        assert!(task.service_agent == service_agent_addr, EUNAUTHORIZED);
        
        // Check if task has not expired
        let current_time = timestamp::now_seconds();
        assert!(current_time <= task.deadline, ETASK_EXPIRED);
        
        // Mark task as completed
        task.is_completed = true;
        task_manager.completed_task_count = task_manager.completed_task_count + 1;
        
        // Release payment to service agent with market-determined amount
        let payment = smart_table::remove(&mut task_manager.escrow_coins, task_id);
        let original_amount = coin::value(&payment);
        
        // If final_amount is less than original (due to market match), refund difference
        if (final_amount < original_amount) {
            let service_payment = coin::extract(&mut payment, final_amount);
            coin::deposit(service_agent_addr, service_payment);
            // Refund remaining to task agent
            coin::deposit(task_agent_addr, payment);
        } else {
            // Pay full amount to service agent
            coin::deposit(service_agent_addr, payment);
        };
        
        // Emit event
        event::emit_event(&mut task_manager.task_completed_events, TaskCompletedEvent {
            task_id,
            task_agent: task.task_agent,
            service_agent: task.service_agent,
            pay_amount: final_amount,
        });
    }

    /// Create a task specifically for market publication (extended version)
    public entry fun create_task_with_market_mode(
        task_agent: &signer,
        task_id: vector<u8>,
        mode: u8, // 1=DirectAssign, 2=PublishToMarket
        service_agent_or_max_price: u64, // For direct: cast from address, for market: max price
        deadline_seconds: u64,
        description: String,
    ) acquires TaskManager {
        let task_agent_addr = signer::address_of(task_agent);
        
        if (mode == 1) {
            // Direct assignment mode - use original create_task function
            let service_agent = @0x0; // This would need proper address casting in real implementation
            create_task(task_agent, task_id, service_agent, service_agent_or_max_price, deadline_seconds, description);
        } else if (mode == 2) {
            // Market publication mode - create task with placeholder service agent
            let max_price = service_agent_or_max_price;
            let placeholder_service_agent = task_agent_addr; // Placeholder, will be set by market
            
            assert!(exists<TaskManager>(task_agent_addr), ETASK_MANAGER_NOT_INITIALIZED);
            let task_manager = borrow_global_mut<TaskManager>(task_agent_addr);
            assert!(!smart_table::contains(&task_manager.tasks, task_id), ETASK_ID_ALREADY_EXISTS);
            
            // Enhanced validation
            assert!(max_price >= MINIMUM_PAY_AMOUNT, EINVALID_PAY_AMOUNT);
            assert!(deadline_seconds >= MINIMUM_TASK_DURATION, EINVALID_DEADLINE);
            assert!(deadline_seconds <= MAXIMUM_TASK_DURATION, EINVALID_DEADLINE);
            
            // Withdraw payment from task agent
            let payment = coin::withdraw<AptosCoin>(task_agent, max_price);
            
            task_manager.task_counter = task_manager.task_counter + 1;
            
            let current_time = timestamp::now_seconds();
            let deadline = current_time + deadline_seconds;
            
            let task = Task {
                task_id,
                task_agent: task_agent_addr,
                service_agent: placeholder_service_agent, // Will be updated when matched
                pay_amount: max_price,
                created_at: current_time,
                deadline,
                is_completed: false,
                is_cancelled: false,
                description,
            };
            
            // Store task and escrow payment
            smart_table::add(&mut task_manager.tasks, task_id, task);
            smart_table::add(&mut task_manager.escrow_coins, task_id, payment);
            
            // Emit event with market mode indicator
            event::emit_event(&mut task_manager.task_created_events, TaskCreatedEvent {
                task_id,
                task_agent: task_agent_addr,
                service_agent: placeholder_service_agent,
                pay_amount: max_price,
                deadline,
                description,
            });
        };
    }

    /// Update service agent when task is matched in market
    public entry fun assign_service_agent_from_market(
        task_agent_addr: address,
        task_id: vector<u8>,
        service_agent_addr: address,
    ) acquires TaskManager {
        assert!(exists<TaskManager>(task_agent_addr), ETASK_MANAGER_NOT_INITIALIZED);
        
        let task_manager = borrow_global_mut<TaskManager>(task_agent_addr);
        assert!(smart_table::contains(&task_manager.tasks, task_id), ETASK_NOT_FOUND);
        
        let task = smart_table::borrow_mut(&mut task_manager.tasks, task_id);
        assert!(!task.is_completed, ETASK_ALREADY_COMPLETED);
        assert!(!task.is_cancelled, ETASK_ALREADY_CANCELLED);
        
        // Update service agent
        task.service_agent = service_agent_addr;
    }

    /// Get market-compatible task information
    #[view]
    public fun get_market_task_info(task_agent_addr: address, task_id: vector<u8>): (u64, u64, bool, bool) acquires TaskManager {
        let task = get_task(task_agent_addr, task_id);
        (
            task.pay_amount,
            task.deadline,
            task.is_completed,
            task.is_cancelled
        )
    }
} 