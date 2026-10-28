"""Regression coverage for claim custody lifecycle, archives, public privacy and sessions."""
from io import BytesIO

from PIL import Image


def assert_code(response, expected):
    assert response.status_code == expected, f'expected {expected}, got {response.status_code}: {response.text}'


def test_register_rotates_csrf_and_next_mutation_succeeds(scenario):
    student = scenario['client']()
    initial_csrf = student.get('/api/v1/auth/csrf').json()['csrf_token']
    scenario['auth'](student, 'first@example.com')
    stale = student.post('/api/v1/reports', headers={'X-CSRF-Token': initial_csrf}, json=scenario['report']('lost'))
    assert_code(stale, 403)
    response = scenario['write'](student, 'POST', '/api/v1/reports', json=scenario['report']('lost'))
    assert_code(response, 201)
    assert response.json()['is_owner'] is True
    assert response.json()['private_details'] == 'Serial number ends in 1934'


def test_public_browse_minimizes_data_and_hides_archived(scenario):
    first, second = scenario['client'](), scenario['client']()
    scenario['auth'](first, 'a@example.com')
    scenario['auth'](second, 'b@example.com')
    item = scenario['write'](first, 'POST', '/api/v1/reports', json=scenario['report']('lost')).json()
    public = scenario['client']().get('/api/v1/reports/public')
    assert_code(public, 200)
    assert public.json()['total'] == 1
    assert 'private_details' not in public.json()['items'][0]
    assert 'reporter' not in public.json()['items'][0]
    assert public.json()['items'][0]['images'] == []
    assert_code(scenario['write'](first, 'DELETE', f"/api/v1/reports/{item['id']}"), 204)
    assert scenario['client']().get('/api/v1/reports/public').json()['total'] == 0
    listing = second.get('/api/v1/reports?status=archived')
    assert_code(listing, 200)
    assert listing.json()['items'] == []
    assert listing.json()['total'] == 0
    assert_code(second.get(f"/api/v1/reports/{item['id']}"), 404)
    owner = first.get('/api/v1/reports?status=archived')
    assert owner.json()['total'] == 1
    assert owner.json()['items'][0]['id'] == item['id']


def test_required_report_fields_reject_whitespace_on_create_and_update(scenario):
    student = scenario['client']()
    scenario['auth'](student, 'a@example.com')
    for data in ({'item_name': '          '}, {'description': '                   '}):
        assert_code(scenario['write'](student, 'POST', '/api/v1/reports', json=scenario['report']('lost', **data)), 422)
    report = scenario['write'](student, 'POST', '/api/v1/reports', json=scenario['report']('lost')).json()
    for patch in ({'item_name': '     '}, {'description': '              '}, {'item_name': None}):
        assert_code(scenario['write'](student, 'PATCH', f"/api/v1/reports/{report['id']}", json=patch), 422)
    trimmed = scenario['write'](student, 'PATCH', f"/api/v1/reports/{report['id']}", json={'item_name': '  Blue earbuds  '})
    assert_code(trimmed, 200)
    assert trimmed.json()['item_name'] == 'Blue earbuds'


def test_claim_and_staff_verified_handover_with_privacy(scenario):
    owner, finder, staff, stranger = [scenario['client']() for _ in range(4)]
    scenario['auth'](owner, 'owner@example.com')
    scenario['auth'](finder, 'finder@example.com')
    scenario['staff'](staff)
    scenario['auth'](stranger, 'stranger@example.com')
    lost = scenario['write'](owner, 'POST', '/api/v1/reports', json=scenario['report']('lost')).json()
    found = scenario['write'](finder, 'POST', '/api/v1/reports', json=scenario['report']('found')).json()
    suggestions = owner.get(f"/api/v1/reports/{lost['id']}/matches")
    assert_code(suggestions, 200)
    assert any(candidate['report']['id'] == found['id'] for candidate in suggestions.json()['items'])
    assert stranger.get(f"/api/v1/reports/{found['id']}").json()['private_details'] is None
    assert_code(scenario['write'](finder, 'POST', f"/api/v1/reports/{found['id']}/claims", json={'proof_text': 'I can describe the serial number and case.'}), 409)
    claim_response = scenario['write'](owner, 'POST', f"/api/v1/reports/{found['id']}/claims", json={'proof_text': 'I own this item, serial ends 1934, black case.', 'lost_report_id': lost['id']})
    assert_code(claim_response, 201)
    claim = claim_response.json()
    assert_code(stranger.get(f"/api/v1/claims/{claim['id']}"), 403)
    assert_code(scenario['write'](owner, 'POST', f"/api/v1/reports/{found['id']}/claims", json={'proof_text': 'Duplicate claim must be rejected.'}), 409)

    buffer = BytesIO()
    Image.new('RGB', (8, 8), color='blue').save(buffer, format='PNG')
    buffer.seek(0)
    evidence = scenario['write'](owner, 'POST', f"/api/v1/claims/{claim['id']}/evidence", files={'file': ('proof.png', buffer, 'image/png')})
    assert_code(evidence, 201)
    assert_code(stranger.get(evidence.json()['url']), 403)
    assert_code(staff.get(evidence.json()['url']), 200)

    custody = scenario['write'](staff, 'POST', '/api/v1/staff/custody', json={'report_id': found['id'], 'storage_location': 'Security locker A'})
    assert_code(custody, 201)
    assert_code(scenario['write'](owner, 'PATCH', f"/api/v1/staff/claims/{claim['id']}/status", json={'status': 'under_review'}), 403)
    assert_code(scenario['write'](staff, 'PATCH', f"/api/v1/staff/claims/{claim['id']}/status", json={'status': 'under_review'}), 200)
    assert_code(scenario['write'](staff, 'PATCH', f"/api/v1/staff/claims/{claim['id']}/status", json={'status': 'approved'}), 200)
    handover = scenario['write'](staff, 'POST', f"/api/v1/staff/claims/{claim['id']}/handover", json={'notes': 'Owner verified in person'})
    assert_code(handover, 200)
    assert_code(scenario['write'](staff, 'POST', f"/api/v1/staff/claims/{claim['id']}/handover", json={}), 409)
    assert_code(scenario['write'](owner, 'PATCH', f"/api/v1/reports/{lost['id']}", json={'item_name': 'Updated name'}), 409)
    assert owner.get(f"/api/v1/reports/{lost['id']}").json()['status'] == 'returned'
    assert finder.get(f"/api/v1/reports/{found['id']}").json()['status'] == 'returned'
    notifications = owner.get('/api/v1/notifications').json()['items']
    assert any(item['kind'] == 'handover_completed' and item['link'] == f"/app/claims/{claim['id']}" for item in notifications)
    assert all(item['link'] is None or item['link'].startswith(('/app/', '/staff/')) for item in notifications)
    with scenario['session']() as db:
        from sqlalchemy import select
        from app.models import AuditEvent
        assert db.scalar(select(AuditEvent).where(AuditEvent.action == 'handover.completed')) is not None


def test_claim_proof_and_custody_location_reject_whitespace(scenario):
    claimant, finder, staff = [scenario['client']() for _ in range(3)]
    scenario['auth'](claimant, 'claimant@example.com')
    scenario['auth'](finder, 'finder@example.com')
    scenario['staff'](staff)
    found = scenario['write'](finder, 'POST', '/api/v1/reports', json=scenario['report']('found')).json()
    claim = scenario['write'](claimant, 'POST', f"/api/v1/reports/{found['id']}/claims", json={'proof_text': ' ' * 35})
    assert_code(claim, 422)
    invalid_location = scenario['write'](staff, 'POST', '/api/v1/staff/custody', json={
        'report_id': found['id'], 'storage_location': '      '
    })
    assert_code(invalid_location, 422)
    assert_code(scenario['write'](staff, 'POST', '/api/v1/staff/custody', json={
        'report_id': found['id'], 'storage_location': '  Locker B  '
    }), 201)


def test_session_expired_after_logout_and_csrf_rejected(scenario):
    student = scenario['client']()
    scenario['auth'](student, 'student@example.com')
    assert_code(student.get('/api/v1/auth/me'), 200)
    assert_code(scenario['write'](student, 'POST', '/api/v1/auth/logout'), 204)
    assert_code(student.get('/api/v1/auth/me'), 401)
    assert_code(student.post('/api/v1/reports', json=scenario['report']('lost')), 401)


def test_claim_review_requires_staff_and_valid_transitions(scenario):
    owner, finder, staff = [scenario['client']() for _ in range(3)]
    scenario['auth'](owner, 'owner@example.com')
    scenario['auth'](finder, 'finder@example.com')
    scenario['staff'](staff)
    found = scenario['write'](finder, 'POST', '/api/v1/reports', json=scenario['report']('found')).json()
    claim = scenario['write'](owner, 'POST', f"/api/v1/reports/{found['id']}/claims", json={
        'proof_text': 'I have the case and a warranty receipt.'
    }).json()
    url = f"/api/v1/staff/claims/{claim['id']}/status"
    assert_code(scenario['write'](staff, 'PATCH', url, json={'status': 'approved'}), 409)
    assert_code(scenario['write'](staff, 'PATCH', url, json={'status': 'rejected', 'reason': '   '}), 422)
    assert_code(scenario['write'](staff, 'PATCH', url, json={'status': 'under_review'}), 200)
    assert_code(scenario['write'](staff, 'PATCH', url, json={'status': 'rejected', 'reason': 'No serial number given'}), 200)
    assert_code(scenario['write'](staff, 'PATCH', url, json={'status': 'approved'}), 409)


def test_linked_lost_report_identity_locked_during_open_claim(scenario):
    claimant, finder = scenario['client'](), scenario['client']()
    scenario['auth'](claimant, 'claimant@example.com')
    scenario['auth'](finder, 'finder@example.com')
    lost = scenario['write'](claimant, 'POST', '/api/v1/reports', json=scenario['report']('lost')).json()
    found = scenario['write'](finder, 'POST', '/api/v1/reports', json=scenario['report']('found')).json()
    response = scenario['write'](claimant, 'POST', f"/api/v1/reports/{found['id']}/claims", json={
        'proof_text': 'The earcup has a distinctive silver mark.', 'lost_report_id': lost['id']
    })
    assert_code(response, 201)
    assert_code(scenario['write'](claimant, 'PATCH', f"/api/v1/reports/{lost['id']}", json={'item_name': 'Entirely different item'}), 409)
    assert_code(scenario['write'](claimant, 'DELETE', f"/api/v1/reports/{lost['id']}"), 409)
    # Non-identity changes remain permitted until return (for example better descriptive notes).
    assert_code(scenario['write'](claimant, 'PATCH', f"/api/v1/reports/{lost['id']}", json={'description': 'Still blue headphones in their soft carrying case.'}), 200)
