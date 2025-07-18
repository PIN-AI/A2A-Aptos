#[test_only]
module aptos_task_manager::task_manager_tests {
    use std::signer;
    use std::string;
    use aptos_framework::account;
    use aptos_framework::aptos_coin::{Self, AptosCoin};
    use aptos_framework::coin;
    use aptos_framework::timestamp;
    use aptos_task_manager::task_manager;

    // Test constants
    const MINIMUM_PAY_AMOUNT: u64 = 1000;
    const MINIMUM_TASK_DURATION: u64 = 3600;
    const TEST_TASK_ID: vector<u8> = b"test_task_1";

    #[test(framework = @0x1, task_agent = @0x100, service_agent = @0x200)]
    public fun test_initialize_and_create_task(
        framework: &signer,
        task_agent: &signer,
        service_agent: &signer,
    ) {
        // Set up the testing environment
        timestamp::set_time_has_started_for_testing(framework);
        let (burn_cap, mint_cap) = aptos_coin::initialize_for_test(framework);

        // Create accounts for testing
        account::create_account_for_test(signer::address_of(task_agent));
        account::create_account_for_test(signer::address_of(service_agent));

        // Mint some APT for task agent
        let coins = coin::mint(100000, &mint_cap);
        coin::deposit(signer::address_of(task_agent), coins);

        // Initialize TaskManager for task agent
        task_manager::initialize(task_agent);

        // Create a task with updated minimum amounts
        let service_agent_addr = signer::address_of(service_agent);
        let pay_amount = MINIMUM_PAY_AMOUNT * 10; // Use minimum * 10
        let deadline_seconds = MINIMUM_TASK_DURATION; // Use minimum duration
        let description = string::utf8(b"Test task description");

        task_manager::create_task(
            task_agent,
            TEST_TASK_ID,
            service_agent_addr,
            pay_amount,
            deadline_seconds,
            description,
        );

        // Verify task was created
        let task_count = task_manager::get_total_tasks_created(signer::address_of(task_agent));
        assert!(task_count == 1, 1);

        let (task_agent_addr, service_agent_return, pay_amount_return, _created_at, _deadline, is_completed, is_cancelled, description_return) = 
            task_manager::get_task_info(signer::address_of(task_agent), TEST_TASK_ID);
        assert!(task_agent_addr == signer::address_of(task_agent), 2);
        assert!(service_agent_return == service_agent_addr, 3);
        assert!(pay_amount_return == pay_amount, 4);
        assert!(!is_completed, 5);
        assert!(!is_cancelled, 5);
        assert!(description_return == description, 6);

        // Clean up
        coin::destroy_burn_cap(burn_cap);
        coin::destroy_mint_cap(mint_cap);
    }

    #[test(framework = @0x1, task_agent = @0x100, service_agent = @0x200)]
    public fun test_complete_task(
        framework: &signer,
        task_agent: &signer,
        service_agent: &signer,
    ) {
        // Set up the testing environment
        timestamp::set_time_has_started_for_testing(framework);
        let (burn_cap, mint_cap) = aptos_coin::initialize_for_test(framework);

        // Create accounts for testing
        account::create_account_for_test(signer::address_of(task_agent));
        account::create_account_for_test(signer::address_of(service_agent));

        // Mint some APT for task agent
        let coins = coin::mint(100000, &mint_cap);
        coin::deposit(signer::address_of(task_agent), coins);

        // Initialize TaskManager for task agent
        task_manager::initialize(task_agent);

        // Create a task with updated amounts
        let service_agent_addr = signer::address_of(service_agent);
        let pay_amount = MINIMUM_PAY_AMOUNT * 10; // Use minimum * 10
        let deadline_seconds = MINIMUM_TASK_DURATION; // Use minimum duration
        let description = string::utf8(b"Test task description");

        task_manager::create_task(
            task_agent,
            TEST_TASK_ID,
            service_agent_addr,
            pay_amount,
            deadline_seconds,
            description,
        );

        // Check service agent balance before completion
        let service_balance_before = coin::balance<AptosCoin>(service_agent_addr);

        // Complete the task
        task_manager::complete_task(
            service_agent,
            signer::address_of(task_agent),
            TEST_TASK_ID,
        );

        // Verify task was completed
        let (_task_agent_addr, _service_agent_return, _pay_amount_return, _created_at, _deadline, is_completed, _is_cancelled, _description_return) = 
            task_manager::get_task_info(signer::address_of(task_agent), TEST_TASK_ID);
        assert!(is_completed, 7);

        // Verify payment was transferred
        let service_balance_after = coin::balance<AptosCoin>(service_agent_addr);
        assert!(service_balance_after == service_balance_before + pay_amount, 8);

        // Clean up
        coin::destroy_burn_cap(burn_cap);
        coin::destroy_mint_cap(mint_cap);
    }

    #[test(framework = @0x1, task_agent = @0x100)]
    #[expected_failure(abort_code = 1, location = aptos_task_manager::task_manager)]
    public fun test_create_task_without_initialization(
        framework: &signer,
        task_agent: &signer,
    ) {
        // Set up the testing environment
        timestamp::set_time_has_started_for_testing(framework);
        let (burn_cap, mint_cap) = aptos_coin::initialize_for_test(framework);

        // Create account for testing
        account::create_account_for_test(signer::address_of(task_agent));

        // Mint some APT for task agent
        let coins = coin::mint(1000, &mint_cap);
        coin::deposit(signer::address_of(task_agent), coins);

        // Try to create a task without initializing TaskManager (should fail)
        task_manager::create_task(
            task_agent,
            TEST_TASK_ID,
            @0x200,
            100,
            3600,
            string::utf8(b"Test task"),
        );

        // Clean up
        coin::destroy_burn_cap(burn_cap);
        coin::destroy_mint_cap(mint_cap);
    }

    #[test(framework = @0x1, task_agent = @0x100, service_agent = @0x200, wrong_agent = @0x300)]
    #[expected_failure(abort_code = 4, location = aptos_task_manager::task_manager)]
    public fun test_unauthorized_complete_task(
        framework: &signer,
        task_agent: &signer,
        service_agent: &signer,
        wrong_agent: &signer,
    ) {
        // Set up the testing environment
        timestamp::set_time_has_started_for_testing(framework);
        let (burn_cap, mint_cap) = aptos_coin::initialize_for_test(framework);

        // Create accounts for testing
        account::create_account_for_test(signer::address_of(task_agent));
        account::create_account_for_test(signer::address_of(service_agent));
        account::create_account_for_test(signer::address_of(wrong_agent));

        // Mint some APT for task agent
        let coins = coin::mint(100000, &mint_cap);
        coin::deposit(signer::address_of(task_agent), coins);

        // Initialize TaskManager and create a task
        task_manager::initialize(task_agent);
        task_manager::create_task(
            task_agent,
            TEST_TASK_ID,
            signer::address_of(service_agent),
            MINIMUM_PAY_AMOUNT * 10, // Use minimum * 10
            MINIMUM_TASK_DURATION,   // Use minimum duration
            string::utf8(b"Test task"),
        );

        // Try to complete task with wrong agent (should fail)
        task_manager::complete_task(
            wrong_agent,
            signer::address_of(task_agent),
            TEST_TASK_ID,
        );

        // Clean up
        coin::destroy_burn_cap(burn_cap);
        coin::destroy_mint_cap(mint_cap);
    }

    #[test(framework = @0x1, task_agent = @0x100, service_agent = @0x200)]
    #[expected_failure(abort_code = 3, location = aptos_task_manager::task_manager)]
    public fun test_complete_already_completed_task(
        framework: &signer,
        task_agent: &signer,
        service_agent: &signer,
    ) {
        // Set up the testing environment
        timestamp::set_time_has_started_for_testing(framework);
        let (burn_cap, mint_cap) = aptos_coin::initialize_for_test(framework);

        // Create accounts for testing
        account::create_account_for_test(signer::address_of(task_agent));
        account::create_account_for_test(signer::address_of(service_agent));

        // Mint some APT for task agent
        let coins = coin::mint(100000, &mint_cap);
        coin::deposit(signer::address_of(task_agent), coins);

        // Initialize TaskManager and create a task
        task_manager::initialize(task_agent);
        task_manager::create_task(
            task_agent,
            TEST_TASK_ID,
            signer::address_of(service_agent),
            MINIMUM_PAY_AMOUNT * 10, // Use minimum * 10
            MINIMUM_TASK_DURATION,   // Use minimum duration
            string::utf8(b"Test task"),
        );

        // Complete the task once
        task_manager::complete_task(
            service_agent,
            signer::address_of(task_agent),
            TEST_TASK_ID,
        );

        // Try to complete the same task again (should fail)
        task_manager::complete_task(
            service_agent,
            signer::address_of(task_agent),
            TEST_TASK_ID,
        );

        // Clean up
        coin::destroy_burn_cap(burn_cap);
        coin::destroy_mint_cap(mint_cap);
    }

    #[test(framework = @0x1, task_agent = @0x100, service_agent = @0x200)]
    public fun test_enhanced_task_creation_and_completion(
        framework: &signer,
        task_agent: &signer,
        service_agent: &signer,
    ) {
        setup_test_environment(framework, task_agent, service_agent);

        // Create a task with enhanced validation
        let service_agent_addr = signer::address_of(service_agent);
        let pay_amount = MINIMUM_PAY_AMOUNT * 100; // 0.001 APT
        let deadline_seconds = MINIMUM_TASK_DURATION * 2; // 2 hours
        let description = string::utf8(b"Enhanced test task");

        task_manager::create_task(
            task_agent,
            TEST_TASK_ID,
            service_agent_addr,
            pay_amount,
            deadline_seconds,
            description,
        );

        // Verify task was created with new structure
        let (total_tasks, completed_tasks, cancelled_tasks) = 
            task_manager::get_task_stats(signer::address_of(task_agent));
        assert!(total_tasks == 1, 1);
        assert!(completed_tasks == 0, 2);
        assert!(cancelled_tasks == 0, 3);

        // Verify task info using new enhanced function
        let (task_agent_addr, service_agent_returned, pay_amt, _created_at, _deadline, is_completed, is_cancelled, desc) = 
            task_manager::get_task_info(signer::address_of(task_agent), TEST_TASK_ID);
        
        assert!(task_agent_addr == signer::address_of(task_agent), 4);
        assert!(service_agent_returned == service_agent_addr, 5);
        assert!(pay_amt == pay_amount, 6);
        assert!(!is_completed, 7);
        assert!(!is_cancelled, 8);
        assert!(desc == description, 9);

        // Check task is not expired
        assert!(!task_manager::is_task_expired(signer::address_of(task_agent), TEST_TASK_ID), 10);

        // Complete the task
        let service_balance_before = coin::balance<AptosCoin>(service_agent_addr);
        task_manager::complete_task(
            service_agent,
            signer::address_of(task_agent),
            TEST_TASK_ID,
        );

        // Verify completion
        let (_, completed_tasks_after, _) = 
            task_manager::get_task_stats(signer::address_of(task_agent));
        assert!(completed_tasks_after == 1, 11);

        // Verify payment was transferred
        let service_balance_after = coin::balance<AptosCoin>(service_agent_addr);
        assert!(service_balance_after == service_balance_before + pay_amount, 12);
    }

    #[test(framework = @0x1, task_agent = @0x100, service_agent = @0x200)]
    public fun test_task_cancellation(
        framework: &signer,
        task_agent: &signer,
        service_agent: &signer,
    ) {
        setup_test_environment(framework, task_agent, service_agent);

        // Create a task
        let service_agent_addr = signer::address_of(service_agent);
        let pay_amount = MINIMUM_PAY_AMOUNT * 50;
        let task_agent_balance_before = coin::balance<AptosCoin>(signer::address_of(task_agent));

        task_manager::create_task(
            task_agent,
            TEST_TASK_ID,
            service_agent_addr,
            pay_amount,
            MINIMUM_TASK_DURATION,
            string::utf8(b"Cancellable task"),
        );

        // Cancel the task
        task_manager::cancel_task(task_agent, TEST_TASK_ID);

        // Verify cancellation
        let (_, _, cancelled_tasks) = 
            task_manager::get_task_stats(signer::address_of(task_agent));
        assert!(cancelled_tasks == 1, 1);

        let (_task_agent_addr, _service_agent_return, _pay_amount_return, _created_at, _deadline, is_completed, is_cancelled, _description_return) = 
            task_manager::get_task_info(signer::address_of(task_agent), TEST_TASK_ID);
        assert!(is_cancelled, 2);
        assert!(!is_completed, 3);

        // Verify refund
        let task_agent_balance_after = coin::balance<AptosCoin>(signer::address_of(task_agent));
        assert!(task_agent_balance_after == task_agent_balance_before, 4);
    }

    #[test(framework = @0x1, task_agent = @0x100, service_agent = @0x200)]
    public fun test_expired_task_refund(
        framework: &signer,
        task_agent: &signer,
        service_agent: &signer,
    ) {
        setup_test_environment(framework, task_agent, service_agent);

        // Create a task with short deadline
        let service_agent_addr = signer::address_of(service_agent);
        let pay_amount = MINIMUM_PAY_AMOUNT * 75;
        let task_agent_balance_before = coin::balance<AptosCoin>(signer::address_of(task_agent));

        task_manager::create_task(
            task_agent,
            TEST_TASK_ID,
            service_agent_addr,
            pay_amount,
            MINIMUM_TASK_DURATION,
            string::utf8(b"Soon to expire task"),
        );

        // Fast forward time to expire the task
        timestamp::fast_forward_seconds(MINIMUM_TASK_DURATION + 1);

        // Verify task is expired
        assert!(task_manager::is_task_expired(signer::address_of(task_agent), TEST_TASK_ID), 1);

        // Claim expired task refund
        task_manager::claim_expired_task_refund(task_agent, TEST_TASK_ID);

        // Verify refund and cancellation
        let (_task_agent_addr, _service_agent_return, _pay_amount_return, _created_at, _deadline, _is_completed, is_cancelled, _description_return) = 
            task_manager::get_task_info(signer::address_of(task_agent), TEST_TASK_ID);
        assert!(is_cancelled, 2);

        let task_agent_balance_after = coin::balance<AptosCoin>(signer::address_of(task_agent));
        assert!(task_agent_balance_after == task_agent_balance_before, 3);
    }

    #[test(framework = @0x1, task_agent = @0x100)]
    #[expected_failure(abort_code = 9, location = aptos_task_manager::task_manager)]
    public fun test_minimum_pay_amount_validation(
        framework: &signer,
        task_agent: &signer,
    ) {
        // Set up basic environment
        timestamp::set_time_has_started_for_testing(framework);
        let (burn_cap, mint_cap) = aptos_coin::initialize_for_test(framework);
        account::create_account_for_test(signer::address_of(task_agent));

        let coins = coin::mint(10000, &mint_cap);
        coin::deposit(signer::address_of(task_agent), coins);

        task_manager::initialize(task_agent);

        // Try to create task with amount below minimum (should fail)
        task_manager::create_task(
            task_agent,
            TEST_TASK_ID,
            @0x200,
            MINIMUM_PAY_AMOUNT - 1, // Below minimum
            MINIMUM_TASK_DURATION,
            string::utf8(b"Invalid task"),
        );

        coin::destroy_burn_cap(burn_cap);
        coin::destroy_mint_cap(mint_cap);
    }

    #[test(framework = @0x1, task_agent = @0x100)]
    #[expected_failure(abort_code = 8, location = aptos_task_manager::task_manager)]
    public fun test_minimum_deadline_validation(
        framework: &signer,
        task_agent: &signer,
    ) {
        // Set up basic environment
        timestamp::set_time_has_started_for_testing(framework);
        let (burn_cap, mint_cap) = aptos_coin::initialize_for_test(framework);
        account::create_account_for_test(signer::address_of(task_agent));

        let coins = coin::mint(10000, &mint_cap);
        coin::deposit(signer::address_of(task_agent), coins);

        task_manager::initialize(task_agent);

        // Try to create task with deadline below minimum (should fail)
        task_manager::create_task(
            task_agent,
            TEST_TASK_ID,
            @0x200,
            MINIMUM_PAY_AMOUNT,
            MINIMUM_TASK_DURATION - 1, // Below minimum
            string::utf8(b"Invalid deadline task"),
        );

        coin::destroy_burn_cap(burn_cap);
        coin::destroy_mint_cap(mint_cap);
    }

    #[test(framework = @0x1, task_agent = @0x100, service_agent = @0x200)]
    #[expected_failure(abort_code = 7, location = aptos_task_manager::task_manager)]
    public fun test_complete_cancelled_task_fails(
        framework: &signer,
        task_agent: &signer,
        service_agent: &signer,
    ) {
        setup_test_environment(framework, task_agent, service_agent);

        // Create and cancel a task
        task_manager::create_task(
            task_agent,
            TEST_TASK_ID,
            signer::address_of(service_agent),
            MINIMUM_PAY_AMOUNT * 10,
            MINIMUM_TASK_DURATION,
            string::utf8(b"Task to cancel"),
        );

        task_manager::cancel_task(task_agent, TEST_TASK_ID);

        // Try to complete cancelled task (should fail)
        task_manager::complete_task(
            service_agent,
            signer::address_of(task_agent),
            TEST_TASK_ID,
        );
    }

    #[test(framework = @0x1, task_agent = @0x100, service_agent = @0x200)]
    #[expected_failure(abort_code = 6, location = aptos_task_manager::task_manager)]
    public fun test_complete_expired_task_fails(
        framework: &signer,
        task_agent: &signer,
        service_agent: &signer,
    ) {
        setup_test_environment(framework, task_agent, service_agent);

        // Create a task
        task_manager::create_task(
            task_agent,
            TEST_TASK_ID,
            signer::address_of(service_agent),
            MINIMUM_PAY_AMOUNT * 10,
            MINIMUM_TASK_DURATION,
            string::utf8(b"Task to expire"),
        );

        // Expire the task
        timestamp::fast_forward_seconds(MINIMUM_TASK_DURATION + 1);

        // Try to complete expired task (should fail)
        task_manager::complete_task(
            service_agent,
            signer::address_of(task_agent),
            TEST_TASK_ID,
        );
    }

    #[test(framework = @0x1, task_agent = @0x100, service_agent = @0x200)]
    #[expected_failure(abort_code = 12, location = aptos_task_manager::task_manager)]
    public fun test_create_task_with_duplicate_id_fails(
        framework: &signer,
        task_agent: &signer,
        service_agent: &signer,
    ) {
        setup_test_environment(framework, task_agent, service_agent);

        let service_agent_addr = signer::address_of(service_agent);

        // Create a task
        task_manager::create_task(
            task_agent,
            TEST_TASK_ID,
            service_agent_addr,
            MINIMUM_PAY_AMOUNT * 10,
            MINIMUM_TASK_DURATION,
            string::utf8(b"First task"),
        );

        // Try to create another task with the same ID (should fail)
        task_manager::create_task(
            task_agent,
            TEST_TASK_ID,
            service_agent_addr,
            MINIMUM_PAY_AMOUNT * 20,
            MINIMUM_TASK_DURATION * 2,
            string::utf8(b"Duplicate task"),
        );
    }

    // Helper function to set up test environment
    fun setup_test_environment(
        framework: &signer,
        task_agent: &signer,
        service_agent: &signer,
    ) {
        timestamp::set_time_has_started_for_testing(framework);
        let (burn_cap, mint_cap) = aptos_coin::initialize_for_test(framework);

        account::create_account_for_test(signer::address_of(task_agent));
        account::create_account_for_test(signer::address_of(service_agent));

        let coins = coin::mint(100000, &mint_cap);
        coin::deposit(signer::address_of(task_agent), coins);

        task_manager::initialize(task_agent);

        coin::destroy_burn_cap(burn_cap);
        coin::destroy_mint_cap(mint_cap);
    }
} 