from flask import render_template, request, jsonify, redirect, url_for, flash, session, send_from_directory
from app.controleur import main_bp
from app.models.modele_auth import AuthSystem
from app.models.modele_graphics import IconLibrary, IconFileManager
from app import db
import os
import json
import time
from datetime import datetime

# =================================================================
# ROUTES DE GESTION DES ICÔNES - VERSION INTÉGRÉE ÉLÉGANTE
# =================================================================

@main_bp.route('/graphics/icons/management')
@AuthSystem.login_required
def icons_management():
    """Page principale de gestion des icônes - Version intégrée sans popup"""
    current_project_id = session.get('current_project_id')
    if not current_project_id:
        flash('Veuillez sélectionner un projet', 'warning')
        return redirect(url_for('main.projects_management'))
    
    return render_template('graphics/icons_management.html')

@main_bp.route('/graphics/icons/library')
@AuthSystem.login_required  
def icons_library():
    """Alias pour la gestion - maintien compatibilité"""
    return redirect(url_for('main.icons_management'))

# =================================================================
# API COMPLÈTE POUR LA GESTION DES ICÔNES
# =================================================================

@main_bp.route('/api/graphics/icons', methods=['GET'])
@AuthSystem.login_required
def api_get_all_icons():
    """API pour récupérer toutes les icônes disponibles - Optimisée"""
    try:
        # Récupérer toutes les icônes actives avec tri intelligent
        icons = IconLibrary.query.filter_by(actif=True).order_by(
            IconLibrary.type_source,
            IconLibrary.categorie, 
            IconLibrary.nom_icon
        ).all()
        
        # Organiser par catégories pour le frontend
        icons_data = []
        for icon in icons:
            icon_dict = icon.to_dict()
            # Ajouter des métadonnées utiles
            icon_dict['display_name'] = get_category_display_name(icon.categorie)
            icon_dict['type_display'] = get_type_display_name(icon.type_source)
            icons_data.append(icon_dict)
        
        # Statistiques pour l'interface
        stats = {
            'total': len(icons),
            'industrial': len([i for i in icons if i.type_source == 'industrial']),
            'custom': len([i for i in icons if i.type_source == 'upload']),
            'external': len([i for i in icons if i.type_source == 'external']),
            'categories': len(set([i.categorie for i in icons if i.categorie]))
        }
        
        return jsonify({
            'success': True,
            'icons': icons_data,
            'stats': stats,
            'total': len(icons)
        })
        
    except Exception as e:
        print(f"Erreur récupération icônes: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@main_bp.route('/api/graphics/icons/categories', methods=['GET'])
@AuthSystem.login_required
def api_get_icon_categories():
    """Récupère les catégories d'icônes avec statistiques"""
    try:
        categories = db.session.query(
            IconLibrary.categorie,
            IconLibrary.type_source,
            db.func.count(IconLibrary.id_icon).label('count')
        ).filter_by(actif=True).group_by(
            IconLibrary.categorie, 
            IconLibrary.type_source
        ).all()
        
        # Organiser par catégorie avec sous-totaux par type
        result = {}
        for cat, type_src, count in categories:
            cat_name = cat or 'Sans catégorie'
            if cat_name not in result:
                result[cat_name] = {
                    'name': cat_name,
                    'display_name': get_category_display_name(cat_name),
                    'total': 0,
                    'types': {}
                }
            result[cat_name]['types'][type_src] = count
            result[cat_name]['total'] += count
        
        return jsonify({
            'success': True,
            'categories': list(result.values())
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@main_bp.route('/api/graphics/icons/search', methods=['GET'])
@AuthSystem.login_required
def api_search_icons():
    """Recherche avancée d'icônes avec filtres multiples"""
    try:
        # Paramètres de recherche
        query = request.args.get('q', '').strip()
        category = request.args.get('category', '')
        type_filter = request.args.get('type', '')
        limit = int(request.args.get('limit', 50))
        
        # Construire la requête de base
        icon_query = IconLibrary.query.filter_by(actif=True)
        
        # Filtrer par catégorie
        if category and category != 'all':
            icon_query = icon_query.filter_by(categorie=category)
        
        # Filtrer par type
        if type_filter and type_filter != 'all':
            icon_query = icon_query.filter_by(type_source=type_filter)
        
        # Recherche textuelle avec priorité sur le nom
        if query:
            icon_query = icon_query.filter(
                db.or_(
                    IconLibrary.nom_icon.contains(query),
                    IconLibrary.description_icon.contains(query),
                    IconLibrary.external_name.contains(query)
                )
            ).order_by(
                # Priorité : correspondance exacte nom, puis contient nom, puis description
                db.case([
                    (IconLibrary.nom_icon == query, 1),
                    (IconLibrary.nom_icon.contains(query), 2),
                    (IconLibrary.description_icon.contains(query), 3)
                ], else_=4)
            )
        
        icons = icon_query.limit(limit).all()
        
        return jsonify({
            'success': True,
            'icons': [icon.to_dict() for icon in icons],
            'total': len(icons),
            'query': query,
            'filters': {
                'category': category,
                'type': type_filter
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@main_bp.route('/api/icons/upload', methods=['POST'])
@AuthSystem.login_required
def api_upload_icon():
    """Upload d'icônes avec gestion multiple et métadonnées"""
    try:
        current_project_id = session.get('current_project_id')
        if not current_project_id:
            return jsonify({
                'success': False,
                'error': 'Aucun projet sélectionné'
            }), 400
        
        # Vérifier qu'un fichier a été envoyé
        if 'file' not in request.files:
            return jsonify({
                'success': False,
                'error': 'Aucun fichier envoyé'
            }), 400
        
        file = request.files['file']
        category = request.form.get('category', 'custom')
        description = request.form.get('description', '')
        custom_name = request.form.get('custom_name', '')
        
        if file.filename == '':
            return jsonify({
                'success': False,
                'error': 'Nom de fichier vide'
            }), 400
        
        # Sauvegarder le fichier avec métadonnées
        icon_entry, message = IconFileManager.save_uploaded_icon(
            file, 
            custom_name, 
            category
        )
        
        if icon_entry:
            # Ajouter les métadonnées supplémentaires
            if description:
                icon_entry.description_icon = description
            
            # Référence utilisateur qui a uploadé
            user = AuthSystem.get_current_user()
            if not user.get('is_hardcoded', True):
                icon_entry.cree_par = user['id']
            
            db.session.commit()
            
            return jsonify({
                'success': True,
                'message': message,
                'icon': icon_entry.to_dict()
            }), 201
        else:
            return jsonify({
                'success': False,
                'error': message
            }), 400
            
    except Exception as e:
        db.session.rollback()
        print(f"Erreur upload icône: {e}")
        return jsonify({
            'success': False,
            'error': f'Erreur upload: {str(e)}'
        }), 500

@main_bp.route('/api/icons/upload_multiple', methods=['POST'])
@AuthSystem.login_required
def api_upload_multiple_icons():
    """Upload de plusieurs icônes en une seule fois"""
    try:
        current_project_id = session.get('current_project_id')
        if not current_project_id:
            return jsonify({
                'success': False,
                'error': 'Aucun projet sélectionné'
            }), 400
        
        files = request.files.getlist('files[]')
        category = request.form.get('category', 'custom')
        
        if not files:
            return jsonify({
                'success': False,
                'error': 'Aucun fichier envoyé'
            }), 400
        
        results = []
        successful = 0
        failed = 0
        
        for file in files:
            if file.filename == '':
                continue
                
            try:
                # Nom personnalisé pour chaque fichier
                custom_name = request.form.get(f'name_{file.filename}', '')
                
                icon_entry, message = IconFileManager.save_uploaded_icon(
                    file, custom_name, category
                )
                
                if icon_entry:
                    successful += 1
                    results.append({
                        'filename': file.filename,
                        'success': True,
                        'icon': icon_entry.to_dict(),
                        'message': message
                    })
                else:
                    failed += 1
                    results.append({
                        'filename': file.filename,
                        'success': False,
                        'message': message
                    })
                    
            except Exception as e:
                failed += 1
                results.append({
                    'filename': file.filename,
                    'success': False,
                    'message': f'Erreur: {str(e)}'
                })
        
        return jsonify({
            'success': True,
            'results': results,
            'summary': {
                'total': len(files),
                'successful': successful,
                'failed': failed
            }
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': f'Erreur upload multiple: {str(e)}'
        }), 500

@main_bp.route('/api/icons/<int:icon_id>', methods=['PUT'])
@AuthSystem.login_required
def api_update_icon(icon_id):
    """Modifier les métadonnées d'une icône avec validation"""
    try:
        icon = IconLibrary.query.get_or_404(icon_id)
        data = request.get_json()
        
        # Vérifier les droits (seul le créateur ou admin peut modifier)
        user = AuthSystem.get_current_user()
        if not user.get('is_hardcoded', True) and user.get('role_level', 0) < 3:
            if icon.cree_par != user.get('id'):
                return jsonify({
                    'success': False,
                    'error': 'Droits insuffisants pour modifier cette icône'
                }), 403
        
        # Validation et mise à jour des champs
        modifiable_fields = ['nom_icon', 'description_icon', 'categorie', 'couleur_defaut']
        updated_fields = []
        
        for field in modifiable_fields:
            if field in data:
                old_value = getattr(icon, field)
                new_value = data[field]
                
                # Validation spécifique par champ
                if field == 'nom_icon' and not new_value.strip():
                    return jsonify({
                        'success': False,
                        'error': 'Le nom de l\'icône ne peut pas être vide'
                    }), 400
                
                if field == 'couleur_defaut' and new_value:
                    if not new_value.startswith('#') or len(new_value) != 7:
                        return jsonify({
                            'success': False,
                            'error': 'Format de couleur invalide (utilisez #RRGGBB)'
                        }), 400
                
                setattr(icon, field, new_value)
                if old_value != new_value:
                    updated_fields.append(field)
        
        if updated_fields:
            db.session.commit()
            return jsonify({
                'success': True,
                'message': f'Icône mise à jour: {", ".join(updated_fields)}',
                'icon': icon.to_dict(),
                'updated_fields': updated_fields
            })
        else:
            return jsonify({
                'success': True,
                'message': 'Aucune modification détectée',
                'icon': icon.to_dict()
            })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@main_bp.route('/api/icons/<int:icon_id>', methods=['DELETE'])
@AuthSystem.login_required
def api_delete_icon(icon_id):
    """Supprimer une icône avec vérifications de sécurité"""
    try:
        icon = IconLibrary.query.get_or_404(icon_id)
        
        # Vérifier les droits
        user = AuthSystem.get_current_user()
        if not user.get('is_hardcoded', True) and user.get('role_level', 0) < 3:
            if icon.cree_par != user.get('id'):
                return jsonify({
                    'success': False,
                    'error': 'Droits insuffisants pour supprimer cette icône'
                }), 403
        
        # Vérifier que l'icône n'est pas utilisée dans le projet actuel
        current_project_id = session.get('current_project_id')
        if current_project_id:
            from app.models.modele_graphics import Animation, ContenirAnimation, Page
            
            # Compter les utilisations dans le projet actuel
            utilisations = db.session.query(Animation).join(ContenirAnimation).join(Page).filter(
                Page.id_projet == current_project_id,
                Animation.regles_animation.contains(f'"id_icon":{icon_id}')
            ).count()
            
            if utilisations > 0:
                return jsonify({
                    'success': False,
                    'error': f'Icône utilisée par {utilisations} objet(s) dans ce projet'
                }), 400
        
        # Supprimer l'icône et son fichier
        nom_icon = icon.nom_icon
        success, message = IconFileManager.delete_icon(icon_id)
        
        if success:
            return jsonify({
                'success': True,
                'message': f'Icône "{nom_icon}" supprimée: {message}'
            })
        else:
            return jsonify({
                'success': False,
                'error': message
            }), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@main_bp.route('/api/icons/<int:icon_id>/duplicate', methods=['POST'])
@AuthSystem.login_required
def api_duplicate_icon(icon_id):
    """Dupliquer une icône (utile pour créer des variations)"""
    try:
        original_icon = IconLibrary.query.get_or_404(icon_id)
        data = request.get_json() or {}
        
        # Créer une copie avec un nouveau nom
        new_name = data.get('new_name', f"{original_icon.nom_icon}_copie")
        new_category = data.get('new_category', original_icon.categorie)
        
        # Vérifier l'unicité du nom
        existing = IconLibrary.query.filter_by(nom_icon=new_name).first()
        if existing:
            new_name = f"{new_name}_{int(time.time())}"
        
        # Dupliquer selon le type d'icône
        if original_icon.type_source == 'upload' and original_icon.fichier_path:
            # Pour les fichiers uploadés, copier le fichier physique
            import shutil
            original_path = original_icon.fichier_path
            filename_parts = os.path.splitext(os.path.basename(original_path))
            new_filename = f"{filename_parts[0]}_copy_{int(time.time())}{filename_parts[1]}"
            new_path = os.path.join(os.path.dirname(original_path), new_filename)
            
            shutil.copy2(original_path, new_path)
            
            duplicate_icon = IconLibrary(
                nom_icon=new_name,
                description_icon=f"Copie de {original_icon.nom_icon}",
                categorie=new_category,
                type_source=original_icon.type_source,
                fichier_path=new_path,
                fichier_original=new_filename,
                mime_type=original_icon.mime_type,
                taille_fichier=original_icon.taille_fichier,
                largeur_defaut=original_icon.largeur_defaut,
                hauteur_defaut=original_icon.hauteur_defaut,
                couleur_defaut=original_icon.couleur_defaut,
                date_creation=datetime.utcnow(),
                actif=True
            )
        else:
            # Pour les icônes externes ou industrielles, juste dupliquer les métadonnées
            duplicate_icon = IconLibrary(
                nom_icon=new_name,
                description_icon=f"Copie de {original_icon.nom_icon}",
                categorie=new_category,
                type_source=original_icon.type_source,
                external_name=original_icon.external_name,
                external_library=original_icon.external_library,
                unicode_char=original_icon.unicode_char,
                is_unicode=original_icon.is_unicode,
                largeur_defaut=original_icon.largeur_defaut,
                hauteur_defaut=original_icon.hauteur_defaut,
                couleur_defaut=original_icon.couleur_defaut,
                date_creation=datetime.utcnow(),
                actif=True
            )
        
        user = AuthSystem.get_current_user()
        if not user.get('is_hardcoded', True):
            duplicate_icon.cree_par = user['id']
        
        db.session.add(duplicate_icon)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Icône dupliquée: "{new_name}"',
            'original': original_icon.to_dict(),
            'duplicate': duplicate_icon.to_dict()
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': f'Erreur duplication: {str(e)}'
        }), 500

# =================================================================
# ENDPOINTS POUR SERVIR LES FICHIERS AVEC OPTIMISATIONS
# =================================================================

@main_bp.route('/static/icons/custom/<filename>')
def serve_custom_icon(filename):
    """Sert les icônes uploadées avec cache et validation"""
    try:
        from flask import current_app

        # Chemin absolu correct vers le dossier des icônes uploadées
        upload_folder = os.path.join(current_app.root_path, 'static', 'icons', 'custom')
        
        # Validation de sécurité sur le nom de fichier
        if '..' in filename or '/' in filename or '\\' in filename:
            return jsonify({'error': 'Nom de fichier invalide'}), 400
        
        # Vérifier que le fichier existe en base ET physiquement
        icon = IconLibrary.query.filter(
            IconLibrary.fichier_path.contains(filename),
            IconLibrary.actif == True
        ).first()
        
        if not icon:
            return jsonify({'error': 'Icône non autorisée'}), 404
        
        file_path = os.path.join(upload_folder, filename)
        if not os.path.exists(file_path):
            return jsonify({'error': 'Fichier physique manquant'}), 404
        
        # Envoi du fichier correctement depuis le dossier absolu
        return send_from_directory(upload_folder, filename)
        
    except Exception as e:
        print(f"Erreur service icône {filename}: {e}")
        return jsonify({'error': 'Erreur serveur'}), 500


@main_bp.route('/api/icons/<int:icon_id>/preview')
@AuthSystem.login_required
def api_get_icon_preview(icon_id):
    """Récupère les données détaillées d'une icône pour prévisualisation"""
    try:
        icon = IconLibrary.query.get_or_404(icon_id)
        
        preview_data = {
            'id': icon.id_icon,
            'nom': icon.nom_icon,
            'description': icon.description_icon,
            'categorie': icon.categorie,
            'type': icon.type_source,
            'couleur_defaut': icon.couleur_defaut,
            'taille_defaut': {
                'width': icon.largeur_defaut,
                'height': icon.hauteur_defaut
            },
            'date_creation': icon.date_creation.isoformat() if icon.date_creation else None,
            'actif': icon.actif
        }
        
        # Données spécifiques selon le type
        if icon.type_source == 'external':
            preview_data['external'] = {
                'library': icon.external_library,
                'name': icon.external_name
            }
        elif icon.type_source == 'industrial':
            preview_data['unicode'] = {
                'char': icon.unicode_char,
                'is_unicode': icon.is_unicode
            }
        elif icon.type_source == 'upload':
            preview_data['file'] = {
                'original_name': icon.fichier_original,
                'mime_type': icon.mime_type,
                'size_bytes': icon.taille_fichier,
                'url': icon.get_url()
            }
        
        return jsonify({
            'success': True,
            'preview': preview_data
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# =================================================================
# ADMINISTRATION ET MAINTENANCE DES ICÔNES
# =================================================================

@main_bp.route('/api/admin/icons/init-defaults', methods=['POST'])
@AuthSystem.admin_required
def api_init_default_icons():
    """Réinitialise les icônes industrielles par défaut"""
    try:
        from app.models.modele_graphics import init_default_industrial_icons, init_feather_icons
        
        # Initialiser les icônes industrielles
        init_default_industrial_icons()
        
        # Initialiser quelques icônes Feather populaires
        init_feather_icons()
        
        # Compter le total
        total_icons = IconLibrary.query.filter_by(actif=True).count()
        
        return jsonify({
            'success': True,
            'message': f'Icônes par défaut réinitialisées (total: {total_icons})'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@main_bp.route('/api/admin/icons/cleanup', methods=['POST'])
@AuthSystem.admin_required
def api_cleanup_unused_icons():
    """Nettoie les icônes uploadées non utilisées"""
    try:
        from app.models.modele_graphics import Animation
        
        # Trouver les icônes uploadées non utilisées
        # Note: Cette requête est simplifiée - dans un vrai système, il faudrait parser le JSON des regles_animation
        used_icon_paths = db.session.query(Animation.regles_animation).filter(
            Animation.regles_animation.contains('icon_data')
        ).all()
        
        # Extraction basique des icônes utilisées (à améliorer selon le format exact)
        used_icons = set()
        for regles_tuple in used_icon_paths:
            try:
                regles = json.loads(regles_tuple[0]) if regles_tuple[0] else {}
                if 'icon_data' in regles:
                    icon_data = json.loads(regles['icon_data']) if isinstance(regles['icon_data'], str) else regles['icon_data']
                    if isinstance(icon_data, dict) and 'id_icon' in icon_data:
                        used_icons.add(icon_data['id_icon'])
            except:
                continue
        
        # Trouver les icônes uploadées non utilisées
        unused_icons = IconLibrary.query.filter(
            IconLibrary.type_source == 'upload',
            ~IconLibrary.id_icon.in_(list(used_icons)),
            IconLibrary.actif == True
        ).all()
        
        deleted_count = 0
        for icon in unused_icons:
            success, _ = IconFileManager.delete_icon(icon.id_icon)
            if success:
                deleted_count += 1
        
        return jsonify({
            'success': True,
            'message': f'{deleted_count} icône(s) non utilisée(s) supprimée(s)',
            'details': {
                'total_checked': len(unused_icons),
                'deleted_count': deleted_count,
                'used_icons_found': len(used_icons)
            }
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@main_bp.route('/api/admin/icons/stats', methods=['GET'])
@AuthSystem.admin_required
def api_get_admin_icon_stats():
    """Statistiques détaillées pour l'administration"""
    try:
        stats = {
            'total_icons': IconLibrary.query.filter_by(actif=True).count(),
            'by_type': {},
            'by_category': {},
            'disk_usage': {'total_mb': 0, 'file_count': 0},
            'recent_uploads': []
        }
        
        # Statistiques par type
        type_stats = db.session.query(
            IconLibrary.type_source,
            db.func.count(IconLibrary.id_icon).label('count')
        ).filter_by(actif=True).group_by(IconLibrary.type_source).all()
        
        for type_src, count in type_stats:
            stats['by_type'][type_src] = count
        
        # Statistiques par catégorie
        cat_stats = db.session.query(
            IconLibrary.categorie,
            db.func.count(IconLibrary.id_icon).label('count')
        ).filter_by(actif=True).group_by(IconLibrary.categorie).all()
        
        for category, count in cat_stats:
            stats['by_category'][category or 'Sans catégorie'] = count
        
        # Utilisation disque pour les fichiers uploadés
        uploaded_icons = IconLibrary.query.filter_by(
            type_source='upload', 
            actif=True
        ).all()
        
        total_size = sum([icon.taille_fichier or 0 for icon in uploaded_icons])
        stats['disk_usage']['total_mb'] = round(total_size / 1024 / 1024, 2)
        stats['disk_usage']['file_count'] = len(uploaded_icons)
        
        # Uploads récents (7 derniers jours)
        from datetime import datetime, timedelta
        recent_date = datetime.utcnow() - timedelta(days=7)
        recent_uploads = IconLibrary.query.filter(
            IconLibrary.date_creation >= recent_date,
            IconLibrary.type_source == 'upload',
            IconLibrary.actif == True
        ).order_by(IconLibrary.date_creation.desc()).limit(10).all()
        
        stats['recent_uploads'] = [{
            'nom': icon.nom_icon,
            'date': icon.date_creation.isoformat(),
            'taille_kb': round((icon.taille_fichier or 0) / 1024, 1)
        } for icon in recent_uploads]
        
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
# UTILITAIRES ET HELPERS
# =================================================================

def get_category_display_name(category):
    """Retourne le nom d'affichage d'une catégorie avec icône"""
    display_names = {
        'actionneurs': '⚡ Actionneurs',
        'capteurs': '📊 Capteurs', 
        'vannes': '🔵 Vannes',
        'tuyauterie': '🔗 Tuyauterie',
        'indicateurs': '🔟 Indicateurs',
        'controle': '🎮 Contrôle',
        'custom': '🎨 Personnalisé',
        'industrial': '🏭 Industriel',
        'interface': '💻 Interface',
        'navigation': '🧭 Navigation',
        'outils': '🔧 Outils'
    }
    return display_names.get(category, f'📁 {category.capitalize()}' if category else '📁 Sans catégorie')

def get_type_display_name(type_source):
    """Retourne le nom d'affichage d'un type de source"""
    type_names = {
        'industrial': 'Industrielle',
        'external': 'Externe', 
        'upload': 'Personnalisée'
    }
    return type_names.get(type_source, type_source.capitalize())

# =================================================================
# INTÉGRATION AVEC L'ÉDITEUR GRAPHIQUE
# =================================================================

@main_bp.route('/api/graphics/icons/for-designer', methods=['GET'])
@AuthSystem.login_required
def api_get_icons_for_designer():
    """API optimisée pour l'éditeur graphique - Organisée par catégories"""
    try:
        # Récupérer uniquement les icônes actives organisées pour l'éditeur
        icons = IconLibrary.query.filter_by(actif=True).order_by(
            IconLibrary.type_source,
            IconLibrary.categorie,
            IconLibrary.nom_icon
        ).all()
        
        # Organiser par type pour les grilles de l'éditeur
        organized_icons = {
            'industrial': [icon.to_dict() for icon in icons if icon.type_source == 'industrial'],
            'custom': [icon.to_dict() for icon in icons if icon.type_source == 'upload'], 
            'external': [icon.to_dict() for icon in icons if icon.type_source == 'external']
        }
        
        return jsonify({
            'success': True,
            'icons': organized_icons,
            'counts': {
                'industrial': len(organized_icons['industrial']),
                'custom': len(organized_icons['custom']),
                'external': len(organized_icons['external']),
                'total': len(icons)
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500