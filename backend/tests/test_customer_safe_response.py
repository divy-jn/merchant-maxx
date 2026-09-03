from agents.maxx import sanitize_customer_text


def test_removes_catalog_item_id_from_parenthesized_product():
    text = "Mechanical Gaming Keyboard (ID: item_ABC123) — INR 5499"
    assert "item_ABC123" not in sanitize_customer_text(text)
    assert "Mechanical Gaming Keyboard" in sanitize_customer_text(text)
    assert "INR 5499" in sanitize_customer_text(text)


def test_removes_product_and_recommendation_ids():
    text = "Product ID: item_XYZ Rec ID: rec_123456"
    cleaned = sanitize_customer_text(text)
    assert "item_XYZ" not in cleaned
    assert "rec_123456" not in cleaned


def test_removes_purchase_intent_and_local_order_ids():
    text = "Intent pi_ABC123 created local order ord_XYZ789 with item oi_LINE456."
    cleaned = sanitize_customer_text(text)
    assert "pi_ABC123" not in cleaned
    assert "ord_XYZ789" not in cleaned
    assert "oi_LINE456" not in cleaned
    assert "created local order" in cleaned


def test_preserves_customer_safe_text_and_razorpay_order_id():
    text = "Your order is ready. Razorpay Order ID: order_Px123 Amount: Rs.8,999"
    cleaned = sanitize_customer_text(text)
    assert cleaned == text


def test_removes_bare_internal_ids():
    text = "Choose item_ABC or rec_DEF if you prefer."
    cleaned = sanitize_customer_text(text)
    assert "item_ABC" not in cleaned
    assert "rec_DEF" not in cleaned
    assert "Choose" in cleaned
