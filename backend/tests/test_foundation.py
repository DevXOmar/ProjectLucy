from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
import hashlib
import json
import subprocess
import sys
import os
from pathlib import Path
import pytest
from sqlalchemy import select
from backend.database import SessionLocal, engine
from backend.domain_models import Reservation, AuditEvent, MerchantOffer, Inventory

CUSTOMER = {'X-Demo-Role': 'customer', 'X-Demo-Id': '6'}
MERCHANT = {'X-Demo-Role': 'merchant', 'X-Demo-Id': '17'}

def post(client, path, body=None, actor=CUSTOMER, key=None, code=200):
    response = client.post(path, json=body, headers={**actor, 'Idempotency-Key': key or str(uuid4())})
    assert response.status_code == code, (path, response.status_code, response.text)
    return response.json()

def draft(client, offer='projector-rent', merchant=17, quantity=1, mission=None, **kw):
    return post(client, '/orders', {'merchant_id': merchant, 'mission_id': mission, 'items': [{'offer_id': offer, 'quantity': quantity}]}, **kw)

def approved_order(client, **kw):
    order = draft(client, **kw)
    post(client, '/reservations', {'order_id': order['id']})
    approval = post(client, '/approvals', {'order_id': order['id']})['approval']
    post(client, f"/approvals/{approval['id']}/decision", {'approve': True})
    return post(client, f"/orders/{order['id']}/confirm")

def payment(client, order=None, **kw):
    return post(client, '/payments', {'merchant_id': order['merchant_id'] if order else 17,
        'amount_paise': order['total_paise'] if order else 45000, 'currency': 'INR', 'order_id': order['id'] if order else None}, **kw)

def simulate(client, p, **kw):
    return post(client, f"/payments/{p['id']}/simulate", {'status':'CONFIRMED', 'event_key': str(uuid4())}, **kw)

def mission(client, budget=250000):
    return post(client, '/missions', {'goal':'Operation Movie Night', 'budget_paise': budget,
        'requirements': {'products':[{'product_id':'projector-rental-01','quantity':1},{'product_id':'snack-box','quantity':10},{'product_id':'drink-bottle','quantity':10}]}})

def transition(client, m, state, **kw):
    return post(client, f"/missions/{m['id']}/transition", {'status':state}, **kw)

def test_complete_movie_night_workflow(client):
    assert client.get('/customers/6').status_code == 200
    assert client.get('/merchants/17').status_code == 200
    assert len(client.get('/merchants').json()) == 24
    assert client.get('/offers/projector-rent', headers=CUSTOMER).json()['available'] == 1
    m = mission(client)
    transition(client, m, 'PLANNING')
    post(client, f"/missions/{m['id']}/tasks", {'agent_id':'missioncart','task_type':'procurement'})
    transition(client, m, 'EXECUTING')
    orders = [approved_order(client, mission=m['id']),
              approved_order(client, offer='snacks-surplus', merchant=1, quantity=10, mission=m['id']),
              approved_order(client, offer='drinks-ten', merchant=2, quantity=10, mission=m['id'])]
    assert sum(o['total_paise'] for o in orders) == 220000
    for order in orders:
        p = payment(client, order)
        assert p['status'] == 'PENDING' and p['mode'] == 'DEMO_SIMULATED' and p['externally_verified'] is False
        assert client.get(f"/orders/{order['id']}", headers=CUSTOMER).json()['status'] == 'CONFIRMED'
        p = simulate(client, p)
        assert p['status'] == 'CONFIRMED' and not p['externally_verified']
        assert client.get(f"/payments/{p['id']}", headers={'X-Demo-Role':'merchant','X-Demo-Id': str(order['merchant_id'])}).json()['status'] == 'CONFIRMED'
        assert client.get(f"/orders/{order['id']}",headers=CUSTOMER).json()['status'] == 'FULFILLMENT_PENDING'
        post(client, f"/orders/{order['id']}/fulfill", actor={'X-Demo-Role':'merchant','X-Demo-Id':str(order['merchant_id'])})
    transition(client, m, 'VERIFYING')
    result = post(client, '/tools/verify_outcome', {'mission_id':m['id'], 'specialist_id':'missioncart'})
    assert result['verification'] == 'DEMO_OUTCOME_VERIFIED' and result['verified'] and not result['externally_verified']
    tasks = client.get(f"/missions/{m['id']}/tasks",headers=CUSTOMER).json()
    assert tasks[0]['status'] == 'COMPLETED' and len(tasks[0]['evidence_refs']) == 6
    assert transition(client, m, 'COMPLETED')['status'] == 'COMPLETED'
    events = client.get(f"/missions/{m['id']}/events",headers=CUSTOMER).json()['events']
    assert any(e['specialist'] == 'missioncart' and e['verification'] == 'DEMO_OUTCOME_VERIFIED' for e in events)
    assert all(e['created_at'].endswith('+00:00') for e in events)
    assert len([t for t in client.get('/customers/6/transactions',headers=CUSTOMER).json() if t.get('provenance') == 'DEMO_SIMULATED']) == 3
    assert client.get('/customers/6/wallet',headers=CUSTOMER).json()['display_balance_paise'] == 530000


def test_payment_creation_never_implies_settlement(client):
    before = client.get('/customers/6/transactions',headers=CUSTOMER).json()
    points = client.get('/rewards/6/multiplier',headers=CUSTOMER).json()['points_balance']
    p = payment(client)
    assert client.get('/customers/6/transactions',headers=CUSTOMER).json() == before
    assert client.get('/rewards/6/multiplier',headers=CUSTOMER).json()['points_balance'] == points
    events = client.get(f"/payments/{p['id']}/events", headers=CUSTOMER).json()
    assert [(e['from_status'],e['to_status']) for e in events] == [('CREATED','INITIATED'),('INITIATED','PENDING')]
    assert all(e['provenance'] == 'DEMO_SIMULATED' for e in events)
    confirmed = simulate(client, p)
    assert confirmed['externally_verified'] is False
    assert client.get('/rewards/6/multiplier',headers=CUSTOMER).json()['points_balance'] == points + 45
    assert client.get('/customers/6/wallet',headers=CUSTOMER).json()['display_balance_paise'] == 705000
    assert any(t['id'] == p['id'] for t in client.get('/merchants/17/transactions',headers=MERCHANT).json())


def test_idempotency_and_duplicate_confirmation(client):
    key = str(uuid4())
    o = draft(client, key=key)
    assert draft(client, key=key)['id'] == o['id']
    draft(client, quantity=2, key=key, code=409)
    key = str(uuid4())
    p = payment(client, key=key)
    assert payment(client, key=key)['id'] == p['id']
    payload = {'status':'CONFIRMED', 'event_key':'demo-event-unique'}
    key = str(uuid4())
    confirmed = post(client, f"/payments/{p['id']}/simulate", payload, key=key)
    assert post(client, f"/payments/{p['id']}/simulate", payload, key=key) == confirmed
    post(client, f"/payments/{p['id']}/simulate", payload, code=409)
    p2 = payment(client)
    post(client, f"/payments/{p2['id']}/simulate", payload, code=409)
    assert client.get(f"/payments/{p2['id']}", headers=CUSTOMER).json()['status'] == 'PENDING'
    assert len([t for t in client.get('/customers/6/transactions',headers=CUSTOMER).json() if t.get('provenance')]) == 1


def test_competing_last_unit_reservations_are_atomic(client):
    orders = [draft(client), draft(client, actor={'X-Demo-Role':'customer','X-Demo-Id':'7'})]
    def reserve(index):
        return client.post('/reservations', json={'order_id':orders[index]['id']}, headers={**CUSTOMER,'X-Demo-Id':str(6+index),'Idempotency-Key':str(uuid4())}).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(reserve, [0,1])) == [200,409]
    assert client.get('/offers/projector-rent',headers=CUSTOMER).json()['available'] == 0


def test_reservation_expiry_and_release(client):
    o = draft(client)
    post(client, '/reservations', {'order_id':o['id']})
    with SessionLocal.begin() as db:
        r = db.scalar(select(Reservation).where(Reservation.order_id == o['id']))
        r.expires_at = '2020-01-01T00:00:00+00:00'
    assert client.get('/offers/projector-rent',headers=CUSTOMER).json()['available'] == 1
    assert client.get(f"/orders/{o['id']}/reservations",headers=CUSTOMER).json()[0]['status'] == 'EXPIRED'
    post(client, '/reservations', {'order_id':o['id']})
    post(client, f"/orders/{o['id']}/cancel")
    assert client.get('/offers/projector-rent',headers=CUSTOMER).json()['available'] == 1


def test_approval_required_before_commitment(client):
    o = draft(client)
    post(client, f"/orders/{o['id']}/confirm", code=409)
    post(client, '/approvals', {'order_id':o['id']}, code=409)
    post(client, '/reservations', {'order_id':o['id']})
    a = post(client, '/approvals', {'order_id':o['id']})['approval']
    post(client, f"/orders/{o['id']}/confirm", code=403)
    post(client, f"/approvals/{a['id']}/decision", {'approve':True}, actor=MERCHANT, code=403)
    post(client, f"/approvals/{a['id']}/decision", {'approve':True})
    post(client, f"/orders/{o['id']}/confirm")


@pytest.mark.parametrize('body', [
    {'merchant_id':17,'amount_paise':0}, {'merchant_id':17,'amount_paise':-5},
    {'merchant_id':17,'amount_paise':12.5}, {'merchant_id':17,'amount_paise':True},
    {'merchant_id':17,'amount_paise':100,'currency':'USD'},
    {'merchant_id':17,'amount_paise':100,'customer_id':7},
])
def test_invalid_payment_contracts(client, body):
    post(client, '/payments', body, code=422)


def test_identity_and_merchant_permissions(client):
    assert client.post('/payments',json={'merchant_id':17,'amount_paise':100},headers={'Idempotency-Key':str(uuid4())}).status_code == 401
    payment(client, actor=MERCHANT, code=403)
    o = draft(client)
    assert client.get(f"/orders/{o['id']}",headers={**CUSTOMER,'X-Demo-Id':'7'}).status_code == 403
    assert client.get(f"/orders/{o['id']}",headers={**MERCHANT,'X-Demo-Id':'1'}).status_code == 403
    draft(client, actor={**CUSTOMER,'X-Demo-Id':'8'}, code=403)
    payment(client, actor={**CUSTOMER,'X-Demo-Id':'99999'},code=404)
    post(client, '/merchant/1/pricing/actions', {'sku':'unknown'}, actor=MERCHANT, code=403)


def test_offer_terms_budget_and_payment_references(client):
    draft(client, offer='drinks-ten', merchant=2, quantity=9, code=422)
    draft(client, offer='snacks-surplus', merchant=17, code=422)
    m = mission(client, budget=80000)
    draft(client, mission=m['id'], code=403)
    with SessionLocal.begin() as db:
        db.get(MerchantOffer, 'projector-rent').expires_at = '2020-01-01T00:00:00+00:00'
    assert client.get('/offers/projector-rent',headers=CUSTOMER).status_code == 409
    draft(client, code=409)


def test_order_linked_payment_mismatch_and_expiry(client):
    o = approved_order(client)
    post(client, '/payments', {'merchant_id':17,'amount_paise':1,'order_id':o['id']}, code=422)
    post(client, '/payments', {'merchant_id':1,'amount_paise':o['total_paise'],'order_id':o['id']}, code=422)
    p = payment(client, o)
    payment(client, o, code=409)
    with SessionLocal.begin() as db:
        db.scalar(select(Reservation).where(Reservation.order_id == o['id'])).expires_at = '2020-01-01T00:00:00+00:00'
    simulate(client, p, code=409)
    assert client.get(f"/payments/{p['id']}",headers=CUSTOMER).json()['status'] == 'PENDING'


@pytest.mark.parametrize('status', ['FAILED','CANCELLED'])
def test_failed_and_cancelled_payment_release_inventory(client, status):
    o = approved_order(client)
    p = payment(client, o)
    post(client, f"/payments/{p['id']}/simulate", {'status':status,'event_key':str(uuid4())})
    assert client.get('/offers/projector-rent',headers=CUSTOMER).json()['available'] == 1
    assert client.get(f"/orders/{o['id']}",headers=CUSTOMER).json()['status'] == status
    assert not any(t.get('provenance') for t in client.get('/customers/6/transactions',headers=CUSTOMER).json())


def test_reset_is_guarded_deterministic_and_preserves_snapshot(client):
    path = Path('backend/data/precomputed.json')
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    simulate(client, payment(client))
    assert client.post('/reset-demo').status_code == 403
    assert client.post('/reset-demo',headers={'X-Reset-Token':'test-reset-token'}).status_code == 200
    assert client.get('/payments',headers=CUSTOMER).json() == []
    assert client.get('/customers/6/wallet',headers=CUSTOMER).json()['display_balance_paise'] == 750000
    assert client.get('/offers/projector-rent',headers=CUSTOMER).json()['available'] == 1
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before
    assert len(client.get('/merchants').json()) == 24


def test_upi_is_preview_only(client):
    result = client.get('/merchants/17/upi-intent?amount=450').json()
    assert result['liveHandoffAllowed'] is False and result['previewOnly'] is True
    assert result['recipientProvenance'] == 'SYNTHETIC'
    assert result['paytmIntent'].startswith('paytmmp://pay?')


def test_registry_policy_tools_and_event_polling(client):
    agents = client.get('/agents').json()
    assert len(agents) == 8 and not any(a['status'] == 'WORKING' for a in agents)
    assert len(client.get('/tools').json()) == 10
    m = mission(client)
    transition(client,m,'COMPLETED',code=409)
    transition(client,m,'PLANNING')
    call = {'mission_id':m['id'],'specialist_id':'missioncart','inputs':{}}
    post(client, '/tools/search_catalog',call,code=403)
    post(client, f"/missions/{m['id']}/tasks",{'agent_id':'missioncart','task_type':'procurement'})
    assert len(post(client, '/tools/search_catalog',call)['offers']) == 4
    post(client, '/tools/search_catalog',{**call,'specialist_id':'swarmbuy'},code=403)
    post(client, '/tools/create_payment_session',{**call,'inputs':{'merchant_id':17,'amount_paise':100}},code=403)
    post(client, '/tools/create_order',{**call,'inputs':{'merchant_id':17,'items':[{'offer_id':'projector-rent','quantity':1}]}},code=403)
    post(client, '/tools/create_order',{**call,'inputs':{'merchant_id':17,'mission_id':m['id'],'items':[{'offer_id':'projector-rent','quantity':1}]}})
    page1 = client.get(f"/missions/{m['id']}/events?limit=2",headers=CUSTOMER).json()
    page2 = client.get(f"/missions/{m['id']}/events", params={'after':page1['next_cursor']},headers=CUSTOMER).json()
    assert not {e['id'] for e in page1['events']} & {e['id'] for e in page2['events']}
    transition(client,m,'EXECUTING')
    transition(client,m,'VERIFYING')
    transition(client,m,'COMPLETED',code=409)


def test_persistence_across_process_restart(client):
    p = payment(client)
    # A fresh interpreter initializes the app against the same configured SQL store.
    script = f'''from fastapi.testclient import TestClient
from backend.app import app
with TestClient(app) as c:
    print(c.get('/payments/{p['id']}',headers={{'X-Demo-Role':'customer','X-Demo-Id':'6'}}).json()['status'])
'''
    result = subprocess.run([sys.executable,'-c',script],capture_output=True,text=True,check=True)
    assert result.stdout.strip() == 'PENDING'


def test_hosted_sqlite_is_rejected():
    env = {**os.environ,'VERCEL':'1','DATABASE_URL':'sqlite:////tmp/lucy-forbidden.db'}
    result = subprocess.run([sys.executable,'-c','import backend.database'],env=env,capture_output=True,text=True)
    assert result.returncode != 0 and 'requires durable PostgreSQL' in result.stderr


def test_expired_mission_read_and_invalid_requirements(client):
    from backend.domain_models import Mission
    m = mission(client)
    with SessionLocal.begin() as db:
        db.get(Mission,m['id']).deadline = '2020-01-01T00:00:00+00:00'
    assert client.get(f"/missions/{m['id']}",headers=CUSTOMER).status_code == 200
    post(client,'/missions',{'goal':'Movie night','budget_paise':100,'requirements':{'products':[{'quantity':'ten'}]}},code=422)
    post(client,'/missions',{'goal':'Movie night','budget_paise':100,'deadline':'2020-01-01T00:00:00Z'},code=422)


def test_rejected_action_ledger_and_approval_provenance(client):
    m = mission(client)
    o = draft(client,mission=m['id'])
    post(client, f"/orders/{o['id']}/confirm",code=409)
    events = client.get(f"/missions/{m['id']}/events",headers=CUSTOMER).json()['events']
    assert any(e['verification'] == 'REJECTED' for e in events)
    post(client,'/reservations',{'order_id':o['id']})
    a = post(client,'/approvals',{'order_id':o['id']})['approval']
    post(client,f"/approvals/{a['id']}/decision",{'approve':True})
    post(client,f"/orders/{o['id']}/confirm")
    events = client.get(f"/missions/{m['id']}/events",headers=CUSTOMER).json()['events']
    assert next(e for e in events if e['action'] == 'order_confirm' and e['verification'] == 'RECORDED')['approval_state'] == 'APPROVED'


def test_task_progress_requires_scoped_evidence(client):
    m = mission(client)
    transition(client,m,'PLANNING')
    first = post(client,f"/missions/{m['id']}/tasks",{'agent_id':'missioncart','task_type':'procurement'})
    next_task = post(client,f"/missions/{m['id']}/tasks",{'agent_id':'rentright','task_type':'rental_compare','dependencies':[first['id']]})
    post(client,f"/tasks/{next_task['id']}/transition",{'status':'EXECUTING'},code=409)
    post(client,f"/tasks/{first['id']}/transition",{'status':'EXECUTING'})
    post(client,f"/tasks/{first['id']}/transition",{'status':'COMPLETED'},code=409)
    o = approved_order(client,mission=m['id'])
    simulate(client,payment(client,o))
    post(client,f"/orders/{o['id']}/fulfill",actor=MERCHANT)
    post(client,f"/tasks/{first['id']}/transition",{'status':'COMPLETED','evidence_refs':[o['id']]})
    assert post(client,f"/tasks/{next_task['id']}/transition",{'status':'EXECUTING'})['status'] == 'EXECUTING'
    post(client,f"/tasks/{first['id']}/transition",{'status':'EXECUTING'},code=409)



def test_replanning_blocking_failure_and_cancellation(client):
    m = mission(client)
    for state in ['PLANNING','AWAITING_APPROVAL','REPLANNING','EXECUTING','BLOCKED','REPLANNING','PLANNING','EXECUTING','FAILED']:
        assert transition(client,m,state)['status'] == state
    transition(client,m,'PLANNING',code=409)
    other = mission(client)
    assert transition(client,other,'CANCELLED')['status'] == 'CANCELLED'
    transition(client,other,'PLANNING',code=409)


def test_standalone_entrypoint_import_and_history_rebuild_guard(client):
    script = "import sys; sys.path.insert(0,'backend'); import app; print(app.app.title)"
    result = subprocess.run([sys.executable,'-c',script],capture_output=True,text=True,check=True)
    assert result.stdout.strip() == 'Project Lucy API'
    from backend.seed import reset_db
    with pytest.raises(RuntimeError, match='separate SQLite'):
        reset_db()
    assert client.get('/health').status_code == 200


def test_multiline_reservation_failure_rolls_back_every_line(client):
    o = post(client,'/orders',{'merchant_id':17,'items':[{'offer_id':'projector-buy','quantity':1},{'offer_id':'projector-rent','quantity':1}]})
    with SessionLocal.begin() as db:
        db.scalar(select(Inventory).where(Inventory.offer_id == 'projector-rent')).available = 0
    post(client,'/reservations',{'order_id':o['id']},code=409)
    assert client.get('/offers/projector-buy',headers=CUSTOMER).json()['available'] == 2
    assert client.get(f"/orders/{o['id']}/reservations",headers=CUSTOMER).json() == []


def test_order_cancellation_cancels_pending_payment_and_releases_hold(client):
    o = approved_order(client)
    p = payment(client,o)
    post(client,f"/orders/{o['id']}/cancel")
    assert client.get(f"/payments/{p['id']}",headers=CUSTOMER).json()['status'] == 'CANCELLED'
    assert client.get('/offers/projector-rent',headers=CUSTOMER).json()['available'] == 1
    simulate(client,p,code=409)


def test_paid_order_cannot_be_silently_cancelled(client):
    o = approved_order(client)
    simulate(client,payment(client,o))
    post(client,f"/orders/{o['id']}/cancel",code=409)
    assert client.get('/offers/projector-rent',headers=CUSTOMER).json()['available'] == 0


def test_pricing_actions_and_reward_redemption_are_durable_and_scoped(client):
    merchant = {'X-Demo-Role':'merchant','X-Demo-Id':'1'}
    sku = client.get('/merchant/1/pricing').json()[0]['sku']
    key = str(uuid4())
    post(client,'/merchant/1/pricing/actions',{'sku':sku},actor=merchant,key=key)
    post(client,'/merchant/1/pricing/actions',{'sku':sku},actor=merchant,key=key)
    assert len(client.get('/merchant/1/pricing/actions',headers=merchant).json()) == 1
    before = client.get('/rewards/6/multiplier',headers=CUSTOMER).json()['points_balance']
    key = str(uuid4())
    post(client,'/rewards/6/redeem',{'offer':'Demo token','points':90},key=key)
    post(client,'/rewards/6/redeem',{'offer':'Demo token','points':90},key=key)
    assert client.get('/rewards/6/multiplier',headers=CUSTOMER).json()['points_balance'] == before - 90
    post(client,'/rewards/7/redeem',{'offer':'Demo token','points':1},code=403)
    assert client.get('/customers/7/wallet',headers=CUSTOMER).status_code == 403


def test_deadline_is_normalized_to_utc(client):
    from datetime import datetime, timedelta, timezone
    deadline = datetime.now(timezone(timedelta(hours=5,minutes=30))) + timedelta(hours=2)
    m = post(client,'/missions',{'goal':'Movie Night','budget_paise':250000,'deadline':deadline.isoformat()})
    assert m['deadline'].endswith('+00:00')
    assert datetime.fromisoformat(m['deadline']) == deadline
