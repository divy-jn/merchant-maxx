# Task 26B: Atomic Inventory Fulfillment & Overselling Remediation

## Executive Summary
**FINAL VERDICT: SECURE (Inventory Decrement Verified)**

The overselling vulnerability identified in Task 26A has been successfully remediated. Inventory is now atomically decremented at capture time, ensuring exactly-once processing per successful order. Duplicate webhooks are safely ignored, and edge cases where a user pays for an out-of-stock item are explicitly tracked and routed for automated refunds.

### Vulnerability Before Fix
Prior to this task, the system verified inventory levels in Python during checkout but never actually decremented the `inventory_qty` in the database upon successful payment. This allowed infinite purchases of any product as long as its quantity was originally > 0.

### Exact Race Condition & Remediation
- **Race Condition**: A TOCTOU race where inventory was checked during intent staging, but multiple concurrent users could purchase the exact same final unit, as the decrement was non-existent.
- **Fix**: We introduced a "Capture-Time Inventory Decrement" architecture. The inventory is only decremented when a successful `payment.captured` or `order.paid` event is received via the Razorpay webhook.

## Architecture

### 1. Database Design (Migration 004)
- **Idempotency Table**: `inventory_decrement_events` ensures inventory is decremented exactly once per `order_id`. If a duplicate webhook fires, it hits a `UNIQUE` constraint violation and returns safely without double-decrementing.
- **Postgres RPC `atomic_inventory_decrement`**:
  - Entirely transactional (all-or-nothing).
  - Locks all affected product rows using `SELECT ... FOR UPDATE`, ordered by `product_id` to eliminate deadlocks.
  - Validates `inventory_qty >= quantity` for every item in the basket.
  - Decrements all quantities atomically.
  - If any item lacks sufficient inventory, the entire transaction is rolled back via `RAISE EXCEPTION`.

### 2. Multi-Product Behavior
The system processes the entire authoritative `basket` attached to the `purchase_intents` table (avoiding client-tampered Razorpay webhook notes). Multi-item decrements either fully succeed or fully fail. There is no partial inventory decrement.

### 3. Payment & Fulfillment State Behavior
- **Payment State**: Remains strictly compliant with the existing state machine. A successful payment always transitions to `PAYMENT_SUCCESS`.
- **Fulfillment Status**: A new column `fulfillment_status` was added to `purchase_intents` and `orders`.
  - If inventory decrement succeeds, it is marked `FULFILLED`.
  - If inventory decrement fails (e.g., overselling occurred because of concurrent checkout), it is marked `UNFULFILLED`.

### 4. Refund Failure Handling
If `UNFULFILLED` occurs, the system logs the failure and automatically triggers the `services.refund_service.initiate_refund` abstraction to explicitly refund the customer. This preserves the immutable payment evidence (`PAYMENT_SUCCESS`) while cleanly handling the fulfillment failure. Automated tests mock this refund abstraction.

## Verification & Testing

### Concurrency Test Results
We explicitly tested the following scenarios in `backend/tests/test_inventory_fulfillment.py`:
1. **Stock 1 / Two Buyers**: Both attempt to decrement simultaneously. **Result**: Exactly one transaction succeeds, the other fails and rolls back atomically.
2. **Stock 5 / Two Buyers Requesting 3**: **Result**: Exactly one transaction succeeds (takes 3, leaving 2). The second one requests 3, sees only 2 available, and fails atomically.
3. **Multi-item rollback**: A basket requiring multiple items where only one lacks inventory. **Result**: No inventory is decremented.
4. **Duplicate webhook**: Sending the same `payment.captured` payload twice. **Result**: RPC returns `already_processed`, skipping decrement entirely.

### Regression & Deployment
- The entire 96-test suite passed without errors.
- The `fulfillment_status` migration was successfully applied.
- The frontend build (`npm run build`) succeeded.
- The deployment revision matches git HEAD (`merchant-maxx-api-00028-sxw`).

No actual Razorpay payments or refunds were performed during testing. All external financial side-effects were safely mocked.
