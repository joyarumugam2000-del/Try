from db import get_deal, update_deal

async def join_deal_seller(user_id, deal_id):
    deal = get_deal(deal_id)
    if deal and str(user_id) == deal[1]:
        update_deal(deal_id, seller_joined=1)
        return True
    return False
