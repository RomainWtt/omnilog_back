# **🚀 Omnilog Backend**

Application API RESTful moderne construite avec **FastAPI**, **Python 3.10+**, **SQLAlchemy** et **Pydantic**.

## **📋 Table des matières**

* [Workflow Git & Branches](#-workflow-git--branches)  
* [Installation](#-installation)  
* [Variables d'environnement](#-variables-denvironnement)  
* [Scripts et Commandes](#-scripts-et-commandes)  
* [Architecture du projet](#️-architecture-du-projet)  
* [Technologies utilisées](#️-technologies-utilisées)  
* [Base de données & Migrations](#️-base-de-données--migrations)  
* [Tests](#-tests)  
* [Documentation de l'API](#-documentation-de-lapi)

## **🌳 Workflow Git & Branches**

### **Structure des branches**

Notre projet suit le modèle **Git Flow** avec les branches suivantes :

```
main (production)  
│  
├── develop (développement actif)  
│   │  
│   ├── feature/nom-feature (nouvelles fonctionnalités)  
│   ├── feature/autre-feature  
│   │  
│   └── release/v1.0.0 (préparation release)  
│  
└── hotfix/correction-urgente (fixes de production)
```

### **📌 Branches principales**

#### **main**

* **Branche de production** - Code en production  
* ⚠️ **Protégée** - Merge uniquement via Pull/Merge Request  
* Contient uniquement du code testé et validé  
* Chaque merge crée automatiquement un tag de version

#### **develop**

* **Branche de développement** - Intégration continue  
* Point de départ pour toutes les features  
* Merge des features terminées  
* Tests d'intégration

### **🔧 Branches de travail**

#### **feature/\***

**Création d'une nouvelle fonctionnalité :**

```bash
# Se placer sur develop  
git checkout develop  
git pull origin develop

# Créer la branche feature  
git checkout -b feature/nom-explicite-de-la-feature

# Exemples de noms :  
# feature/user-authentication  
# feature/crud-items  
# feature/jwt-security
```

**Workflow feature :**

```bash
# Développement  
git add .  
git commit -m "feat: description de la fonctionnalité"

# Push de la feature  
git push origin feature/nom-feature

# Créer une Merge Request vers develop  
# Via GitLab UI → Create merge request
```

**Conventions de commit :**

```
feat: nouvelle fonctionnalité  
fix: correction de bug  
docs: documentation  
style: formatage, linting  
refactor: refactoring du code  
test: ajout de tests  
chore: maintenance, mise à jour des dépendances  
db: migration ou modification de schéma
```

#### **release/\***

**Préparation d'une nouvelle version :**

```bash
# 1. PRÉPARATION - Créer depuis develop  
git checkout develop  
git pull origin develop  
git checkout -b release/v1.2.0

# 2. VERSION - (Optionnel : Mettre à jour la version de l'API dans le code/docs)  
# ... modifications ...  
git add .  
git commit -m "chore: prepare release v1.2.0"

# 3. MERGE MAIN - D'abord vers main  
git checkout main  
git pull origin main  # IMPORTANT: être à jour  
git merge --no-ff release/v1.2.0 -m "Merge branch 'release/v1.2.0'"  
git tag -a v1.2.0 -m "Version 1.2.0"  
git push origin main --tags

# 4. MERGE DEVELOP - Puis vers develop  
git checkout develop  
git pull origin develop  # IMPORTANT: être à jour  
git merge --no-ff release/v1.2.0 -m "Merge branch 'release/v1.2.0' into develop"  
git push origin develop

# 5. NETTOYAGE - Supprimer la branche release  
git branch -d release/v1.2.0
```

#### **hotfix/\***

**Correction urgente en production :**

```bash
# Créer depuis main  
git checkout main  
git pull origin main  
git checkout -b hotfix/fix-critical-bug

# Corriger le bug  
git add .  
git commit -m "fix: correction du bug critique"

# Merge vers main ET develop  
git checkout main  
git merge --no-ff hotfix/fix-critical-bug  
git tag -a v1.1.1 -m "Hotfix v1.1.1"  
git push origin main --tags

git checkout develop  
git merge --no-ff hotfix/fix-critical-bug  
git push origin develop
```

### **✅ Règles et bonnes pratiques**

1. **Ne jamais commit directement sur main ou develop**  
2. **Toujours créer une feature branch depuis develop**  
3. **Une feature \= une branche \= une fonctionnalité**  
4. **Faire des commits atomiques et bien décrits**  
5. **Tester localement avant de push (pytest)**  
6. **Demander une review pour chaque Merge Request**  
7. **Mettre à jour sa branche avec develop régulièrement :**  
```bash
   git checkout feature/ma-feature  
   git pull origin develop  
   # Résoudre les conflits si nécessaire
   ```

## **💻 Installation**

### **Prérequis**

* **Python** >= 3.10  
* **pip** (gestionnaire de paquets Python)  
* **Git**  
* (Optionnel mais recommandé) Une base de données PostgreSQL

### **Installation du projet**

```bash
# Cloner le repository  
git clone [URL]
cd omnilog-backend

Installer uv
# Créer un environnement virtuel  
uv venv

# Activer l'environnement virtuel  
#Commande normalement affichée a l'écran

# Installer les dépendances  
uv pip install -e ".[dev]"

#Pour ajouter rapidement des trucs
uv pip install requests

Après avoir copié le fichier .env, **vous devez le remplir** avec vos propres configurations (voir section suivante).

#Lancer Redis + Postgres
docker run -d --name omnilog_db -e POSTGRES_USER=omnilog_user -e POSTGRES_PASSWORD=omnilog_password -e POSTGRES_DB=omnilog_db -p 5432:5432 postgres:15-alpine

docker run -d --name omnilog_redis -p 6379:6379 redis:7-alpine

# Copier le fichier d'environnement  
cp .env.example .env

alembic upgrade head

# Lancer le serveur avec rechargement automatique  
uvicorn app.main:app --reload
```

L'API sera accessible sur [http://localhost:8000](http://localhost:8000)

## **🔒 Variables d'environnement**

Le fichier .env est utilisé pour configurer l'application. Il est chargé au démarrage (typiquement via Pydantic Settings).

**Exemple de fichier .env :**

```json
# .env

# Application Settings
DEBUG=True
PROJECT_NAME="Omnilog API"
VERSION="1.0.0"

# Database Configuration
# Format: postgresql+asyncpg://username:password@host:port/database
DATABASE_URL=postgresql+asyncpg://omnilog_user:your_password@localhost:5432/omnilog_db

# Redis Configuration
REDIS_URL=redis://localhost:6379/0
REDIS_CACHE_TTL=3600

# Security / JWT
# Generate a secret key: openssl rand -hex 32
SECRET_KEY=your_super_secret_key_here_change_this_in_production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440
REFRESH_TOKEN_EXPIRE_DAYS=7

# TMDB API
TMDB_API_KEY=your_tmdb_api_key_here
TMDB_BASE_URL=https://api.themoviedb.org/3
TMDB_IMAGE_BASE_URL=https://image.tmdb.org/t/p

# OAuth - Google (Optional)
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=http://localhost:8000/api/v1/auth/google/callback

# OAuth - Facebook (Optional)
FACEBOOK_CLIENT_ID=
FACEBOOK_CLIENT_SECRET=
FACEBOOK_REDIRECT_URI=http://localhost:8000/api/v1/auth/facebook/callback

# OAuth - Apple (Optional)
APPLE_CLIENT_ID=
APPLE_CLIENT_SECRET=
APPLE_REDIRECT_URI=http://localhost:8000/api/v1/auth/apple/callback

# CORS Origins (comma-separated)
CORS_ORIGINS=["http://localhost:3000","http://localhost:5173","http://localhost:8080"]

# Cache Settings
TOP_MOVIES_CACHE_SIZE=500
```

## **📜 Scripts et Commandes**

| Commande | Description |  
| --- | --- |
| ``uvicorn app.main:app --reload`` | Lance le serveur de développement (auto-reload) |  
| ``pytest`` | Lance la suite de tests unitaires et d'intégration |  
| ``pytest --cov=app tests/`` | Lance la suite de tests avec coverage |  
| ``alembic upgrade head`` | Applique les dernières migrations à la base de données |  
| ``alembic revision --autogenerate -m "description"`` | Crée un nouveau fichier de migration basé sur les modèles |
| ``alembic dowgrade -1`` | Rollback |


## **🏗️ Architecture du projet**

```
omnilog-backend/
├── .env.example
├── .gitignore
├── .gitlab-ci.yml
├── .python-version
├── Dockerfile
├── README.md
├── alembic.ini
├── docker-compose.yml
├── pyproject.toml
│
├── alembic/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│
├── app/
│   ├── __init__.py
│   ├── main.py
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── router.py
│   │   └── endpoints/
│   │       ├── __init__.py
│   │       ├── auth.py          # Register, login, refresh token
│   │       ├── users.py         # User profile management
│   │       ├── media.py         # Media search & details
│   │       └── library.py       # Progress tracking
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py            # Settings & environment variables
│   │   ├── security.py          # JWT & password hashing
│   │   └── deps.py              # FastAPI dependencies
│   │
│   ├── crud/
│   │   ├── __init__.py
│   │   ├── crud_user.py         # User database operations
│   │   └── crud_media.py        # Media database operations
│   │
│   ├── db/
│   │   ├── __init__.py
│   │   ├── base.py              # SQLModel base
│   │   ├── models.py            # Database models
│   │   └── session.py           # Database session
│   │
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── user.py              # User Pydantic schemas
│   │   ├── media.py             # Media Pydantic schemas
│   │   └── token.py             # Auth token schemas
│   │
│   └── services/
│       ├── __init__.py
│       ├── auth_service.py      # OAuth
│       ├── tmdb_service.py      # TMDB API integration
│       └── redis_service.py     # Redis caching
│
└── tests/
    ├── conftest.py              # Test fixtures
    └── api/
        └── test_auth.py         # Authentication tests
```

```
FastAPI → PostgreSQL (async) → SQLModel ORM
       → Redis → Caching
       → TMDB API → Media data
```

## **🛠️ Technologies utilisées**

### **Backend**

* [**FastAPI**](https://fastapi.tiangolo.com/) - Framework API haute performance  
* [**Python 3.10+**](https://www.python.org/) - Langage de programmation  
* [**Pydantic**](https://docs.pydantic.dev/latest/) - Validation des données et gestion des settings  
* [**Uvicorn**](https://www.uvicorn.org/) - Serveur ASGI

### **Base de données**

* [**SQLAlchemy**](https://www.sqlalchemy.org/) - ORM SQL (mode asynchrone)  
* [**Alembic**](https://alembic.sqlalchemy.org/en/latest/) - Outil de migration de base de données  
* [**psycopg (asyncpg)**](https://www.psycopg.org/psycopg3/docs/basic/async.html) - Driver PostgreSQL asynchrone

### **Tests**

* [**Pytest**](https://pytest.org/) - Framework de test  
* [**TestClient**](https://fastapi.tiangolo.com/tutorial/testing/) - Client de test pour les applications ASGI

## **🗄️ Base de données & Migrations**

Nous utilisons **Alembic** (basé sur SQLAlchemy) pour gérer les migrations de schéma de la base de données.

### **Créer une nouvelle migration**

Après avoir modifié un modèle dans app/db/models.py :

```bash
# Générer automatiquement un fichier de migration  
alembic revision --autogenerate -m "Description concise de la modification"

# Exemple:  
# alembic revision --autogenerate -m "Ajout de la colonne 'last_login' au modèle User"

Vérifiez toujours le fichier de migration généré dans alembic/versions/ avant d appliquer.

### Appliquer les migrations

Pour mettre à jour votre base de données vers la dernière version :

alembic upgrade head
```

## **🧪 Tests**

Les tests sont écrits avec Pytest et se trouvent dans le dossier tests/. Ils utilisent TestClient pour envoyer des requêtes HTTP à l'API sans passer par un vrai serveur.

### **Lancer les tests**

```bash
pytest #sans coverage
pytest --cov=app tests/ #avec coverage
```


## **📚 Documentation de l'API**

FastAPI génère automatiquement une documentation interactive de l'API. Une fois le serveur lancé (uvicorn app.main:app --reload), vous pouvez y accéder :

* Documentation Swagger UI :  
  http://localhost:8000/docs  
* Documentation ReDoc :  
  http://localhost:8000/redoc

Cette documentation est générée à partir des endpoints, des modèles Pydantic et des docstrings.