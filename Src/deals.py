"""
deals.py - formatting helpers for posts
"""

from .utils import shorten_username


def format_money(amount: float) -> str:
    try:
        return f"${amount:,.2f}"
    except Exception:
        return str(amount)


def format_form_preview(form_type: str, buyer: str, seller: str, amount: float, purpose: str, posted_by: str, created_at: str) -> str:
    return (
        f"Preview — {form_type}\n"
        f"BUYER: {buyer}\n"
        f"SELLER: {seller}\n"
        f"AMOUNT: {format_money(amount)}\n"
        f"Purpose: {purpose}\n"
        f"Posted by: @{posted_by} at {created_at}"
    )


def format_form_post(form_id: int, form_type: str, buyer: str, seller: str, amount: float, purpose: str, filler_username: str, created_at: str) -> str:
    return (
        f"✅ {form_type}\n"
        f"👤 BUYER: {buyer}\n"
        f"🔗 SELLER: {seller}\n"
        f"💰 AMOUNT: {format_money(amount)}\n"
        f"📝 Purpose: {purpose}\n"
        f"🧾 Form ID: {form_id} — posted by @{filler_username} at {created_at}"
    )


def format_deal_added(form_id: int, buyer: str, seller: str, amount: float, admin_username: str, deal_id: int, accepted_at: str) -> str:
    return (
        f"✅ DEAL ACCEPTED — Form ID {form_id}\n"
        f"👤 BUYER: {buyer}\n"
        f"🔗 SELLER: {seller}\n"
        f"💰 AMOUNT: {format_money(amount)}\n"
        f"🛡️ ACCEPTED BY: @{admin_username}\n"
        f"🆔 Deal ID: {deal_id} — at {accepted_at}"
    )


def format_deal_closed(form_id: int, buyer: str, seller: str, amount: float, admin_username: str, deal_id: int, closed_at: str) -> str:
    # Use shortened usernames to mimic your example like @T...x
    return (
        f"✅ ESCROW DONE ✅\n"
        f"👤 BUYER: {shorten_username(buyer)} 🔗 SELLER: {shorten_username(seller)} 💰 RELEASED AMOUNT: {format_money(amount)}\n"
        f"🛡️ RELEASED BY: @{admin_username} | ID: {deal_id} - {closed_at}"
    )
