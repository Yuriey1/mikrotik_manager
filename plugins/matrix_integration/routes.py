"""API-эндпоинты для Matrix-интеграции"""

import logging
import services.state as state

log = logging.getLogger(__name__)


def handle_get_pending(handler, parsed):
    """GET /api/matrix/pending — список ожидающих заявок"""
    handler._send_json({
        'success': True,
        'requests': list(state.pending_requests),
        'count': len(state.pending_requests),
    })


def handle_confirm(handler, data):
    """POST /api/matrix/confirm — подтвердить и удалить заявку"""
    pending_id = data.get('pending_id', '').strip()
    if not pending_id:
        handler._send_json({'error': 'Укажите pending_id'}, 400)
        return

    before = len(state.pending_requests)
    state.pending_requests = [r for r in state.pending_requests if r['id'] != pending_id]
    removed = before - len(state.pending_requests)

    handler._send_json({
        'success': True,
        'removed': removed,
        'message': f'Заявка подтверждена и удалена ({removed} шт.)',
    })


def handle_reject(handler, data):
    """POST /api/matrix/reject — отклонить и удалить заявку"""
    pending_id = data.get('pending_id', '').strip()
    if not pending_id:
        handler._send_json({'error': 'Укажите pending_id'}, 400)
        return

    before = len(state.pending_requests)
    state.pending_requests = [r for r in state.pending_requests if r['id'] != pending_id]
    removed = before - len(state.pending_requests)

    handler._send_json({
        'success': True,
        'removed': removed,
        'message': f'Заявка отклонена и удалена ({removed} шт.)',
    })


def register_routes(get_routes, post_routes, delete_routes):
    """Зарегистрировать роуты в web_service"""
    get_routes['/api/matrix/pending'] = handle_get_pending
    post_routes['/api/matrix/confirm'] = handle_confirm
    post_routes['/api/matrix/reject'] = handle_reject
