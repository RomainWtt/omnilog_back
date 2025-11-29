import httpx
from typing import Dict, Any, List
from app.core.config import settings
from app.schemas.streaming_availability import StreamLink


class StreamingService:
    def __init__(self):
        base_url = f"https://{settings.STREAMING_API_HOST}"

        self.client = httpx.AsyncClient(
            base_url=base_url,
            headers={
                "X-RapidAPI-Key": settings.STREAMING_AVAILABILITY_KEY,
                "X-RapidAPI-Host": settings.STREAMING_API_HOST,
                "accept": "application/json"
            },
            timeout=10.0
        )

        if not settings.STREAMING_AVAILABILITY_KEY:
            print("AVERTISSEMENT: La variable d'environnement 'STREAMING_AVAILABILITY_KEY' n'est pas définie.")

    async def get_country_services(self, country_code: str) -> List[Dict[str, Any]]:
        """
        Récupère la liste des services de streaming disponibles dans un pays.

        :param country_code: Code ISO 3166-1 alpha-2 (ex: 'US', 'FR')
        :return: Liste des services avec leurs infos (id, name, homePage, themeColorCode)
        """
        if not settings.STREAMING_AVAILABILITY_KEY:
            raise Exception("Clé API RapidAPI manquante.")

        country_code = country_code.lower()
        endpoint = f"/countries/{country_code}"

        try:
            response = await self.client.get(endpoint)
            response.raise_for_status()
            data = response.json()

            print(f"✅ Services disponibles dans {country_code.upper()}: {len(data.get('services', []))} services")
            return data.get('services', [])

        except httpx.HTTPStatusError as e:
            print(f"❌ Erreur HTTP {e.response.status_code}: {e.response.text}")

            if e.response.status_code == 403:
                raise Exception(
                    "Erreur 403: Vérifiez votre clé API RapidAPI et votre abonnement."
                ) from e
            elif e.response.status_code == 429:
                raise Exception("Limite de requêtes dépassée") from e
            else:
                raise Exception(f"Erreur API Streaming: {e.response.status_code}") from e

        except httpx.RequestError as e:
            print(f"❌ Erreur de connexion: {e}")
            raise Exception(f"Erreur de connexion API Streaming: {e}") from e

    async def get_availability_by_tmdb_id(
            self,
            tmdb_id: int,
            media_type: str,
            country: str
    ) -> Dict[str, Any]:
        """
        Récupère la disponibilité en streaming pour un ID TMDB donné.

        Format attendu par l'API:
        - Pour un film: movie/{tmdb_id} (ex: movie/597 pour Titanic)
        - Pour une série: tv/{tmdb_id} (ex: tv/1396 pour Breaking Bad)

        :param tmdb_id: ID TMDB du média
        :param media_type: 'movie' ou 'tv'
        :param country: Code ISO 3166-1 alpha-2 du pays (ex: 'FR', 'US')
        :return: Données de disponibilité formatées
        """
        if not settings.STREAMING_AVAILABILITY_KEY:
            raise Exception("Clé API RapidAPI manquante.")

        # Formater l'ID selon le format attendu: movie/{id} ou tv/{id}
        api_media_type = "movie" if media_type.lower() == "movie" else "tv"
        show_id = f"{api_media_type}/{tmdb_id}"
        endpoint = f"/shows/{show_id}"

        print(f"🌐 Requête Streaming API:")
        print(f"   Endpoint: {endpoint}")
        print(f"   Country: {country.upper()}")

        try:
            response = await self.client.get(endpoint)

            print(f"📡 Status: {response.status_code}")

            response.raise_for_status()
            data = response.json()

        except httpx.HTTPStatusError as e:
            print(f"❌ Erreur HTTP {e.response.status_code}")
            print(f"   Response: {e.response.text}")

            if e.response.status_code == 403:
                raise Exception(
                    "Erreur 403: Vérifiez votre clé API RapidAPI et votre abonnement à l'API."
                ) from e
            elif e.response.status_code == 404:
                raise Exception(f"Média non trouvé: {show_id}") from e
            elif e.response.status_code == 429:
                raise Exception("Limite de requêtes dépassée (429)") from e
            else:
                raise Exception(f"Erreur API Streaming: {e.response.status_code}") from e

        except httpx.RequestError as e:
            print(f"❌ Erreur de connexion: {e}")
            raise Exception(f"Erreur de connexion API Streaming: {e}") from e

        # --- Transformation des données ---
        # La structure de la réponse de l'API:
        # {
        #   "id": "...",
        #   "title": "...",
        #   "streamingOptions": {
        #     "fr": [  // Code pays
        #       {
        #         "service": {...},
        #         "type": "subscription|free|buy|rent|addon",
        #         "link": "...",
        #       }
        #     ]
        #   }
        # }

        streaming_options = data.get("streamingOptions", {})
        country_lower = country.lower()
        country_options = streaming_options.get(country_lower, [])

        formatted_links = {}
        is_available = False

        if country_options:
            is_available = True

            # Grouper par type (subscription, buy, rent, etc.)
            for option in country_options:
                option_type = option.get("type", "unknown")
                service_info = option.get("service", {})
                service_name = service_info.get("id", "unknown")

                if option_type not in formatted_links:
                    formatted_links[option_type] = []

                link_data = StreamLink(
                    service=service_name,
                    type=option_type,
                    link=option.get("link", ""),
                    price=None
                )
                formatted_links[option_type].append(link_data)

        print(f"✅ Disponibilité trouvée: {is_available}")
        print(f"   Types disponibles: {list(formatted_links.keys())}")

        return {
            "tmdb_id": tmdb_id,
            "country": country.upper(),
            "is_available": is_available,
            "streaming_links": formatted_links
        }


streaming_service = StreamingService()
