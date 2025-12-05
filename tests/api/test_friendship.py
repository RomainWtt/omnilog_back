import pytest
from httpx import AsyncClient
from uuid import uuid4
from typing import AsyncGenerator, Any, Coroutine

# Assurez-vous d'importer les modèles nécessaires depuis les chemins corrects
from app.schemas.friendship import FriendshipStatus, FriendshipRead


# --- Fixtures pour l'utilisateur Bob ---
# (Ces fixtures restent inchangées, elles sont correctes)

@pytest.fixture
async def create_user_bob_data(client: AsyncClient) -> dict:
    bob_data = {
        "email": "bob@example.com",
        "username": "bob_tester",
        "password": "BobPassword456",
        "birth_date": "1995-05-15"
    }
    await client.post("/api/v1/auth/register", json=bob_data)
    login_response = await client.post(
        "/api/v1/auth/login",
        json={"identifier": bob_data["email"], "password": bob_data["password"]}
    )
    tokens = login_response.json()
    original_auth = client.headers.get("Authorization")
    client.headers["Authorization"] = f"Bearer {tokens['access_token']}"
    profile_response = await client.get("/api/v1/users/me")
    bob_data["id"] = profile_response.json()["id"]
    if original_auth:
        client.headers["Authorization"] = original_auth
    else:
        client.headers.pop("Authorization", None)
    bob_data["tokens"] = tokens
    return bob_data


@pytest.fixture
async def authenticated_client_bob(
        client: AsyncClient, create_user_bob_data: dict
) -> AsyncGenerator[tuple[AsyncClient, dict], None]:
    bob_data = create_user_bob_data
    tokens = bob_data["tokens"]
    original_auth = client.headers.get("Authorization")
    client.headers["Authorization"] = f"Bearer {tokens['access_token']}"
    yield client, tokens
    if original_auth:
        client.headers["Authorization"] = original_auth
    else:
        client.headers.pop("Authorization", None)


# --- FONCTION UTILITAIRE ---

async def get_user_id_from_client(client: AsyncClient, tokens: dict) -> Any | None:
    if "user_id" in tokens:
        return tokens["user_id"]
    try:
        profile_response = await client.get("/api/v1/users/me")
        if profile_response.status_code == 200:
            return profile_response.json()["id"]
        else:
            pytest.fail(f"Impossible de récupérer l'ID utilisateur via /users/me: {profile_response.status_code}")
    except Exception as e:
        pytest.fail(f"Erreur lors de la récupération de l'ID utilisateur: {e}")
    return None


# --- TESTS CORRIGÉS ---

@pytest.mark.asyncio
async def test_send_friend_request_success(
        authenticated_client: tuple[AsyncClient, dict],
        create_user_bob_data: dict
):
    """Test 1: Envoi réussi d'une demande d'amitié (Alice -> Bob)."""
    alice_client, tokens = authenticated_client
    bob_id = create_user_bob_data["id"]
    alice_id = await get_user_id_from_client(alice_client, tokens)

    # CORRECTION : Utilisation de 'params' au lieu de 'json' pour le POST
    response = await alice_client.post(
        "/api/v1/friendships/",
        params={"user_two_id": str(bob_id)}
    )

    assert response.status_code == 201
    data = response.json()
    assert data["user_two_id"] == str(bob_id)
    assert data["status"] == FriendshipStatus.PENDING.value
    assert data["user_one_id"] == alice_id


@pytest.mark.asyncio
async def test_send_request_to_self(authenticated_client: tuple[AsyncClient, dict]):
    """Test 2: Tentative d'envoi d'une demande à soi-même (doit échouer)."""
    client, tokens = authenticated_client
    alice_id = await get_user_id_from_client(client, tokens)

    # CORRECTION : Utilisation de 'params'
    response = await client.post(
        "/api/v1/friendships/",
        params={"user_two_id": alice_id}
    )

    assert response.status_code == 400
    assert "cannot send a friend request to yourself" in response.json()["detail"]


@pytest.mark.asyncio
async def test_duplicate_friend_request(
        authenticated_client: tuple[AsyncClient, dict],
        create_user_bob_data: dict
):
    """Test 3: Tentative d'envoyer deux fois la même demande (Alice -> Bob)."""
    alice_client, tokens = authenticated_client
    bob_id = create_user_bob_data["id"]

    # 1. Première demande (CORRECTION : params)
    await alice_client.post("/api/v1/friendships/", params={"user_two_id": str(bob_id)})

    # 2. Deuxième tentative (CORRECTION : params)
    response = await alice_client.post(
        "/api/v1/friendships/",
        params={"user_two_id": str(bob_id)}
    )

    assert response.status_code == 409
    assert "already sent and pending" in response.json()["detail"]


@pytest.mark.asyncio
async def test_get_user_friendships_no_match(authenticated_client: tuple[AsyncClient, dict]):
    client, tokens = authenticated_client

    # Ici c'est un GET, 'params' est implicite dans l'URL string ou explicite via params=
    response = await client.get(
        f"/api/v1/friendships/friends?status={FriendshipStatus.BLOCKED.value}"
    )

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_decline_friend_request(
        authenticated_client: tuple[AsyncClient, dict],  # Alice
        authenticated_client_bob: tuple[AsyncClient, dict],  # Bob
        create_user_bob_data: dict
):
    """Test 8: Bob décline la demande d'Alice (PENDING -> DECLINED)."""
    alice_client, alice_tokens = authenticated_client
    bob_client, bob_tokens = authenticated_client_bob

    alice_header = {"Authorization": f"Bearer {alice_tokens['access_token']}"}
    bob_header = {"Authorization": f"Bearer {bob_tokens['access_token']}"}

    alice_client.headers.update(alice_header)
    alice_id = await get_user_id_from_client(alice_client, alice_tokens)
    bob_id = create_user_bob_data["id"]

    # Cleanup
    alice_client.headers.update(alice_header)
    await alice_client.delete(f"/api/v1/friendships/{bob_id}")

    # SETUP : Créer l'état PENDING (CORRECTION : params)
    alice_client.headers.update(alice_header)
    response_post = await alice_client.post(
        "/api/v1/friendships/",
        params={"user_two_id": str(bob_id)}
    )
    assert response_post.status_code == 201, f"Setup POST failed: {response_post.text}"

    # TEST PRINCIPAL : Bob DECLINE (PUT utilise toujours JSON car attend un schéma Update)
    bob_client.headers.update(bob_header)
    response = await bob_client.put(
        f"/api/v1/friendships/{alice_id}",
        json={"status": FriendshipStatus.DECLINED.value}
    )

    assert response.status_code == 200
    assert response.json()["status"] == FriendshipStatus.DECLINED.value

    # Cleanup final
    bob_client.headers.update(bob_header)
    await bob_client.delete(f"/api/v1/friendships/{alice_id}")


@pytest.mark.asyncio
async def test_unauthorized_update_pending(
        authenticated_client: tuple[AsyncClient, dict],  # Alice
        authenticated_client_bob: tuple[AsyncClient, dict],  # Bob
        create_user_bob_data: dict
):
    """Test 9: Alice (expéditeur) tente d'ACCEPTER/DECLINER sa propre demande (doit échouer)."""
    alice_client, alice_tokens = authenticated_client
    bob_client, bob_tokens = authenticated_client_bob

    alice_client.headers["Authorization"] = f"Bearer {alice_tokens['access_token']}"
    bob_id = create_user_bob_data["id"]

    await alice_client.delete(f"/api/v1/friendships/{bob_id}")

    # SETUP (CORRECTION : params)
    response_post = await alice_client.post(
        "/api/v1/friendships/",
        params={"user_two_id": str(bob_id)}
    )
    assert response_post.status_code == 201, f"Setup POST failed: {response_post.text}"

    # TEST : Alice tente update (PUT utilise JSON)
    response = await alice_client.put(
        f"/api/v1/friendships/{bob_id}",
        json={"status": FriendshipStatus.ACCEPTED.value}
    )

    assert response.status_code == 403
    assert "Only the recipient can manage a pending request" in response.json()["detail"]

    bob_client.headers["Authorization"] = f"Bearer {bob_tokens['access_token']}"
    alice_id = await get_user_id_from_client(alice_client, alice_tokens)
    await bob_client.delete(f"/api/v1/friendships/{alice_id}")


@pytest.mark.asyncio
async def test_delete_friendship_success(
        authenticated_client: tuple[AsyncClient, dict],  # Alice
        authenticated_client_bob: tuple[AsyncClient, dict],  # Bob
        create_user_bob_data: dict
):
    """Test 10: Suppression réussie d'une relation."""
    alice_client, alice_tokens = authenticated_client
    alice_client.headers["Authorization"] = f"Bearer {alice_tokens['access_token']}"
    bob_id = create_user_bob_data["id"]

    await alice_client.delete(f"/api/v1/friendships/{bob_id}")

    # SETUP (CORRECTION : params)
    response_create = await alice_client.post(
        "/api/v1/friendships/",
        params={"user_two_id": str(bob_id)}
    )
    assert response_create.status_code == 201, f"Setup failed: {response_create.text}"

    # TEST DELETE
    response = await alice_client.delete(f"/api/v1/friendships/{bob_id}")

    assert response.status_code == 204

    check_response = await alice_client.get(f"/api/v1/friendships/friends?status={FriendshipStatus.PENDING.value}")
    if check_response.status_code == 200:
        friend_ids = [str(f["user_two_id"]) for f in check_response.json()]
        assert str(bob_id) not in friend_ids


@pytest.mark.asyncio
async def test_block_user(
        authenticated_client: tuple[AsyncClient, dict],  # Alice
        authenticated_client_bob: tuple[AsyncClient, dict],  # Bob
        create_user_bob_data: dict
):
    """Test 11: Alice bloque Bob."""
    alice_client, alice_tokens = authenticated_client
    bob_client, bob_tokens = authenticated_client_bob

    alice_header = {"Authorization": f"Bearer {alice_tokens['access_token']}"}
    bob_header = {"Authorization": f"Bearer {bob_tokens['access_token']}"}

    alice_client.headers.update(alice_header)
    alice_id = await get_user_id_from_client(alice_client, alice_tokens)
    bob_id = create_user_bob_data["id"]

    alice_client.headers.update(alice_header)
    await alice_client.delete(f"/api/v1/friendships/{bob_id}")

    # SETUP : POST (CORRECTION : params)
    alice_client.headers.update(alice_header)
    res_post = await alice_client.post(
        "/api/v1/friendships/",
        params={"user_two_id": str(bob_id)}
    )
    assert res_post.status_code == 201, f"Setup POST failed: {res_post.text}"

    # Setup : ACCEPT (PUT utilise JSON)
    bob_client.headers.update(bob_header)
    res_accept = await bob_client.put(
        f"/api/v1/friendships/{alice_id}",
        json={"status": FriendshipStatus.ACCEPTED.value}
    )
    assert res_accept.status_code == 200, f"Setup ACCEPT failed: {res_accept.text}"

    # TEST : BLOCK (PUT utilise JSON)
    alice_client.headers.update(alice_header)
    response = await alice_client.put(
        f"/api/v1/friendships/{bob_id}",
        json={"status": FriendshipStatus.BLOCKED.value}
    )

    assert response.status_code == 200
    assert response.json()["status"] == FriendshipStatus.BLOCKED.value

    # Nettoyage
    await alice_client.delete(f"/api/v1/friendships/{bob_id}")