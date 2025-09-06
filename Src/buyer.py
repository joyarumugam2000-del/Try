from db import get_deal, update_deal

async def join_deal_buyer(user_id, deal_id):
    deal = get_deal(deal_id)
    if deal and str(user_id) == deal[2]:
        update_deal(deal_id, buyer_joined=1)
        return True
    return False
