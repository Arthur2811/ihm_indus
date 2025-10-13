# =================================================================
# MODIFICATIONS À AJOUTER DANS config.py
# =================================================================

import os
import secrets
from dotenv import load_dotenv
from urllib.parse import quote_plus

load_dotenv()

class ConfigSimple:
    # Flask
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-key-change-me')
    DEBUG = True
    
    # Configuration sessions sécurisées
    PERMANENT_SESSION_LIFETIME = 14400  # 4 heures
    SESSION_COOKIE_SECURE = False  # True en production avec HTTPS
    SESSION_COOKIE_HTTPONLY = True  # Empêche l'accès JavaScript
    SESSION_COOKIE_SAMESITE = 'Lax'  # Protection CSRF
    
    # Base de données MySQL - Construction automatique
    @staticmethod
    def get_database_url():
        db_host = os.environ.get('DB_HOST')
        db_name = os.environ.get('DB_NAME')
        db_user = os.environ.get('DB_USER')
        db_password = os.environ.get('DB_PASSWORD')
        db_port = os.environ.get('DB_PORT')
        
        # Encoder le mot de passe pour le caractère #
        encoded_password = quote_plus(db_password)
        
        return f"mysql+pymysql://{db_user}:{encoded_password}@{db_host}:{db_port}/{db_name}"
    
    # Configuration SQLAlchemy
    SQLALCHEMY_DATABASE_URI = get_database_url.__func__()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = False
    
    # Configuration Automate
    AUTOMATE_IP = os.environ.get('AUTOMATE_IP_DEFAULT', '192.168.0.1')
    AUTOMATE_RACK = int(os.environ.get('AUTOMATE_RACK_DEFAULT', '0'))
    AUTOMATE_SLOT = int(os.environ.get('AUTOMATE_SLOT_DEFAULT', '1'))
    AUTOMATE_PORT = 102
    MODE_COMMUNICATION = os.environ.get('MODE_COMMUNICATION', 'REEL')
    TIMEOUT_CONNEXION = int(os.environ.get('TIMEOUT_CONNEXION', '10'))
    VALIDATION_PING = True
    
    # Configuration IHM
    PROJET_PAR_DEFAUT = "IHM_Industrielle_Arthur"
    VERSION_PROJET = "1.0"

# Configuration pour la production
class ConfigProduction(ConfigSimple):
    """Configuration sécurisée pour la production"""
    DEBUG = False
    SECRET_KEY = os.environ.get('SECRET_KEY') or secrets.token_hex(32)
    
    # Sessions sécurisées pour production
    SESSION_COOKIE_SECURE = True      # HTTPS uniquement
    SESSION_COOKIE_HTTPONLY = True    # Pas d'accès JavaScript
    SESSION_COOKIE_SAMESITE = 'Lax'   # Protection CSRF
    
    # Mode communication par défaut en production
    MODE_COMMUNICATION = os.environ.get('MODE_COMMUNICATION', 'SIMULATEUR')
    
    # Logging en production
    SQLALCHEMY_ECHO = False

# Configuration pour les tests
class ConfigTesting(ConfigSimple):
    """Configuration pour les tests"""
    TESTING = True
    DEBUG = False
    WTF_CSRF_ENABLED = False
    
    # Base de données en mémoire pour les tests
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    
    # Sessions de test
    PERMANENT_SESSION_LIFETIME = 300  # 5 minutes pour tests

# Configuration par défaut
config = {
    'development': ConfigSimple,
    'production': ConfigProduction,
    'testing': ConfigTesting,          
    'default': ConfigSimple
}