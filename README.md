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

# Copier le fichier d'environnement  
cp .env.example .env

Après avoir copié le fichier .env, **vous devez le remplir** avec vos propres configurations (voir section suivante).

# Lancer le serveur avec rechargement automatique  
uvicorn app.main:app --reload
```

L'API sera accessible sur [http://localhost:8000](http://localhost:8000)

## **🔒 Variables d'environnement**

Le fichier .env est utilisé pour configurer l'application. Il est chargé au démarrage (typiquement via Pydantic Settings).

**Exemple de fichier .env :**

```json
# .env

# Configuration de la base de données (exemple PostgreSQL)  
# Format: "postgresql+asyncpg://USER:PASSWORD@HOST:PORT/DB_NAME"  
DATABASE_URL="postgresql+asyncpg://omnilog_user:secret_password@localhost:5432/omnilog_db"

# Sécurité (JWT)  
# Générer une clé secrète forte (ex: openssl rand -hex 32)  
JWT_SECRET_KEY="votre_cle_secrete_tres_tres_longue_de_32_octets"  
JWT_ALGORITHM="HS256"  
ACCESS_TOKEN_EXPIRE_MINUTES=60

# Mode debug de l'application  
DEBUG=True
```

## **📜 Scripts et Commandes**

| Commande | Description |  
| --- | --- |
| ``uvicorn app.main:app --reload`` | Lance le serveur de développement (auto-reload) |  
| ``pytest`` | Lance la suite de tests unitaires et d'intégration |  
| ``alembic upgrade head`` | Applique les dernières migrations à la base de données |  
| ``alembic revision --autogenerate -m "..."`` | Crée un nouveau fichier de migration basé sur les modèles |


## **🏗️ Architecture du projet**

```
omnilog-backend/  
├── alembic/                    # Fichiers de migration Alembic  
│   ├── versions/               # Fichiers de migration auto-générés  
│   └── env.py                  # Configuration d'exécution d'Alembic  
├── app/                        # Cœur de l'application FastAPI  
│   ├── __init__.py  
│   ├── api/                    # Routers et endpoints de l'API  
│   │   ├── __init__.py  
│   │   └── v1/                 # Version 1 de l'API  
│   │       ├── __init__.py  
│   │       ├── endpoints/      # Fichiers par ressource (auth.py, users.py)  
│   │       └── router.py       # Agrégation des routers v1  
│   ├── core/                   # Configuration et sécurité  
│   │   ├── __init__.py  
│   │   ├── config.py           # Chargement du .env (Pydantic Settings)  
│   │   └── security.py         # Gestion JWT, hash de mots de passe  
│   ├── crud/                   # Fonctions CRUD (logique base de données)  
│   │   ├── __init__.py  
│   │   └── crud_user.py  
│   ├── db/                     # Session et modèles SQLAlchemy  
│   │   ├── __init__.py  
│   │   ├── base.py             # Classe de base déclarative (Base)  
│   │   ├── models.py           # Modèles SQLAlchemy (tables)  
│   │   └── session.py          # Gestion de la session (dépendance)  
│   ├── schemas/                # Modèles Pydantic (validation des données)  
│   │   ├── __init__.py  
│   │   ├── token.py  
│   │   └── user.py             # Schémas UserCreate, UserRead, etc.  
│   ├── services/               # Logique métier complexe  
│   │   ├── __init__.py  
│   │   └── auth_service.py  
│   └── main.py                 # Point d'entrée de l'app (FastAPI factory)  
├── tests/                      # Tests Pytest  
│   ├── __init__.py  
│   ├── api/                    # Tests par endpoint  
│   │   └── test_auth.py  
│   ├── crud/                   # Tests des fonctions CRUD  
│   └── conftest.py             # Fixtures Pytest (TestClient, session DB)  
├── .env.example                # Fichier d'exemple pour l'environnement  
├── .gitignore  
├── alembic.ini                 # Configuration générale d'Alembic  
├── requirements.txt            # Dépendances Python  
├── pyproject.toml              # Configuration Black, Ruff, Pytest  
└── README.md
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

```
pytest
```

**Exemple de test (Pytest) :**

```py
# tests/api/test_auth.py  
from fastapi.testclient import TestClient  
from app.main import app

client = TestClient(app)

def test_login_success():  
    # Note : Nécessite une fixture pour créer un utilisateur au préalable  
    response = client.post(  
        "/api/v1/auth/token",  
        data={"username": "testuser@example.com", "password": "testpassword"}  
    )  
    assert response.status_code == 200  
    data = response.json()  
    assert "access_token" in data  
    assert data["token_type"] == "bearer"

def test_login_invalid_password():  
    response = client.post(  
        "/api/v1/auth/token",  
        data={"username": "testuser@example.com", "password": "wrongpassword"}  
    )  
    assert response.status_code == 401  
    assert response.json() == {"detail": "Incorrect username or password"}
```

## **📚 Documentation de l'API**

FastAPI génère automatiquement une documentation interactive de l'API. Une fois le serveur lancé (uvicorn app.main:app --reload), vous pouvez y accéder :

* Documentation Swagger UI :  
  http://localhost:8000/docs  
* Documentation ReDoc :  
  http://localhost:8000/redoc

Cette documentation est générée à partir de vos endpoints, des modèles Pydantic et des docstrings.