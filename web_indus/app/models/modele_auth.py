from functools import wraps
from flask import session, redirect, url_for, request, jsonify, flash, current_app
from app.models.modele_user_management import UserManagement
from datetime import datetime, timedelta
import secrets

class AuthSystem:
    
    # =================================================================
    # COMPTE ADMIN EN DUR (FALLBACK SI BDD CASSÉE)
    # =================================================================
    
    HARDCODED_ADMIN = {
        'username': 'root',
        'password': 'Industrial123!',  # Mot de passe fort
        'role': 'ADMIN',
        'role_level': 3,
        'nom_complet': 'Administrateur Root'
    }
    
    @staticmethod
    def authenticate_hardcoded_admin(username, password):
        """Authentification admin en dur (fallback)"""
        if (username == AuthSystem.HARDCODED_ADMIN['username'] and 
            password == AuthSystem.HARDCODED_ADMIN['password']):
            return True, {
                'id': -1,  # ID spécial pour admin en dur
                'username': username,
                'nom_complet': AuthSystem.HARDCODED_ADMIN['nom_complet'],
                'role': AuthSystem.HARDCODED_ADMIN['role'],
                'role_level': AuthSystem.HARDCODED_ADMIN['role_level'],
                'is_hardcoded': True
            }
        return False, None
    
    # =================================================================
    # AUTHENTIFICATION PRINCIPALE
    # =================================================================
    
    @staticmethod
    def authenticate_user(username, password):
        """Authentifier un utilisateur (BDD + fallback admin)"""
        try:
            from app.models.modele_tag import Utilisateur, Role
            from app import db
            
            # 1. Essayer l'admin en dur d'abord
            hardcoded_success, hardcoded_user = AuthSystem.authenticate_hardcoded_admin(username, password)
            if hardcoded_success:
                print(f"[AUTH] Connexion admin en dur: {username}")
                return True, hardcoded_user, "Authentification admin en dur réussie"
            
            # 2. Authentification base de données
            user_data = db.session.query(Utilisateur, Role).join(
                Role, Utilisateur.id_role == Role.id_role
            ).filter(
                Utilisateur.identifiant_utilisateur == username,
                Utilisateur.actif == True
            ).first()
            
            if not user_data:
                return False, None, "Utilisateur non trouvé ou inactif"
            
            user_obj, role_obj = user_data
            
            # Vérifier le mot de passe
            if UserManagement.verify_password(password, user_obj.mot_de_passe):
                # Mettre à jour la dernière connexion
                user_obj.derniere_connexion = datetime.utcnow()
                db.session.commit()
                
                user_info = {
                    'id': user_obj.id_utilisateur,
                    'username': user_obj.identifiant_utilisateur,
                    'nom_complet': f"{user_obj.prenom_utilisateur} {user_obj.nom_utilisateur}",
                    'role': role_obj.nom_role,
                    'role_level': role_obj.niveau_role,
                    'is_hardcoded': False
                }
                
                print(f"[AUTH] Connexion BDD réussie: {username} ({role_obj.nom_role})")
                return True, user_info, "Authentification réussie"
            else:
                return False, None, "Mot de passe incorrect"
                
        except Exception as e:
            print(f"[AUTH] Erreur authentification: {e}")
            # En cas d'erreur BDD, essayer l'admin en dur
            hardcoded_success, hardcoded_user = AuthSystem.authenticate_hardcoded_admin(username, password)
            if hardcoded_success:
                print(f"[AUTH] Fallback admin en dur après erreur BDD")
                return True, hardcoded_user, "Authentification admin (BDD indisponible)"
            
            return False, None, f"Erreur d'authentification: {str(e)}"
    
    @staticmethod
    def login_user(user_info):
        """Connecter un utilisateur (créer la session)"""
        try:
            # Générer un token de session sécurisé
            session_token = secrets.token_hex(32)
            
            # Créer la session
            session.permanent = True
            session['user_id'] = user_info['id']
            session['username'] = user_info['username']
            session['nom_complet'] = user_info['nom_complet']
            session['user_role'] = user_info['role']
            session['user_role_level'] = user_info['role_level']
            session['is_hardcoded'] = user_info.get('is_hardcoded', False)
            session['session_token'] = session_token
            session['login_time'] = datetime.utcnow().isoformat()
            
            # Enregistrer la session en BDD si pas admin en dur
            if not user_info.get('is_hardcoded', False):
                AuthSystem._create_session_record(user_info['id'], session_token)
            
            print(f"[AUTH] Session créée pour {user_info['username']}")
            return True, "Session créée"
            
        except Exception as e:
            print(f"[AUTH] Erreur création session: {e}")
            return False, f"Erreur création session: {str(e)}"
    
    @staticmethod
    def logout_user():
        """Déconnecter un utilisateur"""
        try:
            # Fermer la session en BDD si elle existe
            if 'user_id' in session and not session.get('is_hardcoded', False):
                AuthSystem._close_session_record(session['user_id'])
            
            username = session.get('username', 'Inconnu')
            session.clear()
            
            print(f"[AUTH] Déconnexion: {username}")
            return True, "Déconnexion réussie"
            
        except Exception as e:
            print(f"[AUTH] Erreur déconnexion: {e}")
            session.clear()  # Vider quand même la session
            return False, f"Erreur déconnexion: {str(e)}"
    
    # =================================================================
    # DÉCORATEURS DE PROTECTION
    # =================================================================
    
    @staticmethod
    def login_required(f):
        """Décorateur pour pages nécessitant une authentification"""
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not AuthSystem.is_user_logged_in():
                if request.is_json:
                    return jsonify({
                        'success': False,
                        'error': 'Authentification requise'
                    }), 401
                else:
                    return redirect(url_for('main.login'))
            return f(*args, **kwargs)
        return decorated_function
    
    @staticmethod
    def role_required(min_level):
        """Décorateur pour contrôle d'accès par niveau de rôle"""
        def decorator(f):
            @wraps(f)
            def decorated_function(*args, **kwargs):
                if not AuthSystem.is_user_logged_in():
                    if request.is_json:
                        return jsonify({'error': 'Authentification requise'}), 401
                    else:
                        return redirect(url_for('main.login'))
                
                user_level = session.get('user_role_level', 0)
                if user_level < min_level:
                    if request.is_json:
                        return jsonify({
                            'success': False,
                            'error': f'Accès refusé - Niveau {min_level} requis'
                        }), 403
                    else:
                        flash('Accès refusé - Privilèges insuffisants', 'error')
                        return redirect(url_for('main.dashboard'))
                
                return f(*args, **kwargs)
            return decorated_function
        return decorator
    
    @staticmethod
    def admin_required(f):
        """Décorateur pour accès administrateur uniquement"""
        return AuthSystem.role_required(3)(f)
    
    @staticmethod
    def auto_required(f):
        """Décorateur pour accès automaticien ou plus"""
        return AuthSystem.role_required(2)(f)
    
    # =================================================================
    # UTILITAIRES SESSION
    # =================================================================
    
    @staticmethod
    def is_user_logged_in():
        """Vérifier si l'utilisateur est connecté"""
        required_keys = ['user_id', 'username', 'user_role', 'session_token']
        return all(key in session for key in required_keys)
    
    @staticmethod
    def get_current_user():
        """Récupérer les infos de l'utilisateur connecté"""
        if not AuthSystem.is_user_logged_in():
            return None
        
        return {
            'id': session['user_id'],
            'username': session['username'],
            'nom_complet': session['nom_complet'],
            'role': session['user_role'],
            'role_level': session['user_role_level'],
            'is_hardcoded': session.get('is_hardcoded', False),
            'login_time': session.get('login_time')
        }
    
    @staticmethod
    def refresh_session():
        """Rafraîchir la session (anti-timeout)"""
        if AuthSystem.is_user_logged_in():
            session.permanent = True
            return True
        return False
    
    # =================================================================
    # GESTION SESSIONS BDD
    # =================================================================
    
    @staticmethod
    def _create_session_record(user_id, session_token):
        """Créer un enregistrement de session en BDD"""
        try:
            from app.models.modele_tag import SessionUtilisateur
            from app import db
            
            # Fermer les anciennes sessions de cet utilisateur
            old_sessions = SessionUtilisateur.query.filter_by(
                id_utilisateur=user_id,
                actif_session=True
            ).all()
            
            for old_session in old_sessions:
                old_session.actif_session = False
                old_session.date_fin_session = datetime.utcnow()
            
            # Créer nouvelle session
            nouvelle_session = SessionUtilisateur(
                token_session=session_token[:50],  # Limité à 50 caractères selon le schéma
                adresse_ip=request.remote_addr,
                user_agent=request.headers.get('User-Agent', '')[:500],  # Limité à 500 caractères
                date_debut_session=datetime.utcnow(),
                actif_session=True,
                id_utilisateur=user_id
            )
            
            db.session.add(nouvelle_session)
            db.session.commit()
            
        except Exception as e:
            print(f"[AUTH] Erreur création session BDD: {e}")
    
    @staticmethod
    def _close_session_record(user_id):
        """Fermer la session en BDD"""
        try:
            from app.models.modele_tag import SessionUtilisateur
            from app import db
            
            active_sessions = SessionUtilisateur.query.filter_by(
                id_utilisateur=user_id,
                actif_session=True
            ).all()
            
            for session_record in active_sessions:
                session_record.actif_session = False
                session_record.date_fin_session = datetime.utcnow()
            
            db.session.commit()
            
        except Exception as e:
            print(f"[AUTH] Erreur fermeture session BDD: {e}")
    
    # =================================================================
    # SÉCURITÉ AVANCÉE
    # =================================================================
    
    @staticmethod
    def check_session_security():
        """Vérifier la sécurité de la session"""
        if not AuthSystem.is_user_logged_in():
            return False
        
        try:
            # Vérifier l'expiration (4 heures max)
            login_time_str = session.get('login_time')
            if login_time_str:
                login_time = datetime.fromisoformat(login_time_str)
                if datetime.utcnow() - login_time > timedelta(hours=4):
                    AuthSystem.logout_user()
                    return False
            
            return True
            
        except Exception as e:
            print(f"[AUTH] Erreur vérification sécurité session: {e}")
            AuthSystem.logout_user()
            return False