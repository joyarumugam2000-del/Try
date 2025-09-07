from Src.db import get_deal, update_deal

async def join_deal_buyer(user_id: int, username: str, deal_id: str) -> bool:
    """
    Mark the buyer as joined in a deal.
    - Stores the numeric user_id for future kicks.
    - Still verifies that the username matches what was in the deal.
    """
    deal = get_deal(deal_id)
    if not deal:
        return False

    # Assuming deal[2] = buyer_username from when deal was created
    buyer_username = str(deal[2]).lstrip("@")

    if username.lstrip("@").lower() == buyer_username.lower():
        update_deal(
            deal_id,
            buyer_id=user_id,      # <-- new: store numeric ID
            buyer_joined=1
        )
        return True

    return False
