"""Capability declarations, not claims of autonomous execution."""
SPECS = [
 ('missioncart','MissionCart','Procurement and order coordination',['procurement'],['search_catalog','check_inventory','get_offer','reserve_inventory','create_order','get_order_status','create_payment_session','get_payment_status','request_approval','verify_outcome'],'LIMITED'),
 ('swarmbuy','SwarmBuy','Consented collective purchasing',['group_purchase'],['search_catalog','get_offer'],'PLANNED'),
 ('shelflife','ShelfLife','Verified surplus matching',['surplus_match'],['search_catalog','get_offer','check_inventory'],'LIMITED'),
 ('rentright','RentRight','Rental versus purchase and reservations',['rental_compare'],['search_catalog','get_offer','check_inventory','reserve_inventory'],'LIMITED'),
 ('splitsettle','SplitSettle','Shared expense and payer-initiated tracking',['shared_expense'],['get_payment_status'],'PLANNED'),
 ('rebound-ai','Rebound AI','Consented checkout recovery',['checkout_recovery'],[],'PLANNED'),
 ('ghostpay','GhostPay','Payment/order discrepancy investigation',['payment_investigation'],['get_order_status','get_payment_status'],'PLANNED'),
 ('disputepilot','DisputePilot','Evidence and dispute case preparation',['dispute_evidence'],['get_order_status','get_payment_status'],'PLANNED'),
]
REGISTRY = {s[0]: dict(id=s[0], display_name=s[1], description=s[2], accepted_task_types=s[3], permitted_tools=s[4], status=s[5]) for s in SPECS}
