> **Project status — Under Development**
>
> Merchant Maxx is under active development. The core application source is maintained in `backend/` and `frontend/`, with supporting documentation in `docs/`.
>
> **Current state:**
> - The production application is deployed through the existing backend/frontend deployment setup.
> - The restored development history contains **108 commits** with original author/committer metadata and timestamps preserved through the security rewrite.
> - Previously exposed credentials were scrubbed from reachable Git history; real credentials must remain in environment/secret-manager configuration and must not be committed.
> - The latest local backend validation recorded **156 passing tests and 1 xpassed**. The GitHub Actions backend test check still needs to be resolved before calling CI fully green.
> - Development-only artifacts have been moved into `underConstruction/` so the repository root stays focused on the application and required project files.
>
> This status block is intentionally kept current as the project continues through development, testing, hardening, and deployment work.
>
> ---
>
# Razorpay Standard Checkout Integration

This plan outlines the steps to implement the Razorpay Standard Checkout flow, allowing users to purchase products directly from the Catalog page.

## Goal
Integrate the official Razorpay Checkout modal into the frontend so users can complete a test purchase end-to-end.

## Proposed Changes

### Backend
We need an API endpoint for the frontend to create an order ID before launching the checkout.

#### [NEW] [checkout.py](file:///c:/building%20projs/razorpay_proj/backend/routes/checkout.py)
Create a new router with a `POST /checkout/create-order` endpoint. It will accept the `amount` and `receipt` data and call our existing `razorpay_service.orders.create_order` function to return an `order_id` to the frontend.

#### [MODIFY] [main.py](file:///c:/building%20projs/razorpay_proj/backend/main.py)
Register the new `checkout` router.

### Frontend
We will add a "Buy Now" button to the catalog products that triggers the checkout modal.

#### [MODIFY] [index.html](file:///c:/building%20projs/razorpay_proj/frontend/index.html)
Add `<script src="https://checkout.razorpay.com/v1/checkout.js"></script>` to the head so the Razorpay class is available globally.

#### [MODIFY] [Catalog.jsx](file:///c:/building%20projs/razorpay_proj/frontend/src/pages/Catalog.jsx)
1. Add a `handleBuy(product)` function.
2. Call `POST /checkout/create-order` to get the `order_id`.
3. Initialize `new window.Razorpay(options)` passing the test API key, order ID, amount, and name.
4. Call `rzp.open()` to show the modal.
5. Handle the `handler` callback (success) to show a success message.

## Verification Plan

### Automated Tests
I will run the existing E2E tests, though they test API endpoints rather than the JS modal.

### Manual Verification
You can open the catalog in your browser, click "Buy Now" on any product, and complete a test payment using the test cards (e.g., `4111 1111 1111 1111`) or test UPI (`success@razorpay`).

## Open Questions

> [!NOTE]
> I notice you provided your test `Key ID` in the chat (`[MASKED_RAZORPAY_KEY]`). The frontend will need this key to launch the modal. Should I hardcode it in the frontend for the hackathon, or should we fetch it dynamically from the backend so it remains only in the `.env` file? (Dynamically fetching is safer, but hardcoding in Vite's `.env` as `VITE_RAZORPAY_KEY_ID` is standard practice for public keys). I will assume `VITE_RAZORPAY_KEY_ID` for now.
