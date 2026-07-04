from database_utils.utils.email_templates import render_email


def test_render_confirmation_template_includes_link_and_name():
    html = render_email(
        "confirmation.html",
        user_name="Jane",
        confirmation_link="https://app.example.com/confirm-email?token=abc",
    )
    assert "Jane" in html
    assert "https://app.example.com/confirm-email?token=abc" in html


def test_render_password_reset_template():
    html = render_email(
        "password_reset.html",
        user_name="Jane",
        reset_link="https://app.example.com/reset-password?token=abc",
    )
    assert "https://app.example.com/reset-password?token=abc" in html


def test_render_payment_receipt_template():
    html = render_email(
        "payment_receipt.html",
        company_name="Acme Inc",
        invoice_number="INV-1",
        total_formatted="$99.00",
    )
    assert "Acme Inc" in html
    assert "INV-1" in html
    assert "$99.00" in html


def test_render_join_request_decision_approved():
    html = render_email(
        "join_request_decision.html",
        user_name="Jane",
        company_name="Acme Inc",
        approved=True,
    )
    assert "Acme Inc" in html
