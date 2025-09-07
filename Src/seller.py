from Src.db import get_deal, update_deal

async def join_deal_seller(user_id: int, username: str, deal_id: str) -> bool:
    """
    Mark the seller as joined in a deal.
    - Stores the numeric user_id for future kicks.
    - Still verifies that the username matches what was in the deal.
    """
    deal = get_deal(deal_id)
    if not deal:
        return False

    # Assuming deal[1] = seller_username from when deal was created
    seller_username = str(deal[1]).lstrip("@")

    if username.lstrip("@").lower() == seller_username.lower():
        update_deal(
            deal_id,
            seller_id=user_id,     # <-- new: store numeric ID
            seller_joined=1
        )
        return True

    return False
