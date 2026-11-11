from typing import Annotated
import os
import secrets
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select, delete
from sqlalchemy.orm import Session
from .database import get_db, HOSTED
from .policy import Actor, identity, idempotency_key
from . import contracts as c, services as s
from .domain_models import (Mission, MissionTask, Order, PaymentSession, PaymentEvent, AuditEvent, Approval,
    Reservation, OrderItem, Idempotency, DemoRedemption, Inventory, MerchantOffer)
from .agents import REGISTRY
from .fixtures import seed_operational

router = APIRouter()
DB = Annotated[Session, Depends(get_db)]
Identity = Annotated[Actor, Depends(identity)]
Key = Annotated[str, Depends(idempotency_key)]

@router.get('/agents')
def agents():
    return list(REGISTRY.values())

@router.get('/offers', response_model=list[c.OfferOut])
def offers(db: DB, actor: Identity):
    return s.catalog(db, actor)

@router.get('/offers/{id}', response_model=c.OfferOut)
def offer(id: str, db: DB, actor: Identity):
    s.expire_reservations(db)
    obj = s.offer(db, id, actor)
    if actor.role == 'merchant':
        actor.merchant(obj.merchant_id)
    return s.offer_out(db, obj)

@router.post('/orders', response_model=c.OrderOut)
def create_order(data: c.OrderIn, db: DB, actor: Identity, key: Key):
    return s.mutate(db, actor, key, 'create_order', data.model_dump(), lambda: s.create_order(db, actor, data), data.mission_id)

@router.get('/orders', response_model=list[c.OrderOut])
def orders(db: DB, actor: Identity):
    field = Order.customer_id if actor.role == 'customer' else Order.merchant_id
    return [s.order_out(db, o) for o in db.scalars(select(Order).where(field == actor.id).order_by(Order.created_at.desc()))]

@router.get('/orders/{id}', response_model=c.OrderOut)
def get_order(id: str, db: DB, actor: Identity):
    return s.order_out(db, s.get_order(db, actor, id))

@router.post('/reservations')
def reserve(data: c.ReserveIn, db: DB, actor: Identity, key: Key):
    order = s.get_order(db, actor, data.order_id)
    return s.mutate(db, actor, key, 'reserve_inventory', data.model_dump(), lambda: s.reserve(db, actor, data), order.mission_id)

@router.get('/orders/{id}/reservations', response_model=list[c.ReservationOut])
def reservations(id: str, db: DB, actor: Identity):
    s.get_order(db, actor, id)
    s.expire_reservations(db)
    return list(db.scalars(select(Reservation).where(Reservation.order_id == id)))

@router.post('/approvals')
def approval(data: c.OrderRef, db: DB, actor: Identity, key: Key):
    order = s.get_order(db, actor, data.order_id)
    return s.mutate(db, actor, key, 'request_approval', data.model_dump(), lambda: s.request_approval(db, actor, data), order.mission_id)

@router.post('/approvals/{id}/decision')
def decision(id: str, data: c.Decision, db: DB, actor: Identity, key: Key):
    approval = s.row(db, Approval, id)
    order = s.get_order(db, actor, approval.order_id)
    return s.mutate(db, actor, key, 'decide_approval', {'id': id, **data.model_dump()}, lambda: s.decide_approval(db, actor, id, data), order.mission_id)

@router.post('/orders/{id}/{action}', response_model=c.OrderOut)
def order_action(id: str, action: str, db: DB, actor: Identity, key: Key):
    order = s.get_order(db, actor, id)
    actions = {'confirm': s.commit_order, 'cancel': s.cancel_order, 'fulfill': s.fulfill_order}
    if action not in actions:
        raise HTTPException(404, 'Unknown order action')
    return s.mutate(db, actor, key, f'order_{action}', {'id': id}, lambda: actions[action](db, actor, id), order.mission_id)

@router.post('/payments', response_model=c.PaymentOut)
def create_payment(data: c.PaymentIn, db: DB, actor: Identity, key: Key):
    mission_id = s.get_order(db, actor, data.order_id).mission_id if data.order_id else None
    return s.mutate(db, actor, key, 'create_payment_session', data.model_dump(), lambda: s.create_payment(db, actor, data), mission_id)

@router.get('/payments', response_model=list[c.PaymentOut])
def payments(db: DB, actor: Identity):
    field = PaymentSession.customer_id if actor.role == 'customer' else PaymentSession.merchant_id
    return list(db.scalars(select(PaymentSession).where(field == actor.id).order_by(PaymentSession.created_at.desc())))

@router.get('/payments/{id}', response_model=c.PaymentOut)
def payment(id: str, db: DB, actor: Identity):
    return s.get_payment(db, actor, id)

@router.get('/payments/{id}/events')
def payment_events(id: str, db: DB, actor: Identity):
    s.get_payment(db, actor, id)
    return [s.dump(e) for e in db.scalars(select(PaymentEvent).where(PaymentEvent.session_id == id).order_by(PaymentEvent.created_at, PaymentEvent.id))]

@router.post('/payments/{id}/simulate', response_model=c.PaymentOut)
def simulate(id: str, data: c.PaymentTransition, db: DB, actor: Identity, key: Key):
    payment = s.get_payment(db, actor, id)
    mission_id = s.get_order(db, actor, payment['order_id']).mission_id if payment['order_id'] else None
    return s.mutate(db, actor, key, 'simulate_payment', {'id': id, **data.model_dump()}, lambda: s.transition_payment(db, actor, id, data.status, data.event_key), mission_id)

@router.post('/missions', response_model=c.MissionOut)
def mission(data: c.MissionIn, db: DB, actor: Identity, key: Key):
    result = s.mutate(db, actor, key, 'create_mission', data.model_dump(mode='json'), lambda: s.create_mission(db, actor, data))
    # Attach creation evidence to the newly allocated mission itself.
    event = db.scalar(select(AuditEvent).where(AuditEvent.action == 'create_mission', AuditEvent.actor == actor.key).order_by(AuditEvent.created_at.desc()))
    if event and event.outputs.get('id') == result['id']:
        event.mission_id = result['id']
    return result

@router.get('/missions', response_model=list[c.MissionOut])
def missions(db: DB, actor: Identity):
    actor.customer()
    return list(db.scalars(select(Mission).where(Mission.requester_id == actor.id).order_by(Mission.created_at.desc())))

@router.get('/missions/{id}', response_model=c.MissionOut)
def mission_status(id: str, db: DB, actor: Identity):
    return s.get_mission(db, actor, id)

@router.post('/missions/{id}/transition', response_model=c.MissionOut)
def mission_transition(id: str, data: c.MissionTransition, db: DB, actor: Identity, key: Key):
    return s.mutate(db, actor, key, 'mission_transition', {'id': id, **data.model_dump()}, lambda: s.transition_mission(db, actor, id, data.status), id)

@router.post('/missions/{id}/tasks')
def task(id: str, data: c.TaskIn, db: DB, actor: Identity, key: Key):
    return s.mutate(db, actor, key, 'assign_task', {'id': id, **data.model_dump()}, lambda: s.create_task(db, actor, id, data), id)

@router.post('/tasks/{id}/transition')
def task_progress(id: str, data: c.TaskProgress, db: DB, actor: Identity, key: Key):
    task = s.row(db, MissionTask, id)
    s.get_mission(db, actor, task.mission_id)
    return s.mutate(db, actor, key, 'task_transition', {'id': id, **data.model_dump()}, lambda: s.update_task(db, actor, id, data), task.mission_id)

@router.get('/missions/{id}/tasks')
def tasks(id: str, db: DB, actor: Identity):
    s.get_mission(db, actor, id)
    return [s.dump(t) for t in db.scalars(select(MissionTask).where(MissionTask.mission_id == id))]

@router.get('/missions/{id}/events')
def events(id: str, db: DB, actor: Identity, after: str = '', limit: int = 100):
    s.get_mission(db, actor, id)
    if limit < 1 or limit > 200:
        raise HTTPException(422, 'Limit must be 1..200')
    # Stable compound cursor: timestamp + UUID; no event is skipped on timestamp ties.
    query = select(AuditEvent).where(AuditEvent.mission_id == id)
    if after:
        cursor = s.row(db, AuditEvent, after)
        if cursor.mission_id != id:
            raise HTTPException(403, 'Cursor outside mission')
        query = query.where((AuditEvent.created_at > cursor.created_at) | ((AuditEvent.created_at == cursor.created_at) & (AuditEvent.id > cursor.id)))
    rows = list(db.scalars(query.order_by(AuditEvent.created_at, AuditEvent.id).limit(limit)))
    return {'events': [s.dump(e) for e in rows], 'next_cursor': rows[-1].id if rows else after}

class OfferRef(c.Contract):
    offer_id: str
class Empty(c.Contract):
    pass
class PaymentRef(c.Contract):
    payment_id: str

class ToolCall(c.Contract):
    mission_id: str
    specialist_id: str
    task_id: str | None = None
    inputs: dict = Field(default_factory=dict)

TOOL_SCHEMAS = {
 'search_catalog': Empty, 'check_inventory': OfferRef, 'get_offer': OfferRef,
 'reserve_inventory': c.ReserveIn, 'create_order': c.OrderIn,
 'get_order_status': c.OrderRef, 'create_payment_session': c.PaymentIn,
 'get_payment_status': PaymentRef,
 'request_approval': c.OrderRef, 'verify_outcome': Empty,
}

@router.get('/tools')
def tool_contracts():
    return [{'name': name, 'input_schema': schema.model_json_schema()} for name, schema in TOOL_SCHEMAS.items()]

@router.post('/tools/{name}')
def invoke_tool(name: str, call: ToolCall, db: DB, actor: Identity, key: Key):
    mission = s.get_mission(db, actor, call.mission_id)
    agent = REGISTRY.get(call.specialist_id)
    if not agent or agent['status'] == 'PLANNED' or name not in agent['permitted_tools']:
        raise HTTPException(403, 'Specialist capability is not implemented or permitted')
    assigned = list(db.scalars(select(MissionTask).where(MissionTask.mission_id == mission.id, MissionTask.agent_id == call.specialist_id)))
    if call.task_id:
        task = next((t for t in assigned if t.id == call.task_id), None)
    else:
        if len(assigned) > 1:
            raise HTTPException(422, 'Specify task_id when a specialist has multiple assignments')
        task = assigned[0] if assigned else None
    replay = s.replay(db, actor, key, f'tool:{name}', call.model_dump())
    if replay is not None:
        return replay
    if task and task.status in {'COMPLETED','FAILED','CANCELLED'}:
        raise HTTPException(409, 'Task is terminal')
    if not task:
        raise HTTPException(403, 'Specialist must have a persisted mission assignment')
    if task.dependencies:
        dependencies = [s.row(db, MissionTask, dep) for dep in task.dependencies]
        if any(dep.status != 'COMPLETED' for dep in dependencies):
            raise HTTPException(409, 'Task dependencies are incomplete')
    if mission.status not in {'PLANNING','EXECUTING','REPLANNING','VERIFYING'}:
        raise HTTPException(409, 'Mission does not permit tool execution in current state')
    if mission.deadline and mission.deadline <= s.now() and name in {'create_order','reserve_inventory','create_payment_session','request_approval'}:
        raise HTTPException(409, 'Mission deadline passed')
    if name not in TOOL_SCHEMAS:
        raise HTTPException(404, 'Unknown tool')
    try:
        data = TOOL_SCHEMAS[name].model_validate(call.inputs)
    except ValidationError as exc:
        raise HTTPException(422, exc.errors(include_context=False)) from exc
    if isinstance(data, c.OrderIn) and data.mission_id != mission.id:
        raise HTTPException(403, 'Order must reference current mission')
    if hasattr(data, 'order_id') and data.order_id:
        if s.get_order(db, actor, data.order_id).mission_id != mission.id:
            raise HTTPException(403, 'Order outside mission')
    if name == 'create_payment_session' and not data.order_id:
        raise HTTPException(403, 'Agent payment tools require an approved mission order')
    if name == 'get_payment_status':
        p = s.get_payment(db, actor, data.payment_id)
        if not p['order_id'] or s.get_order(db, actor, p['order_id']).mission_id != mission.id:
            raise HTTPException(403, 'Payment outside mission')
    operations = {
        'search_catalog': lambda: {'offers': s.catalog(db, actor)},
        'get_offer': lambda: s.offer_out(db, s.offer(db, data.offer_id, actor)),
        'check_inventory': lambda: s.offer_out(db, s.offer(db, data.offer_id, actor)),
        'create_order': lambda: s.create_order(db, actor, data),
        'reserve_inventory': lambda: s.reserve(db, actor, data),
        'get_order_status': lambda: s.order_out(db, s.get_order(db, actor, data.order_id)),
        'create_payment_session': lambda: s.create_payment(db, actor, data),
        'get_payment_status': lambda: s.get_payment(db, actor, data.payment_id),
        'request_approval': lambda: s.request_approval(db, actor, data),
        'verify_outcome': lambda: s.verify_outcome(db, actor, mission.id),
    }
    def run_tool():
        result = operations[name]()
        if name == 'verify_outcome' and result.get('verified'):
            task.status = 'COMPLETED'
            task.evidence_refs = result['order_ids'] + result['payment_ids']
        elif task.status == 'CREATED':
            task.status = 'EXECUTING'
        return result
    result = s.mutate(db, actor, key, f'tool:{name}', call.model_dump(), run_tool, mission.id, call.specialist_id)
    return result

@router.post('/reset-demo')
def reset(db: DB, x_reset_token: str = Header(default='')):
    if HOSTED or os.getenv('LUCY_ALLOW_RESET', 'true') != 'true':
        raise HTTPException(403, 'Developer reset is disabled')
    if not secrets.compare_digest(x_reset_token, os.getenv('LUCY_RESET_TOKEN', 'local-reset')):
        raise HTTPException(403, 'Developer reset token required')
    # Delete only operational records, in FK order. Historical snapshot and identities remain.
    for model in [Idempotency, AuditEvent, PaymentEvent, PaymentSession, Approval, Reservation, OrderItem, Order, MissionTask, Mission, DemoRedemption, Inventory, MerchantOffer]:
        db.execute(delete(model))
    from .app import DATA
    seed_operational(db, DATA)
    return {'ok': True, 'source': 'operational demo fixtures; historical ML unchanged'}
