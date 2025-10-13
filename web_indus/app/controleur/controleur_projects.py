from flask import render_template, request, jsonify, redirect, url_for, flash, session, current_app, send_file
from app.controleur import main_bp
from app.models.modele_auth import AuthSystem
from app.models.modele_projects import ProjectManager
from app import db
import json
import tempfile
import os
from datetime import datetime
import zipfile

# =================================================================
# PAGE PRINCIPALE - GESTION PROJETS
# =================================================================

@main_bp.route('/projects')
@AuthSystem.login_required
def projects_management():
    """Page principale de gestion des projets - NOUVELLE PAGE D'ACCUEIL"""
    try:
        # Récupérer tous les projets
        projects = ProjectManager.get_all_projects()
        
        # Statistiques globales
        summary = ProjectManager.get_project_summary()
        
        # Projet actuel en session (si défini)
        current_project_id = session.get('current_project_id')
        current_project = None
        if current_project_id:
            current_project = ProjectManager.get_project_by_id(current_project_id)
        
        return render_template('projects/projects_management.html',
                             projects=projects,
                             summary=summary,
                             current_project=current_project,
                             user=AuthSystem.get_current_user())
        
    except Exception as e:
        print(f"Erreur page projets: {e}")
        flash(f"Erreur chargement projets: {str(e)}", "error")
        return redirect(url_for('main.login'))

@main_bp.route('/projects/<int:project_id>/select')
@AuthSystem.login_required
def select_project(project_id):
    """Sélectionner un projet et rediriger vers le dashboard"""
    try:
        project = ProjectManager.get_project_by_id(project_id)
        if not project:
            flash("Projet non trouvé", "error")
            return redirect(url_for('main.projects_management'))
        
        # Stocker le projet actuel en session
        session['current_project_id'] = project_id
        session['current_project_name'] = project['nom_projet']
        
        flash(f"Projet '{project['nom_projet']}' sélectionné", "success")
        return redirect(url_for('main.dashboard'))
        
    except Exception as e:
        print(f"Erreur sélection projet: {e}")
        flash(f"Erreur sélection: {str(e)}", "error")
        return redirect(url_for('main.projects_management'))

@main_bp.route('/projects/<int:project_id>')
@AuthSystem.login_required
def project_details(project_id):
    """Détails d'un projet spécifique"""
    try:
        project = ProjectManager.get_project_by_id(project_id)
        if not project:
            flash("Projet non trouvé", "error")
            return redirect(url_for('main.projects_management'))
        
        return render_template('projects/project_details.html', project=project)
        
    except Exception as e:
        print(f"Erreur détails projet: {e}")
        flash(f"Erreur: {str(e)}", "error")
        return redirect(url_for('main.projects_management'))

# =================================================================
# API GESTION PROJETS - SELON DROITS UTILISATEUR
# =================================================================

@main_bp.route('/api/projects', methods=['GET'])
@AuthSystem.login_required
def api_get_projects():
    """API: Liste des projets"""
    try:
        projects = ProjectManager.get_all_projects()
        summary = ProjectManager.get_project_summary()
        
        return jsonify({
            'success': True,
            'projects': projects,
            'summary': summary,
            'total': len(projects)
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@main_bp.route('/api/projects', methods=['POST'])
@AuthSystem.auto_required  # AUTO ou ADMIN peuvent créer
def api_create_project():
    """API: Créer un nouveau projet"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': 'Aucune donnée reçue'
            }), 400
        
        user = AuthSystem.get_current_user()
        creator_id = user['id'] if not user['is_hardcoded'] else None
        
        success, message = ProjectManager.create_project(data, creator_id)
        
        if success:
            return jsonify({
                'success': True,
                'message': message
            }), 201
        else:
            return jsonify({
                'success': False,
                'error': message
            }), 400
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Erreur création: {str(e)}'
        }), 500

@main_bp.route('/api/projects/<int:project_id>', methods=['GET'])
@AuthSystem.login_required
def api_get_project(project_id):
    """API: Détails d'un projet"""
    try:
        project = ProjectManager.get_project_by_id(project_id)
        
        if not project:
            return jsonify({
                'success': False,
                'error': 'Projet non trouvé'
            }), 404
        
        return jsonify({
            'success': True,
            'project': project
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@main_bp.route('/api/projects/<int:project_id>', methods=['PUT'])
@AuthSystem.auto_required  # AUTO ou ADMIN peuvent modifier
def api_update_project(project_id):
    """API: Modifier un projet"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': 'Aucune donnée reçue'
            }), 400
        
        success, message = ProjectManager.update_project(project_id, data)
        
        if success:
            # Mettre à jour la session si c'est le projet actuel
            if session.get('current_project_id') == project_id:
                session['current_project_name'] = data.get('nom_projet', session.get('current_project_name'))
            
            return jsonify({
                'success': True,
                'message': message
            })
        else:
            return jsonify({
                'success': False,
                'error': message
            }), 400
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Erreur modification: {str(e)}'
        }), 500

@main_bp.route('/api/projects/<int:project_id>', methods=['DELETE'])
@AuthSystem.auto_required  # AUTO ou ADMIN peuvent supprimer
def api_delete_project(project_id):
    """API: Supprimer un projet"""
    try:
        # Vérifier si ce n'est pas le projet actuel
        if session.get('current_project_id') == project_id:
            session.pop('current_project_id', None)
            session.pop('current_project_name', None)
        
        success, message = ProjectManager.delete_project(project_id)
        
        if success:
            return jsonify({
                'success': True,
                'message': message
            })
        else:
            return jsonify({
                'success': False,
                'error': message
            }), 400
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Erreur suppression: {str(e)}'
        }), 500

@main_bp.route('/api/projects/<int:project_id>/duplicate', methods=['POST'])
@AuthSystem.auto_required  # AUTO ou ADMIN peuvent dupliquer
def api_duplicate_project(project_id):
    """API: Dupliquer un projet"""
    try:
        data = request.get_json()
        if not data or 'new_name' not in data:
            return jsonify({
                'success': False,
                'error': 'Nouveau nom requis'
            }), 400
        
        user = AuthSystem.get_current_user()
        creator_id = user['id'] if not user['is_hardcoded'] else None
        
        success, message = ProjectManager.duplicate_project(
            project_id, 
            data['new_name'], 
            creator_id
        )
        
        if success:
            return jsonify({
                'success': True,
                'message': message
            })
        else:
            return jsonify({
                'success': False,
                'error': message
            }), 400
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Erreur duplication: {str(e)}'
        }), 500

@main_bp.route('/api/projects/<int:project_id>/archive', methods=['POST'])
@AuthSystem.auto_required  # AUTO ou ADMIN peuvent archiver
def api_archive_project(project_id):
    """API: Archiver/désarchiver un projet"""
    try:
        data = request.get_json()
        archive = data.get('archive', True)
        
        success, message = ProjectManager.archive_project(project_id, archive)
        
        if success:
            return jsonify({
                'success': True,
                'message': message
            })
        else:
            return jsonify({
                'success': False,
                'error': message
            }), 400
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Erreur archivage: {str(e)}'
        }), 500

# =================================================================
# IMPORT/EXPORT DE PROJETS
# =================================================================

@main_bp.route('/api/projects/<int:project_id>/export')
@AuthSystem.auto_required  # AUTO ou ADMIN peuvent exporter
def api_export_project(project_id):
    """API: Exporter un projet"""
    try:
        export_data, error = ProjectManager.export_project(project_id)
        
        if error:
            return jsonify({
                'success': False,
                'error': error
            }), 400
        
        # Créer un fichier temporaire
        project_name = export_data['project']['nom_projet']
        safe_name = project_name.replace(' ', '_').replace('/', '_')
        filename = f"{safe_name}_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        # Retourner les données pour téléchargement côté client
        return jsonify({
            'success': True,
            'data': export_data,
            'filename': filename,
            'message': f"Projet '{project_name}' prêt pour export"
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Erreur export: {str(e)}'
        }), 500

@main_bp.route('/api/projects/import', methods=['POST'])
@AuthSystem.auto_required  # AUTO ou ADMIN peuvent importer
def api_import_project():
    """API: Importer un projet"""
    try:
        data = request.get_json()
        if not data or 'project_data' not in data:
            return jsonify({
                'success': False,
                'error': 'Données d\'import manquantes'
            }), 400
        
        user = AuthSystem.get_current_user()
        creator_id = user['id'] if not user['is_hardcoded'] else None
        
        new_name = data.get('new_name')  # Optionnel
        project_data = data['project_data']
        
        success, message = ProjectManager.import_project(
            project_data,
            creator_id,
            new_name
        )
        
        if success:
            return jsonify({
                'success': True,
                'message': message
            })
        else:
            return jsonify({
                'success': False,
                'error': message
            }), 400
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Erreur import: {str(e)}'
        }), 500

# =================================================================
# GESTION SESSION PROJET
# =================================================================

@main_bp.route('/api/projects/current')
@AuthSystem.login_required
def api_get_current_project():
    """API: Projet actuellement sélectionné"""
    try:
        project_id = session.get('current_project_id')
        
        if not project_id:
            return jsonify({
                'success': True,
                'current_project': None,
                'message': 'Aucun projet sélectionné'
            })
        
        project = ProjectManager.get_project_by_id(project_id)
        if not project:
            # Nettoyer la session si projet supprimé
            session.pop('current_project_id', None)
            session.pop('current_project_name', None)
            return jsonify({
                'success': True,
                'current_project': None,
                'message': 'Projet précédent introuvable'
            })
        
        return jsonify({
            'success': True,
            'current_project': project
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@main_bp.route('/api/projects/<int:project_id>/set_current', methods=['POST'])
@AuthSystem.login_required
def api_set_current_project(project_id):
    """API: Définir le projet actuel"""
    try:
        project = ProjectManager.get_project_by_id(project_id)
        if not project:
            return jsonify({
                'success': False,
                'error': 'Projet non trouvé'
            }), 404
        
        session['current_project_id'] = project_id
        session['current_project_name'] = project['nom_projet']
        
        return jsonify({
            'success': True,
            'message': f"Projet '{project['nom_projet']}' défini comme actuel",
            'current_project': project
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# =================================================================
# ROUTES D'AIDE ET OUTILS
# =================================================================

@main_bp.route('/api/projects/validate_name', methods=['POST'])
@AuthSystem.auto_required
def api_validate_project_name():
    """API: Valider l'unicité d'un nom de projet"""
    try:
        data = request.get_json()
        if not data or 'nom_projet' not in data:
            return jsonify({
                'success': False,
                'error': 'Nom de projet requis'
            }), 400
        
        from app.models.modele_tag import HMIProject
        
        existing = HMIProject.query.filter_by(nom_projet=data['nom_projet']).first()
        
        return jsonify({
            'success': True,
            'available': existing is None,
            'message': 'Nom disponible' if not existing else 'Nom déjà utilisé'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@main_bp.route('/api/projects/templates')
@AuthSystem.auto_required
def api_get_project_templates():
    """API: Modèles de projets disponibles"""
    try:
        templates = [
            {
                'id': 'basic_hmi',
                'nom': 'IHM Basique',
                'description': 'Projet avec pages et tags de base',
                'tags_count': 8,
                'pages_count': 2
            },
            {
                'id': 'siemens_s7',
                'nom': 'Siemens S7 Standard',
                'description': 'Configuration type pour automates S7',
                'tags_count': 12,
                'pages_count': 3
            },
            {
                'id': 'demo_project',
                'nom': 'Projet de Démonstration',
                'description': 'Exemple complet avec animations',
                'tags_count': 15,
                'pages_count': 4
            }
        ]
        
        return jsonify({
            'success': True,
            'templates': templates
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@main_bp.route('/api/projects/<int:project_id>/stats')
@AuthSystem.login_required
def api_project_stats(project_id):
    """API: Statistiques détaillées d'un projet"""
    try:
        project = ProjectManager.get_project_by_id(project_id)
        if not project:
            return jsonify({
                'success': False,
                'error': 'Projet non trouvé'
            }), 404
        
        # Statistiques enrichies
        from app.models.modele_tag import Tag
        from app.models.modele_graphics import Page
        
        tags = Tag.query.filter_by(id_projet=project_id).all()
        pages = Page.query.filter_by(id_projet=project_id).all()
        
        stats = {
            'basic': project['stats'],
            'tags_by_type': {},
            'tags_by_access': {},
            'pages_info': []
        }
        
        # Répartition tags par type
        for tag in tags:
            type_donnee = tag.type_donnee
            if type_donnee not in stats['tags_by_type']:
                stats['tags_by_type'][type_donnee] = 0
            stats['tags_by_type'][type_donnee] += 1
        
        # Répartition tags par accès
        for tag in tags:
            acces = tag.acces or 'R'
            if acces not in stats['tags_by_access']:
                stats['tags_by_access'][acces] = 0
            stats['tags_by_access'][acces] += 1
        
        # Info pages
        for page in pages:
            stats['pages_info'].append({
                'nom': page.nom_page,
                'taille': f"{page.largeur_page}x{page.hauteur_page}",
                'accueil': page.page_accueil
            })
        
        return jsonify({
            'success': True,
            'stats': stats
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# =================================================================
# MIDDLEWARE PROJET (pour toutes les autres pages)
# =================================================================

def get_current_project_context():
    """Récupère le contexte du projet actuel pour les autres contrôleurs"""
    project_id = session.get('current_project_id')
    if project_id:
        return ProjectManager.get_project_by_id(project_id)
    return None

def require_project_selected(f):
    """Décorateur pour s'assurer qu'un projet est sélectionné"""
    from functools import wraps
    
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('current_project_id'):
            if request.is_json:
                return jsonify({
                    'success': False,
                    'error': 'Aucun projet sélectionné',
                    'redirect': url_for('main.projects_management')
                }), 400
            else:
                flash('Veuillez sélectionner un projet', 'warning')
                return redirect(url_for('main.projects_management'))
        return f(*args, **kwargs)
    return decorated_function

# =================================================================
# UTILITAIRES POUR DEBUG
# =================================================================

@main_bp.route('/api/projects/debug/session')
@AuthSystem.admin_required
def api_debug_project_session():
    """Debug: Informations session projet"""
    return jsonify({
        'current_project_id': session.get('current_project_id'),
        'current_project_name': session.get('current_project_name'),
        'session_keys': list(session.keys())
    })

@main_bp.route('/api/projects/debug/reset_session', methods=['POST'])
@AuthSystem.admin_required
def api_reset_project_session():
    """Debug: Réinitialiser la session projet"""
    session.pop('current_project_id', None)
    session.pop('current_project_name', None)
    
    return jsonify({
        'success': True,
        'message': 'Session projet réinitialisée'
    })