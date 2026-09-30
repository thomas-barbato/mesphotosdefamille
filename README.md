# Mes photos de famille

Un album de famille privé, en Python/Django. Deux dépendances : **Django et Pillow**.
SQLite, HTML, CSS et JavaScript natif : aucun npm, framework frontend ou service externe.

## Fonctionnalités

- Connexion obligatoire, y compris pour accéder directement aux fichiers des photos.
- Comptes créés par l’administrateur dans `/admin/`, sans inscription publique.
- Album commun aux utilisateurs connectés, catégories et recherche dans les légendes.
- Envoi de 1 à 12 photos avec aperçu, glisser-déposer, légende et catégorie facultatives.
- Conversion JPEG/PNG/WebP vers WebP, correction de l’orientation et suppression des métadonnées EXIF/GPS.
- Photo limitée à 2 560 pixels sur son plus grand côté, qualité 82 ; miniature de 600 pixels, qualité 75.
- Seules la photo convertie et sa miniature sont conservées. L’original n’est pas stocké.
- Limites d’envoi : 20 Mo et 40 mégapixels par photo. Images fixes uniquement.
- Galerie paginée (24 photos), miniatures chargées à la demande, vue en grand avec flèches et Échap.
- Modification et suppression par l’auteur de la photo ou un administrateur.
- Ajout de photos et catégories sans rechargement : la galerie et ses filtres se mettent à jour automatiquement.
- Les formulaires classiques suivent **POST → redirection → GET**, même en cas d’erreur : F5 ne renvoie pas le formulaire.
- Les boutons d’envoi sont bloqués pendant la requête pour éviter les doubles clics.

L’album est partagé entre tous les comptes actifs de ce site. Il n’y a pas d’albums privés par utilisateur.
Supprimer une catégorie depuis l’administration conserve ses photos, désormais sans catégorie.
Supprimer une photo libère aussi l’espace de ses deux fichiers.

## Démarrer sur Windows

Python 3.10 à 3.14.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py createsuperuser
.\.venv\Scripts\python.exe manage.py runserver
```

Ouvrir <http://127.0.0.1:8000/>, se connecter avec le compte créé, puis utiliser
<http://127.0.0.1:8000/admin/auth/user/add/> pour créer les autres comptes.
Pour un utilisateur ordinaire, garder « Actif » coché et laisser « Équipe » et « Super-utilisateur » décochés.
Les comptes ordinaires peuvent ajouter des photos et des catégories depuis la galerie.

En local, sans `.env`, le mode développement est actif. Ne pas utiliser `runserver` pour héberger le site public.

## Héberger sur PythonAnywhere

La configuration vise **https://mesphotosdefamille.pythonanywhere.com/**.
Ce dépôt ne déploie rien automatiquement.

La base est déjà configurée en **SQLite**, disponible aussi sur les comptes gratuits de PythonAnywhere. `python manage.py migrate` crée `db.sqlite3`, qui contient les comptes, catégories et légendes ; les images restent dans `media/`. Aucun serveur MySQL ou PostgreSQL n’est nécessaire. Ce choix convient à un petit album familial avec peu d’écritures simultanées.
Voir les [bases disponibles sur PythonAnywhere](https://help.pythonanywhere.com/pages/KindsOfDatabases/).

1. Copier le projet dans `/home/mesphotosdefamille/mesphotosdefamille`.
2. Dans une console Bash PythonAnywhere, choisir une version de Python disponible, identique à celle de la Web app. Exemple avec Python 3.13 :

   ```bash
   cd /home/mesphotosdefamille/mesphotosdefamille
   mkvirtualenv --python=/usr/bin/python3.13 mesphotosdefamille
   python -m pip install -r requirements.txt
   python -m pip check
   cp .env.example .env
   python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
   ```

3. Modifier `.env` et copier la clé générée dans `DJANGO_SECRET_KEY`. Conserver `DJANGO_DEBUG=0` et le domaine prévu dans `DJANGO_ALLOWED_HOSTS`. Le fichier `.env` est lu automatiquement et ignoré par Git ; une variable d’environnement existante prend priorité.

   ```bash
   python manage.py migrate
   python manage.py createsuperuser
   python manage.py collectstatic --noinput
   python manage.py check --deploy
   ```

4. Dans l’onglet **Web**, créer l’application avec **Manual configuration**, la même version de Python et le virtualenv `/home/mesphotosdefamille/.virtualenvs/mesphotosdefamille`.
5. Dans le fichier WSGI lié par l’onglet Web, copier le contenu de [`deploy/pythonanywhere_wsgi.py`](deploy/pythonanywhere_wsgi.py). Adapter le chemin si nécessaire. Le nom de configuration Django est `config.settings`.
6. Ajouter **uniquement** cette correspondance de fichiers statiques :

   | URL | Répertoire |
   | --- | --- |
   | `/static/` | `/home/mesphotosdefamille/mesphotosdefamille/staticfiles` |

   **Ne créer aucune correspondance `/media/`, `/photos/` ou `/thumbnails/`**, et ne pas publier le répertoire du projet. Les photos doivent passer par les vues Django qui contrôlent la connexion. Une correspondance publique contournerait cette protection.

7. Activer **Force HTTPS** dans l’onglet Web puis cliquer sur **Reload**. Le site active également les cookies sécurisés et la redirection HTTPS en production.
8. Tester une connexion, un envoi, une création de catégorie et la vue en grand. Depuis une fenêtre privée déconnectée, vérifier qu’un lien direct `/photos/…/grande.webp` redirige vers la connexion.

Pour une mise à jour : réinstaller les dépendances si nécessaire, exécuter `migrate`, `collectstatic --noinput`, puis **Reload**.
Le quota disque de l’hébergement reste à surveiller : la conversion réduit la taille, mais ne rend pas le stockage illimité.

Guides officiels : [déploiement Django](https://help.pythonanywhere.com/pages/DeployExistingDjangoProject/), [fichiers statiques](https://help.pythonanywhere.com/pages/DjangoStaticFiles/).
La configuration des photos privées ci-dessus remplace la correspondance publique habituelle des fichiers média.

### Si pip signale un conflit entre MoviePy et Pillow

Ce site n’utilise pas MoviePy. Ce message indique que l’environnement d’installation contient aussi des packages extérieurs au projet, par exemple les packages préinstallés de PythonAnywhere. Utiliser un environnement réservé au site pour isoler ses dépendances.

Dans une console Bash, créer un nouvel environnement. L’exemple utilise Python 3.13 : remplacer cette version par celle affichée dans l’onglet **Web** si nécessaire.

```bash
cd /home/mesphotosdefamille/mesphotosdefamille
mkvirtualenv mesphotosdefamille-web --python=/usr/bin/python3.13
python -m pip install -r requirements.txt
python -m pip check
```

`mkvirtualenv` active automatiquement le nouvel environnement. Pour le réactiver dans une autre console : `workon mesphotosdefamille-web`.
`python -m pip check` doit afficher `No broken requirements found.`

Dans **Web → Virtualenv**, indiquer `/home/mesphotosdefamille/.virtualenvs/mesphotosdefamille-web`, puis cliquer sur **Reload**.
Installer les dépendances sans `--user` et sans `--system-site-packages`. Conserver les versions de `requirements.txt` : aucune mise à jour de MoviePy n’est nécessaire pour ce site.

## Sauvegarder les souvenirs

Sauvegarder ensemble `db.sqlite3` (comptes, catégories, légendes), `media/` (photos et miniatures) et la clé secrète `.env`.
Pour une sauvegarde cohérente de SQLite, utiliser son API de sauvegarde, par exemple :

```bash
python -c "import sqlite3; source=sqlite3.connect('db.sqlite3'); target=sqlite3.connect('album-backup.sqlite3'); source.backup(target); target.close(); source.close()"
```

Copier ensuite `media/` pendant une période sans envoi ni suppression de photos. Conserver les sauvegardes hors du répertoire public.

## Vérifier le projet

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
```

Les tests couvrent la confidentialité, la conversion, l’orientation, les limites d’envoi, le nettoyage en cas d’échec, les catégories, les droits, le CSRF et les redirections après formulaire.
La CI GitHub Actions exécute ces vérifications avec Python 3.10 et 3.14. Elle ne publie pas le site.

## Organisation

```text
config/       configuration Django et WSGI
gallery/      modèles, formulaires, conversion, vues, tests
templates/    pages françaises
static/       CSS, JavaScript et icône SVG locaux
deploy/       exemple WSGI PythonAnywhere
```
