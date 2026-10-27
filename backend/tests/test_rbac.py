"""С1: права проверяются на сервере по АКТИВНОЙ роли, а не по набору ролей аккаунта."""

from app.core.security import create_access_token
from app.models.enums import RoleCode
from tests.helpers import PASSWORD, auth, make_user

API = "/api/v1"


async def login(client, email: str, role: str | None = None) -> str:
    r = await client.post(f"{API}/auth/login", json={"email": email, "password": PASSWORD, "role": role})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


async def test_endpoint_allows_own_role_and_denies_others(client, session):
    multi = await make_user(session, [RoleCode.ATHLETE, RoleCode.COACH], email="multi@test.example.com")
    token = await login(client, multi.email)  # по умолчанию входим спортсменом
    h = {"Authorization": f"Bearer {token}"}

    assert (await client.get(f"{API}/rbac/athlete", headers=h)).status_code == 200
    assert (await client.get(f"{API}/rbac/coach", headers=h)).status_code == 403
    assert (await client.get(f"{API}/rbac/federation", headers=h)).status_code == 403

    # переключение роли без повторного входа: права меняются вместе с активной ролью
    switched = await client.post(f"{API}/auth/switch-role", json={"role": "coach"}, headers=h)
    assert switched.status_code == 200 and switched.json()["active_role"] == "coach"
    h2 = {"Authorization": f"Bearer {switched.json()['access_token']}"}
    assert (await client.get(f"{API}/rbac/coach", headers=h2)).status_code == 200
    assert (await client.get(f"{API}/rbac/athlete", headers=h2)).status_code == 403


async def test_federation_only_endpoints_reject_other_roles(client, session):
    fed = await make_user(session, [RoleCode.FEDERATION])
    athlete = await make_user(session, [RoleCode.ATHLETE])

    assert (await client.get(f"{API}/federation/dashboard", headers=auth(fed, RoleCode.FEDERATION))).status_code == 200
    denied = await client.get(f"{API}/federation/dashboard", headers=auth(athlete, RoleCode.ATHLETE))
    assert denied.status_code == 403
    assert "Федерация" in denied.json()["detail"]
    assert (await client.post(f"{API}/competitions", json={}, headers=auth(athlete, RoleCode.ATHLETE))).status_code == 403


async def test_anonymous_and_tampered_tokens_get_401(client, session):
    user = await make_user(session, [RoleCode.ATHLETE])
    assert (await client.get(f"{API}/rbac/athlete")).status_code == 401
    good = auth(user, RoleCode.ATHLETE)["Authorization"]
    assert (await client.get(f"{API}/rbac/athlete", headers={"Authorization": good[:-3] + "abc"})).status_code == 401


async def test_forged_role_claim_is_not_trusted(client, session):
    """Токен с active_role=federation у пользователя без этой роли в БД отклоняется."""
    user = await make_user(session, [RoleCode.ATHLETE])
    token, _ = create_access_token(user.id, ["federation"], "federation")
    r = await client.get(f"{API}/rbac/federation", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


async def test_cannot_switch_to_unassigned_role(client, session):
    user = await make_user(session, [RoleCode.ATHLETE], email="solo@test.example.com")
    token = await login(client, user.email)
    r = await client.post(f"{API}/auth/switch-role", json={"role": "federation"}, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403
    wrong = await client.post(f"{API}/auth/login", json={"email": user.email, "password": "wrong-password"})
    assert wrong.status_code == 401
