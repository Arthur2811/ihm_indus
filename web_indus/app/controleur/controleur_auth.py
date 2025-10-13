from flask import render_template, request, jsonify, redirect, url_for, flash, session
from app.controleur import main_bp
from app.models.modele_auth import AuthSystem
from app import db
from datetime import datetime
import re

# =================================================================
# PAGES PRINCIPALES D'AUTHENTIFICATION
# =================================================================

@main_bp.route('/login')
def login():
    """Page de connexion"""
    # Si déjà connecté, rediriger vers gestion projets
    if AuthSystem.is_user_logged_in():
        return redirect(url_for('main.projects_management'))
    
    return render_template('auth/login.html')

@main_bp.route('/logout')
def logout():
    """Déconnexion"""
    success, message = AuthSystem.logout_user()
    # Nettoyer la session projet lors de la déconnexion
    session.pop('current_project_id', None)
    session.pop('current_project_name', None)
    
    flash(message, 'info' if success else 'error')
    return redirect(url_for('main.login'))

@main_bp.route('/dashboard')
@AuthSystem.login_required
def dashboard():
    """Tableau de bord - maintenant contexte projet"""
    user = AuthSystem.get_current_user()
    
    # Vérifier qu'un projet est sélectionné
    current_project_id = session.get('current_project_id')
    if not current_project_id:
        flash('Veuillez sélectionner un projet', 'warning')
        return redirect(url_for('main.projects_management'))
    
    # Récupérer le projet actuel
    from app.models.modele_projects import ProjectManager
    current_project = ProjectManager.get_project_by_id(current_project_id)
    
    if not current_project:
        # Projet supprimé entre temps
        session.pop('current_project_id', None)
        session.pop('current_project_name', None)
        flash('Le projet sélectionné n\'existe plus', 'error')
        return redirect(url_for('main.projects_management'))
    
    # Récupérer quelques statistiques selon le rôle
    stats = {}
    try:
        if user['role_level'] >= 2:  # AUTO ou ADMIN
            from app.models.modele_tag import Tag
            project_tags = Tag.query.filter_by(id_projet=current_project_id).all()
            stats['total_tags'] = len(project_tags)
            stats['tags_actifs'] = len([tag for tag in project_tags if tag.actif])
        
        if user['role_level'] >= 3:  # ADMIN uniquement
            from app.models.modele_user_management import UserManagement
            user_stats = UserManagement.get_user_stats()
            stats.update(user_stats)
        
        # Statistiques du projet actuel
        stats.update(current_project['stats'])
            
    except Exception as e:
        print(f"Erreur récupération stats dashboard: {e}")
        stats = {'error': 'Impossible de récupérer les statistiques'}
    
    return render_template('auth/dashboard.html', 
                         user=user, 
                         stats=stats,
                         current_project=current_project)

# =================================================================
# API AUTHENTIFICATION
# =================================================================

@main_bp.route('/api/auth/login', methods=['POST'])
def api_login():
    """API de connexion - redirection vers projets"""
    try:
        data = request.get_json()
        
        # Validation des données
        if not data or 'username' not in data or 'password' not in data:
            return jsonify({
                'success': False,
                'error': 'Nom d\'utilisateur et mot de passe requis'
            }), 400
        
        username = data['username'].strip()
        password = data['password']
        
        # Validation basique
        if len(username) < 3 or len(password) < 6:
            return jsonify({
                'success': False,
                'error': 'Identifiants invalides'
            }), 400
        
        # Log de la tentative
        client_ip = request.remote_addr
        print(f"[AUTH] Tentative connexion: {username} depuis {client_ip}")
        
        # Authentification
        auth_success, user_info, auth_message = AuthSystem.authenticate_user(username, password)
        
        if auth_success:
            # Créer la session
            login_success, login_message = AuthSystem.login_user(user_info)
            
            if login_success:
                return jsonify({
                    'success': True,
                    'message': 'Connexion réussie',
                    'user': {
                        'username': user_info['username'],
                        'nom_complet': user_info['nom_complet'],
                        'role': user_info['role']
                    },
                    'redirect': url_for('main.projects_management')  # 🔧 MODIFIÉ
                })
            else:
                return jsonify({
                    'success': False,
                    'error': f'Erreur session: {login_message}'
                }), 500
        else:
            print(f"[AUTH] Échec connexion: {username} - {auth_message}")
            return jsonify({
                'success': False,
                'error': auth_message
            }), 401
            
    except Exception as e:
        print(f"[AUTH] Erreur API login: {e}")
        return jsonify({
            'success': False,
            'error': 'Erreur interne du serveur'
        }), 500

@main_bp.route('/api/auth/logout', methods=['POST'])
@AuthSystem.login_required
def api_logout():
    """API de déconnexion"""
    try:
        success, message = AuthSystem.logout_user()
        
        # Nettoyer la session projet
        session.pop('current_project_id', None)
        session.pop('current_project_name', None)
        
        return jsonify({
            'success': success,
            'message': message,
            'redirect': url_for('main.login')
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Erreur déconnexion: {str(e)}'
        }), 500

@main_bp.route('/api/auth/status')
def api_auth_status():
    """Vérifier le statut d'authentification"""
    if AuthSystem.is_user_logged_in():
        user = AuthSystem.get_current_user()
        
        # Ajouter info projet actuel
        current_project = None
        current_project_id = session.get('current_project_id')
        if current_project_id:
            from app.models.modele_projects import ProjectManager
            current_project = ProjectManager.get_project_by_id(current_project_id)
        
        return jsonify({
            'authenticated': True,
            'user': {
                'username': user['username'],
                'nom_complet': user['nom_complet'],
                'role': user['role'],
                'role_level': user['role_level']
            },
            'current_project': {
                'id': current_project['id_projet'] if current_project else None,
                'nom': current_project['nom_projet'] if current_project else None
            } if current_project else None
        })
    else:
        return jsonify({
            'authenticated': False
        })

@main_bp.route('/api/auth/refresh', methods=['POST'])
@AuthSystem.login_required
def api_refresh_session():
    """Rafraîchir la session (anti-timeout)"""
    try:
        if AuthSystem.refresh_session():
            return jsonify({
                'success': True,
                'message': 'Session rafraîchie'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Impossible de rafraîchir la session'
            }), 401
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# =================================================================
# PAGES D'INFORMATION ET AIDE
# =================================================================

@main_bp.route('/profil')
@AuthSystem.login_required
def profil():
    """Page de profil utilisateur"""
    user = AuthSystem.get_current_user()
    
    # Récupérer les détails complets si pas admin en dur
    user_details = None
    if not user['is_hardcoded']:
        try:
            from app.models.modele_user_management import UserManagement
            user_details = UserManagement.get_user_by_id(user['id'])
        except Exception as e:
            print(f"Erreur récupération profil: {e}")
    
    return render_template('auth/profil.html', user=user, user_details=user_details)

@main_bp.route('/acces-refuse')
def acces_refuse():
    """Page d'accès refusé"""
    return render_template('auth/acces_refuse.html'), 403

# =================================================================
# MIDDLEWARE DE SÉCURITÉ - FLUX MODIFIÉ
# =================================================================

def setup_auth_middleware(app):
    """Configure le middleware d'authentification"""
    
    @app.before_request
    def check_auth():
        """Vérifier l'authentification avant chaque requête"""
        
        # Routes publiques (pas besoin d'authentification)
        public_routes = [
            'main.login',
            'main.api_login',
            'static'
        ]
        
        # Si route publique, passer
        if request.endpoint in public_routes:
            return
        
        # Si page login ou static, passer
        if request.path.startswith('/login') or request.path.startswith('/static'):
            return
        
        # Vérifier la sécurité de la session pour les autres routes
        if request.endpoint and not request.path.startswith('/api/auth'):
            if AuthSystem.is_user_logged_in():
                if not AuthSystem.check_session_security():
                    # Nettoyer la session projet aussi
                    session.pop('current_project_id', None)
                    session.pop('current_project_name', None)
                    
                    if request.is_json:
                        return jsonify({
                            'success': False,
                            'error': 'Session expirée'
                        }), 401
                    else:
                        flash('Session expirée, veuillez vous reconnecter', 'warning')
                        return redirect(url_for('main.login'))
    
    @app.context_processor
    def inject_user():
        """Injecter les infos utilisateur ET projet dans tous les templates"""
        current_project = None
        current_project_id = session.get('current_project_id')
        
        if current_project_id and AuthSystem.is_user_logged_in():
            try:
                from app.models.modele_projects import ProjectManager
                current_project = ProjectManager.get_project_by_id(current_project_id)
            except:
                pass
        
        return {
            'current_user': AuthSystem.get_current_user(),
            'is_logged_in': AuthSystem.is_user_logged_in(),
            'current_project': current_project
        }

# =================================================================
# ROUTE RACINE MODIFIÉE
# =================================================================

# Cette route doit être mise dans app/__init__.py
def setup_root_route(app):
    """Configure la route racine pour rediriger vers projets"""
    
    @app.route('/')
    def root():
        from app.models.modele_auth import AuthSystem
        if AuthSystem.is_user_logged_in():
            return redirect(url_for('main.projects_management'))  # 🔧 MODIFIÉ
        else:
            return redirect(url_for('main.login'))

# =================================================================
# ROUTES DE TEST ET DEBUG
# =================================================================

@main_bp.route('/debug/auth')
def debug_auth():
    """Page de debug authentification (développement uniquement)"""
    from flask import current_app
    if not current_app.debug:
        return "Debug désactivé", 404
    
    debug_info = {
        'session_data': dict(session),
        'is_logged_in': AuthSystem.is_user_logged_in(),
        'current_user': AuthSystem.get_current_user(),
        'hardcoded_admin': AuthSystem.HARDCODED_ADMIN['username'],
        'current_project_id': session.get('current_project_id'),
        'current_project_name': session.get('current_project_name')
    }
    
    return jsonify(debug_info)

@main_bp.route('/debug/create-test-users')
def debug_create_test_users():
    """Créer des utilisateurs de test (développement uniquement)"""
    from flask import current_app
    if not current_app.debug:
        return "Debug désactivé", 404
    
    try:
        from app.models.modele_user_management import UserManagement
        
        # Créer les rôles par défaut
        UserManagement.create_default_roles()
        
        # Créer l'admin par défaut
        success, message = UserManagement.create_default_admin()
        
        return jsonify({
            'success': success,
            'message': message,
            'hardcoded_admin': f"root/{AuthSystem.HARDCODED_ADMIN['password']}"
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500