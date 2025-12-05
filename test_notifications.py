# test_notifications.py

import asyncio
import httpx
from typing import Optional

API_BASE = "http://localhost:8000/api/v1"

# Credentials de l'expéditeur par défaut
DEFAULT_SENDER_EMAIL = "test@example.com"
DEFAULT_SENDER_PASSWORD = "TestPassword123"


async def login(email: str, password: str) -> Optional[str]:
    """Se connecter et récupérer le token"""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{API_BASE}/auth/login",
                json={"identifier": email, "password": password}
            )
            if response.status_code == 200:
                data = response.json()
                return data.get("access_token")
            else:
                print(f"❌ Login failed: {response.text}")
                return None
        except Exception as e:
            print(f"❌ Error: {e}")
            return None


async def get_users(token: str) -> list:
    """Récupérer la liste des utilisateurs"""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{API_BASE}/users/",
                headers={"Authorization": f"Bearer {token}"},
                params={"limit": 100}
            )
            if response.status_code == 200:
                return response.json()
            else:
                print(f"❌ Failed to get users: {response.text}")
                return []
        except Exception as e:
            print(f"❌ Error: {e}")
            return []


async def get_pending_requests(token: str) -> list:
    """Récupérer les demandes d'ami en attente"""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{API_BASE}/friendships/pending",
                headers={"Authorization": f"Bearer {token}"}
            )
            if response.status_code == 200:
                return response.json()
            else:
                print(f"❌ Failed to get pending requests: {response.text}")
                return []
        except Exception as e:
            print(f"❌ Error: {e}")
            return []


async def send_friend_request(token: str, receiver_id: str) -> bool:
    """Envoyer une demande d'ami"""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{API_BASE}/friendships/",
                headers={"Authorization": f"Bearer {token}"},
                params={"user_two_id": receiver_id}
            )

            if response.status_code == 201:
                return True
            else:
                print(f"❌ Failed: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            print(f"❌ Error: {e}")
            return False


async def accept_friend_request(token: str, user_id: str) -> bool:
    """Accepter une demande d'ami"""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.put(
                f"{API_BASE}/friendships/{user_id}",
                headers={"Authorization": f"Bearer {token}"},
                json={"status": "accepted"}
            )
            if response.status_code == 200:
                return True
            else:
                print(f"❌ Failed: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            print(f"❌ Error: {e}")
            return False


async def decline_friend_request(token: str, user_id: str) -> bool:
    """Refuser une demande d'ami"""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.put(
                f"{API_BASE}/friendships/{user_id}",
                headers={"Authorization": f"Bearer {token}"},
                json={"status": "declined"}
            )
            if response.status_code == 200:
                return True
            else:
                print(f"❌ Failed: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            print(f"❌ Error: {e}")
            return False


async def search_media(token: str, query: str) -> list:
    """Rechercher un média"""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{API_BASE}/media/search",
                headers={"Authorization": f"Bearer {token}"},
                params={"query": query, "limit": 10}
            )
            if response.status_code == 200:
                data = response.json()
                # Gérer le cas où la réponse est un dict avec une clé 'results'
                if isinstance(data, dict) and 'results' in data:
                    return data['results']
                # Gérer le cas où la réponse est directement une liste
                elif isinstance(data, list):
                    return data
                else:
                    print(f"⚠️ Format de réponse inattendu: {type(data)}")
                    return []
            else:
                print(f"❌ Failed to search media: {response.text}")
                return []
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
            return []


async def verify_media_exists(token: str, media_id: str) -> bool:
    """Vérifier qu'un média existe en base"""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{API_BASE}/media/{media_id}",
                headers={"Authorization": f"Bearer {token}"}
            )
            return response.status_code == 200
        except Exception as e:
            print(f"❌ Error verifying media: {e}")
            return False


async def add_to_favorites(token: str, media_id: str) -> bool:
    """Ajouter un média aux favoris"""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{API_BASE}/library/{media_id}/favorite",
                headers={"Authorization": f"Bearer {token}"}
            )
            if response.status_code == 200:
                return True
            else:
                print(f"❌ Failed: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
            return False


# test_notifications.py

async def create_review(token: str, media_id: str, rating: int, content: str = "") -> bool:
    """Créer une review/critique"""
    async with httpx.AsyncClient() as client:
        try:
            payload = {
                "media_id": media_id,
                "rating": rating
            }

            if content:
                payload["content"] = content

            url = f"{API_BASE}/review/"
            print(f"🔍 DEBUG - URL appelée: {url}")  # 🆕 Debug
            print(f"🔍 DEBUG - Payload: {payload}")  # 🆕 Debug

            response = await client.post(
                url,
                headers={"Authorization": f"Bearer {token}"},
                json=payload
            )

            print(f"📥 Status Code: {response.status_code}")  # 🆕 Debug
            print(f"📥 Response: {response.text}")  # 🆕 Debug

            if response.status_code == 201:
                return True
            else:
                print(f"❌ Failed: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
            return False

def display_users(users: list):
    """Affiche la liste des utilisateurs de manière formatée"""
    print("\n📋 Utilisateurs disponibles:")
    print("=" * 60)
    for i, user in enumerate(users, 1):
        print(f"   {i}. {user['username']:<20} ({user['email']})")
    print("=" * 60)


def display_media(media_list: list):
    """Affiche la liste des médias de manière formatée"""
    print("\n📺 Médias trouvés:")
    print("=" * 80)

    if not media_list:
        print("   Aucun média trouvé")
        print("=" * 80)
        return

    for i, media in enumerate(media_list, 1):
        # Vérifier que media est bien un dict
        if not isinstance(media, dict):
            print(f"   {i}. [Format invalide] {media}")
            continue

        media_type = media.get('media_type', 'unknown')
        title = media.get('title', 'Unknown')
        year = media.get('release_date', '')[:4] if media.get('release_date') else 'N/A'
        print(f"   {i}. [{media_type.upper()}] {title:<40} ({year})")
    print("=" * 80)


async def send_friend_request_flow():
    """Envoie une demande d'ami de test@example.com vers un utilisateur choisi"""
    print("\n🎨 Envoi d'une demande d'ami\n")

    # Se connecter avec le compte test
    print(f"🔐 Connexion avec {DEFAULT_SENDER_EMAIL}...")
    sender_token = await login(DEFAULT_SENDER_EMAIL, DEFAULT_SENDER_PASSWORD)
    if not sender_token:
        print("❌ Échec de connexion")
        return

    print("✅ Connecté\n")

    # Récupérer tous les utilisateurs
    print("📋 Récupération des utilisateurs...")
    all_users = await get_users(sender_token)

    # Filtrer pour exclure test@example.com
    other_users = [u for u in all_users if u['email'] != DEFAULT_SENDER_EMAIL]

    if not other_users:
        print("❌ Aucun autre utilisateur trouvé")
        return

    # Afficher la liste
    display_users(other_users)

    # Sélectionner le destinataire
    while True:
        try:
            choice = input(f"\nSélectionner le destinataire (1-{len(other_users)}): ")
            idx = int(choice) - 1
            if 0 <= idx < len(other_users):
                receiver = other_users[idx]
                break
            else:
                print(f"❌ Choisir un nombre entre 1 et {len(other_users)}")
        except ValueError:
            print("❌ Entrée invalide")

    print(f"\n✅ Destinataire sélectionné: {receiver['username']} ({receiver['email']})")

    # Envoyer la demande d'ami
    print(f"\n📤 Envoi de la demande d'ami...")
    success = await send_friend_request(sender_token, receiver['id'])

    if success:
        print("\n" + "=" * 60)
        print("✅ DEMANDE D'AMI ENVOYÉE!")
        print("=" * 60)
        print(f"📤 De: test@example.com")
        print(f"📥 Vers: {receiver['username']} ({receiver['email']})")
        print(f"🔔 Notification: FRIEND_REQUEST")
        print(f"\n💡 Connecte-toi avec {receiver['email']} pour voir la notification!")
        print("=" * 60)
    else:
        print("\n❌ Échec de l'envoi de la demande (peut-être déjà existante)")


async def accept_friend_request_flow():
    """Accepter une demande d'ami reçue"""
    print("\n✅ Accepter une demande d'ami\n")

    # Demander les credentials
    email = input("Email du compte: ")
    password = input("Mot de passe: ")

    print(f"\n🔐 Connexion avec {email}...")
    token = await login(email, password)
    if not token:
        print("❌ Échec de connexion")
        return

    print("✅ Connecté\n")

    # Récupérer les demandes en attente
    print("📋 Récupération des demandes en attente...")
    pending = await get_pending_requests(token)

    if not pending:
        print("❌ Aucune demande d'ami en attente")
        return

    # Afficher les demandes
    print("\n📨 Demandes d'ami en attente:")
    print("=" * 60)
    for i, user in enumerate(pending, 1):
        username = user.get('username', 'Unknown')
        user_email = user.get('email', 'N/A')
        print(f"   {i}. {username:<20} ({user_email})")
    print("=" * 60)

    # Sélectionner la demande
    while True:
        try:
            choice = input(f"\nSélectionner la demande à accepter (1-{len(pending)}): ")
            idx = int(choice) - 1
            if 0 <= idx < len(pending):
                requester = pending[idx]
                break
            else:
                print(f"❌ Choisir un nombre entre 1 et {len(pending)}")
        except ValueError:
            print("❌ Entrée invalide")

    # Accepter la demande
    requester_name = requester.get('username', 'Unknown')
    print(f"\n✅ Acceptation de la demande de {requester_name}...")
    success = await accept_friend_request(token, requester['id'])

    if success:
        print("\n" + "=" * 60)
        print("✅ DEMANDE D'AMI ACCEPTÉE!")
        print("=" * 60)
        print(f"🔔 Notification: FRIEND_ACCEPTED")
        print(f"📥 Envoyée à: {requester_name}")
        print(f"\n💡 {requester_name} recevra une notification!")
        print("=" * 60)
    else:
        print("\n❌ Échec de l'acceptation")


async def decline_friend_request_flow():
    """Refuser une demande d'ami reçue"""
    print("\n❌ Refuser une demande d'ami\n")

    # Demander les credentials
    email = input("Email du compte: ")
    password = input("Mot de passe: ")

    print(f"\n🔐 Connexion avec {email}...")
    token = await login(email, password)
    if not token:
        print("❌ Échec de connexion")
        return

    print("✅ Connecté\n")

    # Récupérer les demandes en attente
    print("📋 Récupération des demandes en attente...")
    pending = await get_pending_requests(token)

    if not pending:
        print("❌ Aucune demande d'ami en attente")
        return

    # Afficher les demandes
    print("\n📨 Demandes d'ami en attente:")
    print("=" * 60)
    for i, user in enumerate(pending, 1):
        username = user.get('username', 'Unknown')
        user_email = user.get('email', 'N/A')
        print(f"   {i}. {username:<20} ({user_email})")
    print("=" * 60)

    # Sélectionner la demande
    while True:
        try:
            choice = input(f"\nSélectionner la demande à refuser (1-{len(pending)}): ")
            idx = int(choice) - 1
            if 0 <= idx < len(pending):
                requester = pending[idx]
                break
            else:
                print(f"❌ Choisir un nombre entre 1 et {len(pending)}")
        except ValueError:
            print("❌ Entrée invalide")

    # Refuser la demande
    requester_name = requester.get('username', 'Unknown')
    print(f"\n❌ Refus de la demande de {requester_name}...")
    success = await decline_friend_request(token, requester['id'])

    if success:
        print("\n" + "=" * 60)
        print("❌ DEMANDE D'AMI REFUSÉE!")
        print("=" * 60)
        print(f"🔔 Notification: FRIEND_DECLINED")
        print(f"📥 Envoyée à: {requester_name}")
        print(f"\n💡 {requester_name} recevra une notification de refus!")
        print("=" * 60)
    else:
        print("\n❌ Échec du refus")


async def add_favorite_flow():
    """Ajouter un média aux favoris"""
    print("\n❤️ Ajouter un média aux favoris\n")

    email = input("Email du compte: ")
    password = input("Mot de passe: ")

    print(f"\n🔐 Connexion avec {email}...")
    token = await login(email, password)
    if not token:
        print("❌ Échec de connexion")
        return

    print("✅ Connecté\n")

    query = input("Rechercher un média (titre): ")
    print(f"\n🔍 Recherche de '{query}'...")
    media_list = await search_media(token, query)

    if not media_list:
        print("❌ Aucun média trouvé")
        return

    display_media(media_list)

    valid_media = [m for m in media_list if isinstance(m, dict)]
    if not valid_media:
        print("❌ Aucun média valide trouvé")
        return

    while True:
        try:
            choice = input(f"\nSélectionner le média (1-{len(valid_media)}): ")
            idx = int(choice) - 1
            if 0 <= idx < len(valid_media):
                media = valid_media[idx]
                break
            else:
                print(f"❌ Choisir un nombre entre 1 et {len(valid_media)}")
        except ValueError:
            print("❌ Entrée invalide")

    media_title = media.get('title', 'Unknown')
    media_id = media.get('id')

    if not media_id:
        print("❌ ID du média manquant")
        return

    # Vérifier que le média existe vraiment
    print(f"\n🔍 Vérification du média...")
    if not await verify_media_exists(token, media_id):
        print("❌ Le média n'existe pas en base. Veuillez d'abord l'ajouter à votre bibliothèque.")
        return

    print(f"\n❤️ Ajout de '{media_title}' aux favoris...")
    success = await add_to_favorites(token, media_id)

    if success:
        print("\n" + "=" * 60)
        print("❤️ AJOUTÉ AUX FAVORIS!")
        print("=" * 60)
        print(f"📺 Média: {media_title}")
        print(f"🔔 Notification: FAVORITE_ADDED")
        print(f"📥 Tous vos amis recevront une notification!")
        print("=" * 60)
    else:
        print("\n❌ Échec de l'ajout aux favoris")


async def create_review_flow():
    """Créer une review/critique"""
    print("\n⭐ Créer une review\n")

    email = input("Email du compte: ")
    password = input("Mot de passe: ")

    print(f"\n🔐 Connexion avec {email}...")
    token = await login(email, password)
    if not token:
        print("❌ Échec de connexion")
        return

    print("✅ Connecté\n")

    query = input("Rechercher un média (titre): ")
    print(f"\n🔍 Recherche de '{query}'...")
    media_list = await search_media(token, query)

    if not media_list:
        print("❌ Aucun média trouvé")
        return

    display_media(media_list)

    valid_media = [m for m in media_list if isinstance(m, dict)]
    if not valid_media:
        print("❌ Aucun média valide trouvé")
        return

    while True:
        try:
            choice = input(f"\nSélectionner le média (1-{len(valid_media)}): ")
            idx = int(choice) - 1
            if 0 <= idx < len(valid_media):
                media = valid_media[idx]
                break
            else:
                print(f"❌ Choisir un nombre entre 1 et {len(valid_media)}")
        except ValueError:
            print("❌ Entrée invalide")

    while True:
        try:
            rating = int(input("\nNote (1-5): "))
            if 1 <= rating <= 5:
                break
            else:
                print("❌ La note doit être entre 1 et 5")
        except ValueError:
            print("❌ Entrée invalide")

    content = input("\nCritique (optionnel, Enter pour passer): ").strip()

    media_title = media.get('title', 'Unknown')
    media_id = media.get('id')

    if not media_id:
        print("❌ ID du média manquant")
        return

    # Vérifier que le média existe vraiment
    print(f"\n🔍 Vérification du média...")
    if not await verify_media_exists(token, media_id):
        print("❌ Le média n'existe pas en base. Veuillez d'abord l'ajouter à votre bibliothèque.")
        return

    print(f"\n⭐ Création de la review...")
    success = await create_review(token, media_id, rating, content)

    if success:
        print("\n" + "=" * 60)
        print("⭐ REVIEW CRÉÉE!")
        print("=" * 60)
        print(f"📺 Média: {media_title}")
        print(f"⭐ Note: {rating}/5")
        if content:
            print(f"📝 Critique: {content[:50]}{'...' if len(content) > 50 else ''}")
        print(f"🔔 Notification: REVIEW_POSTED")
        print(f"📥 Tous vos amis recevront une notification!")
        print("=" * 60)
    else:
        print("\n❌ Échec de la création de la review")


async def main():
    """Menu principal"""
    while True:
        print("\n" + "=" * 60)
        print("🧪 TEST DES NOTIFICATIONS")
        print("=" * 60)
        print("1. Envoyer une demande d'ami (test@example.com → user)")
        print("2. Accepter une demande d'ami (→ notif FRIEND_ACCEPTED)")
        print("3. Refuser une demande d'ami (→ notif FRIEND_DECLINED)")
        print("4. Ajouter un média aux favoris (→ notif FAVORITE_ADDED)")
        print("5. Créer une review (→ notif REVIEW_POSTED)")
        print("6. Quitter")
        print("=" * 60)

        choice = input("\nChoisir une option (1-6): ")

        if choice == "1":
            await send_friend_request_flow()
        elif choice == "2":
            await accept_friend_request_flow()
        elif choice == "3":
            await decline_friend_request_flow()
        elif choice == "4":
            await add_favorite_flow()
        elif choice == "5":
            await create_review_flow()
        elif choice == "6":
            print("\n👋 Au revoir!")
            break
        else:
            print("\n❌ Option invalide")


if __name__ == "__main__":
    asyncio.run(main())