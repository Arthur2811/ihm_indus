# 🏭 IHM Industrielle Arthur - Communication Ethernet/IP

Interface Homme-Machine industrielle pour automates Allen-Bradley via protocole Ethernet/IP.

## 🎯 Fonctionnalités

- ✅ **Communication Ethernet/IP** avec automates Allen-Bradley (CompactLogix, ControlLogix)
- ✅ **Interface web temps réel** avec rafraîchissement automatique
- ✅ **Lecture/Écriture de tags** industriels (BOOL, INT, REAL, STRING)
- ✅ **Mode simulation intégré** pour tests sans automate
- ✅ **Base de données MySQL** pour persistance des données
- ✅ **API REST** complète pour intégrations externes
- ✅ **Containerisation Docker** pour déploiement facile

## 🚀 Installation Rapide

### Prérequis
- Python 3.10+ ou Docker
- MySQL 8.0+ (ou via Docker)
- Automate Allen-Bradley compatible Ethernet/IP

### Option 1: Installation locale

```bash
# 1. Cloner le projet
git clone https://github.com/arthur/ihm-industrielle.git
cd ihm-industrielle

# 2. Créer l'environnement virtuel
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# ou .venv\Scripts\activate  # Windows

# 3. Installer les dépendances
pip install -r requirements.txt

# 4. Configurer l'environnement
cp .env.example .env
# Éditer .env avec vos paramètres

# 5. Initialiser la base de données
python app.py init-db

# 6. Démarrer l'application
python app.py
```

### Option 2: Docker (Recommandé)

```bash
# 1. Cloner et configurer
git clone https://github.com/arthur/ihm-industrielle.git
cd ihm-industrielle
cp .env.example .env
# Éditer .env avec vos paramètres

# 2. Démarrer la stack complète
docker-compose up -d

# 3. Accéder à l'interface
# http://localhost:5000 - IHM principale
# http://localhost:8080 - phpMyAdmin (optionnel)
```

## ⚙️ Configuration

### Fichier .env

```bash
# Base de données
BD_HOTE=localhost
BD_PORT=3306
BD_UTILISATEUR=arthur
BD_MOT_DE_PASSE=votre_mot_de_passe
BD_NOM=ihm_indus

# Flask
CLE_SECRETE=votre-cle-secrete-unique
MODE_DEBUG=True

# Automate
AUTOMATE_IP=192.168.1.10
AUTOMATE_PORT=44818
MODE_COMMUNICATION=ETHERNET_IP  # ou SIMULATEUR
TIMEOUT_CONNEXION=10

# Tags de test
TAG_TEST_BOOL=Program:MainProgram.TestBool
TAG_TEST_INT=Program:MainProgram.TestInt
TAG_TEST_REAL=Program:MainProgram.TestReal
```

### Configuration Automate

**Pour CompactLogix/ControlLogix :**
1. Activer le serveur Ethernet/IP dans RSLogix 5000
2. Configurer l'adresse IP dans le module Ethernet
3. Créer vos tags dans le programme principal
4. Tester la connectivité réseau

## 📡 Communication Automate

### Formats d'adresses supportés

```python
# Format Studio 5000 standard
"Program:MainProgram.MonTag"
"Program:Production.Temperature"
"Controller:Status.Outputs"

# Format simple (si supporté par votre automate)
"MonTag"
"Temperature" 
"Status"

# Types de données supportés
BOOL    # Booléen (True/False)
INT     # Entier 16-bit (-32768 à 32767)
REAL    # Réel 32-bit (float)
STRING  # Chaîne de caractères
```

### Exemple de programme automate (Ladder)

```
// Programme principal - MainProgram
TestBool        BOOL    := FALSE;       // Tag test booléen
TestInt         INT     := 42;          // Tag test entier  
TestReal        REAL    := 25.7;        // Tag test réel
Compteur        INT     := 0;           // Compteur automatique
Temperature     REAL    := 22.5;        // Température simulée
```

## 🌐 Interface Web

### Fonctionnalités principales

- **Dashboard temps réel** avec statistiques
- **Visualisation des tags** avec valeurs actuelles
- **Écriture interactive** pour les tags en R/W
- **Historique des lectures** avec timestamps
- **Mode pause/reprise** du rafraîchissement
- **Export JSON** des configurations

### Raccourcis clavier

- `Ctrl+R` : Rafraîchir manuellement
- `Ctrl+Space` : Pause/Reprendre le rafraîchissement automatique
- `Ctrl+N` : Créer un nouveau tag

## 🔌 API REST

### Endpoints disponibles

```bash
# Liste tous les tags
GET /api/tags

# Lire un tag spécifique
GET /api/read/MonTag

# Écrire un tag
POST /api/write/MonTag
Content-Type: application/json
{"valeur": true}

# Lire tous les tags actifs
GET /api/read_all

# Statut de l'automate
GET /api/status

# Créer un nouveau tag
POST /api/tags/create
Content-Type: application/json
{
  "nom_tag": "NouveauTag",
  "adresse_tag": "Program:MainProgram.NouveauTag",
  "type_donnee": "BOOL",
  "acces": "RW"
}

# Supprimer un tag
DELETE /api/tags/123
```

## 🗄️ Structure de Base de Données

### Table Tag (principale)

```sql
CREATE TABLE tag (
    id_tag INT AUTO_INCREMENT PRIMARY KEY,
    nom_tag VARCHAR(100) NOT NULL,
    adresse_tag VARCHAR(100) NOT NULL,
    type_donnee VARCHAR(20) NOT NULL,
    description_tag TEXT,
    acces VARCHAR(10) DEFAULT 'R',
    valeur_courante VARCHAR(50),
    qualite VARCHAR(20) DEFAULT 'GOOD',
    timestamp_lecture DATETIME,
    historisation_active BOOLEAN DEFAULT FALSE,
    alarmes_actives BOOLEAN DEFAULT FALSE,
    date_creation DATETIME DEFAULT CURRENT_TIMESTAMP,
    date_modification DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    actif BOOLEAN DEFAULT TRUE
);
```

## 🐳 Déploiement Docker

### Services inclus

```yaml
services:
  web:        # Application Flask IHM (port 5000)
  mysql:      # Base de données (port 3306)  
  phpmyadmin: # Interface DB (port 8080) [optionnel]
  prometheus: # Monitoring (port 9090) [optionnel]
  grafana:    # Dashboards (port 3000) [optionnel]
```

### Commandes utiles

```bash
# Démarrage complet
docker-compose up -d

# Avec monitoring
docker-compose --profile monitoring up -d

# Avec administration DB
docker-compose --profile admin up -d

# Logs en temps réel
docker-compose logs -f web

# Redémarrage après modification
docker-compose restart web

# Arrêt complet
docker-compose down

# Nettoyage complet (ATTENTION: supprime les données)
docker-compose down -v
```

## 🔧 Développement

### Structure du projet

```
ihm-industrielle/
├── app/
│   ├── __init__.py           # Factory Flask
│   ├── controleur/
│   │   ├── __init__.py
│   │   └── controleur_tags.py # Logique métier
│   ├── models/
│   │   ├── __init__.py
│   │   └── modele_tag.py     # Modèle Tag SQLAlchemy
│   └── templates/
│       └── test_automate.html # Interface web
├── config.py                 # Configuration Flask
├── app.py                   # Point d'entrée principal
├── requirements.txt         # Dépendances Python
├── .env                    # Configuration environnement
├── Dockerfile              # Image Docker
├── docker-compose.yml      # Stack complète
└── README.md              # Documentation
```

### Lancer en mode développement

```bash
# Activation de l'environnement virtuel
source .venv/bin/activate

# Variables d'environnement
export FLASK_ENV=development
export FLASK_DEBUG=True

# Démarrage avec rechargement automatique
python app.py

# Ou avec Flask CLI
flask run --reload --debugger
```

## 🛠️ Dépannage

### Problèmes courants

**Erreur de connexion automate :**
```bash
# Vérifier la connectivité réseau
ping 192.168.1.10

# Tester le port Ethernet/IP
telnet 192.168.1.10 44818

# Vérifier la configuration automate
# - Module Ethernet configuré ?
# - Serveur Ethernet/IP activé ?
# - Tags existants dans le programme ?
```

**Erreur base de données :**
```bash
# Vérifier MySQL
mysql -h localhost -u arthur -p ihm_indus

# Recréer la base de données
docker-compose exec mysql mysql -u root -p
> DROP DATABASE ihm_indus;
> CREATE DATABASE ihm_indus;
> GRANT ALL ON ihm_indus.* TO 'arthur'@'%';

# Réinitialiser les tables
python app.py init-db
```

**Mode simulation ne fonctionne pas :**
```bash
# Forcer le mode simulation
export MODE_COMMUNICATION=SIMULATEUR

# Vérifier les logs
docker-compose logs web

# Redémarrer l'application
docker-compose restart web
```

**Interface web inaccessible :**
```bash
# Vérifier les ports
netstat -tulpn | grep :5000

# Vérifier les logs Flask
tail -f logs/app.log

# Tester l'API directement
curl http://localhost:5000/api/status
```

### Logs et debugging

```bash
# Logs Docker Compose
docker-compose logs -f web

# Logs dans le conteneur
docker-compose exec web tail -f /app/logs/app.log

# Debug interactif
docker-compose exec web python
>>> from app import create_app, db
>>> from app.models.modele_tag import Tag
>>> app = create_app()
>>> with app.app_context():
...     tags = Tag.query.all()
...     print(f"Tags trouvés: {len(tags)}")
```

## 📊 Monitoring et Performance

### Métriques disponibles

- **Temps de cycle** de lecture des tags
- **Nombre de tags actifs** en temps réel
- **Qualité des communications** automate
- **Statistiques de connexion** réseau
- **Performance de l'interface** (temps de réponse)

### Configuration Prometheus

```yaml
# monitoring/prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'ihm-industrielle'
    static_configs:
      - targets: ['web:5000']
    metrics_path: '/metrics'
    scrape_interval: 5s
```

### Dashboards Grafana

Les dashboards prédéfinis incluent :
- **Vue d'ensemble système** (CPU, mémoire, réseau)
- **Performance communication** automate
- **Historique des valeurs** de tags
- **Alertes** en cas de dysfonctionnement

## 🔐 Sécurité

### Bonnes pratiques

1. **Changez les mots de passe par défaut**
2. **Utilisez HTTPS en production** (certificat SSL)
3. **Configurez un firewall** pour les ports industriels
4. **Sauvegardez régulièrement** la base de données
5. **Surveillez les logs** pour détecter des anomalies

### Configuration production

```bash
# Variables d'environnement production
MODE_DEBUG=False
CLE_SECRETE=cle-aleatoire-securisee-longue
FLASK_ENV=production

# SSL/TLS (recommandé)
SSL_CERT=/path/to/cert.pem
SSL_KEY=/path/to/key.pem

# Reverse proxy (nginx/apache)
# Voir documentation séparée
```

## 📈 Évolutions Futures

### Roadmap

- [ ] **Support multi-protocoles** (Modbus TCP, OPC-UA)
- [ ] **Interface graphique avancée** (synoptiques, HMI)
- [ ] **Système d'alarmes** complet
- [ ] **Historisation** longue durée
- [ ] **Rapports automatiques** (PDF, Excel)
- [ ] **API GraphQL** pour requêtes complexes
- [ ] **Support mobile** (PWA)
- [ ] **Authentification utilisateurs** (LDAP, OAuth)

### Architecture extensible

```python
# Ajout d'un nouveau protocole
class ModbusClient(ProtocolInterface):
    def connect(self, ip, port=502):
        # Implémentation Modbus TCP
        pass
    
    def read_tag(self, address):
        # Lecture registre Modbus
        pass

# Enregistrement dynamique
protocol_manager.register('MODBUS', ModbusClient)
```

## 👥 Contribution

### Comment contribuer

1. **Fork** le projet
2. **Créez une branche** pour votre fonctionnalité
3. **Committez** vos changements
4. **Poussez** vers la branche
5. **Ouvrez une Pull Request**

### Standards de code

```bash
# Formatage avec black
black app/ config.py app.py

# Vérification avec flake8
flake8 app/ --max-line-length=88

# Tests unitaires
pytest tests/ -v --cov=app
```

## 📞 Support

### Contact

- **Email** : arthur@ihmindustrielle.fr
- **GitHub** : [Issues](https://github.com/arthur/ihm-industrielle/issues)
- **Documentation** : [Wiki](https://github.com/arthur/ihm-industrielle/wiki)

### FAQ

**Q: Puis-je utiliser avec des automates Siemens ?**
R: Pas directement. Installez `python-snap7` et adaptez le contrôleur.

**Q: Comment sauvegarder mes configurations ?**
R: Utilisez l'export JSON ou sauvegardez la base MySQL.

**Q: L'interface est-elle utilisable sur mobile ?**
R: Oui, l'interface est responsive et fonctionne sur tablette/mobile.

**Q: Peut-on avoir plusieurs automates ?**
R: Actuellement non, mais c'est prévu dans la roadmap.

## 📄 Licence

```
MIT License

Copyright (c) 2025 Arthur - IHM Industrielle

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

**🏭 IHM Industrielle Arthur - Connectez votre industrie au futur !**