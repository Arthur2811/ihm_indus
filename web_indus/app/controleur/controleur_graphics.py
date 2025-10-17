from flask import render_template, request, jsonify, redirect, url_for, flash, current_app, session
from app.controleur import main_bp
from app.models.modele_tag import Tag
from app.models.modele_auth import AuthSystem
from app.models.modele_graphics import ColorRule
from app import db
import json
import time
from datetime import datetime


# =================================================================
# CONTRÔLEUR GRAPHICS ÉTENDU AVEC SUPPORT COMPLET DES ICÔNES ET NAVIGATION
# =================================================================

# Cache simple pour le runtime (n'affecte pas le reste)
runtime_cache_values = {}  # Cache des valeurs runtime
runtime_cache_tags = {}    # Cache des résolutions de tags

# =================================================================
# FONCTION DE RÉSOLUTION DES TAGS AMÉLIORÉE
# =================================================================

def resoudre_adresse_tag(tag_reference, projet_id=None):
    """
    Résout une référence de tag en adresse S7 AVEC filtrage par projet
    - Si c'est déjà une adresse S7 (DB1.DBX0.0) -> retourne tel quel
    - Si c'est un nom de tag (bp_marche) -> cherche l'adresse dans la BDD du projet
    """
    if not tag_reference or not tag_reference.strip():
        return tag_reference
    
    # Vérifier si c'est déjà une adresse S7
    if 'DB' in tag_reference.upper() and '.' in tag_reference:
        return tag_reference
    
    # Sinon, chercher par nom de tag dans le projet
    try:
        if not projet_id:
            projet_id = session.get('current_project_id')
        
        query = Tag.query.filter_by(nom_tag=tag_reference)
        if projet_id:
            query = query.filter_by(id_projet=projet_id)
        
        tag = query.first()
        
        if tag:
            adresse = tag.adresse_tag
            print(f"🔍 Résolution tag '{tag_reference}' -> '{adresse}' (projet {projet_id})")
            return adresse
        else:
            print(f"⚠️ Tag '{tag_reference}' non trouvé dans le projet {projet_id}")
            return tag_reference
    except Exception as e:
        print(f"❌ Erreur résolution tag '{tag_reference}': {e}")
        return tag_reference

# =================================================================
# ROUTES ÉDITEUR GRAPHIQUE AVEC SUPPORT ICÔNES
# =================================================================

@main_bp.route('/graphics')
@AuthSystem.login_required
def graphics():
    """Route simple pour rediriger vers l'éditeur"""
    return redirect(url_for('main.graphics_designer'))

@main_bp.route('/graphics/designer')
@main_bp.route('/graphics/designer/<int:page_id>')
@AuthSystem.login_required
def graphics_designer(page_id=None):
    """Éditeur graphique - AVEC support icônes complet"""
    current_project_id = session.get('current_project_id')
    if not current_project_id:
        flash('Aucun projet sélectionné', 'warning')
        return redirect(url_for('main.projects_management'))
    
    from app.models.modele_graphics import Page, Animation, ContenirAnimation
    
    if page_id:
        # Vérifier que la page appartient au projet
        page = Page.query.filter_by(
            id_page=page_id,
            id_projet=current_project_id
        ).first()
        
        if not page:
            flash('Page non trouvée dans ce projet', 'error')
            return redirect(url_for('main.graphics_designer'))
        
        animations = Animation.query.join(ContenirAnimation).filter(
            ContenirAnimation.id_page == page_id
        ).all()
    else:
        # Page par défaut DU PROJET
        page = Page.query.filter_by(
            id_projet=current_project_id,
            page_accueil=True
        ).first()
        
        if not page:
            page = Page.query.filter_by(id_projet=current_project_id).first()
        
        animations = []
        if page:
            animations = Animation.query.join(ContenirAnimation).filter(
                ContenirAnimation.id_page == page.id_page
            ).all()
    
    # Tags du projet uniquement
    tags_disponibles = Tag.query.filter_by(id_projet=current_project_id).all()
    
    return render_template('graphics/designer.html', 
                         page=page, 
                         animations=animations,
                         tags_disponibles=tags_disponibles)

@main_bp.route('/graphics/runtime')
@main_bp.route('/graphics/runtime/<int:page_id>')
@AuthSystem.login_required
def graphics_runtime(page_id=None):
    """Mode Runtime - AVEC support icônes"""
    current_project_id = session.get('current_project_id')
    if not current_project_id:
        flash('Aucun projet sélectionné', 'warning')
        return redirect(url_for('main.projects_management'))
    
    from app.models.modele_graphics import Page, Animation, ContenirAnimation
    
    if page_id:
        page = Page.query.filter_by(
            id_page=page_id,
            id_projet=current_project_id
        ).first()
        
        if not page:
            flash('Page non trouvée dans ce projet', 'error')
            return redirect(url_for('main.graphics_runtime'))
            
        animations = Animation.query.join(ContenirAnimation).filter(
            ContenirAnimation.id_page == page_id
        ).all()
    else:
        page = Page.query.filter_by(
            id_projet=current_project_id,
            page_accueil=True
        ).first()
        
        if not page:
            page = Page.query.filter_by(id_projet=current_project_id).first()
        
        if page:
            animations = Animation.query.join(ContenirAnimation).filter(
                ContenirAnimation.id_page == page.id_page
            ).all()
        else:
            animations = []
    
    return render_template('graphics/runtime.html', page=page, animations=animations)

# =================================================================
# API GRAPHICS - GESTION DES PAGES ET OBJETS AVEC ICÔNES
# =================================================================

@main_bp.route('/api/graphics/pages', methods=['GET'])
@AuthSystem.login_required
def api_get_pages():
    """Liste des pages - CORRIGÉE avec filtre projet"""
    current_project_id = session.get('current_project_id')
    if not current_project_id:
        return jsonify({
            'success': False,
            'error': 'Aucun projet sélectionné'
        }), 400
    
    try:
        from app.models.modele_graphics import Page
        
        pages = Page.query.filter_by(id_projet=current_project_id).all()
        
        return jsonify({
            'success': True,
            'pages': [{
                'id': page.id_page,
                'nom': page.nom_page,
                'largeur': page.largeur_page,
                'hauteur': page.hauteur_page,
                'couleur_fond': page.couleur_fond,
                'page_accueil': page.page_accueil
            } for page in pages],
            'projet_id': current_project_id
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@main_bp.route('/api/graphics/pages', methods=['POST'])
@AuthSystem.login_required
def api_create_page():
    """Créer une nouvelle page - AVEC lien projet"""
    current_project_id = session.get('current_project_id')
    if not current_project_id:
        return jsonify({
            'success': False,
            'error': 'Aucun projet sélectionné'
        }), 400
    
    data = request.get_json()
    
    try:
        from app.models.modele_graphics import Page
        
        nouvelle_page = Page(
            nom_page=data.get('nom', 'Nouvelle Page'),
            largeur_page=data.get('largeur', 1920),
            hauteur_page=data.get('hauteur', 1080),
            couleur_fond=data.get('couleur_fond', '#F0F0F0'),
            page_accueil=data.get('page_accueil', False),
            ordre_affichage=data.get('ordre_affichage', 1),
            id_projet=current_project_id
        )
        
        db.session.add(nouvelle_page)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Page créée dans le projet {current_project_id}',
            'page_id': nouvelle_page.id_page
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@main_bp.route('/api/graphics/pages/<int:page_id>', methods=['PUT'])
@AuthSystem.login_required
def api_update_page(page_id):
    """Mettre à jour les propriétés d'une page"""
    current_project_id = session.get('current_project_id')
    if not current_project_id:
        return jsonify({'success': False, 'error': 'Aucun projet sélectionné'}), 400
    
    try:
        from app.models.modele_graphics import Page
        page = Page.query.filter_by(id_page=page_id, id_projet=current_project_id).first()
        
        if not page:
            return jsonify({'success': False, 'error': 'Page non trouvée'}), 404
        
        data = request.get_json()
        if 'largeur_page' in data:
            page.largeur_page = max(800, min(4000, int(data['largeur_page'])))
        if 'hauteur_page' in data:
            page.hauteur_page = max(600, min(3000, int(data['hauteur_page'])))
        
        db.session.commit()
        return jsonify({'success': True, 'message': 'Page mise à jour avec succès'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@main_bp.route('/api/graphics/animations/<int:page_id>', methods=['GET'])
@AuthSystem.login_required
def api_get_animations(page_id):
    """Récupérer les animations d'une page AVEC données icônes"""
    from app.models.modele_graphics import Animation, ContenirAnimation
    
    try:
        animations = Animation.query.join(ContenirAnimation).filter(
            ContenirAnimation.id_page == page_id
        ).all()
        
        animations_data = []
        for anim in animations:
            anim_dict = anim.to_dict()
            
            # NOUVEAU : Enrichir avec les données d'icônes si applicable
            if anim.type_objet == 'icon':
                icon_info = anim.get_icon_info()
                if icon_info:
                    anim_dict['icon_info'] = icon_info
            
            animations_data.append(anim_dict)
        
        return jsonify({
            'success': True,
            'animations': animations_data
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@main_bp.route('/api/graphics/animations', methods=['POST'])
@AuthSystem.login_required
def api_create_animation():
    """Créer un objet graphique AVEC support icônes complet - CORRIGÉ"""
    data = request.get_json()
    
    try:
        from app.models.modele_graphics import Animation, ContenirAnimation
        
        print(f"🔍 Données reçues pour création animation: {data}")
        
        # Règles d'animation par défaut selon le type
        regles_defaut = {
            'couleur_condition': data.get('tag_lie', '') if data.get('tag_lie') else '',
            'valeur_active': True if data.get('type_objet') == 'button' else 1,
            'animation_type': 'couleur',
            'vitesse': 1000,
            'tag_lie': data.get('tag_lie', ''),
            'action_clic': data.get('action_clic', 'read'),
            'valeur_ecriture': data.get('valeur_ecriture', ''),
            # NOUVEAU : Support navigation
            'page_destination': data.get('page_destination', '')
        }
        
        # CORRECTION CRITIQUE : Gestion des données d'icône
        if data.get('type_objet') == 'icon':
            print("🖼️ Création d'un objet icône")
            
            # Récupérer les données d'icône depuis le frontend
            icon_data_raw = data.get('icon_data', '{}')
            print(f"📦 Données icône reçues (brutes): {icon_data_raw}")
            
            # S'assurer que c'est du JSON valide
            if isinstance(icon_data_raw, str):
                try:
                    # Tester si c'est du JSON valide
                    json.loads(icon_data_raw)
                    icon_data_json = icon_data_raw
                except json.JSONDecodeError as e:
                    print(f"❌ Erreur JSON icon_data: {e}")
                    icon_data_json = '{}'
            elif isinstance(icon_data_raw, dict):
                icon_data_json = json.dumps(icon_data_raw)
            else:
                icon_data_json = '{}'
            
            print(f"🔍 Données icône finales (JSON): {icon_data_json}")
            
            regles_defaut.update({
                'icon_data': icon_data_json,  # IMPORTANT: Utiliser les vraies données
                'icon_source': data.get('icon_source', 'upload'),
                'icon_size': float(data.get('icon_size', 1.0)),
                'icon_rotation': int(data.get('icon_rotation', 0)),
                'icon_keep_aspect': bool(data.get('icon_keep_aspect', True)),
                'icon_opacity': float(data.get('icon_opacity', 1.0)),
                'icon_flip_x': bool(data.get('icon_flip_x', False)),
                'icon_flip_y': bool(data.get('icon_flip_y', False))
            })
            
            print(f"⚙️ Règles complètes pour icône: {regles_defaut}")
        
        # CORRECTION PRINCIPALE : Créer l'animation SANS passer regles_animation au constructeur
        nouvelle_animation = Animation(
            nom_animation=data.get('nom', f"Objet_{int(time.time())}"),
            type_objet=data.get('type_objet', 'rectangle'),
            position_x=data.get('x', 100),
            position_y=data.get('y', 100),
            largeur=data.get('width', 100),
            hauteur=data.get('height', 50),
            couleur_normale=data.get('couleur_normale', '#CCCCCC'),
            couleur_active=data.get('couleur_active', '#00FF00'),
            texte_affiche=data.get('texte', '')
            # SUPPRIMÉ: regles_animation=json.dumps(regles_defaut)
        )
        
        # CORRECTION : Définir les règles APRÈS la création
        nouvelle_animation.set_regles_animation(regles_defaut)
        
        print(f"💾 Animation créée avec regles_animation: {nouvelle_animation.regles_animation}")
        
        db.session.add(nouvelle_animation)
        db.session.flush()  # Pour obtenir l'ID
        
        # Lier à la page
        page_id = data.get('page_id')
        if page_id:
            liaison = ContenirAnimation(
                id_animation=nouvelle_animation.id_animation,
                id_page=page_id
            )
            db.session.add(liaison)
        
        db.session.commit()
        
        # Vérification finale des données
        icon_data_verification = nouvelle_animation.get_icon_data()
        print(f"🔍 Données icône récupérées après création: {icon_data_verification}")
        
        # NOUVEAU : Incrémenter la popularité de l'icône si applicable
        if nouvelle_animation.type_objet == 'icon' and icon_data_verification:
            try:
                if 'id_icon' in icon_data_verification:
                    from app.models.modele_graphics import IconLibrary
                    icon = IconLibrary.query.get(icon_data_verification['id_icon'])
                    if icon:
                        icon.increment_popularity()
                        db.session.commit()
                        print(f"📈 Popularité icône {icon.nom_icon} incrémentée")
            except Exception as e:
                print(f"⚠️ Erreur incrémentation popularité icône: {e}")
        
        # Préparer la réponse avec toutes les données
        response_data = nouvelle_animation.to_dict()
        print(f"📤 Données renvoyées au frontend: {response_data}")
        
        return jsonify({
            'success': True,
            'message': 'Objet créé avec succès',
            'animation': response_data
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Erreur création animation: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@main_bp.route('/api/graphics/animations/<int:animation_id>', methods=['PUT'])
@AuthSystem.login_required
def api_update_animation(animation_id):
    """Modifier un objet graphique AVEC propriétés icônes ET navigation"""
    from app.models.modele_graphics import Animation
    
    animation = Animation.query.get_or_404(animation_id)
    data = request.get_json()
    
    try:
        # Mettre à jour les propriétés de base
        if 'nom' in data:
            animation.nom_animation = data['nom']
        if 'x' in data:
            animation.position_x = data['x']
        if 'y' in data:
            animation.position_y = data['y']
        if 'width' in data:
            animation.largeur = data['width']
        if 'height' in data:
            animation.hauteur = data['height']
        if 'couleur_normale' in data:
            animation.couleur_normale = data['couleur_normale']
        if 'couleur_active' in data:
            animation.couleur_active = data['couleur_active']
        if 'texte' in data:
            animation.texte_affiche = data['texte']
        
        # Récupérer les règles existantes
        regles = animation.get_regles_animation()
        
        # Mettre à jour les règles standard
        if 'tag_lie' in data:
            regles['tag_lie'] = data['tag_lie']
            animation.tag_lie = data['tag_lie']  # Propriété directe pour compatibilité
        if 'action_clic' in data:
            regles['action_clic'] = data['action_clic']
            animation.action_clic = data['action_clic']
        if 'valeur_ecriture' in data:
            regles['valeur_ecriture'] = data['valeur_ecriture']
            animation.valeur_ecriture = data['valeur_ecriture']
        
        # NOUVEAU : Gestion de la page de destination pour navigation
        if 'page_destination' in data:
            regles['page_destination'] = data['page_destination']
            animation.page_destination = data['page_destination']
            print(f"🧭 Page destination mise à jour: {data['page_destination']}")
        
        # NOUVEAU : Gérer les propriétés spécifiques aux icônes
        if animation.type_objet == 'icon':
            icon_properties_updated = []
            
            if 'icon_data' in data:
                regles['icon_data'] = data['icon_data'] if isinstance(data['icon_data'], str) else json.dumps(data['icon_data'])
                icon_properties_updated.append('données icône')
            if 'icon_source' in data:
                regles['icon_source'] = data['icon_source']
                icon_properties_updated.append('source')
            if 'icon_size' in data:
                regles['icon_size'] = float(data['icon_size'])
                icon_properties_updated.append('taille')
            if 'icon_rotation' in data:
                regles['icon_rotation'] = int(data['icon_rotation'])
                icon_properties_updated.append('rotation')
            if 'icon_keep_aspect' in data:
                regles['icon_keep_aspect'] = bool(data['icon_keep_aspect'])
                icon_properties_updated.append('proportions')
            if 'icon_opacity' in data:
                regles['icon_opacity'] = float(data['icon_opacity'])
                icon_properties_updated.append('opacité')
            if 'icon_flip_x' in data:
                regles['icon_flip_x'] = bool(data['icon_flip_x'])
                icon_properties_updated.append('miroir X')
            if 'icon_flip_y' in data:
                regles['icon_flip_y'] = bool(data['icon_flip_y'])
                icon_properties_updated.append('miroir Y')
            
            if icon_properties_updated:
                print(f"🖼️ Propriétés icône mises à jour: {', '.join(icon_properties_updated)}")
        
        # Sauvegarder les règles mises à jour
        animation.set_regles_animation(regles)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Objet modifié avec succès',
            'animation': animation.to_dict()
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"Erreur mise à jour animation: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@main_bp.route('/api/graphics/animations/<int:animation_id>', methods=['DELETE'])
@AuthSystem.login_required
def api_delete_animation(animation_id):
    """Supprimer un objet graphique"""
    from app.models.modele_graphics import Animation, ContenirAnimation
    
    animation = Animation.query.get_or_404(animation_id)
    
    try:
        # Supprimer les liaisons
        ContenirAnimation.query.filter_by(id_animation=animation_id).delete()
        
        # Supprimer l'animation
        db.session.delete(animation)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Objet supprimé avec succès'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# =================================================================
# NOUVELLES APIS POUR LA NAVIGATION ENTRE PAGES
# =================================================================

@main_bp.route('/api/graphics/navigation/pages/<int:current_page_id>')
@AuthSystem.login_required
def api_get_navigation_pages(current_page_id):
    """API spécialisée pour récupérer les pages disponibles pour navigation"""
    current_project_id = session.get('current_project_id')
    if not current_project_id:
        return jsonify({
            'success': False,
            'error': 'Aucun projet sélectionné'
        }), 400
    
    try:
        from app.models.modele_graphics import Page
        
        # Récupérer toutes les pages du projet SAUF la page courante
        pages = Page.query.filter(
            Page.id_projet == current_project_id,
            Page.id_page != current_page_id
        ).order_by(Page.ordre_affichage, Page.nom_page).all()
        
        return jsonify({
            'success': True,
            'pages': [{
                'id': page.id_page,
                'nom': page.nom_page,
                'largeur': page.largeur_page,
                'hauteur': page.hauteur_page,
                'couleur_fond': page.couleur_fond,
                'page_accueil': page.page_accueil,
                'description': f"{page.nom_page} ({page.largeur_page}×{page.hauteur_page}px)"
            } for page in pages],
            'total': len(pages),
            'current_page_id': current_page_id,
            'projet_id': current_project_id
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@main_bp.route('/api/graphics/navigation/validate', methods=['POST'])
@AuthSystem.login_required
def api_validate_navigation():
    """Valide une configuration de navigation avant sauvegarde"""
    data = request.get_json()
    animation_id = data.get('animation_id')
    page_destination = data.get('page_destination')
    
    if not animation_id or not page_destination:
        return jsonify({
            'success': False,
            'error': 'Paramètres manquants'
        }), 400
    
    try:
        from app.models.modele_graphics import Animation, Page, ContenirAnimation
        
        # Vérifier que l'animation existe
        animation = Animation.query.get(animation_id)
        if not animation:
            return jsonify({
                'success': False,
                'error': 'Animation introuvable'
            }), 404
        
        # Vérifier que la page de destination existe
        page_destination_obj = Page.query.get(page_destination)
        if not page_destination_obj:
            return jsonify({
                'success': False,
                'error': 'Page de destination introuvable'
            }), 404
        
        # Récupérer la page courante de l'animation
        current_page = db.session.query(Page).join(
            ContenirAnimation, Page.id_page == ContenirAnimation.id_page
        ).filter(ContenirAnimation.id_animation == animation_id).first()
        
        if not current_page:
            return jsonify({
                'success': False,
                'error': 'Page courante introuvable'
            }), 404
        
        # Validations
        if current_page.id_projet != page_destination_obj.id_projet:
            return jsonify({
                'success': False,
                'error': 'La page de destination doit être dans le même projet'
            }), 400
        
        if current_page.id_page == page_destination_obj.id_page:
            return jsonify({
                'success': False,
                'error': 'Une page ne peut pas naviguer vers elle-même'
            }), 400
        
        return jsonify({
            'success': True,
            'message': 'Configuration de navigation valide',
            'navigation_info': {
                'from_page': {
                    'id': current_page.id_page,
                    'nom': current_page.nom_page
                },
                'to_page': {
                    'id': page_destination_obj.id_page,
                    'nom': page_destination_obj.nom_page,
                    'largeur': page_destination_obj.largeur_page,
                    'hauteur': page_destination_obj.hauteur_page
                },
                'animation': {
                    'id': animation.id_animation,
                    'nom': animation.nom_animation,
                    'type': animation.type_objet
                }
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@main_bp.route('/api/graphics/navigation/statistics/<int:project_id>')
@AuthSystem.login_required
def api_navigation_statistics(project_id):
    """Statistiques sur les navigations configurées dans un projet"""
    try:
        from app.models.modele_graphics import Animation, Page, ContenirAnimation
        
        # Récupérer toutes les pages du projet
        pages = Page.query.filter_by(id_projet=project_id).all()
        page_ids = [p.id_page for p in pages]
        
        if not page_ids:
            return jsonify({
                'success': True,
                'statistics': {
                    'total_pages': 0,
                    'navigation_objects': 0,
                    'pages_with_navigation': 0,
                    'navigation_enabled': False
                }
            })
        
        # Compter les objets avec navigation configurée
        animations_with_navigation = Animation.query.join(ContenirAnimation).filter(
            ContenirAnimation.id_page.in_(page_ids),
            Animation.regles_animation.contains('"action_clic":"navigate"')
        ).all()
        
        # Analyser les destinations de navigation
        navigation_destinations = {}
        pages_with_nav_objects = set()
        
        for anim in animations_with_navigation:
            try:
                regles = anim.get_regles_animation()
                page_dest = regles.get('page_destination')
                if page_dest:
                    # Récupérer la page source
                    source_page = db.session.query(Page).join(
                        ContenirAnimation, Page.id_page == ContenirAnimation.id_page
                    ).filter(ContenirAnimation.id_animation == anim.id_animation).first()
                    
                    if source_page:
                        pages_with_nav_objects.add(source_page.id_page)
                        
                        dest_page = Page.query.get(page_dest)
                        if dest_page:
                            nav_key = f"{source_page.nom_page} → {dest_page.nom_page}"
                            if nav_key not in navigation_destinations:
                                navigation_destinations[nav_key] = []
                            navigation_destinations[nav_key].append({
                                'animation_id': anim.id_animation,
                                'animation_name': anim.nom_animation,
                                'animation_type': anim.type_objet
                            })
            except:
                continue
        
        return jsonify({
            'success': True,
            'statistics': {
                'total_pages': len(pages),
                'navigation_objects': len(animations_with_navigation),
                'pages_with_navigation': len(pages_with_nav_objects),
                'navigation_enabled': len(animations_with_navigation) > 0,
                'navigation_paths': navigation_destinations,
                'project_id': project_id
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# =================================================================
# API RUNTIME - LECTURE/ÉCRITURE TEMPS RÉEL AVEC ICÔNES ET NAVIGATION - CORRIGÉE
# =================================================================

@main_bp.route('/api/graphics/runtime/values/<int:page_id>')
@AuthSystem.login_required
def api_get_runtime_values(page_id):
    """Version corrigée avec couleurs dynamiques ET données complètes pour icônes"""
    try:
        from app.controleur.controleur_tags import automate
        from app.models.modele_graphics import apply_color_rules_batch
    except ImportError:
        return jsonify({'success': False, 'error': 'Module automate non disponible'}), 500
    
    from app.models.modele_graphics import Animation, ContenirAnimation, ColorRule
    
    try:
        # Récupérer TOUTES les animations de la page
        animations = Animation.query.join(ContenirAnimation).filter(
            ContenirAnimation.id_page == page_id
        ).all()
        
        print(f"📊 Runtime API - Page {page_id}: {len(animations)} objets trouvés")
        
        # Séparer les animations avec et sans tags
        animations_avec_tags = [a for a in animations if a.tag_lie and a.tag_lie.strip()]
        animations_sans_tags = [a for a in animations if not (a.tag_lie and a.tag_lie.strip())]
        
        print(f"  - {len(animations_avec_tags)} avec tags")
        print(f"  - {len(animations_sans_tags)} sans tags")
        
        valeurs = {}
        animations_avec_valeurs = []
        current_project_id = session.get('current_project_id')
        
        # TRAITER TOUTES LES ANIMATIONS, pas seulement celles avec tags
        for animation in animations:
            try:
                # Données de base pour tous les objets
                animation_data = {
                    'valeur': None,
                    'qualite': 'NO_TAG' if not animation.tag_lie else 'READING',
                    'timestamp': datetime.now().isoformat(),
                    'couleur_normale': animation.couleur_normale,
                    'couleur_actuelle': animation.couleur_normale,
                    'objet_type': animation.type_objet
                }
                
                # CORRECTION PRINCIPALE : Ajouter les données complètes pour le rendu frontend
                # Récupérer les règles pour avoir les données d'icônes
                regles = animation.get_regles_animation()
                
                # Pour les icônes, s'assurer que les données sont disponibles
                if animation.type_objet == 'icon':
                    icon_data_raw = regles.get('icon_data', '{}')
                    
                    # Parser et vérifier les données d'icône
                    try:
                        if isinstance(icon_data_raw, str):
                            icon_data_parsed = json.loads(icon_data_raw) if icon_data_raw.strip() else {}
                        else:
                            icon_data_parsed = icon_data_raw or {}
                        
                        # NOUVEAU : Passer les données d'icône au frontend
                        animation_data['icon_data'] = icon_data_parsed
                        animation_data['icon_size'] = regles.get('icon_size', 1.0)
                        animation_data['icon_rotation'] = regles.get('icon_rotation', 0)
                        
                        print(f"🖼️ Icône {animation.nom_animation}: {icon_data_parsed.get('nom_icon', 'INCONNU')}")
                        
                    except Exception as e:
                        print(f"❌ Erreur parsing icon_data pour {animation.nom_animation}: {e}")
                        animation_data['icon_data'] = {}
                
                # Si l'animation a un tag, lire sa valeur
                if animation.tag_lie and animation.tag_lie.strip():
                    try:
                        adresse_resolue = resoudre_adresse_tag(animation.tag_lie, current_project_id)
                        valeur, qualite = automate.lire_tag_par_adresse(adresse_resolue)
                        
                        animation_data.update({
                            'valeur': valeur,
                            'qualite': qualite,
                            'tag_adresse': adresse_resolue
                        })
                        
                        if valeur is not None:
                            animations_avec_valeurs.append((animation, valeur))
                            
                    except Exception as e:
                        animation_data.update({
                            'valeur': None,
                            'qualite': 'ERROR',
                            'error': str(e)
                        })
                
                valeurs[animation.id_animation] = animation_data
                
            except Exception as e:
                print(f"❌ Erreur traitement animation {animation.id_animation}: {e}")
                valeurs[animation.id_animation] = {
                    'valeur': None,
                    'qualite': 'ERROR',
                    'error': str(e),
                    'couleur_normale': animation.couleur_normale or '#CCCCCC',
                    'couleur_actuelle': animation.couleur_normale or '#CCCCCC',
                    'objet_type': animation.type_objet
                }
        
        # Appliquer les couleurs dynamiques
        if animations_avec_valeurs:
            try:
                couleurs_finales = {}
                for animation, valeur in animations_avec_valeurs:
                    couleur_finale = ColorRule.apply_rules_to_object(animation, valeur, current_project_id)
                    couleurs_finales[animation.id_animation] = couleur_finale
                
                # Mettre à jour les valeurs avec les couleurs finales
                for animation_id, couleur_finale in couleurs_finales.items():
                    if animation_id in valeurs:
                        valeurs[animation_id]['couleur_actuelle'] = couleur_finale
                        valeurs[animation_id]['couleur_dynamique'] = (couleur_finale != valeurs[animation_id]['couleur_normale'])
                        
            except Exception as e:
                print(f"Erreur application couleurs dynamiques: {e}")
        
        # Statut de connexion
        connection_status = automate.get_status()
        
        # Statistiques de debug
        icon_objects = len([a for a in animations if a.type_objet == 'icon'])
        print(f"📊 Statistiques finales - Icônes: {icon_objects}, Tags: {len(animations_avec_tags)}")
        
        return jsonify({
            'success': True,
            'valeurs': valeurs,
            'timestamp': datetime.now().isoformat(),
            'connection_status': {
                'connected': connection_status.get('connected', False),
                'simulation_mode': connection_status.get('simulation_mode', True),
                'ip_address': connection_status.get('ip_address', '')
            },
            'debug_info': {
                'total_objects': len(animations),
                'icon_objects': icon_objects,
                'tagged_objects': len(animations_avec_tags),
                'page_id': page_id,
                'project_id': current_project_id
            }
        })
        
    except Exception as e:
        print(f"❌ Erreur API runtime values: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@main_bp.route('/api/graphics/runtime/action', methods=['POST'])
@AuthSystem.login_required
def api_runtime_action():
    """Exécuter une action depuis le runtime - AVEC support icônes ET navigation"""
    try:
        from app.controleur.controleur_tags import automate
    except ImportError:
        return jsonify({
            'success': False,
            'error': 'Module automate non disponible'
        }), 500
    
    from app.models.modele_graphics import Animation
    
    data = request.get_json()
    animation_id = data.get('animation_id')
    
    if not animation_id:
        return jsonify({
            'success': False,
            'error': 'ID animation manquant'
        }), 400
    
    animation = Animation.query.get_or_404(animation_id)
    
    # NOUVELLE LOGIQUE : Gérer la navigation
    if animation.action_clic == 'navigate':
        regles = animation.get_regles_animation()
        page_destination = regles.get('page_destination')
        
        print(f"🧭 Action navigation: {animation.nom_animation} vers page {page_destination}")
        
        if not page_destination:
            return jsonify({
                'success': False,
                'error': 'Aucune page de destination configurée'
            }), 400
        
        # Vérifier que la page existe
        from app.models.modele_graphics import Page
        target_page = Page.query.get(page_destination)
        if not target_page:
            return jsonify({
                'success': False,
                'error': 'Page de destination introuvable'
            }), 404
        
        return jsonify({
            'success': True,
            'action': 'navigate',
            'message': f'Navigation vers "{target_page.nom_page}"',
            'target_page_id': page_destination,
            'target_page_name': target_page.nom_page,
            'redirect_url': f'/graphics/runtime/{page_destination}',
            'objet_type': animation.type_objet
        })
    
    # LOGIQUE EXISTANTE pour les autres actions (write, toggle, etc.)
    # Résoudre l'adresse du tag avec projet
    current_project_id = session.get('current_project_id')
    adresse_resolue = resoudre_adresse_tag(animation.tag_lie, current_project_id)
    
    print(f"🖱️ Action runtime {animation.type_objet}: {animation.nom_animation} | Tag: {animation.tag_lie} -> {adresse_resolue} | Action: {animation.action_clic}")
    
    try:
        if animation.action_clic == 'write' and adresse_resolue and animation.valeur_ecriture:
            print(f"✏️ Écriture tag {adresse_resolue} = {animation.valeur_ecriture}")
            success, status = automate.ecrire_tag_par_adresse(
                adresse_resolue, 
                animation.valeur_ecriture
            )
            
            return jsonify({
                'success': success,
                'message': f"Écriture {'réussie' if success else 'échouée'}: {status}",
                'action': 'write',
                'tag': adresse_resolue,
                'valeur': animation.valeur_ecriture,
                'objet_type': animation.type_objet
            })
            
        elif animation.action_clic == 'toggle' and adresse_resolue:
            print(f"🔄 Basculement tag {adresse_resolue}")
            valeur_actuelle, _ = automate.lire_tag_par_adresse(adresse_resolue)
            nouvelle_valeur = not bool(valeur_actuelle) if valeur_actuelle is not None else True
            
            success, status = automate.ecrire_tag_par_adresse(
                adresse_resolue, 
                nouvelle_valeur
            )
            
            return jsonify({
                'success': success,
                'message': f"Basculement {'réussi' if success else 'échoué'}: {status}",
                'action': 'toggle',
                'tag': adresse_resolue,
                'nouvelle_valeur': nouvelle_valeur,
                'objet_type': animation.type_objet
            })
            
        else:
            return jsonify({
                'success': False,
                'error': 'Action non supportée ou configuration incomplète'
            }), 400
            
    except Exception as e:
        print(f"❌ Erreur action runtime: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@main_bp.route('/api/graphics/runtime/navigate', methods=['POST'])
@AuthSystem.login_required
def api_runtime_navigate():
    """API spécialisée pour la navigation en mode runtime"""
    data = request.get_json()
    animation_id = data.get('animation_id')
    
    if not animation_id:
        return jsonify({
            'success': False,
            'error': 'ID animation manquant'
        }), 400
    
    try:
        from app.models.modele_graphics import Animation, Page, ContenirAnimation
        
        animation = Animation.query.get_or_404(animation_id)
        
        # Vérifier que c'est bien une action de navigation
        if animation.action_clic != 'navigate':
            return jsonify({
                'success': False,
                'error': 'Cette animation n\'est pas configurée pour la navigation'
            }), 400
        
        # Récupérer la page de destination
        regles = animation.get_regles_animation()
        page_destination_id = regles.get('page_destination')
        
        if not page_destination_id:
            return jsonify({
                'success': False,
                'error': 'Aucune page de destination configurée'
            }), 400
        
        # Vérifier que la page de destination existe
        page_destination = Page.query.get(page_destination_id)
        if not page_destination:
            return jsonify({
                'success': False,
                'error': 'Page de destination introuvable'
            }), 404
        
        # Log de la navigation pour debug
        print(f"🧭 Navigation: Animation '{animation.nom_animation}' ({animation.type_objet}) vers page '{page_destination.nom_page}'")
        
        return jsonify({
            'success': True,
            'message': f'Navigation vers "{page_destination.nom_page}"',
            'navigation_data': {
                'target_page_id': page_destination.id_page,
                'target_page_name': page_destination.nom_page,
                'target_page_url': f'/graphics/runtime/{page_destination.id_page}',
                'animation_name': animation.nom_animation,
                'animation_type': animation.type_objet
            }
        })
        
    except Exception as e:
        print(f"❌ Erreur navigation runtime: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# =================================================================
# API RUNTIME OPTIMISÉE AVEC ICÔNES
# =================================================================

@main_bp.route('/api/graphics/runtime/values/optimized/<int:page_id>')
@AuthSystem.login_required
def api_get_runtime_values_turbo(page_id):
    """API RUNTIME OPTIMISÉE avec couleurs dynamiques"""
    try:
        from app.controleur.controleur_tags import automate
    except ImportError:
        return jsonify({
            'success': False,
            'error': 'Module automate non disponible'
        }), 500
    
    from app.models.modele_graphics import Animation, ContenirAnimation, apply_color_rules_batch
    
    try:
        # Récupérer les animations avec tags liés
        animations = Animation.query.join(ContenirAnimation).filter(
            ContenirAnimation.id_page == page_id
        ).all()
        
        animations_avec_tags = []
        for animation in animations:
            tag_lie = animation.tag_lie
            if tag_lie and tag_lie.strip():
                animations_avec_tags.append(animation)
        
        valeurs = {}
        changed_objects = []
        animations_avec_valeurs = []
        current_project_id = session.get('current_project_id')
        
        for animation in animations_avec_tags:
            try:
                # OPTIMISATION : Utiliser le cache de résolution des tags
                tag_lie = animation.tag_lie
                cache_key_tag = f"{current_project_id}_{tag_lie}"
                if cache_key_tag in runtime_cache_tags:
                    adresse_resolue = runtime_cache_tags[cache_key_tag]
                else:
                    adresse_resolue = resoudre_adresse_tag(tag_lie, current_project_id)
                    runtime_cache_tags[cache_key_tag] = adresse_resolue
                
                # Lire la valeur
                valeur, qualite = automate.lire_tag_par_adresse(adresse_resolue)
                
                # Ajouter pour les règles de couleur
                if valeur is not None:
                    animations_avec_valeurs.append((animation, valeur))
                
                # OPTIMISATION : Détecter les changements
                cache_key = f"{page_id}_{animation.id_animation}"
                old_value = runtime_cache_values.get(cache_key)
                
                value_changed = old_value is None or old_value.get('valeur') != valeur
                if value_changed:
                    changed_objects.append(animation.id_animation)
                
                # Mettre à jour le cache
                runtime_cache_values[cache_key] = {
                    'valeur': valeur,
                    'qualite': qualite,
                    'timestamp': datetime.now().isoformat()
                }
                
                # Données enrichies
                valeur_data = {
                    'valeur': valeur,
                    'qualite': qualite,
                    'timestamp': datetime.now().isoformat(),
                    'changed': value_changed,
                    'tag_adresse': adresse_resolue,
                    'tag_original': animation.tag_lie,
                    'objet_type': animation.type_objet,
                    'couleur_normale': animation.couleur_normale,
                    'couleur_actuelle': animation.couleur_normale
                }
                
                # Ajouter les données d'icône pour le rendu
                if animation.type_objet == 'icon':
                    icon_info = animation.get_icon_info()
                    if icon_info:
                        valeur_data['icon_info'] = icon_info
                
                valeurs[animation.id_animation] = valeur_data
                
            except Exception as e:
                valeur_data = {
                    'valeur': None,
                    'qualite': 'ERROR',
                    'error': str(e),
                    'changed': True,
                    'tag_adresse': animation.tag_lie,
                    'objet_type': animation.type_objet,
                    'couleur_normale': animation.couleur_normale,
                    'couleur_actuelle': animation.couleur_normale
                }
                
                # Ajouter données d'icône même en cas d'erreur
                if animation.type_objet == 'icon':
                    icon_info = animation.get_icon_info()
                    if icon_info:
                        valeur_data['icon_info'] = icon_info
                
                valeurs[animation.id_animation] = valeur_data
                changed_objects.append(animation.id_animation)
        
        # NOUVEAU : Appliquer les règles de couleur dynamique
        if animations_avec_valeurs:
            try:
                couleurs_finales = apply_color_rules_batch(  # Fonction corrigée
                    animations_avec_valeurs, 
                    current_project_id
                )
                
                # Détecter les changements de couleur
                for animation_id, couleur_finale in couleurs_finales.items():
                    if animation_id in valeurs:
                        couleur_precedente = valeurs[animation_id]['couleur_actuelle']
                        valeurs[animation_id]['couleur_actuelle'] = couleur_finale
                        valeurs[animation_id]['couleur_dynamique'] = True
                        
                        # Marquer comme changé si couleur différente
                        if couleur_finale != couleur_precedente and animation_id not in changed_objects:
                            changed_objects.append(animation_id)
                            valeurs[animation_id]['changed'] = True
                            print(f"🎨 Couleur changée pour {animation_id}: {couleur_precedente} → {couleur_finale}")
                            
            except Exception as e:
                print(f"⚠️ Erreur couleurs dynamiques: {e}")
        
        # Statut de connexion
        connection_status = automate.get_status()
        
        return jsonify({
            'success': True,
            'valeurs': valeurs,
            'timestamp': datetime.now().isoformat(),
            'changed_objects': changed_objects,
            'total_changed': len(changed_objects),
            'connection_status': {
                'connected': connection_status.get('connected', False),
                'simulation_mode': connection_status.get('simulation_mode', True),
                'ip_address': connection_status.get('ip_address', '')
            },
            'debug_info': {
                'total_animations': len(animations),
                'animations_with_tags': len(animations_avec_tags),
                'page_id': page_id,
                'projet_id': current_project_id
            }
        })
        
    except Exception as e:
        print(f"⚠️ Erreur API runtime values optimisée: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e),
            'debug': 'Erreur dans api_get_runtime_values_turbo'
        }), 500

@main_bp.route('/api/graphics/runtime/action/fast', methods=['POST'])
@AuthSystem.login_required
def api_runtime_action_turbo():
    """Action runtime OPTIMISÉE avec feedback immédiat et icônes"""
    try:
        from app.controleur.controleur_tags import automate
    except ImportError:
        return jsonify({
            'success': False,
            'error': 'Module automate non disponible'
        }), 500
    
    from app.models.modele_graphics import Animation
    
    data = request.get_json()
    animation_id = data.get('animation_id')
    
    if not animation_id:
        return jsonify({
            'success': False,
            'error': 'ID animation manquant'
        }), 400
    
    animation = Animation.query.get_or_404(animation_id)
    
    # OPTIMISATION : Utiliser le cache de résolution des tags
    tag_lie = animation.tag_lie
    current_project_id = session.get('current_project_id')
    cache_key_tag = f"{current_project_id}_{tag_lie}"
    
    if cache_key_tag in runtime_cache_tags:
        adresse_resolue = runtime_cache_tags[cache_key_tag]
    else:
        adresse_resolue = resoudre_adresse_tag(tag_lie, current_project_id)
        runtime_cache_tags[cache_key_tag] = adresse_resolue
    
    obj_desc = f"{animation.type_objet} '{animation.nom_animation}'"
    print(f"🖱️ Action runtime turbo {obj_desc} | Tag: {tag_lie} -> {adresse_resolue} | Action: {animation.action_clic}")
    
    try:
        if animation.action_clic == 'write' and adresse_resolue and animation.valeur_ecriture:
            # OPTIMISATION : Conversion de type automatique
            valeur_a_ecrire = animation.valeur_ecriture
            
            # Conversion intelligente du type
            try:
                if isinstance(valeur_a_ecrire, str):
                    if valeur_a_ecrire.lower() in ['true', 'false']:
                        valeur_a_ecrire = valeur_a_ecrire.lower() == 'true'
                    elif valeur_a_ecrire.isdigit():
                        valeur_a_ecrire = int(valeur_a_ecrire)
                    elif '.' in valeur_a_ecrire and valeur_a_ecrire.replace('.', '').isdigit():
                        valeur_a_ecrire = float(valeur_a_ecrire)
            except:
                pass  # Garder la valeur string
            
            print(f"✏️ Écriture tag turbo {adresse_resolue} = {valeur_a_ecrire}")
            success, status = automate.ecrire_tag_par_adresse(adresse_resolue, valeur_a_ecrire)
            
            # OPTIMISATION : Mise à jour immédiate du cache si succès
            if success:
                cache_key = f"*_{animation_id}"  # Générique pour toutes les pages
                runtime_cache_values[cache_key] = {
                    'valeur': valeur_a_ecrire,
                    'qualite': 'GOOD',
                    'timestamp': datetime.now().isoformat()
                }
            
            response_data = {
                'success': success,
                'message': f"Écriture {'réussie' if success else 'échouée'}: {status}",
                'action': 'write',
                'tag': adresse_resolue,
                'valeur': valeur_a_ecrire,
                'objet_type': animation.type_objet,
                'immediate_update': success
            }
            
            # NOUVEAU : Ajouter les données d'icône si applicable
            if animation.type_objet == 'icon':
                icon_info = animation.get_icon_info()
                if icon_info:
                    response_data['icon_info'] = icon_info
            
            return jsonify(response_data)
            
        elif animation.action_clic == 'toggle' and adresse_resolue:
            print(f"🔄 Basculement tag turbo {adresse_resolue}")
            
            # OPTIMISATION : Essayer d'abord le cache
            cache_key = f"*_{animation_id}"
            cached_value = runtime_cache_values.get(cache_key)
            if cached_value and cached_value['qualite'] == 'GOOD':
                valeur_actuelle = cached_value['valeur']
                print(f"📦 Valeur depuis cache: {valeur_actuelle}")
            else:
                valeur_actuelle, _ = automate.lire_tag_par_adresse(adresse_resolue)
                print(f"📡 Valeur depuis automate: {valeur_actuelle}")
            
            nouvelle_valeur = not bool(valeur_actuelle) if valeur_actuelle is not None else True
            
            success, status = automate.ecrire_tag_par_adresse(adresse_resolue, nouvelle_valeur)
            
            # OPTIMISATION : Mise à jour immédiate du cache si succès
            if success:
                runtime_cache_values[cache_key] = {
                    'valeur': nouvelle_valeur,
                    'qualite': 'GOOD',
                    'timestamp': datetime.now().isoformat()
                }
            
            response_data = {
                'success': success,
                'message': f"Basculement {'réussi' if success else 'échoué'}: {status}",
                'action': 'toggle',
                'tag': adresse_resolue,
                'ancienne_valeur': valeur_actuelle,
                'nouvelle_valeur': nouvelle_valeur,
                'objet_type': animation.type_objet,
                'immediate_update': success
            }
            
            # NOUVEAU : Ajouter les données d'icône si applicable
            if animation.type_objet == 'icon':
                icon_info = animation.get_icon_info()
                if icon_info:
                    response_data['icon_info'] = icon_info
            
            return jsonify(response_data)
            
        else:
            return jsonify({
                'success': False,
                'error': 'Action non supportée ou configuration incomplète',
                'objet_type': animation.type_objet
            }), 400
            
    except Exception as e:
        print(f"⚠️ Erreur action runtime turbo: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'objet_type': animation.type_objet
        }), 500

# =================================================================
# API SPÉCIALISÉES POUR LES ICÔNES
# =================================================================

@main_bp.route('/api/graphics/icons/popular', methods=['GET'])
@AuthSystem.login_required
def api_get_popular_icons():
    """Récupère les icônes les plus populaires pour l'éditeur"""
    try:
        from app.models.modele_graphics import IconLibrary
        
        popular_icons = IconLibrary.query.filter_by(actif=True).filter(
            IconLibrary.popularite > 0
        ).order_by(IconLibrary.popularite.desc()).limit(20).all()
        
        return jsonify({
            'success': True,
            'icons': [icon.to_dict() for icon in popular_icons],
            'total': len(popular_icons)
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# =================================================================
# UTILITAIRES CACHE RUNTIME
# =================================================================

@main_bp.route('/api/graphics/runtime/cache/clear', methods=['POST'])
@AuthSystem.login_required
def api_clear_runtime_cache():
    """Vide le cache runtime (utile pour debug)"""
    global runtime_cache_values, runtime_cache_tags
    runtime_cache_values = {}
    runtime_cache_tags = {}
    return jsonify({
        'success': True,
        'message': 'Cache runtime vidé'
    })

@main_bp.route('/api/graphics/runtime/cache/stats')
@AuthSystem.login_required
def api_runtime_cache_stats():
    """Statistiques du cache runtime"""
    return jsonify({
        'success': True,
        'stats': {
            'cached_values': len(runtime_cache_values),
            'cached_tags': len(runtime_cache_tags),
            'sample_values': list(runtime_cache_values.keys())[:5],
            'sample_tags': list(runtime_cache_tags.items())[:5]
        }
    })

# =================================================================
# FONCTIONS UTILITAIRES POUR LA NAVIGATION
# =================================================================

def get_navigation_objects_by_page(page_id):
    """Récupère tous les objets configurés pour la navigation sur une page"""
    try:
        from app.models.modele_graphics import Animation, ContenirAnimation
        
        animations = Animation.query.join(ContenirAnimation).filter(
            ContenirAnimation.id_page == page_id,
            Animation.regles_animation.contains('"action_clic":"navigate"')
        ).all()
        
        navigation_objects = []
        for anim in animations:
            regles = anim.get_regles_animation()
            page_dest_id = regles.get('page_destination')
            
            if page_dest_id:
                from app.models.modele_graphics import Page
                page_dest = Page.query.get(page_dest_id)
                
                navigation_objects.append({
                    'animation_id': anim.id_animation,
                    'animation_name': anim.nom_animation,
                    'animation_type': anim.type_objet,
                    'destination_page_id': page_dest_id,
                    'destination_page_name': page_dest.nom_page if page_dest else 'Page inconnue',
                    'position': {'x': anim.position_x, 'y': anim.position_y},
                    'size': {'width': anim.largeur, 'height': anim.hauteur}
                })
        
        return navigation_objects
        
    except Exception as e:
        print(f"Erreur récupération objets navigation: {e}")
        return []

def validate_project_navigation_integrity(project_id):
    """Valide l'intégrité des navigations dans un projet"""
    try:
        from app.models.modele_graphics import Page, Animation, ContenirAnimation
        
        pages = Page.query.filter_by(id_projet=project_id).all()
        page_ids = [p.id_page for p in pages]
        page_dict = {p.id_page: p for p in pages}
        
        issues = []
        
        # Récupérer toutes les animations avec navigation
        nav_animations = Animation.query.join(ContenirAnimation).filter(
            ContenirAnimation.id_page.in_(page_ids),
            Animation.regles_animation.contains('"action_clic":"navigate"')
        ).all()
        
        for anim in nav_animations:
            try:
                regles = anim.get_regles_animation()
                page_dest_id = regles.get('page_destination')
                
                if not page_dest_id:
                    issues.append({
                        'type': 'missing_destination',
                        'animation_id': anim.id_animation,
                        'animation_name': anim.nom_animation,
                        'message': 'Page de destination manquante'
                    })
                    continue
                
                if page_dest_id not in page_dict:
                    issues.append({
                        'type': 'invalid_destination',
                        'animation_id': anim.id_animation,
                        'animation_name': anim.nom_animation,
                        'destination_id': page_dest_id,
                        'message': 'Page de destination introuvable'
                    })
                    continue
                
                # Vérifier les références circulaires
                source_page = db.session.query(Page).join(
                    ContenirAnimation, Page.id_page == ContenirAnimation.id_page
                ).filter(ContenirAnimation.id_animation == anim.id_animation).first()
                
                if source_page and source_page.id_page == page_dest_id:
                    issues.append({
                        'type': 'circular_reference',
                        'animation_id': anim.id_animation,
                        'animation_name': anim.nom_animation,
                        'page_name': source_page.nom_page,
                        'message': 'Référence circulaire: page navigue vers elle-même'
                    })
                
            except Exception as e:
                issues.append({
                    'type': 'validation_error',
                    'animation_id': anim.id_animation,
                    'animation_name': anim.nom_animation,
                    'error': str(e),
                    'message': 'Erreur lors de la validation'
                })
        
        return {
            'valid': len(issues) == 0,
            'total_navigation_objects': len(nav_animations),
            'issues_count': len(issues),
            'issues': issues
        }
        
    except Exception as e:
        return {
            'valid': False,
            'error': str(e),
            'message': 'Erreur lors de la validation du projet'
        }

# =================================================================
# FONCTIONS UTILITAIRES
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
    return display_names.get(category, f'🔍 {category.capitalize()}' if category else '🔍 Sans catégorie')

# =================================================================
# DEBUG / TEST
# =================================================================

@main_bp.route('/api/graphics/icons/debug')
@AuthSystem.login_required
def debug_icons():
    """Diagnostic des icônes uploadées"""
    try:
        from app.models.modele_graphics import IconLibrary
        import os
        
        # Récupérer toutes les icônes uploadées
        uploaded_icons = IconLibrary.query.filter_by(
            type_source='upload',
            actif=True
        ).all()
        
        diagnostic_results = []
        upload_folder = os.path.join('web_indus', 'app', 'static', 'icons', 'custom')
        
        print(f"Dossier d'upload: {upload_folder}")
        print(f"Existe: {os.path.exists(upload_folder)}")
        
        if os.path.exists(upload_folder):
            files_in_folder = os.listdir(upload_folder)
            print(f"Fichiers dans le dossier: {files_in_folder}")
        else:
            files_in_folder = []
        
        for icon in uploaded_icons:
            result = {
                'id': icon.id_icon,
                'nom': icon.nom_icon,
                'fichier_original': icon.fichier_original,
                'fichier_path': icon.fichier_path,
                'url_generee': icon.get_url(),
                'fichier_existe': False,
                'fichier_accessible': False,
                'dans_dossier_upload': False
            }
            
            # Vérifier l'existence du fichier
            if icon.fichier_path and os.path.exists(icon.fichier_path):
                result['fichier_existe'] = True
                result['fichier_accessible'] = os.access(icon.fichier_path, os.R_OK)
            
            # Vérifier dans le dossier d'upload
            if icon.fichier_original:
                result['dans_dossier_upload'] = icon.fichier_original in files_in_folder
            
            diagnostic_results.append(result)
        
        return jsonify({
            'success': True,
            'diagnostic': {
                'total_icons': len(uploaded_icons),
                'upload_folder': upload_folder,
                'upload_folder_exists': os.path.exists(upload_folder),
                'files_in_upload_folder': files_in_folder,
                'icons_details': diagnostic_results
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@main_bp.route('/api/graphics/navigation/debug/<int:project_id>')
@AuthSystem.login_required
def api_debug_navigation(project_id):
    """Debug des configurations de navigation d'un projet"""
    try:
        navigation_objects = []
        
        from app.models.modele_graphics import Page
        pages = Page.query.filter_by(id_projet=project_id).all()
        
        for page in pages:
            nav_objs = get_navigation_objects_by_page(page.id_page)
            if nav_objs:
                navigation_objects.append({
                    'page_id': page.id_page,
                    'page_name': page.nom_page,
                    'navigation_objects': nav_objs
                })
        
        validation_result = validate_project_navigation_integrity(project_id)
        
        return jsonify({
            'success': True,
            'debug_info': {
                'project_id': project_id,
                'total_pages': len(pages),
                'pages_with_navigation': len(navigation_objects),
                'navigation_details': navigation_objects,
                'validation': validation_result
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
    
# ============================================================
# API COLOR RULES - GET, UPDATE ET DELETE
# ============================================================
@main_bp.route('/api/graphics/color_rules', methods=['POST'])
@AuthSystem.login_required
def api_create_color_rule():
    """Créer une nouvelle règle de couleur"""
    try:
        data = request.get_json()
        current_project_id = session.get('current_project_id')
        
        if not current_project_id:
            return jsonify({
                'success': False,
                'error': 'Aucun projet sélectionné'
            }), 400
        
        # Validations de base
        required_fields = ['nom_regle', 'object_id', 'tag_name', 'target_value', 'color']
        for field in required_fields:
            if not data.get(field):
                return jsonify({
                    'success': False,
                    'error': f'Champ manquant: {field}'
                }), 400
        
        # Vérifier que l'objet existe
        from app.models.modele_graphics import Animation
        animation = Animation.query.get(data['object_id'])
        if not animation:
            return jsonify({
                'success': False,
                'error': 'Objet non trouvé'
            }), 404
        
        # Créer la règle
        from app.models.modele_graphics import ColorRule
        rule = ColorRule(
            nom_regle=data['nom_regle'],
            id_projet=current_project_id,
            object_id=data['object_id'],
            tag_name=data['tag_name'],
            operator=data.get('operator', '='),
            target_value=str(data['target_value']),
            color=data['color'],
            priorite=data.get('priorite', 1),
            actif=data.get('actif', True)
        )
        
        db.session.add(rule)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Règle créée avec succès',
            'rule': rule.to_dict()
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@main_bp.route('/api/graphics/color_rules/<int:object_id>', methods=['GET'])
@AuthSystem.login_required
def api_get_color_rules(object_id):
    """Récupérer les règles d'un objet"""
    try:
        current_project_id = session.get('current_project_id')
        
        from app.models.modele_graphics import ColorRule
        rules = ColorRule.get_rules_for_object(object_id, current_project_id)
        
        return jsonify({
            'success': True,
            'rules': [rule.to_dict() for rule in rules],
            'object_id': object_id,
            'total': len(rules)
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@main_bp.route('/api/graphics/color_rules/<int:rule_id>', methods=['PUT'])
@AuthSystem.login_required
def api_update_color_rule(rule_id):
    """Modifier une règle (activer/désactiver ou modifier propriétés)"""
    try:
        from app.models.modele_graphics import ColorRule
        rule = ColorRule.query.get(rule_id)
        
        if not rule:
            return jsonify({
                'success': False,
                'error': 'Règle non trouvée'
            }), 404
        
        data = request.get_json()
        updated_fields = []
        
        # Champs modifiables
        if 'nom_regle' in data:
            rule.nom_regle = data['nom_regle']
            updated_fields.append('nom_regle')
            
        if 'tag_name' in data:
            rule.tag_name = data['tag_name']
            updated_fields.append('tag_name')
            
        if 'operator' in data:
            rule.operator = data['operator']
            updated_fields.append('operator')
            
        if 'target_value' in data:
            rule.target_value = str(data['target_value'])
            updated_fields.append('target_value')
            
        if 'color' in data:
            rule.color = data['color']
            updated_fields.append('color')
            
        if 'priorite' in data:
            rule.priorite = data['priorite']
            updated_fields.append('priorite')
            
        if 'actif' in data:
            rule.actif = data['actif']
            updated_fields.append('actif')
        
        if updated_fields:
            rule.date_modification = datetime.utcnow()
            db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Règle mise à jour: {", ".join(updated_fields)}',
            'rule': rule.to_dict(),
            'updated_fields': updated_fields
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@main_bp.route('/api/graphics/color_rules/<int:rule_id>', methods=['DELETE'])
@AuthSystem.login_required
def api_delete_color_rule(rule_id):
    """Supprimer une règle"""
    try:
        from app.models.modele_graphics import ColorRule
        rule = ColorRule.query.get(rule_id)
        
        if not rule:
            return jsonify({
                'success': False,
                'error': 'Règle non trouvée'
            }), 404
        
        rule_name = rule.nom_regle
        db.session.delete(rule)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Règle "{rule_name}" supprimée'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@main_bp.route('/api/graphics/color_rules/test/<int:rule_id>', methods=['POST'])
@AuthSystem.login_required
def api_test_color_rule(rule_id):
    """Tester une règle avec une valeur donnée"""
    try:
        from app.models.modele_graphics import ColorRule
        rule = ColorRule.query.get(rule_id)
        
        if not rule:
            return jsonify({
                'success': False,
                'error': 'Règle non trouvée'
            }), 404
        
        data = request.get_json()
        test_value = data.get('test_value')
        
        if test_value is None:
            return jsonify({
                'success': False,
                'error': 'Valeur de test manquante'
            }), 400
        
        # Tester la condition
        result = rule.test_condition(test_value)
        
        return jsonify({
            'success': True,
            'rule': rule.to_dict(),
            'test_value': test_value,
            'result': result,
            'color_applied': rule.color if result else None,
            'message': f'Condition {"remplie" if result else "non remplie"}: {test_value} {rule.operator} {rule.target_value}'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@main_bp.route('/api/graphics/color_rules/<int:object_id>/bulk', methods=['POST'])
@AuthSystem.login_required
def api_bulk_color_rules(object_id):
    """Actions en lot sur les règles d'un objet"""
    try:
        data = request.get_json()
        action = data.get('action')
        
        if action not in ['enable_all', 'disable_all', 'delete_all']:
            return jsonify({
                'success': False,
                'error': 'Action invalide'
            }), 400
        
        current_project_id = session.get('current_project_id')
        from app.models.modele_graphics import ColorRule
        
        query = ColorRule.query.filter_by(object_id=object_id)
        if current_project_id:
            query = query.filter_by(id_projet=current_project_id)
        
        rules = query.all()
        affected_count = len(rules)
        
        if affected_count == 0:
            return jsonify({
                'success': False,
                'error': 'Aucune règle trouvée'
            }), 404
        
        if action == 'enable_all':
            for rule in rules:
                rule.actif = True
                rule.date_modification = datetime.utcnow()
            message = f'{affected_count} règle(s) activée(s)'
            
        elif action == 'disable_all':
            for rule in rules:
                rule.actif = False
                rule.date_modification = datetime.utcnow()
            message = f'{affected_count} règle(s) désactivée(s)'
            
        elif action == 'delete_all':
            for rule in rules:
                db.session.delete(rule)
            message = f'{affected_count} règle(s) supprimée(s)'
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': message,
            'affected_count': affected_count,
            'action': action
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@main_bp.route('/api/graphics/color_rules/project/stats')
@AuthSystem.login_required
def api_color_rules_project_stats():
    """Statistiques des règles du projet courant"""
    try:
        current_project_id = session.get('current_project_id')
        
        if not current_project_id:
            return jsonify({
                'success': False,
                'error': 'Aucun projet sélectionné'
            }), 400
        
        from app.models.modele_graphics import ColorRule
        from sqlalchemy import func
        
        # Compter les règles par statut
        total_rules = ColorRule.query.filter_by(id_projet=current_project_id).count()
        active_rules = ColorRule.query.filter_by(id_projet=current_project_id, actif=True).count()
        
        # Compter par objet
        rules_per_object = db.session.query(
            ColorRule.object_id,
            func.count(ColorRule.id_color_rule).label('count')
        ).filter_by(
            id_projet=current_project_id,
            actif=True
        ).group_by(ColorRule.object_id).all()
        
        # Compter par opérateur
        operators_stats = db.session.query(
            ColorRule.operator,
            func.count(ColorRule.id_color_rule).label('count')
        ).filter_by(
            id_projet=current_project_id,
            actif=True
        ).group_by(ColorRule.operator).all()
        
        return jsonify({
            'success': True,
            'stats': {
                'total_rules': total_rules,
                'active_rules': active_rules,
                'inactive_rules': total_rules - active_rules,
                'objects_with_rules': len(rules_per_object),
                'rules_per_object': [
                    {'object_id': obj_id, 'rule_count': count}
                    for obj_id, count in rules_per_object
                ],
                'operators_usage': [
                    {'operator': op, 'count': count}
                    for op, count in operators_stats
                ],
                'project_id': current_project_id
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# =================================================================
# FONCTION D'APPLICATION DANS LE RUNTIME - VERSION SIMPLIFIÉE
# =================================================================

def apply_dynamic_colors_to_runtime_values(animations_with_values, project_id=None):
    """
    Applique les règles de couleur aux valeurs runtime
    animations_with_values: liste de tuples (animation, tag_value)
    Retourne: dict {animation_id: couleur_finale}
    """
    try:
        from app.models.modele_graphics import ColorRule
        
        result_colors = {}
        
        for animation, tag_value in animations_with_values:
            # Obtenir la couleur finale après application des règles
            final_color = ColorRule.apply_rules_to_object(animation, tag_value, project_id)
            result_colors[animation.id_animation] = final_color
            
            # Log pour debug
            if final_color != animation.couleur_normale:
                print(f"🎨 Couleur dynamique: {animation.nom_animation} -> {final_color} (valeur: {tag_value})")
        
        return result_colors
        
    except Exception as e:
        print(f"❌ Erreur application couleurs dynamiques: {e}")
        # En cas d'erreur, retourner les couleurs normales
        return {anim.id_animation: anim.couleur_normale for anim, _ in animations_with_values}

# =================================================================
# FONCTIONS UTILITAIRES DE MAINTENANCE
# =================================================================

@main_bp.route('/api/graphics/color_rules/maintenance/cleanup')
@AuthSystem.login_required
def api_cleanup_orphaned_rules():
    """Nettoyer les règles orphelines (objets supprimés)"""
    try:
        from app.models.modele_graphics import ColorRule, Animation
        
        # Trouver les règles dont l'objet n'existe plus
        orphaned_rules = []
        all_rules = ColorRule.query.all()
        
        for rule in all_rules:
            animation = Animation.query.get(rule.object_id)
            if not animation:
                orphaned_rules.append(rule)
        
        # Supprimer les règles orphelines
        deleted_count = 0
        for rule in orphaned_rules:
            db.session.delete(rule)
            deleted_count += 1
        
        if deleted_count > 0:
            db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'{deleted_count} règle(s) orpheline(s) supprimée(s)',
            'deleted_count': deleted_count
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@main_bp.route('/api/graphics/color_rules/maintenance/validate')
@AuthSystem.login_required  
def api_validate_all_rules():
    """Valider toutes les règles du projet courant"""
    try:
        current_project_id = session.get('current_project_id')
        
        if not current_project_id:
            return jsonify({
                'success': False,
                'error': 'Aucun projet sélectionné'
            }), 400
        
        from app.models.modele_graphics import ColorRule, Animation
        from app.models.modele_tag import Tag
        
        rules = ColorRule.query.filter_by(id_projet=current_project_id).all()
        validation_results = []
        
        for rule in rules:
            result = {
                'rule_id': rule.id_color_rule,
                'rule_name': rule.nom_regle,
                'valid': True,
                'warnings': [],
                'errors': []
            }
            
            # Vérifier que l'objet existe
            animation = Animation.query.get(rule.object_id)
            if not animation:
                result['valid'] = False
                result['errors'].append('Objet animation introuvable')
            else:
                # Vérifier que le tag existe
                tag = Tag.query.filter_by(
                    nom_tag=rule.tag_name,
                    id_projet=current_project_id
                ).first()
                
                if not tag:
                    result['warnings'].append(f'Tag "{rule.tag_name}" introuvable dans le projet')
                
                # Vérifier que l'objet est lié au même tag
                if animation.tag_lie != rule.tag_name:
                    result['warnings'].append(f'Objet lié au tag "{animation.tag_lie}" mais règle sur "{rule.tag_name}"')
            
            # Vérifier l'opérateur
            valid_operators = ['=', '==', '!=', '>', '<', '>=', '<=']
            if rule.operator not in valid_operators:
                result['valid'] = False
                result['errors'].append(f'Opérateur invalide: {rule.operator}')
            
            # Vérifier la couleur
            import re
            if not re.match(r'^#[0-9A-Fa-f]{6}$', rule.color):
                result['valid'] = False
                result['errors'].append(f'Format couleur invalide: {rule.color}')
            
            validation_results.append(result)
        
        # Compter les résultats
        total_rules = len(rules)
        valid_rules = len([r for r in validation_results if r['valid']])
        rules_with_warnings = len([r for r in validation_results if r['warnings']])
        
        return jsonify({
            'success': True,
            'validation': {
                'total_rules': total_rules,
                'valid_rules': valid_rules,
                'invalid_rules': total_rules - valid_rules,
                'rules_with_warnings': rules_with_warnings,
                'results': validation_results
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
    
# =================================================================
# API VISIBILITY RULES - GESTION DES RÈGLES DE VISIBILITÉ
# =================================================================

@main_bp.route('/api/visibility-rules', methods=['GET'])
@AuthSystem.login_required
def api_get_visibility_rules():
    """Récupère toutes les règles de visibilité actives du projet"""
    current_project_id = session.get('current_project_id')
    
    if not current_project_id:
        return jsonify({
            'success': False,
            'error': 'Aucun projet sélectionné'
        }), 400
    
    try:
        from app.models.modele_graphics import VisibilityRule
        
        rules = VisibilityRule.query.filter_by(
            id_projet=current_project_id,
            actif=True
        ).order_by(VisibilityRule.priorite.asc()).all()
        
        return jsonify([rule.to_dict() for rule in rules]), 200
        
    except Exception as e:
        print(f"❌ Erreur récupération règles visibilité: {e}")
        return jsonify({'error': str(e)}), 500


@main_bp.route('/api/visibility-rules', methods=['POST'])
@AuthSystem.login_required
def api_create_visibility_rule():
    """Crée une nouvelle règle de visibilité"""
    current_project_id = session.get('current_project_id')
    
    if not current_project_id:
        return jsonify({
            'success': False,
            'error': 'Aucun projet sélectionné'
        }), 400
    
    try:
        data = request.json
        
        # Validation
        required_fields = ['nom_regle', 'object_id', 'tag_name', 'target_value', 'action']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    'success': False,
                    'error': f'Champ manquant: {field}'
                }), 400
        
        # Validation des valeurs
        valid_operators = ['=', '!=', '>', '<', '>=', '<=']
        if data.get('operator', '=') not in valid_operators:
            return jsonify({
                'success': False,
                'error': 'Opérateur invalide'
            }), 400
        
        valid_actions = ['show', 'hide']
        if data['action'] not in valid_actions:
            return jsonify({
                'success': False,
                'error': 'Action invalide (show/hide uniquement)'
            }), 400
        
        from app.models.modele_graphics import VisibilityRule
        
        rule = VisibilityRule(
            nom_regle=data['nom_regle'],
            id_projet=current_project_id,
            object_id=data['object_id'],
            tag_name=data['tag_name'],
            operator=data.get('operator', '='),
            target_value=str(data['target_value']),
            action=data['action'],
            priorite=data.get('priorite', 1),
            actif=data.get('actif', True)
        )
        
        db.session.add(rule)
        db.session.commit()
        
        print(f"✅ Règle visibilité créée: {data['nom_regle']} (ID: {rule.id_visibility_rule})")
        return jsonify({
            'id': rule.id_visibility_rule,
            'message': 'Règle créée avec succès'
        }), 201
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Erreur création règle visibilité: {e}")
        return jsonify({'error': str(e)}), 500


@main_bp.route('/api/visibility-rules/<int:rule_id>', methods=['DELETE'])
@AuthSystem.login_required
def api_delete_visibility_rule(rule_id):
    """Supprime une règle de visibilité"""
    try:
        from app.models.modele_graphics import VisibilityRule
        
        rule = VisibilityRule.query.get(rule_id)
        if not rule:
            return jsonify({
                'success': False,
                'error': 'Règle non trouvée'
            }), 404
        
        rule_name = rule.nom_regle
        db.session.delete(rule)
        db.session.commit()
        
        print(f"✅ Règle visibilité {rule_id} supprimée")
        return jsonify({'message': f'Règle "{rule_name}" supprimée'}), 200
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Erreur suppression règle: {e}")
        return jsonify({'error': str(e)}), 500


@main_bp.route('/api/visibility-rules/all', methods=['DELETE'])
@AuthSystem.login_required
def api_delete_all_visibility_rules():
    """Supprime toutes les règles de visibilité du projet"""
    current_project_id = session.get('current_project_id')
    
    if not current_project_id:
        return jsonify({
            'success': False,
            'error': 'Aucun projet sélectionné'
        }), 400
    
    try:
        from app.models.modele_graphics import VisibilityRule
        
        deleted_count = VisibilityRule.query.filter_by(
            id_projet=current_project_id
        ).delete()
        
        db.session.commit()
        
        print(f"✅ {deleted_count} règles visibilité supprimées")
        return jsonify({
            'message': f'{deleted_count} règles supprimées',
            'count': deleted_count
        }), 200
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Erreur suppression règles: {e}")
        return jsonify({'error': str(e)}), 500


@main_bp.route('/api/visibility-rules/<int:object_id>/object', methods=['GET'])
@AuthSystem.login_required
def api_get_visibility_rules_for_object(object_id):
    """Récupère les règles de visibilité pour un objet spécifique"""
    current_project_id = session.get('current_project_id')
    
    try:
        from app.models.modele_graphics import VisibilityRule
        
        rules = VisibilityRule.get_rules_for_object(object_id, current_project_id)
        
        return jsonify({
            'success': True,
            'rules': [rule.to_dict() for rule in rules],
            'object_id': object_id,
            'total': len(rules)
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500