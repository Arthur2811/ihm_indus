from app import db
from datetime import datetime
from sqlalchemy import and_
import json
import os
import zipfile
import tempfile

class ProjectManager:
    """Classe utilitaire pour la gestion des projets IHM"""
    
    # =================================================================
    # GESTION DES PROJETS
    # =================================================================
    
    @staticmethod
    def get_all_projects():
        """Récupère tous les projets avec leurs détails"""
        try:
            from app.models.modele_tag import HMIProject, Utilisateur
            
            projects = db.session.query(HMIProject, Utilisateur).outerjoin(
                Utilisateur, HMIProject.id_utilisateur == Utilisateur.id_utilisateur
            ).order_by(HMIProject.date_modification.desc()).all()
            
            projects_list = []
            for project, user in projects:
                # Calculer les statistiques du projet
                stats = ProjectManager._get_project_stats(project.id_projet)
                
                projects_list.append({
                    'id_projet': project.id_projet,
                    'nom_projet': project.nom_projet,
                    'chemin_fichier': project.chemin_fichier,
                    'date_creation_projet': project.date_creation_projet,
                    'date_modification': project.date_modification,
                    'version_projet': project.version_projet,
                    'actif_projet': project.actif_projet,
                    'createur': {
                        'nom': f"{user.prenom_utilisateur} {user.nom_utilisateur}" if user else "Système",
                        'id': user.id_utilisateur if user else None
                    },
                    'stats': stats
                })
            
            return projects_list
        except Exception as e:
            print(f"Erreur récupération projets: {e}")
            return []
    
    @staticmethod
    def get_project_by_id(project_id):
        """Récupère un projet spécifique par son ID"""
        try:
            from app.models.modele_tag import HMIProject, Utilisateur
            
            result = db.session.query(HMIProject, Utilisateur).outerjoin(
                Utilisateur, HMIProject.id_utilisateur == Utilisateur.id_utilisateur
            ).filter(HMIProject.id_projet == project_id).first()
            
            if not result:
                return None
            
            project, user = result
            stats = ProjectManager._get_project_stats(project.id_projet)
            
            return {
                'id_projet': project.id_projet,
                'nom_projet': project.nom_projet,
                'chemin_fichier': project.chemin_fichier,
                'date_creation_projet': project.date_creation_projet,
                'date_modification': project.date_modification,
                'version_projet': project.version_projet,
                'actif_projet': project.actif_projet,
                'createur': {
                    'nom': f"{user.prenom_utilisateur} {user.nom_utilisateur}" if user else "Système",
                    'id': user.id_utilisateur if user else None
                },
                'stats': stats
            }
        except Exception as e:
            print(f"Erreur récupération projet {project_id}: {e}")
            return None
    
    @staticmethod
    def create_project(project_data, creator_id=None):
        """Crée un nouveau projet"""
        try:
            from app.models.modele_tag import HMIProject
            
            # Validation des données
            if not project_data.get('nom_projet'):
                return False, "Nom de projet requis"
            
            # Vérifier l'unicité du nom
            existing = HMIProject.query.filter_by(nom_projet=project_data['nom_projet']).first()
            if existing:
                return False, f"Un projet nommé '{project_data['nom_projet']}' existe déjà"
            
            # Générer le chemin fichier
            safe_name = project_data['nom_projet'].replace(' ', '_').replace('/', '_')
            chemin_fichier = f"/projects/{safe_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            # Créer le projet
            nouveau_projet = HMIProject(
                nom_projet=project_data['nom_projet'],
                chemin_fichier=chemin_fichier,
                date_creation_projet=datetime.utcnow(),
                date_modification=datetime.utcnow(),
                version_projet=project_data.get('version_projet', '1.0'),
                actif_projet=project_data.get('actif_projet', True),
                id_utilisateur=creator_id
            )
            
            db.session.add(nouveau_projet)
            db.session.commit()
            
            # Créer la structure par défaut du projet
            ProjectManager._create_default_project_structure(nouveau_projet.id_projet)
            
            return True, f"Projet '{project_data['nom_projet']}' créé avec succès"
            
        except Exception as e:
            db.session.rollback()
            print(f"Erreur création projet: {e}")
            return False, f"Erreur création: {str(e)}"
    
    @staticmethod
    def update_project(project_id, project_data):
        """Met à jour un projet"""
        try:
            from app.models.modele_tag import HMIProject
            
            project = HMIProject.query.get(project_id)
            if not project:
                return False, "Projet non trouvé"
            
            # Vérifier l'unicité du nom si modifié
            if 'nom_projet' in project_data and project_data['nom_projet'] != project.nom_projet:
                existing = HMIProject.query.filter_by(nom_projet=project_data['nom_projet']).first()
                if existing:
                    return False, f"Un projet nommé '{project_data['nom_projet']}' existe déjà"
            
            # Mettre à jour les champs
            for field, value in project_data.items():
                if hasattr(project, field):
                    setattr(project, field, value)
            
            project.date_modification = datetime.utcnow()
            
            db.session.commit()
            
            return True, f"Projet '{project.nom_projet}' modifié avec succès"
            
        except Exception as e:
            db.session.rollback()
            print(f"Erreur modification projet: {e}")
            return False, f"Erreur modification: {str(e)}"
    
    @staticmethod
    def delete_project(project_id):
        """Supprime un projet et toutes ses données associées"""
        try:
            from app.models.modele_tag import HMIProject, Tag
            from app.models.modele_graphics import Page, Animation, ContenirAnimation
            
            project = HMIProject.query.get(project_id)
            if not project:
                return False, "Projet non trouvé"
            
            project_name = project.nom_projet
            
            # Supprimer les données associées
            # 1. Animations des pages du projet
            pages = Page.query.filter_by(id_projet=project_id).all()
            for page in pages:
                # Supprimer les liaisons animations-page
                ContenirAnimation.query.filter_by(id_page=page.id_page).delete()
                
                # Supprimer les animations
                animations = Animation.query.join(ContenirAnimation).filter(
                    ContenirAnimation.id_page == page.id_page
                ).all()
                for anim in animations:
                    db.session.delete(anim)
            
            # 2. Supprimer les pages
            Page.query.filter_by(id_projet=project_id).delete()
            
            # 3. Supprimer les tags
            Tag.query.filter_by(id_projet=project_id).delete()
            
            # 4. Supprimer le projet
            db.session.delete(project)
            
            db.session.commit()
            
            return True, f"Projet '{project_name}' et toutes ses données supprimés avec succès"
            
        except Exception as e:
            db.session.rollback()
            print(f"Erreur suppression projet: {e}")
            return False, f"Erreur suppression: {str(e)}"
    
    @staticmethod
    def duplicate_project(project_id, new_name, creator_id=None):
        """Duplique un projet existant"""
        try:
            from app.models.modele_tag import HMIProject, Tag
            from app.models.modele_graphics import Page, Animation, ContenirAnimation
            
            # Récupérer le projet source
            source_project = HMIProject.query.get(project_id)
            if not source_project:
                return False, "Projet source non trouvé"
            
            # Vérifier l'unicité du nouveau nom
            existing = HMIProject.query.filter_by(nom_projet=new_name).first()
            if existing:
                return False, f"Un projet nommé '{new_name}' existe déjà"
            
            # Créer le nouveau projet
            safe_name = new_name.replace(' ', '_').replace('/', '_')
            chemin_fichier = f"/projects/{safe_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            new_project = HMIProject(
                nom_projet=new_name,
                chemin_fichier=chemin_fichier,
                date_creation_projet=datetime.utcnow(),
                date_modification=datetime.utcnow(),
                version_projet="1.0",  # Reset version
                actif_projet=True,
                id_utilisateur=creator_id
            )
            
            db.session.add(new_project)
            db.session.flush()  # Pour obtenir l'ID
            
            # Dupliquer les tags
            source_tags = Tag.query.filter_by(id_projet=project_id).all()
            tag_mapping = {}
            
            for tag in source_tags:
                new_tag = Tag(
                    nom_tag=tag.nom_tag,
                    type_donnee=tag.type_donnee,
                    description_tag=tag.description_tag,
                    acces=tag.acces,
                    alarmes_actives=tag.alarmes_actives,
                    historisation_active=tag.historisation_active,
                    disponibilite_externe=tag.disponibilite_externe,
                    id_projet=new_project.id_projet
                )
                db.session.add(new_tag)
                db.session.flush()
                tag_mapping[tag.id_tag] = new_tag.id_tag
            
            # Dupliquer les pages et animations
            source_pages = Page.query.filter_by(id_projet=project_id).all()
            
            for page in source_pages:
                new_page = Page(
                    nom_page=page.nom_page,
                    largeur_page=page.largeur_page,
                    hauteur_page=page.hauteur_page,
                    couleur_fond=page.couleur_fond,
                    image_fond=page.image_fond,
                    ordre_affichage=page.ordre_affichage,
                    page_accueil=page.page_accueil,
                    id_projet=new_project.id_projet
                )
                db.session.add(new_page)
                db.session.flush()
                
                # Dupliquer les animations de cette page
                animations = Animation.query.join(ContenirAnimation).filter(
                    ContenirAnimation.id_page == page.id_page
                ).all()
                
                for anim in animations:
                    new_anim = Animation(
                        nom_animation=anim.nom_animation,
                        type_objet=anim.type_objet,
                        position_x=anim.position_x,
                        position_y=anim.position_y,
                        largeur=anim.largeur,
                        hauteur=anim.hauteur,
                        couleur_normale=anim.couleur_normale,
                        couleur_active=anim.couleur_active,
                        texte_affiche=anim.texte_affiche,
                        regles_animation=anim.regles_animation
                    )
                    db.session.add(new_anim)
                    db.session.flush()
                    
                    # Créer la liaison page-animation
                    liaison = ContenirAnimation(
                        id_animation=new_anim.id_animation,
                        id_page=new_page.id_page
                    )
                    db.session.add(liaison)
            
            db.session.commit()
            
            return True, f"Projet '{source_project.nom_projet}' dupliqué vers '{new_name}' avec succès"
            
        except Exception as e:
            db.session.rollback()
            print(f"Erreur duplication projet: {e}")
            return False, f"Erreur duplication: {str(e)}"
    
    @staticmethod
    def archive_project(project_id, archive=True):
        """Archive/désarchive un projet"""
        try:
            from app.models.modele_tag import HMIProject
            
            project = HMIProject.query.get(project_id)
            if not project:
                return False, "Projet non trouvé"
            
            project.actif_projet = not archive
            project.date_modification = datetime.utcnow()
            
            db.session.commit()
            
            action = "archivé" if archive else "désarchivé"
            return True, f"Projet '{project.nom_projet}' {action} avec succès"
            
        except Exception as e:
            db.session.rollback()
            print(f"Erreur archivage projet: {e}")
            return False, f"Erreur archivage: {str(e)}"
    
    # =================================================================
    # IMPORT/EXPORT DE PROJETS
    # =================================================================
    
    @staticmethod
    def export_project(project_id):
        """Exporte un projet complet (config + données)"""
        try:
            from app.models.modele_tag import HMIProject, Tag
            from app.models.modele_graphics import Page, Animation, ContenirAnimation
            
            project = HMIProject.query.get(project_id)
            if not project:
                return None, "Projet non trouvé"
            
            # Structure d'export
            export_data = {
                'metadata': {
                    'export_version': '1.0',
                    'export_date': datetime.utcnow().isoformat(),
                    'export_tool': 'IHM_Arthur_ProjectManager'
                },
                'project': {
                    'nom_projet': project.nom_projet,
                    'version_projet': project.version_projet,
                    'date_creation_projet': project.date_creation_projet.isoformat(),
                    'date_modification': project.date_modification.isoformat()
                },
                'tags': [],
                'pages': [],
                'animations': [],
                'liaisons_animations': []
            }
            
            # Exporter les tags
            tags = Tag.query.filter_by(id_projet=project_id).all()
            for tag in tags:
                export_data['tags'].append({
                    'nom_tag': tag.nom_tag,
                    'type_donnee': tag.type_donnee,
                    'description_tag': tag.description_tag,
                    'acces': tag.acces,
                    'alarmes_actives': tag.alarmes_actives,
                    'historisation_active': tag.historisation_active,
                    'disponibilite_externe': tag.disponibilite_externe
                })
            
            # Exporter les pages
            pages = Page.query.filter_by(id_projet=project_id).all()
            for page in pages:
                export_data['pages'].append({
                    'nom_page': page.nom_page,
                    'largeur_page': page.largeur_page,
                    'hauteur_page': page.hauteur_page,
                    'couleur_fond': page.couleur_fond,
                    'image_fond': page.image_fond,
                    'ordre_affichage': page.ordre_affichage,
                    'page_accueil': page.page_accueil
                })
                
                # Exporter les animations de cette page
                animations = Animation.query.join(ContenirAnimation).filter(
                    ContenirAnimation.id_page == page.id_page
                ).all()
                
                for anim in animations:
                    export_data['animations'].append({
                        'page_nom': page.nom_page,  # Référence par nom
                        'nom_animation': anim.nom_animation,
                        'type_objet': anim.type_objet,
                        'position_x': anim.position_x,
                        'position_y': anim.position_y,
                        'largeur': anim.largeur,
                        'hauteur': anim.hauteur,
                        'couleur_normale': anim.couleur_normale,
                        'couleur_active': anim.couleur_active,
                        'texte_affiche': anim.texte_affiche,
                        'regles_animation': anim.regles_animation
                    })
            
            return export_data, None
            
        except Exception as e:
            print(f"Erreur export projet: {e}")
            return None, f"Erreur export: {str(e)}"
    
    @staticmethod
    def import_project(import_data, creator_id=None, new_name=None):
        """Importe un projet à partir de données d'export"""
        try:
            from app.models.modele_tag import HMIProject, Tag
            from app.models.modele_graphics import Page, Animation, ContenirAnimation
            
            # Validation des données d'import
            if not import_data.get('project') or not import_data.get('project', {}).get('nom_projet'):
                return False, "Données d'import invalides"
            
            project_name = new_name or f"{import_data['project']['nom_projet']}_import_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            # Vérifier l'unicité du nom
            existing = HMIProject.query.filter_by(nom_projet=project_name).first()
            if existing:
                return False, f"Un projet nommé '{project_name}' existe déjà"
            
            # Créer le nouveau projet
            safe_name = project_name.replace(' ', '_').replace('/', '_')
            chemin_fichier = f"/projects/{safe_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            new_project = HMIProject(
                nom_projet=project_name,
                chemin_fichier=chemin_fichier,
                date_creation_projet=datetime.utcnow(),
                date_modification=datetime.utcnow(),
                version_projet=import_data['project'].get('version_projet', '1.0'),
                actif_projet=True,
                id_utilisateur=creator_id
            )
            
            db.session.add(new_project)
            db.session.flush()
            
            # Importer les tags
            if 'tags' in import_data:
                for tag_data in import_data['tags']:
                    new_tag = Tag(
                        nom_tag=tag_data['nom_tag'],
                        type_donnee=tag_data['type_donnee'],
                        description_tag=tag_data.get('description_tag', ''),
                        acces=tag_data.get('acces', 'R'),
                        alarmes_actives=tag_data.get('alarmes_actives', False),
                        historisation_active=tag_data.get('historisation_active', False),
                        disponibilite_externe=tag_data.get('disponibilite_externe', True),
                        id_projet=new_project.id_projet
                    )
                    db.session.add(new_tag)
            
            # Importer les pages et animations
            if 'pages' in import_data:
                page_mapping = {}
                
                for page_data in import_data['pages']:
                    new_page = Page(
                        nom_page=page_data['nom_page'],
                        largeur_page=page_data.get('largeur_page', 1920),
                        hauteur_page=page_data.get('hauteur_page', 1080),
                        couleur_fond=page_data.get('couleur_fond', '#FFFFFF'),
                        image_fond=page_data.get('image_fond'),
                        ordre_affichage=page_data.get('ordre_affichage', 1),
                        page_accueil=page_data.get('page_accueil', False),
                        id_projet=new_project.id_projet
                    )
                    db.session.add(new_page)
                    db.session.flush()
                    page_mapping[page_data['nom_page']] = new_page.id_page
                
                # Importer les animations
                if 'animations' in import_data:
                    for anim_data in import_data['animations']:
                        page_id = page_mapping.get(anim_data.get('page_nom'))
                        if page_id:
                            new_anim = Animation(
                                nom_animation=anim_data['nom_animation'],
                                type_objet=anim_data.get('type_objet', 'rectangle'),
                                position_x=anim_data.get('position_x', 100),
                                position_y=anim_data.get('position_y', 100),
                                largeur=anim_data.get('largeur', 100),
                                hauteur=anim_data.get('hauteur', 50),
                                couleur_normale=anim_data.get('couleur_normale', '#CCCCCC'),
                                couleur_active=anim_data.get('couleur_active', '#00FF00'),
                                texte_affiche=anim_data.get('texte_affiche', ''),
                                regles_animation=anim_data.get('regles_animation', '{}')
                            )
                            db.session.add(new_anim)
                            db.session.flush()
                            
                            # Créer la liaison
                            liaison = ContenirAnimation(
                                id_animation=new_anim.id_animation,
                                id_page=page_id
                            )
                            db.session.add(liaison)
            
            db.session.commit()
            
            return True, f"Projet '{project_name}' importé avec succès"
            
        except Exception as e:
            db.session.rollback()
            print(f"Erreur import projet: {e}")
            return False, f"Erreur import: {str(e)}"
    
    # =================================================================
    # MÉTHODES UTILITAIRES
    # =================================================================
    
    @staticmethod
    def _get_project_stats(project_id):
        """Calcule les statistiques d'un projet"""
        try:
            from app.models.modele_tag import Tag
            from app.models.modele_graphics import Page, Animation, ContenirAnimation
            
            # Compter les tags
            tags_count = Tag.query.filter_by(id_projet=project_id).count()
            tags_actifs = Tag.query.filter_by(id_projet=project_id, disponibilite_externe=True).count()
            
            # Compter les pages
            pages_count = Page.query.filter_by(id_projet=project_id).count()
            
            # Compter les animations
            animations_count = db.session.query(Animation).join(ContenirAnimation).join(Page).filter(
                Page.id_projet == project_id
            ).count()
            
            return {
                'tags_total': tags_count,
                'tags_actifs': tags_actifs,
                'pages_total': pages_count,
                'animations_total': animations_count
            }
            
        except Exception as e:
            print(f"Erreur calcul stats projet {project_id}: {e}")
            return {
                'tags_total': 0,
                'tags_actifs': 0,
                'pages_total': 0,
                'animations_total': 0
            }
    
    @staticmethod
    def _create_default_project_structure(project_id):
        """Crée une structure par défaut pour un nouveau projet"""
        try:
            from app.models.modele_graphics import Page
            
            # Créer une page d'accueil par défaut
            page_accueil = Page(
                nom_page="Page d'accueil",
                largeur_page=1920,
                hauteur_page=1080,
                couleur_fond="#F0F0F0",
                ordre_affichage=1,
                page_accueil=True,
                id_projet=project_id
            )
            
            db.session.add(page_accueil)
            db.session.commit()
            
        except Exception as e:
            print(f"Erreur création structure par défaut: {e}")
    
    @staticmethod
    def get_project_summary():
        """Retourne un résumé global des projets"""
        try:
            from app.models.modele_tag import HMIProject
            
            total = HMIProject.query.count()
            actifs = HMIProject.query.filter_by(actif_projet=True).count()
            archives = total - actifs
            
            return {
                'total_projets': total,
                'projets_actifs': actifs,
                'projets_archives': archives,
                'dernier_modifie': HMIProject.query.order_by(
                    HMIProject.date_modification.desc()
                ).first()
            }
            
        except Exception as e:
            print(f"Erreur résumé projets: {e}")
            return {
                'total_projets': 0,
                'projets_actifs': 0,
                'projets_archives': 0,
                'dernier_modifie': None
            }