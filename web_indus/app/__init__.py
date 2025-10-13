from flask import Flask, redirect, url_for
from flask_sqlalchemy import SQLAlchemy


import os

# Instance globale de la base de données
db = SQLAlchemy()

def create_app(config_name='default'):
    app = Flask(__name__)
    
    # Configuration
    from config import config
    app.config.from_object(config[config_name])
    
    # Configuration sessions sécurisées
    app.config['PERMANENT_SESSION_LIFETIME'] = 14400  # 4 heures
    
    # Initialisation des extensions
    db.init_app(app)
    
    # Import et initialisation de l'automate
    try:
        from app.controleur.controleur_tags import init_automate
        init_automate(app)
    except ImportError:
        print("Module automate non disponible")
    
    # Import et enregistrement des blueprints
    from app.controleur import main_bp
    app.register_blueprint(main_bp)
    
    # Configuration du middleware d'authentification
    from app.controleur.controleur_auth import setup_auth_middleware
    setup_auth_middleware(app)
    
    # Route racine redirige vers gestion projets
    @app.route('/')
    def root():
        from app.models.modele_auth import AuthSystem
        if AuthSystem.is_user_logged_in():
            return redirect(url_for('main.projects_management'))
        else:
            return redirect(url_for('main.login'))
    
    # Création des tables
    with app.app_context():
        try:
            # Import des modèles
            from app.models.modele_tag import Tag
            from app.models.modele_graphics import Page, Animation, ContenirAnimation
            from app.models.modele_projects import ProjectManager
            
            db.create_all()
            print("Tables de base de données créées/vérifiées")
            
            # Initialiser l'authentification
            from app.controleur.controleur_user_management import init_user_management
            init_user_management()
            
            # ✅ CORRIGÉ : Créer un projet par défaut si aucun existe
            from app.models.modele_tag import HMIProject
            if HMIProject.query.count() == 0:
                project_data = {
                    'nom_projet': 'IHM_Industrielle_Arthur',
                    'version_projet': '1.0'
                }
                success, message = ProjectManager.create_project(project_data)
                if success:
                    print("Projet par défaut créé")
                    
                    # ✅ CORRIGÉ : Récupérer le projet créé et créer les données liées
                    default_project = HMIProject.query.filter_by(
                        nom_projet='IHM_Industrielle_Arthur'
                    ).first()
                    
                    if default_project:
                        # ⚠️ IMPORTANT : Simuler une session pour les fonctions de création
                        from flask import session
                        with app.test_request_context():
                            session['current_project_id'] = default_project.id_projet
                            
                            # Créer les tags par défaut DANS CE PROJET
                            from app.controleur.controleur_tags import creer_tags_siemens_defaut
                            tags_crees = creer_tags_siemens_defaut()
                            print(f"Tags par défaut créés dans le projet {default_project.id_projet}")
                            
                            # Créer une page par défaut DANS CE PROJET
                            from app.models.modele_graphics import creer_page_defaut
                            page_creee = creer_page_defaut()
                            if page_creee:
                                print(f"Page par défaut créée dans le projet {default_project.id_projet}")
                        
                        print(f"✅ Projet par défaut complètement initialisé : ID {default_project.id_projet}")
            
            else:
                print("Des projets existent déjà - pas d'initialisation automatique")
                
                # ⚠️ ATTENTION : Ne plus créer de tags/pages globaux !
                # Les anciennes versions créaient des tags sans projet
                # Il faut les nettoyer ou les migrer
                
                # Détecter les données orphelines (sans projet)
                orphan_tags = Tag.query.filter_by(id_projet=None).count()
                orphan_pages = Page.query.filter_by(id_projet=None).count()
                
                if orphan_tags > 0 or orphan_pages > 0:
                    print(f"⚠️ ATTENTION : {orphan_tags} tags et {orphan_pages} pages sans projet détectés")
                    print("Considérez lancer la migration des données orphelines")
                
        except Exception as e:
            print(f"Erreur initialisation: {e}")
            import traceback
            traceback.print_exc()
    
    return app

# NOUVELLE FONCTION : Migrer les données orphelines vers un projet
def migrer_donnees_orphelines_vers_projet(app, project_id):
    """Migre les tags et pages sans projet vers un projet spécifique"""
    with app.app_context():
        try:
            # Migrer les tags orphelins
            orphan_tags = Tag.query.filter_by(id_projet=None).all()
            for tag in orphan_tags:
                tag.id_projet = project_id
            
            # Migrer les pages orphelines
            orphan_pages = Page.query.filter_by(id_projet=None).all()
            for page in orphan_pages:
                page.id_projet = project_id
            
            db.session.commit()
            
            print(f"✅ Migration terminée : {len(orphan_tags)} tags et {len(orphan_pages)} pages migrés vers le projet {project_id}")
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Erreur migration : {e}")

# NOUVELLE FONCTION : Nettoyer les données orphelines
def nettoyer_donnees_orphelines(app):
    """Supprime les données sans projet (ATTENTION : destructeur)"""
    with app.app_context():
        try:
            # Compter d'abord
            orphan_tags = Tag.query.filter_by(id_projet=None).count()
            orphan_pages = Page.query.filter_by(id_projet=None).count()
            
            print(f"⚠️ SUPPRESSION : {orphan_tags} tags et {orphan_pages} pages orphelines")
            
            # Supprimer
            Tag.query.filter_by(id_projet=None).delete()
            Page.query.filter_by(id_projet=None).delete()
            
            db.session.commit()
            print("✅ Données orphelines supprimées")
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Erreur suppression : {e}")