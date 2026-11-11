"""Validated commerce actions shared by HTTP endpoints and future agent tools.

All methods execute in the caller's SQL transaction. No network payment handoff.
"""
import hashlib
import json
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException
from sqlalchemy import select, update
from .domain_models import (Mission, MissionTask, MerchantOffer, Inventory, Order, OrderItem,
    Reservation, Approval, PaymentSession, PaymentEvent, AuditEvent, Idempotency, now)
from .models import Customer, Merchant
from .contracts import OrderOut, PaymentOut, MissionOut, OfferOut, ReservationOut, ApprovalOut
from .providers import provider
from .agents import REGISTRY

def fail(message, code=409):
    raise HTTPException(code, message)

def row(db, model, id):
    result = db.get(model, id)
    if result is None:
        fail(f'{model.__name__} not found', 404)
    return result

def dump(obj):
    return {column.name: getattr(obj, column.name) for column in obj.__table__.columns}

def audit(db, actor, action, inputs, outputs, mission_id=None, specialist='lucy', approval='NOT_REQUIRED', verification='RECORDED'):
    event = AuditEvent(actor=actor.key, specialist=specialist, mission_id=mission_id, action=action,
                       inputs=inputs, outputs=outputs, approval_state=approval, verification=verification)
    db.add(event)
    db.flush()
    return event

def replay(db, actor, key, action, inputs):
    row(db, Customer if actor.role == 'customer' else Merchant, actor.id)
    fingerprint = hashlib.sha256(json.dumps(inputs, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    previous = db.scalar(select(Idempotency).where(Idempotency.actor == actor.key, Idempotency.key == key))
    if previous:
        if previous.action != action or previous.fingerprint != fingerprint:
            fail('Idempotency key reused with different action or inputs')
        return previous.result
    return None

def mutate(db, actor, key, action, inputs, run, mission_id=None, specialist='lucy'):
    previous = replay(db, actor, key, action, inputs)
    if previous is not None:
        return previous
    fingerprint = hashlib.sha256(json.dumps(inputs, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    try:
        result = run()
        db.flush()
    except HTTPException as exc:
        # The request transaction rolls back first. get_db then records a safe
        # rejected attempt in a separate transaction, without partial commerce writes.
        exc.audit_failure = dict(actor=actor.key, specialist=specialist, mission_id=mission_id,
            action=action, inputs=inputs, outputs={'error': str(exc.detail), 'status_code': exc.status_code},
            approval_state='REJECTED', verification='REJECTED')
        raise
    approval = result.get('approval', {}).get('status', 'NOT_REQUIRED') if isinstance(result.get('approval'), dict) else result.get('approval_state', 'NOT_REQUIRED')
    order_id = result.get('order_id') or result.get('order', {}).get('id')
    if not order_id and result.get('status') in {'DRAFT','AWAITING_APPROVAL','CONFIRMED','FULFILLMENT_PENDING','FULFILLED'} and 'total_paise' in result:
        order_id = result.get('id')
    if order_id:
        decision = db.scalar(select(Approval).where(Approval.order_id == order_id))
        approval = decision.status if decision else 'REQUIRED'
    audit(db, actor, action, inputs, result, mission_id, specialist, approval,
          result.get('verification', 'RECORDED'))
    db.add(Idempotency(actor=actor.key, key=key, action=action, fingerprint=fingerprint, result=result))
    db.flush()
    return result

def expire_reservations(db):
    for reservation in db.scalars(select(Reservation).where(Reservation.status == 'ACTIVE', Reservation.expires_at <= now())):
        db.execute(update(Inventory).where(Inventory.offer_id == reservation.offer_id).values(available=Inventory.available + reservation.quantity))
        reservation.status = 'EXPIRED'
    db.flush()

def offer(db, id, actor=None):
    obj = row(db, MerchantOffer, id)
    if obj.expires_at <= now():
        fail('Offer quote expired')
    if not obj.terms.get('merchant_consent'):
        fail('Merchant consent missing', 403)
    if actor and actor.role == 'customer' and actor.id not in obj.terms.get('permitted_customer_ids', []):
        fail('Customer not eligible for this offer', 403)
    if obj.kind == 'SURPLUS' and (not obj.terms.get('merchant_attested') or obj.terms.get('eligible_until', '') <= now()):
        fail('Surplus eligibility expired or unattested')
    if obj.kind == 'RENTAL' and not obj.terms['window_start'] <= now() < obj.terms['window_end']:
        fail('Rental window unavailable')
    return obj

def offer_out(db, obj):
    stock = db.scalar(select(Inventory).where(Inventory.offer_id == obj.id))
    return OfferOut(**dump(obj), available=stock.available).model_dump()

def catalog(db, actor):
    expire_reservations(db)
    return [offer_out(db, o) for o in db.scalars(select(MerchantOffer).order_by(MerchantOffer.id))
            if o.expires_at > now() and (actor.role == 'merchant' and actor.id == o.merchant_id or actor.role == 'customer' and actor.id in o.terms.get('permitted_customer_ids', []))]

def get_order(db, actor, id):
    obj = row(db, Order, id)
    actor.record(obj)
    return obj

def order_out(db, obj):
    return OrderOut(**dump(obj), items=[dump(i) for i in db.scalars(select(OrderItem).where(OrderItem.order_id == obj.id))]).model_dump()

def create_order(db, actor, data):
    actor.customer()
    row(db, Merchant, data.merchant_id)
    mission = None
    if data.mission_id:
        mission = row(db, Mission, data.mission_id)
        actor.customer(mission.requester_id)
        if mission.status in {'COMPLETED','CANCELLED','FAILED'}:
            fail('Mission is terminal')
    if len({item.offer_id for item in data.items}) != len(data.items):
        fail('Duplicate order lines', 422)
    lines, total = [], 0
    for item in data.items:
        obj = offer(db, item.offer_id, actor)
        if obj.merchant_id != data.merchant_id:
            fail('Offer merchant mismatch', 422)
        if item.quantity < obj.terms.get('min_quantity', 1):
            fail('Quantity does not meet merchant threshold', 422)
        total += item.quantity * obj.price_paise
        lines.append((item, obj))
    if mission:
        committed = sum(o.total_paise for o in db.scalars(select(Order).where(Order.mission_id == mission.id, Order.status.not_in(['CANCELLED','FAILED']))))
        if total + committed > mission.budget_paise:
            fail('Mission spending budget exceeded', 403)
    order = Order(customer_id=actor.id, merchant_id=data.merchant_id, mission_id=data.mission_id, total_paise=total)
    db.add(order)
    db.flush()
    for item, obj in lines:
        db.add(OrderItem(order_id=order.id, offer_id=obj.id, quantity=item.quantity, unit_price_paise=obj.price_paise))
    db.flush()
    return order_out(db, order)

def reserve(db, actor, data):
    actor.customer()
    expire_reservations(db)
    order = get_order(db, actor, data.order_id)
    if order.status != 'DRAFT':
        fail('Only draft orders can reserve inventory')
    if db.scalar(select(Reservation).where(Reservation.order_id == order.id, Reservation.status == 'ACTIVE')):
        fail('Order already has active reservations')
    result = []
    for item in db.scalars(select(OrderItem).where(OrderItem.order_id == order.id)):
        obj = offer(db, item.offer_id, actor)
        changed = db.execute(update(Inventory).where(Inventory.offer_id == item.offer_id, Inventory.available >= item.quantity).values(available=Inventory.available - item.quantity))
        if changed.rowcount != 1:
            fail('Insufficient stock')
        expiry = min((datetime.now(timezone.utc) + timedelta(seconds=data.ttl_seconds)).isoformat(), obj.expires_at, obj.terms.get('eligible_until', obj.expires_at), obj.terms.get('window_end', obj.expires_at))
        r = Reservation(order_id=order.id, offer_id=item.offer_id, customer_id=actor.id, quantity=item.quantity, expires_at=expiry)
        db.add(r)
        db.flush()
        result.append(ReservationOut.model_validate(r).model_dump())
    return {'reservations': result}

def active_reservations(db, order):
    expire_reservations(db)
    items = list(db.scalars(select(OrderItem).where(OrderItem.order_id == order.id)))
    held = list(db.scalars(select(Reservation).where(Reservation.order_id == order.id, Reservation.status == 'ACTIVE')))
    if {(x.offer_id, x.quantity) for x in items} != {(x.offer_id, x.quantity) for x in held}:
        fail('Active inventory reservations required; reserve again or replan')
    return held

def request_approval(db, actor, data):
    actor.customer()
    order = get_order(db, actor, data.order_id)
    if order.status != 'DRAFT':
        fail('Order is not a draft')
    active_reservations(db, order)
    approval = db.scalar(select(Approval).where(Approval.order_id == order.id))
    if approval:
        fail('Approval already requested')
    approval = Approval(order_id=order.id, customer_id=actor.id, amount_paise=order.total_paise)
    db.add(approval)
    order.status = 'AWAITING_APPROVAL'
    db.flush()
    return {'approval': ApprovalOut.model_validate(approval).model_dump(), 'order': order_out(db, order)}

def decide_approval(db, actor, id, data):
    approval = row(db, Approval, id)
    actor.customer(approval.customer_id)
    if approval.status != 'REQUESTED':
        fail('Approval already decided')
    order = get_order(db, actor, approval.order_id)
    if order.status != 'AWAITING_APPROVAL':
        fail('Order is not awaiting approval')
    approval.status = 'APPROVED' if data.approve else 'REJECTED'
    approval.decided_at = now()
    if not data.approve:
        release_order(db, order)
        order.status = 'CANCELLED'
    return {'approval': ApprovalOut.model_validate(approval).model_dump(), 'order': order_out(db, order)}

def commit_order(db, actor, id):
    actor.customer()
    order = get_order(db, actor, id)
    if order.status != 'AWAITING_APPROVAL':
        fail('Order must await approval before confirmation')
    approval = db.scalar(select(Approval).where(Approval.order_id == id))
    if not approval or approval.status != 'APPROVED' or approval.amount_paise != order.total_paise:
        fail('Explicit customer approval required', 403)
    active_reservations(db, order)
    for item in db.scalars(select(OrderItem).where(OrderItem.order_id == id)):
        offer(db, item.offer_id, actor)
    if order.mission_id:
        mission = row(db, Mission, order.mission_id)
        if mission.deadline and mission.deadline <= now():
            fail('Mission deadline passed')
        if mission.status in {'COMPLETED','FAILED','CANCELLED'}:
            fail('Mission is terminal')
    order.status = 'CONFIRMED'
    return order_out(db, order)

def release_order(db, order):
    for r in db.scalars(select(Reservation).where(Reservation.order_id == order.id, Reservation.status == 'ACTIVE')):
        db.execute(update(Inventory).where(Inventory.offer_id == r.offer_id).values(available=Inventory.available + r.quantity))
        r.status = 'RELEASED'
    db.flush()

def cancel_order(db, actor, id):
    actor.customer()
    order = get_order(db, actor, id)
    if order.status not in {'DRAFT','AWAITING_APPROVAL','CONFIRMED'}:
        fail('Order cannot be cancelled in its current state')
    payment = db.scalar(select(PaymentSession).where(PaymentSession.order_id == id))
    if payment and payment.status == 'CONFIRMED':
        fail('Confirmed payment requires a future authorized refund workflow')
    if payment and payment.status == 'PENDING':
        transition_payment(db, actor, payment.id, 'CANCELLED', f'order-cancel-{id}')
    release_order(db, order)
    order.status = 'CANCELLED'
    return order_out(db, order)

def payment_event(db, payment, target, key):
    if db.scalar(select(PaymentEvent).where(PaymentEvent.event_key == key)):
        fail('Duplicate payment event')
    db.add(PaymentEvent(session_id=payment.id, event_key=key, from_status=payment.status, to_status=target))
    payment.status = target
    db.flush()

def create_payment(db, actor, data):
    actor.customer()
    row(db, Customer, actor.id)
    row(db, Merchant, data.merchant_id)
    if data.order_id:
        order = get_order(db, actor, data.order_id)
        if order.status != 'CONFIRMED' or order.merchant_id != data.merchant_id or order.total_paise != data.amount_paise or order.currency != data.currency:
            fail('Payment does not match a confirmed approved order', 422)
        active_reservations(db, order)
        if db.scalar(select(PaymentSession).where(PaymentSession.order_id == order.id)):
            fail('Order already has a payment session')
    payment = PaymentSession(customer_id=actor.id, merchant_id=data.merchant_id, order_id=data.order_id,
                             amount_paise=data.amount_paise, mode=provider.mode)
    db.add(payment)
    db.flush()
    payment_event(db, payment, 'INITIATED', f'{payment.id}:initiated')
    payment_event(db, payment, provider.initial_status(), f'{payment.id}:pending')
    return PaymentOut.model_validate(payment).model_dump()

def get_payment(db, actor, id):
    payment = row(db, PaymentSession, id)
    actor.record(payment)
    return PaymentOut.model_validate(payment).model_dump()

def transition_payment(db, actor, id, status, key):
    payment = row(db, PaymentSession, id)
    actor.customer(payment.customer_id)
    if payment.status != 'PENDING':
        fail('Payment must be pending; duplicate or invalid transition')
    if payment.mode != 'DEMO_SIMULATED':
        fail('Only demo sessions can be simulated', 403)
    provider.verify_event(status)
    if payment.order_id:
        order = get_order(db, actor, payment.order_id)
        if order.status != 'CONFIRMED':
            fail('Associated order is no longer confirmed')
        if status == 'CONFIRMED':
            reservations = active_reservations(db, order)
            for r in reservations:
                r.status = 'CONSUMED'
            order.status = 'FULFILLMENT_PENDING'
        else:
            release_order(db, order)
            order.status = 'FAILED' if status == 'FAILED' else 'CANCELLED'
    payment_event(db, payment, status, key)
    return PaymentOut.model_validate(payment).model_dump()

def fulfill_order(db, actor, id):
    order = row(db, Order, id)
    actor.merchant(order.merchant_id)
    if order.status != 'FULFILLMENT_PENDING':
        fail('Paid order required before fulfillment')
    order.status = 'FULFILLED'
    return order_out(db, order)

MISSION_TRANSITIONS = {
 'CREATED': {'PLANNING','CANCELLED'},
 'PLANNING': {'AWAITING_APPROVAL','EXECUTING','BLOCKED','FAILED','CANCELLED'},
 'AWAITING_APPROVAL': {'EXECUTING','REPLANNING','BLOCKED','CANCELLED'},
 'EXECUTING': {'REPLANNING','VERIFYING','BLOCKED','FAILED','CANCELLED'},
 'REPLANNING': {'PLANNING','AWAITING_APPROVAL','EXECUTING','BLOCKED','FAILED','CANCELLED'},
 'VERIFYING': {'COMPLETED','REPLANNING','BLOCKED','FAILED','CANCELLED'},
 'BLOCKED': {'REPLANNING','FAILED','CANCELLED'},
 'COMPLETED': set(), 'FAILED': set(), 'CANCELLED': set(),
}

def create_mission(db, actor, data):
    actor.customer()
    m = Mission(requester_id=actor.id, goal=data.goal, requirements=data.requirements, budget_paise=data.budget_paise,
                deadline=data.deadline.astimezone(timezone.utc).isoformat() if data.deadline else None,
                authorization_scope={'customer_id': actor.id, 'max_spend_paise': data.budget_paise, 'payment_mode': 'DEMO_SIMULATED', 'requires_order_approval': True})
    db.add(m)
    db.flush()
    return MissionOut.model_validate(m).model_dump(mode='json')

def get_mission(db, actor, id):
    m = row(db, Mission, id)
    actor.customer(m.requester_id)
    return m

def verify_outcome(db, actor, id):
    m = get_mission(db, actor, id)
    orders = list(db.scalars(select(Order).where(Order.mission_id == id, Order.status.not_in(['CANCELLED','FAILED']))))
    payments = list(db.scalars(select(PaymentSession).where(PaymentSession.order_id.in_([o.id for o in orders]))))
    # Requirements coverage is a deterministic list of product IDs, never an LLM assertion.
    required = m.requirements.get('products', [])
    quantities = {}
    for o in orders:
        for item in db.scalars(select(OrderItem).where(OrderItem.order_id == o.id)):
            product = row(db, MerchantOffer, item.offer_id).product_id
            quantities[product] = quantities.get(product, 0) + item.quantity
    coverage = all(quantities.get(r['product_id'], 0) >= r['quantity'] for r in required) if required else False
    deadline_met = not m.deadline or m.deadline > now()
    verified = deadline_met and bool(orders) and coverage and all(o.status == 'FULFILLED' for o in orders) and len(payments) == len(orders) and all(p.status == 'CONFIRMED' and p.mode == 'DEMO_SIMULATED' for p in payments) and sum(o.total_paise for o in orders) <= m.budget_paise
    return {'mission_id': id, 'verification': 'DEMO_OUTCOME_VERIFIED' if verified else 'INCOMPLETE',
            'verified': verified, 'requirements_covered': coverage, 'order_ids': [o.id for o in orders], 'payment_ids': [p.id for p in payments], 'externally_verified': False}

def transition_mission(db, actor, id, target):
    m = get_mission(db, actor, id)
    if target not in MISSION_TRANSITIONS[m.status]:
        fail(f'Invalid mission transition {m.status} -> {target}')
    if target == 'COMPLETED':
        evidence = verify_outcome(db, actor, id)
        if not evidence['verified']:
            fail('Outcome has not been verified')
        if any(t.status not in {'COMPLETED','CANCELLED'} for t in db.scalars(select(MissionTask).where(MissionTask.mission_id == id))):
            fail('Assigned mission tasks must be completed or explicitly cancelled')
        m.evidence_refs = evidence['order_ids'] + evidence['payment_ids']
    m.status = target
    return MissionOut.model_validate(m).model_dump(mode='json')

def create_task(db, actor, id, data):
    m = get_mission(db, actor, id)
    if m.status not in {'PLANNING','REPLANNING'}:
        fail('Task assignment requires planning state')
    agent = REGISTRY.get(data.agent_id)
    if not agent or data.task_type not in agent['accepted_task_types']:
        fail('Unsupported specialist task type', 422)
    for dependency in data.dependencies:
        if row(db, MissionTask, dependency).mission_id != id:
            fail('Dependency belongs to another mission', 403)
    task = MissionTask(mission_id=id, **data.model_dump())
    db.add(task)
    db.flush()
    return dump(task)

TASK_TRANSITIONS = {
    'CREATED': {'EXECUTING','BLOCKED','CANCELLED'},
    'EXECUTING': {'COMPLETED','BLOCKED','FAILED','CANCELLED'},
    'BLOCKED': {'EXECUTING','FAILED','CANCELLED'},
    'COMPLETED': set(), 'FAILED': set(), 'CANCELLED': set(),
}

def update_task(db, actor, id, data):
    task = row(db, MissionTask, id)
    mission = get_mission(db, actor, task.mission_id)
    if mission.status in {'COMPLETED','FAILED','CANCELLED'}:
        fail('Mission is terminal')
    if data.status not in TASK_TRANSITIONS[task.status]:
        fail('Invalid task transition')
    if data.status == 'EXECUTING':
        if REGISTRY[task.agent_id]['status'] == 'PLANNED':
            fail('Specialist implementation is planned', 403)
        if any(row(db, MissionTask, dep).status != 'COMPLETED' for dep in task.dependencies):
            fail('Task dependencies are incomplete')
    if data.status == 'COMPLETED' and not data.evidence_refs:
        fail('Task completion requires persisted evidence')
    for reference in data.evidence_refs:
        order = db.get(Order, reference)
        payment = db.get(PaymentSession, reference)
        if order:
            if order.mission_id != mission.id or order.status != 'FULFILLED':
                fail('Task evidence must be a fulfilled order in the current mission', 403)
        elif payment:
            if not payment.order_id or row(db, Order, payment.order_id).mission_id != mission.id or payment.status != 'CONFIRMED':
                fail('Task evidence must be a confirmed payment in the current mission', 403)
        else:
            fail('Evidence reference not found', 404)
    task.status = data.status
    task.evidence_refs = data.evidence_refs
    return dump(task)
