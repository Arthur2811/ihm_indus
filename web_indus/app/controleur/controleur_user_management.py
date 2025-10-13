from flask import render_template, request, jsonify, redirect, url_for, flash
from app.controleur import main_bp
from app.models.modele_auth import AuthSystem  # NOUVEAU IMPORT
from app import db
import json

# =================================================================
# ROUTE PRINCIPALE - INTERFACE WEB ADMIN
# =================================================================

@main_bp.route('/admin/users')
@AuthSystem.admin_required
def user_management():
    """Page principale de gestion des utilisateurs - USE CASE ADMIN"""
    try:
        from app.models.modele_user_management import UserManagement
        
        # Récupérer tous les utilisateurs avec leurs rôles
        users = UserManagement.get_all_users()
        
        # Récupérer tous les rôles disponibles (Attribuer rôles)
        roles = UserManagement.get_all_roles()
        
        # Récupérer les statistiques
        stats = UserManagement.get_user_stats()
        
        return render_template('users/user_management.html', 
                             users=users, 
                             roles=roles, 
                             stats=stats)
        
    except Exception as e:
        print(f"Erreur page admin users: {e}")
        flash(f"Erreur chargement: {str(e)}", "error")
        return redirect(url_for('main.index'))

# =================================================================
# API USER1: AJOUTER UTILISATEUR
# =================================================================

@main_bp.route('/api/admin/users', methods=['POST'])
@AuthSystem.admin_required
def api_create_user():
    """API: Créer un nouvel utilisateur"""
    try:
        from app.models.modele_user_management import UserManagement
        
        # Récupération et validation des données
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': 'Aucune donnée reçue'
            }), 400
        
        # Log de la tentative de création
        print(f"[USER1] Tentative création utilisateur: {data.get('identifiant_utilisateur', 'N/A')}")
        
        # Appel du USER1
        success, message = UserManagement.create_user(data)
        
        if success:
            print(f"[USER1] ✅ Utilisateur créé: {message}")
            return jsonify({
                'success': True,
                'message': message
            }), 201
        else:
            print(f"[USER1] ❌ Échec création: {message}")
            return jsonify({
                'success': False,
                'error': message
            }), 400
            
    except Exception as e:
        print(f"[USER1] ❌ Erreur système: {e}")
        return jsonify({
            'success': False,
            'error': f'Erreur système: {str(e)}'
        }), 500

# =================================================================
# API USER2: SUPPRIMER UTILISATEUR
# =================================================================

@main_bp.route('/api/admin/users/<int:user_id>', methods=['DELETE'])
@AuthSystem.admin_required
def api_delete_user(user_id):
    """API: Supprimer un utilisateur"""
    try:
        from app.models.modele_user_management import UserManagement
        
        # Récupérer les infos de l'utilisateur avant suppression pour le log
        user_info = UserManagement.get_user_by_id(user_id)
        user_identifier = user_info['identifiant_utilisateur'] if user_info else f"ID:{user_id}"
        
        # Log de la tentative de suppression
        print(f"[USER2] Tentative suppression utilisateur: {user_identifier}")
        
        # Appel du USER2
        success, message = UserManagement.delete_user(user_id)
        
        if success:
            print(f"[USER2] ✅ Utilisateur supprimé: {message}")
            return jsonify({
                'success': True,
                'message': message
            })
        else:
            print(f"[USER2] ❌ Échec suppression: {message}")
            return jsonify({
                'success': False,
                'error': message
            }), 400
            
    except Exception as e:
        print(f"[USER2] ❌ Erreur système: {e}")
        return jsonify({
            'success': False,
            'error': f'Erreur système: {str(e)}'
        }), 500

# =================================================================
# API USER3: ATTRIBUER RÔLES
# =================================================================

@main_bp.route('/api/admin/users/<int:user_id>/role', methods=['POST'])
@AuthSystem.admin_required
def api_assign_user_role(user_id):
    """API USER3: Attribuer un rôle à un utilisateur"""
    try:
        from app.models.modele_user_management import UserManagement
        
        # Récupération et validation des données
        data = request.get_json()
        if not data or 'role_id' not in data:
            return jsonify({
                'success': False,
                'error': 'ID du rôle manquant'
            }), 400
        
        role_id = data['role_id']
        
        # Récupérer les infos pour le log
        user_info = UserManagement.get_user_by_id(user_id)
        user_identifier = user_info['identifiant_utilisateur'] if user_info else f"ID:{user_id}"
        
        # Log de la tentative d'attribution
        print(f"[USER3] Tentative attribution rôle {role_id} à {user_identifier}")
        
        # Appel du USER3
        success, message = UserManagement.assign_role(user_id, role_id)
        
        if success:
            print(f"[USER3] ✅ Rôle attribué: {message}")
            return jsonify({
                'success': True,
                'message': message
            })
        else:
            print(f"[USER3] ❌ Échec attribution: {message}")
            return jsonify({
                'success': False,
                'error': message
            }), 400
            
    except Exception as e:
        print(f"[USER3] ❌ Erreur système: {e}")
        return jsonify({
            'success': False,
            'error': f'Erreur système: {str(e)}'
        }), 500

# =================================================================
# APIS DE CONSULTATION
# =================================================================

@main_bp.route('/api/admin/users', methods=['GET'])
@AuthSystem.admin_required
def api_get_users():
    """API: Liste de tous les utilisateurs"""
    try:
        from app.models.modele_user_management import UserManagement
        
        users = UserManagement.get_all_users()
        
        return jsonify({
            'success': True,
            'users': users,
            'total': len(users)
        })
        
    except Exception as e:
        print(f"Erreur récupération utilisateurs: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@main_bp.route('/api/admin/users/<int:user_id>', methods=['GET'])
@AuthSystem.admin_required
def api_get_user(user_id):
    """API: Récupérer les détails d'un utilisateur"""
    try:
        from app.models.modele_user_management import UserManagement
        
        user_data = UserManagement.get_user_by_id(user_id)
        
        if not user_data:
            return jsonify({
                'success': False,
                'error': 'Utilisateur non trouvé'
            }), 404
        
        return jsonify({
            'success': True,
            'user': user_data
        })
        
    except Exception as e:
        print(f"Erreur récupération utilisateur {user_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@main_bp.route('/api/admin/users/<int:user_id>', methods=['PUT'])
@AuthSystem.admin_required
def api_update_user(user_id):
    """API: Modifier un utilisateur (extension du USE CASE USER1)"""
    try:
        from app.models.modele_user_management import UserManagement
        
        # Récupération des données
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': 'Aucune donnée reçue'
            }), 400
        
        # Vérifier que l'utilisateur existe
        existing_user = UserManagement.get_user_by_id(user_id)
        if not existing_user:
            return jsonify({
                'success': False,
                'error': 'Utilisateur non trouvé'
            }), 404
        
        # Log de la tentative de modification
        print(f"[USER1-UPDATE] Tentative modification utilisateur: {existing_user['identifiant_utilisateur']}")
        
        # Si changement de rôle, utiliser USER3
        if 'id_role' in data and data['id_role'] != existing_user['id_role']:
            success, message = UserManagement.assign_role(user_id, data['id_role'])
            if not success:
                return jsonify({
                    'success': False,
                    'error': f'Erreur changement rôle: {message}'
                }), 400
        
        # Validation des données pour modification
        valid, errors = UserManagement.validate_user_data(data, is_update=True)
        if not valid:
            return jsonify({
                'success': False,
                'error': 'Données invalides',
                'details': errors
            }), 400
        
        # Appel de la mise à jour
        success, message = UserManagement.update_user(user_id, data)
        
        if success:
            print(f"[USER1-UPDATE] ✅ Utilisateur modifié: {message}")
            return jsonify({
                'success': True,
                'message': message
            })
        else:
            print(f"[USER1-UPDATE] ❌ Échec modification: {message}")
            return jsonify({
                'success': False,
                'error': message
            }), 400
            
    except Exception as e:
        print(f"[USER1-UPDATE] ❌ Erreur système: {e}")
        return jsonify({
            'success': False,
            'error': f'Erreur système: {str(e)}'
        }), 500

@main_bp.route('/api/admin/users/<int:user_id>/toggle', methods=['POST'])
@AuthSystem.admin_required
def api_toggle_user_status(user_id):
    """API: Activer/désactiver un utilisateur (extension USE CASE USER1)"""
    try:
        from app.models.modele_user_management import UserManagement
        
        # Récupérer les infos pour le log
        user_info = UserManagement.get_user_by_id(user_id)
        if not user_info:
            return jsonify({
                'success': False,
                'error': 'Utilisateur non trouvé'
            }), 404
        
        user_identifier = user_info['identifiant_utilisateur']
        current_status = user_info['actif']
        new_status = not current_status
        
        # Log de la tentative
        print(f"[USER1-TOGGLE] Tentative {'activation' if new_status else 'désactivation'} de {user_identifier}")
        
        # Utiliser la méthode update pour changer le statut
        success, message = UserManagement.update_user(user_id, {'actif': new_status})
        
        if success:
            status_text = "activé" if new_status else "désactivé"
            message = f"Utilisateur '{user_identifier}' {status_text} avec succès"
            print(f"[USER1-TOGGLE] ✅ {message}")
            return jsonify({
                'success': True,
                'message': message
            })
        else:
            print(f"[USER1-TOGGLE] ❌ Échec: {message}")
            return jsonify({
                'success': False,
                'error': message
            }), 400
            
    except Exception as e:
        print(f"[USER1-TOGGLE] ❌ Erreur système: {e}")
        return jsonify({
            'success': False,
            'error': f'Erreur système: {str(e)}'
        }), 500

@main_bp.route('/api/admin/roles', methods=['GET'])
@AuthSystem.admin_required
def api_get_roles():
    """API: Liste de tous les rôles (pour USE CASE USER3)"""
    try:
        from app.models.modele_user_management import UserManagement
        
        roles = UserManagement.get_all_roles()
        
        return jsonify({
            'success': True,
            'roles': roles
        })
        
    except Exception as e:
        print(f"Erreur récupération rôles: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@main_bp.route('/api/admin/stats', methods=['GET'])
@AuthSystem.admin_required
def api_get_user_stats():
    """API: Statistiques des utilisateurs"""
    try:
        from app.models.modele_user_management import UserManagement
        
        stats = UserManagement.get_user_stats()
        
        return jsonify({
            'success': True,
            'stats': stats
        })
        
    except Exception as e:
        print(f"Erreur récupération statistiques: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# =================================================================
# ROUTES D'INITIALISATION SYSTÈME
# =================================================================

@main_bp.route('/api/admin/init_default_data', methods=['POST'])
@AuthSystem.admin_required
def api_init_default_data():
    """API: Initialiser les données par défaut (rôles + admin)"""
    try:
        from app.models.modele_user_management import UserManagement
        
        print("[INIT] Initialisation des données par défaut...")
        
        # Créer les rôles par défaut selon Use Case
        UserManagement.create_default_roles()
        
        # Créer l'admin par défaut avec USE CASE USER1
        success, message = UserManagement.create_default_admin()
        
        if success:
            print(f"[INIT] ✅ {message}")
            return jsonify({
                'success': True,
                'message': f'Données initialisées. {message}. Identifiants: admin/admin123'
            })
        else:
            print(f"[INIT] ❌ Erreur admin: {message}")
            return jsonify({
                'success': True,  # Rôles créés même si admin existait
                'message': f'Rôles initialisés. {message}'
            })
        
    except Exception as e:
        print(f"[INIT] ❌ Erreur système: {e}")
        return jsonify({
            'success': False,
            'error': f'Erreur initialisation: {str(e)}'
        }), 500

# =================================================================
# ROUTES DE TEST ET DIAGNOSTIC
# =================================================================

@main_bp.route('/api/admin/test_password', methods=['POST'])
@AuthSystem.admin_required
def api_test_password():
    """API: Tester le hashage/vérification de mot de passe"""
    try:
        from app.models.modele_user_management import UserManagement
        
        data = request.get_json()
        password = data.get('password', 'test123')
        
        # Tester le hashage sécurisé
        try:
            hashed = UserManagement._hash_password_secure(password)
            
            # Vérifier le mot de passe
            is_valid = UserManagement.verify_password(password, hashed)
            is_invalid = UserManagement.verify_password('wrong_password', hashed)
            
            return jsonify({
                'success': True,
                'original_password': password,
                'hashed_password': hashed,
                'verification_correct': is_valid,
                'verification_incorrect': is_invalid,
                'hash_length': len(hashed),
                'security_status': 'bcrypt_secure'
            })
            
        except Exception as hash_error:
            return jsonify({
                'success': False,
                'error': f'Erreur hashage sécurisé: {str(hash_error)}',
                'security_status': 'hash_failed'
            })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Erreur test: {str(e)}'
        }), 500

@main_bp.route('/api/admin/system_check', methods=['GET'])
@AuthSystem.admin_required
def api_system_check():
    """API: Vérification état du système de gestion utilisateurs"""
    try:
        from app.models.modele_user_management import UserManagement
        
        # Vérifications système
        checks = {
            'database_connection': False,
            'roles_exist': False,
            'admin_exists': False,
            'users_count': 0,
            'roles_count': 0
        }
        
        try:
            # Test connexion base
            users = UserManagement.get_all_users()
            checks['database_connection'] = True
            checks['users_count'] = len(users)
            
            # Test rôles
            roles = UserManagement.get_all_roles()
            checks['roles_exist'] = len(roles) > 0
            checks['roles_count'] = len(roles)
            
            # Test admin
            admin_exists = any(user['role_nom'] == 'ADMIN' for user in users)
            checks['admin_exists'] = admin_exists
            
        except Exception as check_error:
            checks['error'] = str(check_error)
        
        return jsonify({
            'success': True,
            'system_checks': checks,
            'status': 'healthy' if all([
                checks['database_connection'],
                checks['roles_exist'],
                checks['admin_exists']
            ]) else 'needs_attention'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Erreur vérification système: {str(e)}'
        }), 500

# =================================================================
# FONCTIONS D'INITIALISATION
# =================================================================

def init_user_management():
    """Initialise le système de gestion des utilisateurs au démarrage"""
    try:
        from app.models.modele_user_management import UserManagement
        
        print("🔧 Initialisation du système de gestion des utilisateurs...")
        
        # Créer les rôles par défaut selon Use Case
        UserManagement.create_default_roles()
        
        # Créer l'admin par défaut si nécessaire
        success, message = UserManagement.create_default_admin()
        if success:
            print(f"✅ {message}")
        else:
            print(f"ℹ️ {message}")  # Admin peut déjà exister
        
        print("✅ Système de gestion des utilisateurs initialisé")
        print("📋 Use Cases disponibles:")
        print("   - USER1: Ajouter utilisateur")
        print("   - USER2: Supprimer utilisateur") 
        print("   - USER3: Attribuer rôles")
        
    except Exception as e:
        print(f"❌ Erreur initialisation gestion utilisateurs: {e}")

def setup_user_management(app):
    """Configuration du système de gestion des utilisateurs"""
    with app.app_context():
        init_user_management()

# =================================================================
# GESTION D'ERREURS SPÉCIFIQUE AU MODULE
# =================================================================

@main_bp.errorhandler(404)
def user_not_found(error):
    """Gestion erreur 404 spécifique aux utilisateurs"""
    if request.path.startswith('/api/admin/users/'):
        return jsonify({
            'success': False,
            'error': 'Utilisateur non trouvé'
        }), 404
    return error

@main_bp.errorhandler(500)
def user_internal_error(error):
    """Gestion erreur 500 spécifique aux utilisateurs"""
    if request.path.startswith('/api/admin/users/'):
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': 'Erreur interne du serveur'
        }), 500
    return error