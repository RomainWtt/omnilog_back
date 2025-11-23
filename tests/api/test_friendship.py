import pytest
from httpx import AsyncClient
from uuid import uuid4
from typing import AsyncGenerator

# Assurez-vous d'importer les modèles nécessaires depuis les chemins corrects
from app.schemas.friendship import FriendshipStatus, FriendshipRead


# --- Fixtures pour l'utilisateur Bob ---

@pytest.fixture
async def create_user_bob_data(client: AsyncClient) -> dict:
    """
    Crée et retourne les données complètes de l'utilisateur Bob (y compris son ID
    et ses tokens), en réutilisant le client principal du conftest.
    """
    bob_data = {
        "email": "bob@example.com",
        "username": "bob_tester",
        "password": "BobPassword456",
        "birth_date": "1995-05-15"
    }

    # 1. Enregistrement de Bob
    await client.post("/api/v1/auth/register", json=bob_data)

    # 2. Connexion pour obtenir les tokens
    login_response = await client.post(
        "/api/v1/auth/login",
        json={"identifier": bob_data["email"], "password": bob_data["password"]}
    )
    tokens = login_response.json()

    # 3. Récupérer l'ID de Bob (NÉCESSITE DE CHANGER L'EN-TÊTE DU CLIENT TEMPORAIREMENT)
    original_auth = client.headers.get("Authorization")
    client.headers["Authorization"] = f"Bearer {tokens['access_token']}"

    profile_response = await client.get("/api/v1/users/me")
    bob_data["id"] = profile_response.json()["id"]

    # 4. Restaurer l'en-tête original pour ne pas affecter la prochaine fixture
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
    """
    Génère le client authentifié pour Bob en réutilisant le client principal.
    Gère le changement et la restauration de l'en-tête d'autorisation.
    """
    bob_data = create_user_bob_data
    tokens = bob_data["tokens"]

    # Sauvegarder l'état actuel de l'authentification (probablement celle d'Alice)
    original_auth = client.headers.get("Authorization")

    # Définir l'authentification de Bob
    client.headers["Authorization"] = f"Bearer {tokens['access_token']}"

    yield client, tokens

    # RESTAURATION: Remettre l'en-tête à son état initial après le test
    if original_auth:
        client.headers["Authorization"] = original_auth
    else:
        client.headers.pop("Authorization", None)


# --- TESTS ---

async def get_user_id_from_client(client: AsyncClient, tokens: dict) -> str:
    """
    Tente d'extraire l'ID de l'utilisateur soit directement des tokens,
    soit en faisant un appel à /users/me si 'user_id' est manquant.
    """
    # 1. Tenter d'obtenir l'ID directement (méthode préférée)
    if "user_id" in tokens:
        return tokens["user_id"]

    # 2. Sinon, faire un appel à /users/me pour le récupérer
    # NOTE: Le client doit être authentifié à ce stade par la fixture authenticated_client.
    try:
        profile_response = await client.get("/api/v1/users/me")
        if profile_response.status_code == 200:
            return profile_response.json()["id"]
        else:
            pytest.fail(f"Impossible de récupérer l'ID utilisateur via /users/me: {profile_response.status_code}")
    except Exception as e:
        pytest.fail(f"Erreur lors de la récupération de l'ID utilisateur: {e}")

    return None


@pytest.mark.asyncio
async def test_send_friend_request_success(
        authenticated_client: tuple[AsyncClient, dict],
        create_user_bob_data: dict
):
    """Test 1: Envoi réussi d'une demande d'amitié (Alice -> Bob)."""
    alice_client, tokens = authenticated_client
    bob_id = create_user_bob_data["id"]

    # Correction: Utiliser la fonction d'aide pour obtenir l'ID d'Alice de manière robuste
    alice_id = await get_user_id_from_client(alice_client, tokens)

    response = await alice_client.post(
        "/api/v1/friendships/",
        json={"user_two_id": str(bob_id)}
    )

    assert response.status_code == 201
    data = response.json()
    assert data["user_two_id"] == str(bob_id)
    assert data["status"] == FriendshipStatus.PENDING.value
    assert data["user_one_id"] == alice_id  # Alice est l'expéditeur


@pytest.mark.asyncio
async def test_send_request_to_self(authenticated_client: tuple[AsyncClient, dict]):
    """Test 2: Tentative d'envoi d'une demande à soi-même (doit échouer)."""
    client, tokens = authenticated_client
    alice_id = await get_user_id_from_client(client, tokens)

    response = await client.post(
        "/api/v1/friendships/",
        json={"user_two_id": alice_id}
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

    # 1. Première demande
    await alice_client.post("/api/v1/friendships/", json={"user_two_id": str(bob_id)})

    # 2. Deuxième tentative
    response = await alice_client.post(
        "/api/v1/friendships/",
        json={"user_two_id": str(bob_id)}
    )

    assert response.status_code == 409
    assert "already sent and pending" in response.json()["detail"]


@pytest.mark.asyncio
async def test_get_user_friendships_no_match(authenticated_client: tuple[AsyncClient, dict]):
    client, tokens = authenticated_client

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

    # --- SETUP INITIAL: Définition des identités et IDs ---
    alice_header = {"Authorization": f"Bearer {alice_tokens['access_token']}"}
    bob_header = {"Authorization": f"Bearer {bob_tokens['access_token']}"}

    # Sécurisation des IDs (seul Alice est nécessaire ici)
    alice_client.headers.update(alice_header)
    alice_id = await get_user_id_from_client(alice_client, alice_tokens)
    bob_id = create_user_bob_data["id"]

    # --- 1. CLEANUP INITIAL ---
    alice_client.headers.update(alice_header)
    await alice_client.delete(f"/api/v1/friendships/{bob_id}")

    # --- 2. SETUP : Créer l'état PENDING ---

    # 2a. Alice envoie la demande (PENDING)
    alice_client.headers.update(alice_header)  # Re-sécuriser Alice
    response_post = await alice_client.post(
        "/api/v1/friendships/",
        json={"user_two_id": str(bob_id)}
    )
    assert response_post.status_code == 201, f"Setup POST failed: {response_post.text}"

    # --- 3. TEST PRINCIPAL : Bob DECLINE la demande (PENDING -> DECLINED) ---
    # Bob (destinataire) agit sur la relation initiée par Alice (cible)
    # ******* Réappliquer Bob Header ICI est CRITIQUE *******
    bob_client.headers.update(bob_header)
    response = await bob_client.put(
        f"/api/v1/friendships/{alice_id}",
        json={"status": FriendshipStatus.DECLINED.value}
    )

    # --- ASSERTIONS ---
    assert response.status_code == 200  # Le CRUD doit trouver la relation (Alice, Bob)
    assert response.json()["status"] == FriendshipStatus.DECLINED.value

    # --- 4. Nettoyage final ---
    # Bob supprime la relation DECLINED (cible Alice)
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

    # --- 1. CORRECTION CRITIQUE (Identité et Setup) ---
    # Forcer l'identité d'Alice sur le client partagé
    alice_client.headers["Authorization"] = f"Bearer {alice_tokens['access_token']}"

    bob_id = create_user_bob_data["id"]

    # Nettoyage préalable pour éviter 409 Conflict si une relation traîne
    await alice_client.delete(f"/api/v1/friendships/{bob_id}")

    # 2. Alice envoie la demande à Bob (SETUP)
    response_post = await alice_client.post(
        "/api/v1/friendships/",
        json={"user_two_id": str(bob_id)}
    )
    # Assurez-vous que la création a fonctionné
    assert response_post.status_code == 201, f"Setup POST failed: {response_post.text}"

    # 3. Alice tente d'ACCEPTER sa propre demande (elle est user_one_id)
    # Le client est toujours Alice, et la relation PENDING existe
    response = await alice_client.put(
        f"/api/v1/friendships/{bob_id}",
        json={"status": FriendshipStatus.ACCEPTED.value}
    )

    # --- 4. ASSERTION DU TEST (Doit être 403 Forbidden) ---
    assert response.status_code == 403
    assert "Only the recipient can manage a pending request" in response.json()["detail"]

    # --- 5. Nettoyage Final ---
    # Pour le nettoyage, on doit utiliser le client de Bob
    bob_client.headers["Authorization"] = f"Bearer {bob_tokens['access_token']}"
    # Bob supprime la PENDING request d'Alice (l'ID à cibler est Alice)
    alice_id = await get_user_id_from_client(alice_client, alice_tokens)
    await bob_client.delete(f"/api/v1/friendships/{alice_id}")


@pytest.mark.asyncio
async def test_delete_friendship_success(
        authenticated_client: tuple[AsyncClient, dict],  # Alice
        authenticated_client_bob: tuple[AsyncClient, dict],  # Bob
        create_user_bob_data: dict
):
    """Test 10: Suppression réussie d'une relation (Unfriend/Annulation)."""
    alice_client, alice_tokens = authenticated_client

    # --- CORRECTION CRITIQUE : FORCER L'IDENTITÉ D'ALICE ---
    # Comme la fixture de Bob a tourné en dernier, le client a le token de Bob.
    # On remet explicitement le token d'Alice.
    alice_client.headers["Authorization"] = f"Bearer {alice_tokens['access_token']}"

    bob_id = create_user_bob_data["id"]

    # 1. NETTOYAGE PRÉALABLE (au cas où une vieille relation traîne)
    await alice_client.delete(f"/api/v1/friendships/{bob_id}")

    # 2. SETUP : Alice envoie la demande à Bob
    response_create = await alice_client.post(
        "/api/v1/friendships/",
        json={"user_two_id": str(bob_id)}
    )
    # On vérifie que le setup a fonctionné
    assert response_create.status_code == 201, f"Setup failed: {response_create.text}"

    # 3. TEST : Alice annule la demande (DELETE)
    response = await alice_client.delete(f"/api/v1/friendships/{bob_id}")

    assert response.status_code == 204

    # 4. VÉRIFICATION
    check_response = await alice_client.get(f"/api/v1/friendships/friends?status={FriendshipStatus.PENDING.value}")

    if check_response.status_code == 200:
        friend_ids = [str(f["user_two_id"]) for f in check_response.json()]
        assert str(bob_id) not in friend_ids
    elif check_response.status_code == 404:
        # C'est parfait, aucune relation trouvée
        pass
    else:
        pytest.fail(f"Unexpected status code after deletion: {check_response.status_code}")


@pytest.mark.asyncio
async def test_block_user(
        authenticated_client: tuple[AsyncClient, dict],  # Alice
        authenticated_client_bob: tuple[AsyncClient, dict],  # Bob
        create_user_bob_data: dict
):
    """Test 11: Alice bloque Bob (PENDING/ACCEPTED/DECLINED -> BLOCKED)."""

    # Note: alice_client et bob_client sont en fait la MÊME instance de httpx.AsyncClient
    alice_client, alice_tokens = authenticated_client
    bob_client, bob_tokens = authenticated_client_bob

    alice_header = {"Authorization": f"Bearer {alice_tokens['access_token']}"}
    bob_header = {"Authorization": f"Bearer {bob_tokens['access_token']}"}

    # Récupération des IDs
    # On s'assure d'être Alice pour récupérer son ID
    alice_client.headers.update(alice_header)
    alice_id = await get_user_id_from_client(alice_client, alice_tokens)
    bob_id = create_user_bob_data["id"]

    # --- NETTOYAGE PRÉALABLE (En tant qu'Alice) ---
    alice_client.headers.update(alice_header)  # On s'assure que c'est Alice
    await alice_client.delete(f"/api/v1/friendships/{bob_id}")

    # --- SETUP : Créer une amitié propre ---

    # 1. Alice envoie la demande
    # (C'est ici que ça plantait : on force les headers d'Alice)
    alice_client.headers.update(alice_header)
    res_post = await alice_client.post("/api/v1/friendships/", json={"user_two_id": str(bob_id)})
    assert res_post.status_code == 201, f"Setup POST failed: {res_post.text}"

    # 2. Bob accepte
    # IMPORTANT : On change le header pour devenir Bob
    bob_client.headers.update(bob_header)
    res_accept = await bob_client.put(
        f"/api/v1/friendships/{alice_id}",
        json={"status": FriendshipStatus.ACCEPTED.value}
    )
    assert res_accept.status_code == 200, f"Setup ACCEPT failed: {res_accept.text}"

    # --- TEST PRINCIPAL : BLOCK ---

    # 3. Alice bloque Bob
    # IMPORTANT : On repasse en Alice
    alice_client.headers.update(alice_header)
    response = await alice_client.put(
        f"/api/v1/friendships/{bob_id}",
        json={"status": FriendshipStatus.BLOCKED.value}
    )

    assert response.status_code == 200
    assert response.json()["status"] == FriendshipStatus.BLOCKED.value

    # Vérifier que la relation BLOCKED est détectée par GET
    response_blocked = await alice_client.get(f"/api/v1/friendships/friends?status={FriendshipStatus.BLOCKED.value}")
    assert response_blocked.status_code == 200
    # Vérification souple (l'ID peut être user_one ou user_two selon le sens de création)
    blocked_user = response_blocked.json()[0]
    assert blocked_user["id"] == str(bob_id)

    # Nettoyage final
    await alice_client.delete(f"/api/v1/friendships/{bob_id}")
