from app import db
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Float
from sqlalchemy.orm import relationship
import json
import os
import uuid
import time
from werkzeug.utils import secure_filename

# =================================================================
# MODÈLES GRAPHIQUES AVEC SUPPORT COMPLET DES ICÔNES ET NAVIGATION
# =================================================================

class Page(db.Model):
    """Modèle Page - EXACTEMENT selon le schéma BDD"""
    
    __tablename__ = 'Page'
    
    # Structure EXACTE selon le schéma
    id_page = Column(Integer, primary_key=True, autoincrement=True)
    nom_page = Column(String(100), nullable=False)
    largeur_page = Column(Integer, nullable=False)
    hauteur_page = Column(Integer, nullable=False)
    couleur_fond = Column(String(7))
    image_fond = Column(String(255))
    ordre_affichage = Column(Integer, nullable=False)
    page_accueil = Column(Boolean, nullable=False)
    id_projet = Column(Integer, ForeignKey('HMI_Project.id_projet'))
    
    def __init__(self, nom_page, **kwargs):
        """Initialisation selon le schéma"""
        self.nom_page = nom_page
        self.largeur_page = kwargs.get('largeur_page', 1920)
        self.hauteur_page = kwargs.get('hauteur_page', 1080)
        self.couleur_fond = kwargs.get('couleur_fond', '#FFFFFF')
        self.image_fond = kwargs.get('image_fond')
        self.ordre_affichage = kwargs.get('ordre_affichage', 1)
        self.page_accueil = kwargs.get('page_accueil', False)
        self.id_projet = kwargs.get('id_projet')
    
    def to_dict(self):
        """Conversion en dictionnaire pour API"""
        return {
            'id_page': self.id_page,
            'nom_page': self.nom_page,
            'largeur_page': self.largeur_page,
            'hauteur_page': self.hauteur_page,
            'couleur_fond': self.couleur_fond,
            'image_fond': self.image_fond,
            'ordre_affichage': self.ordre_affichage,
            'page_accueil': self.page_accueil,
            'id_projet': self.id_projet
        }
    
    # NOUVEAU : Méthodes pour la navigation
    def get_navigation_info(self):
        """Retourne les informations nécessaires pour la navigation"""
        return {
            'id': self.id_page,
            'nom': self.nom_page,
            'largeur': self.largeur_page,
            'hauteur': self.hauteur_page,
            'couleur_fond': self.couleur_fond
        }
    
    def can_navigate_to(self, target_page_id):
        """Vérifie si on peut naviguer vers une page cible"""
        if not target_page_id or target_page_id == self.id_page:
            return False
        
        # Vérifier que la page cible existe dans le même projet
        target_page = Page.query.filter_by(
            id_page=target_page_id,
            id_projet=self.id_projet
        ).first()
        
        return target_page is not None

class Animation(db.Model):
    """Modèle Animation - AMÉLIORÉ avec support icônes ET navigation"""
    
    __tablename__ = 'Animation'
    
    # Structure selon le schéma
    id_animation = Column(Integer, primary_key=True, autoincrement=True)
    nom_animation = Column(String(100), nullable=False)
    type_objet = Column(String(30), nullable=False)
    position_x = Column(Integer, nullable=False)
    position_y = Column(Integer, nullable=False)
    largeur = Column(Integer, nullable=False)
    hauteur = Column(Integer, nullable=False)
    couleur_normale = Column(String(7))
    texte_affiche = Column(String(100))
    regles_animation = Column(String(2000))  # AUGMENTÉ pour stocker les données d'icônes ET navigation
    
    def __init__(self, nom_animation, type_objet, **kwargs):
        """Initialisation AMÉLIORÉE selon le schéma"""
        self.nom_animation = nom_animation
        self.type_objet = type_objet
        self.position_x = kwargs.get('position_x', 100)
        self.position_y = kwargs.get('position_y', 100)
        self.largeur = kwargs.get('largeur', 100)
        self.hauteur = kwargs.get('hauteur', 50)
        self.couleur_normale = kwargs.get('couleur_normale', '#CCCCCC')
        self.texte_affiche = kwargs.get('texte_affiche', '')
        
        # SYSTÈME AMÉLIORÉ : Toutes les données dans regles_animation en JSON
        regles = {
            'tag_lie': kwargs.get('tag_lie', ''),
            'action_clic': kwargs.get('action_clic', 'read'),
            'valeur_ecriture': kwargs.get('valeur_ecriture', ''),
            'page_destination': kwargs.get('page_destination', '')
        }
        
        # Propriétés spécifiques aux icônes
        if type_objet == 'icon' or kwargs.get('icon_data'):
            regles.update({
                'icon_data': kwargs.get('icon_data', '{}'),
                'icon_source': kwargs.get('icon_source', 'upload'),
                'icon_size': kwargs.get('icon_size', 1.0),
                'icon_rotation': kwargs.get('icon_rotation', 0),
                'icon_keep_aspect': kwargs.get('icon_keep_aspect', True),
                'icon_opacity': kwargs.get('icon_opacity', 1.0),
                'icon_flip_x': kwargs.get('icon_flip_x', False),
                'icon_flip_y': kwargs.get('icon_flip_y', False)
            })
        
        self.regles_animation = json.dumps(regles)
    
    # CORRECTION CRITIQUE: Méthode to_dict() au niveau de la classe, PAS dans __init__
    def to_dict(self):
        """Version corrigée - au bon niveau de classe"""
        regles = self.get_regles_animation()
        
        base_dict = {
            'id': self.id_animation,
            'nom': self.nom_animation,
            'type': self.type_objet,
            'x': self.position_x,
            'y': self.position_y,
            'width': self.largeur,
            'height': self.hauteur,
            'couleur_normale': self.couleur_normale,
            'texte': self.texte_affiche,
            'tag_lie': regles.get('tag_lie', ''),
            'action_clic': regles.get('action_clic', 'read'),
            'valeur_ecriture': regles.get('valeur_ecriture', ''),
            'page_destination': regles.get('page_destination', ''),
            'regles': regles
        }
        return base_dict
    
    def get_regles_animation(self):
        """Récupère les règles d'animation décodées AVEC gestion d'erreur"""
        try:
            if self.regles_animation:
                return json.loads(self.regles_animation)
            else:
                return {}
        except (json.JSONDecodeError, TypeError) as e:
            print(f"Erreur décodage règles animation {self.id_animation}: {e}")
            return {}
    
    def set_regles_animation(self, regles):
        """Définit les règles d'animation AVEC validation"""
        try:
            self.regles_animation = json.dumps(regles) if regles else '{}'
        except (TypeError, ValueError) as e:
            print(f"Erreur encodage règles animation {self.id_animation}: {e}")
            self.regles_animation = '{}'
    
    def update_regles(self, **kwargs):
        """Met à jour des règles spécifiques AVEC merge intelligent"""
        regles = self.get_regles_animation()
        regles.update(kwargs)
        self.set_regles_animation(regles)
    
    def get_icon_data(self):
        """Récupère les données d'icône parsées"""
        regles = self.get_regles_animation()
        icon_data_raw = regles.get('icon_data', '{}')
        
        if isinstance(icon_data_raw, str):
            try:
                return json.loads(icon_data_raw)
            except json.JSONDecodeError:
                return {}
        elif isinstance(icon_data_raw, dict):
            return icon_data_raw
        else:
            return {}
    
    def set_icon_data(self, icon_data):
        """Définit les données d'icône"""
        regles = self.get_regles_animation()
        regles['icon_data'] = json.dumps(icon_data) if isinstance(icon_data, dict) else icon_data
        self.set_regles_animation(regles)
    
    # PROPRIÉTÉS RUNTIME VIA regles_animation (maintien compatibilité)
    @property
    def tag_lie(self):
        """Tag lié via les règles d'animation"""
        return self.get_regles_animation().get('tag_lie', '')
    
    @tag_lie.setter
    def tag_lie(self, value):
        """Définit le tag lié"""
        self.update_regles(tag_lie=value)
    
    @property
    def action_clic(self):
        """Action au clic via les règles d'animation"""
        return self.get_regles_animation().get('action_clic', 'read')
    
    @action_clic.setter
    def action_clic(self, value):
        """Définit l'action au clic"""
        self.update_regles(action_clic=value)
    
    @property
    def valeur_ecriture(self):
        """Valeur d'écriture via les règles d'animation"""
        return self.get_regles_animation().get('valeur_ecriture', '')
    
    @valeur_ecriture.setter
    def valeur_ecriture(self, value):
        """Définit la valeur d'écriture"""
        self.update_regles(valeur_ecriture=value)
    
    # NOUVELLES PROPRIÉTÉS POUR LA NAVIGATION
    @property
    def page_destination(self):
        """Page de destination pour la navigation"""
        return self.get_regles_animation().get('page_destination', '')
    
    @page_destination.setter  
    def page_destination(self, value):
        """Définit la page de destination"""
        self.update_regles(page_destination=value)
    
    # PROPRIÉTÉS ICÔNES EXISTANTES
    @property
    def icon_size(self):
        """Taille de l'icône"""
        return self.get_regles_animation().get('icon_size', 1.0)
    
    @icon_size.setter
    def icon_size(self, value):
        """Définit la taille de l'icône"""
        self.update_regles(icon_size=float(value))
    
    @property
    def icon_rotation(self):
        """Rotation de l'icône"""
        return self.get_regles_animation().get('icon_rotation', 0)
    
    @icon_rotation.setter
    def icon_rotation(self, value):
        """Définit la rotation de l'icône"""
        self.update_regles(icon_rotation=int(value))
    
    def est_lie_a_tag(self):
        """Vérifie si l'animation est liée à un tag"""
        return bool(self.tag_lie and self.tag_lie.strip())
    
    def peut_ecrire(self):
        """Vérifie si l'animation peut écrire dans un tag"""
        return self.action_clic in ['write', 'toggle'] and self.est_lie_a_tag()
    
    # NOUVELLES MÉTHODES POUR LA NAVIGATION
    def peut_naviguer(self):
        """Vérifie si l'animation peut naviguer vers une page"""
        return self.action_clic == 'navigate' and bool(self.page_destination)
    
    def get_page_destination_info(self):
        """Retourne les informations de la page de destination"""
        if not self.page_destination:
            return None
        
        try:
            page = Page.query.get(self.page_destination)
            if page:
                return {
                    'id': page.id_page,
                    'nom': page.nom_page,
                    'largeur': page.largeur_page,
                    'hauteur': page.hauteur_page,
                    'couleur_fond': page.couleur_fond
                }
        except:
            pass
        
        return None
    
    def validate_navigation_target(self):
        """Valide que la page de destination est accessible"""
        if not self.page_destination:
            return False, "Aucune page de destination configurée"
        
        target_page = Page.query.get(self.page_destination)
        if not target_page:
            return False, f"Page de destination {self.page_destination} introuvable"
        
        # Vérifier que c'est dans le même projet
        # Pour cela, il faut récupérer la page courante
        try:
            # On peut récupérer le projet via une animation liée à une page
            from sqlalchemy import and_
            current_page = db.session.query(Page).join(
                ContenirAnimation, Page.id_page == ContenirAnimation.id_page
            ).filter(ContenirAnimation.id_animation == self.id_animation).first()
            
            if current_page and target_page.id_projet != current_page.id_projet:
                return False, "La page de destination n'appartient pas au même projet"
                
        except Exception as e:
            print(f"Erreur validation navigation: {e}")
        
        return True, "Page de destination valide"
    
    def get_navigation_data(self):
        """Retourne toutes les données nécessaires pour la navigation"""
        if not self.peut_naviguer():
            return None
        
        target_info = self.get_page_destination_info()
        is_valid, message = self.validate_navigation_target()
        
        return {
            'can_navigate': self.peut_naviguer(),
            'page_destination': self.page_destination,
            'target_info': target_info,
            'is_valid': is_valid,
            'validation_message': message
        }
    
    def get_icon_info(self):
        """Récupère les informations complètes de l'icône associée"""
        if self.type_objet != 'icon':
            return None
        
        icon_data = self.get_icon_data()
        if not icon_data:
            return None
        
        return {
            'data': icon_data,
            'size': self.icon_size,
            'rotation': self.icon_rotation,
            'keep_aspect': self.get_regles_animation().get('icon_keep_aspect', True),
            'opacity': self.get_regles_animation().get('icon_opacity', 1.0),
            'flip_x': self.get_regles_animation().get('icon_flip_x', False),
            'flip_y': self.get_regles_animation().get('icon_flip_y', False)
        }

class ContenirAnimation(db.Model):
    """Table de liaison CONTENIR_ANIMATION - EXACTEMENT selon votre schéma"""
    
    __tablename__ = 'CONTENIR_ANIMATION'
    
    # Clés primaires composites selon le schéma
    id_animation = Column(Integer, ForeignKey('Animation.id_animation'), primary_key=True)
    id_page = Column(Integer, ForeignKey('Page.id_page'), primary_key=True)
    
    def __init__(self, id_animation, id_page):
        self.id_animation = id_animation
        self.id_page = id_page

# =================================================================
# MODÈLE ICÔNES AMÉLIORÉ AVEC TOUTES LES FONCTIONNALITÉS
# =================================================================

class IconLibrary(db.Model):
    """Modèle Icon_Library COMPLET avec tous les champs et méthodes"""
    
    __tablename__ = 'Icon_Library'
    
    id_icon = Column(Integer, primary_key=True, autoincrement=True)
    nom_icon = Column(String(100), nullable=False)
    description_icon = Column(String(255))
    categorie = Column(String(50))
    type_source = Column(String(20), nullable=False)  # 'industrial', 'external', 'upload'
    
    # Pour icônes externes (Feather, FontAwesome, etc.)
    external_name = Column(String(100))
    external_library = Column(String(50))
    
    # Pour icônes uploadées
    fichier_path = Column(String(500))
    fichier_original = Column(String(255))
    mime_type = Column(String(50))
    taille_fichier = Column(Integer)
    
    # Propriétés visuelles
    largeur_defaut = Column(Integer)
    hauteur_defaut = Column(Integer)
    couleur_defaut = Column(String(7))
    
    # Pour icônes Unicode/industrielles
    unicode_char = Column(String(10))
    is_unicode = Column(Boolean, default=False)
    
    # Métadonnées
    date_creation = Column(DateTime)
    date_modification = Column(DateTime)
    cree_par = Column(Integer)
    actif = Column(Boolean, default=True)
    
    # Métadonnées étendues
    tags_recherche = Column(String(500))  # Tags pour recherche
    popularite = Column(Integer, default=0)  # Compteur d'utilisation
    version = Column(String(10), default='1.0')
    
    def __init__(self, **kwargs):
        self.nom_icon = kwargs.get('nom_icon')
        self.description_icon = kwargs.get('description_icon', '')
        self.categorie = kwargs.get('categorie', 'custom')
        self.type_source = kwargs.get('type_source', 'upload')
        self.external_name = kwargs.get('external_name')
        self.external_library = kwargs.get('external_library')
        self.fichier_path = kwargs.get('fichier_path')
        self.fichier_original = kwargs.get('fichier_original')
        self.mime_type = kwargs.get('mime_type')
        self.taille_fichier = kwargs.get('taille_fichier')
        self.largeur_defaut = kwargs.get('largeur_defaut', 32)
        self.hauteur_defaut = kwargs.get('hauteur_defaut', 32)
        self.couleur_defaut = kwargs.get('couleur_defaut', '#2a5298')
        self.unicode_char = kwargs.get('unicode_char')
        self.is_unicode = kwargs.get('is_unicode', False)
        self.date_creation = kwargs.get('date_creation', datetime.utcnow())
        self.date_modification = kwargs.get('date_modification')
        self.cree_par = kwargs.get('cree_par')
        self.actif = kwargs.get('actif', True)
        self.tags_recherche = kwargs.get('tags_recherche', '')
        self.popularite = kwargs.get('popularite', 0)
        self.version = kwargs.get('version', '1.0')

    def to_dict(self):
        """Retourne l'objet COMPLET sous forme de dictionnaire JSON"""
        return {
            "id_icon": self.id_icon,
            "id": self.id_icon,  # Alias pour compatibilité
            "nom_icon": self.nom_icon,
            "description_icon": self.description_icon,
            "categorie": self.categorie,
            "type_source": self.type_source,
            "external_name": self.external_name,
            "external_library": self.external_library,
            "fichier_path": self.fichier_path,
            "fichier_original": self.fichier_original,
            "mime_type": self.mime_type,
            "taille_fichier": self.taille_fichier,
            "largeur_defaut": self.largeur_defaut,
            "hauteur_defaut": self.hauteur_defaut,
            "couleur_defaut": self.couleur_defaut,
            "unicode_char": self.unicode_char,
            "is_unicode": self.is_unicode,
            "date_creation": self.date_creation.isoformat() if self.date_creation else None,
            "date_modification": self.date_modification.isoformat() if self.date_modification else None,
            "cree_par": self.cree_par,
            "actif": self.actif,
            "tags_recherche": self.tags_recherche,
            "popularite": self.popularite,
            "version": self.version,
            "url": self.get_url(),
            "preview_data": self.get_preview_data()
        }

    def get_url(self):
        """Retourne l'URL utilisable pour accéder à l'icône"""
        if self.type_source == 'upload' and self.fichier_path:
            filename = os.path.basename(self.fichier_path)
            return f"/static/icons/custom/{filename}"
        elif self.type_source == 'external' and self.external_library and self.external_name:
            return f"{self.external_library}/{self.external_name}"
        elif self.is_unicode and self.unicode_char:
            return f"unicode:{self.unicode_char}"
        return ""

    def get_preview_data(self):
        """Génère les données de prévisualisation pour le frontend"""
        preview = {
            'type': self.type_source,
            'size': {'width': self.largeur_defaut, 'height': self.hauteur_defaut}
        }
        
        if self.type_source == 'industrial' or self.is_unicode:
            preview['unicode'] = self.unicode_char
        elif self.type_source == 'external':
            preview['external'] = {
                'library': self.external_library,
                'name': self.external_name
            }
        elif self.type_source == 'upload':
            preview['file'] = {
                'url': self.get_url(),
                'mime_type': self.mime_type,
                'size_bytes': self.taille_fichier
            }
        
        return preview

    def increment_popularity(self):
        """Incrémente le compteur de popularité"""
        self.popularite = (self.popularite or 0) + 1
        self.date_modification = datetime.utcnow()

    def add_search_tags(self, tags):
        """Ajoute des tags de recherche"""
        if isinstance(tags, list):
            tags = ' '.join(tags)
        
        existing_tags = set(self.tags_recherche.split() if self.tags_recherche else [])
        new_tags = set(tags.split())
        all_tags = existing_tags.union(new_tags)
        
        self.tags_recherche = ' '.join(sorted(all_tags))

    def validate_data(self):
        """Valide les données de l'icône"""
        errors = []
        
        if not self.nom_icon or not self.nom_icon.strip():
            errors.append("Le nom de l'icône est requis")
        
        if self.type_source not in ['industrial', 'external', 'upload']:
            errors.append("Type de source invalide")
        
        if self.type_source == 'external' and not (self.external_library and self.external_name):
            errors.append("Nom et bibliothèque requis pour les icônes externes")
        
        if self.type_source == 'upload' and not self.fichier_path:
            errors.append("Chemin de fichier requis pour les icônes uploadées")
        
        return len(errors) == 0, errors

class IconFileManager:
    """Gestionnaire de fichiers d'icônes AMÉLIORÉ avec toutes les fonctionnalités"""
    
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'svg', 'bmp', 'webp', 'ico'}
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB (augmenté)
    UPLOAD_FOLDER = os.path.join('web_indus', 'app', 'static', 'icons', 'custom')
    THUMBNAIL_FOLDER = os.path.join('web_indus','app', 'static', 'icons', 'thumbnails')
    
    @staticmethod
    def save_uploaded_icon(file, custom_name=None, category='custom'):
        """Sauvegarde un fichier d'icône uploadé AVEC optimisations"""
        if not file or file.filename == '':
            return None, "Aucun fichier sélectionné"
        
        if not IconFileManager.allowed_file(file.filename):
            return None, f"Type de fichier non autorisé. Types acceptés: {', '.join(IconFileManager.ALLOWED_EXTENSIONS)}"
        
        # Vérifier la taille
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)
        
        if file_size > IconFileManager.MAX_FILE_SIZE:
            return None, f"Fichier trop volumineux (max {IconFileManager.MAX_FILE_SIZE // 1024 // 1024}MB)"
        
        # Créer les dossiers si nécessaires
        os.makedirs(IconFileManager.UPLOAD_FOLDER, exist_ok=True)
        os.makedirs(IconFileManager.THUMBNAIL_FOLDER, exist_ok=True)
        
        # Générer nom unique et sécurisé
        filename = secure_filename(file.filename)
        name, ext = os.path.splitext(filename)
        timestamp = int(time.time())
        unique_filename = f"{secure_filename(custom_name or name)}_{timestamp}{ext}"
        file_path = os.path.join(IconFileManager.UPLOAD_FOLDER, unique_filename)
        
        try:
            # Sauvegarder le fichier
            file.save(file_path)
            
            # Obtenir dimensions et créer thumbnail
            width, height = IconFileManager.get_image_dimensions(file_path)
            thumbnail_path = IconFileManager.create_thumbnail(file_path, unique_filename)
            
            # Générer tags de recherche automatiques
            search_tags = IconFileManager.generate_search_tags(filename, category)
            
            # Créer l'entrée en base
            icon_name = custom_name or name
            new_icon = IconLibrary(
                nom_icon=icon_name,
                description_icon=f"Image uploadée: {filename}",
                categorie=category,
                type_source='upload',
                fichier_path=file_path,
                fichier_original=filename,
                mime_type=file.content_type,
                taille_fichier=file_size,
                largeur_defaut=width,
                hauteur_defaut=height,
                couleur_defaut='#2a5298',
                tags_recherche=search_tags,
                date_creation=datetime.utcnow(),
                actif=True,
                version='1.0'
            )
            
            db.session.add(new_icon)
            db.session.commit()
            
            return new_icon, f"Icône '{icon_name}' uploadée avec succès ({width}×{height}px, {IconFileManager.format_file_size(file_size)})"
            
        except Exception as e:
            # Nettoyage en cas d'erreur
            for path in [file_path, thumbnail_path]:
                if path and os.path.exists(path):
                    try:
                        os.remove(path)
                    except:
                        pass
            
            db.session.rollback()
            return None, f"Erreur sauvegarde: {str(e)}"
    
    @staticmethod
    def delete_icon(icon_id):
        """Supprimer une icône et ses fichiers associés"""
        try:
            icon = IconLibrary.query.get(icon_id)
            if not icon:
                return False, "Icône non trouvée"
            
            files_deleted = []
            
            # Supprimer le fichier principal si c'est un upload
            if icon.type_source == 'upload' and icon.fichier_path:
                try:
                    if os.path.exists(icon.fichier_path):
                        os.remove(icon.fichier_path)
                        files_deleted.append("fichier principal")
                    
                    # Supprimer le thumbnail associé
                    thumbnail_path = IconFileManager.get_thumbnail_path(icon.fichier_path)
                    if thumbnail_path and os.path.exists(thumbnail_path):
                        os.remove(thumbnail_path)
                        files_deleted.append("thumbnail")
                        
                except Exception as e:
                    print(f"Erreur suppression fichiers {icon.fichier_path}: {e}")
            
            # Supprimer de la base
            nom_icon = icon.nom_icon
            db.session.delete(icon)
            db.session.commit()
            
            message = f"Icône '{nom_icon}' supprimée"
            if files_deleted:
                message += f" ({', '.join(files_deleted)} supprimé(s))"
            
            return True, message
            
        except Exception as e:
            db.session.rollback()
            return False, f"Erreur suppression: {str(e)}"
    
    @staticmethod
    def get_image_dimensions(file_path):
        """Obtient les dimensions d'une image AVEC fallback"""
        try:
            from PIL import Image
            with Image.open(file_path) as img:
                return img.size
        except ImportError:
            print("PIL (Pillow) non installé - utilisation dimensions par défaut")
            return 64, 64  # Dimensions par défaut plus grandes
        except Exception as e:
            print(f"Erreur lecture dimensions image: {e}")
            return 64, 64
    
    @staticmethod
    def create_thumbnail(file_path, filename, size=(64, 64)):
        """Crée un thumbnail de l'image"""
        try:
            from PIL import Image
            
            thumbnail_name = f"thumb_{filename}"
            thumbnail_path = os.path.join(IconFileManager.THUMBNAIL_FOLDER, thumbnail_name)
            
            with Image.open(file_path) as img:
                # Conserver le ratio d'aspect
                img.thumbnail(size, Image.Resampling.LANCZOS)
                
                # Créer un fond transparent pour PNG ou blanc pour les autres
                if img.mode in ('RGBA', 'LA'):
                    background = Image.new('RGBA', size, (255, 255, 255, 0))
                else:
                    background = Image.new('RGB', size, (255, 255, 255))
                
                # Centrer l'image sur le fond
                offset = ((size[0] - img.size[0]) // 2, (size[1] - img.size[1]) // 2)
                background.paste(img, offset)
                
                # Sauvegarder
                background.save(thumbnail_path, 'PNG', optimize=True)
                return thumbnail_path
                
        except ImportError:
            print("PIL non disponible pour la création de thumbnails")
            return None
        except Exception as e:
            print(f"Erreur création thumbnail: {e}")
            return None
    
    @staticmethod
    def get_thumbnail_path(file_path):
        """Retourne le chemin du thumbnail associé à un fichier"""
        if not file_path:
            return None
        
        filename = os.path.basename(file_path)
        thumbnail_name = f"thumb_{filename}"
        return os.path.join(IconFileManager.THUMBNAIL_FOLDER, thumbnail_name)
    
    @staticmethod
    def generate_search_tags(filename, category):
        """Génère automatiquement des tags de recherche"""
        tags = set()
        
        # Tags basés sur le nom de fichier
        name_parts = os.path.splitext(filename)[0].lower()
        name_parts = name_parts.replace('_', ' ').replace('-', ' ')
        tags.update(name_parts.split())
        
        # Tags basés sur la catégorie
        if category:
            tags.add(category.lower())
        
        # Tags de type
        tags.add('image')
        tags.add('icon')
        
        return ' '.join(sorted(tags))
    
    @staticmethod
    def format_file_size(bytes):
        """Formate une taille de fichier en format lisible"""
        if bytes == 0:
            return '0 B'
        
        units = ['B', 'KB', 'MB', 'GB']
        size = bytes
        unit_index = 0
        
        while size >= 1024 and unit_index < len(units) - 1:
            size /= 1024
            unit_index += 1
        
        return f"{size:.1f} {units[unit_index]}"
    
    @staticmethod
    def allowed_file(filename):
        """Vérifie si le type de fichier est autorisé"""
        return '.' in filename and \
               filename.rsplit('.', 1)[1].lower() in IconFileManager.ALLOWED_EXTENSIONS

class GestionIcon(db.Model):
    """Table de liaison GESTION_ICON selon votre schéma"""
    
    __tablename__ = 'GESTION_ICON'
    
    id_page = Column(Integer, ForeignKey('Page.id_page'), primary_key=True)
    id_icon = Column(Integer, ForeignKey('Icon_Library.id_icon'), primary_key=True)

    def __init__(self, id_page, id_icon):
        self.id_page = id_page
        self.id_icon = id_icon

# =================================================================
# FONCTIONS D'INITIALISATION ET DE MAINTENANCE
# =================================================================

def init_default_industrial_icons():
    """Initialise les icônes industrielles par défaut AVEC vraies données"""
    industrial_icons = [
        # Actionneurs - Icônes réelles
        {'nom': 'Motor_Electric', 'unicode': '⚡', 'categorie': 'actionneurs', 'description': 'Moteur électrique', 'tags': 'moteur electrique machine rotation'},
        {'nom': 'Pump_Centrifugal', 'unicode': '🔄', 'categorie': 'actionneurs', 'description': 'Pompe centrifuge', 'tags': 'pompe eau fluide circulation'},
        {'nom': 'Fan_Industrial', 'unicode': '🌀', 'categorie': 'actionneurs', 'description': 'Ventilateur industriel', 'tags': 'ventilateur air climatisation'},
        {'nom': 'Heater_Electric', 'unicode': '🔥', 'categorie': 'actionneurs', 'description': 'Réchauffeur électrique', 'tags': 'chauffage temperature thermique'},
        {'nom': 'Compressor', 'unicode': '🗜️', 'categorie': 'actionneurs', 'description': 'Compresseur', 'tags': 'compression air pression'},
        
        # Capteurs - Avec métadonnées complètes  
        {'nom': 'Temperature_Sensor', 'unicode': '🌡️', 'categorie': 'capteurs', 'description': 'Capteur de température', 'tags': 'temperature mesure thermique'},
        {'nom': 'Pressure_Sensor', 'unicode': '📊', 'categorie': 'capteurs', 'description': 'Capteur de pression', 'tags': 'pression mesure jauge'},
        {'nom': 'Level_Sensor', 'unicode': '📏', 'categorie': 'capteurs', 'description': 'Capteur de niveau', 'tags': 'niveau liquide mesure hauteur'},
        {'nom': 'Flow_Sensor', 'unicode': '💧', 'categorie': 'capteurs', 'description': 'Débitmètre', 'tags': 'debit fluide mesure'},
        {'nom': 'Vibration_Sensor', 'unicode': '📳', 'categorie': 'capteurs', 'description': 'Capteur de vibration', 'tags': 'vibration oscillation mesure'},
        
        # Vannes - Système de contrôle
        {'nom': 'Valve_Manual', 'unicode': '⚙️', 'categorie': 'vannes', 'description': 'Vanne manuelle', 'tags': 'vanne manuelle controle fluide'},
        {'nom': 'Valve_Motorized', 'unicode': '🔵', 'categorie': 'vannes', 'description': 'Vanne motorisée', 'tags': 'vanne automatique moteur'},
        {'nom': 'Safety_Valve', 'unicode': '⭕', 'categorie': 'vannes', 'description': 'Soupape de sécurité', 'tags': 'securite soupape protection'},
        {'nom': 'Check_Valve', 'unicode': '↗️', 'categorie': 'vannes', 'description': 'Clapet anti-retour', 'tags': 'clapet antiretour sens unique'},
        
        # Tuyauterie
        {'nom': 'Pipe_Straight', 'unicode': '—', 'categorie': 'tuyauterie', 'description': 'Tuyau droit', 'tags': 'tuyau pipe conduite droite'},
        {'nom': 'Pipe_Elbow', 'unicode': '↩️', 'categorie': 'tuyauterie', 'description': 'Coude de tuyauterie', 'tags': 'coude tuyau angle'},
        {'nom': 'Tank_Storage', 'unicode': '⬛', 'categorie': 'tuyauterie', 'description': 'Réservoir de stockage', 'tags': 'reservoir stockage cuve'},
        
        # Indicateurs - Interface utilisateur
        {'nom': 'Alarm_Red', 'unicode': '🚨', 'categorie': 'indicateurs', 'description': 'Alarme rouge', 'tags': 'alarme rouge urgence'},
        {'nom': 'Warning_Yellow', 'unicode': '⚠️', 'categorie': 'indicateurs', 'description': 'Avertissement jaune', 'tags': 'attention avertissement jaune'},
        {'nom': 'Status_OK', 'unicode': '✅', 'categorie': 'indicateurs', 'description': 'État OK', 'tags': 'ok validation vert bon'},
        {'nom': 'Status_Error', 'unicode': '❌', 'categorie': 'indicateurs', 'description': 'État d\'erreur', 'tags': 'erreur rouge probleme'},
        {'nom': 'LED_Green', 'unicode': '🟢', 'categorie': 'indicateurs', 'description': 'LED verte', 'tags': 'led vert indicateur'},
        {'nom': 'LED_Red', 'unicode': '🔴', 'categorie': 'indicateurs', 'description': 'LED rouge', 'tags': 'led rouge indicateur'},
        
        # Contrôle - Éléments d'interface
        {'nom': 'Button_Start', 'unicode': '▶️', 'categorie': 'controle', 'description': 'Bouton démarrer', 'tags': 'bouton demarrer start play'},
        {'nom': 'Button_Stop', 'unicode': '⏹️', 'categorie': 'controle', 'description': 'Bouton arrêt', 'tags': 'bouton arret stop'},
        {'nom': 'Button_Pause', 'unicode': '⏸️', 'categorie': 'controle', 'description': 'Bouton pause', 'tags': 'bouton pause attendre'},
        {'nom': 'Emergency_Stop', 'unicode': '🛑', 'categorie': 'controle', 'description': 'Arrêt d\'urgence', 'tags': 'urgence arret secours'},
        {'nom': 'Settings_Gear', 'unicode': '⚙️', 'categorie': 'controle', 'description': 'Paramètres', 'tags': 'parametres configuration reglage'},
        
        # NOUVEAU : Icônes de navigation
        {'nom': 'Navigate_Home', 'unicode': '🏠', 'categorie': 'navigation', 'description': 'Accueil', 'tags': 'accueil home navigation'},
        {'nom': 'Navigate_Back', 'unicode': '⬅️', 'categorie': 'navigation', 'description': 'Retour', 'tags': 'retour precedent navigation'},
        {'nom': 'Navigate_Forward', 'unicode': '➡️', 'categorie': 'navigation', 'description': 'Suivant', 'tags': 'suivant avant navigation'},
        {'nom': 'Navigate_Up', 'unicode': '⬆️', 'categorie': 'navigation', 'description': 'Haut', 'tags': 'haut monter navigation'},
        {'nom': 'Navigate_Down', 'unicode': '⬇️', 'categorie': 'navigation', 'description': 'Bas', 'tags': 'bas descendre navigation'},
        {'nom': 'Page_Link', 'unicode': '🔗', 'categorie': 'navigation', 'description': 'Lien page', 'tags': 'lien page navigation'}
    ]
    
    icons_created = 0
    for icon_data in industrial_icons:
        existing = IconLibrary.query.filter_by(
            nom_icon=icon_data['nom'],
            type_source='industrial'
        ).first()
        
        if not existing:
            new_icon = IconLibrary(
                nom_icon=icon_data['nom'],
                description_icon=icon_data['description'],
                categorie=icon_data['categorie'],
                type_source='industrial',
                unicode_char=icon_data['unicode'],
                is_unicode=True,
                largeur_defaut=32,
                hauteur_defaut=32,
                couleur_defaut='#2a5298',
                tags_recherche=icon_data.get('tags', ''),
                date_creation=datetime.utcnow(),
                actif=True,
                version='1.0'
            )
            db.session.add(new_icon)
            icons_created += 1
    
    if icons_created > 0:
        db.session.commit()
        print(f"✅ {icons_created} icônes industrielles créées")
    else:
        print("ℹ️ Icônes industrielles déjà présentes")

def init_feather_icons():
    """Initialise une sélection d'icônes Feather populaires"""
    feather_icons = [
        # Contrôle
        {'name': 'play', 'categorie': 'controle', 'description': 'Démarrer', 'tags': 'play start demarrer'},
        {'name': 'pause', 'categorie': 'controle', 'description': 'Pause', 'tags': 'pause attendre suspendre'},
        {'name': 'square', 'categorie': 'controle', 'description': 'Arrêter', 'tags': 'stop arret carre'},
        {'name': 'power', 'categorie': 'controle', 'description': 'Alimentation', 'tags': 'power alimentation marche'},
        {'name': 'settings', 'categorie': 'controle', 'description': 'Paramètres', 'tags': 'settings parametres configuration'},
        
        # Indicateurs
        {'name': 'activity', 'categorie': 'indicateurs', 'description': 'Activité', 'tags': 'activite signal etat'},
        {'name': 'alert-circle', 'categorie': 'indicateurs', 'description': 'Alerte', 'tags': 'alerte attention warning'},
        {'name': 'check-circle', 'categorie': 'indicateurs', 'description': 'Validation', 'tags': 'validation ok check'},
        {'name': 'x-circle', 'categorie': 'indicateurs', 'description': 'Erreur', 'tags': 'erreur error croix'},
        {'name': 'info', 'categorie': 'indicateurs', 'description': 'Information', 'tags': 'info information aide'},
        
        # Navigation
        {'name': 'home', 'categorie': 'navigation', 'description': 'Accueil', 'tags': 'accueil home maison'},
        {'name': 'menu', 'categorie': 'navigation', 'description': 'Menu', 'tags': 'menu hamburger navigation'},
        {'name': 'arrow-left', 'categorie': 'navigation', 'description': 'Flèche gauche', 'tags': 'fleche gauche retour'},
        {'name': 'arrow-right', 'categorie': 'navigation', 'description': 'Flèche droite', 'tags': 'fleche droite suivant'},
        {'name': 'chevron-up', 'categorie': 'navigation', 'description': 'Chevron haut', 'tags': 'chevron haut monter'},
        {'name': 'chevron-down', 'categorie': 'navigation', 'description': 'Chevron bas', 'tags': 'chevron bas descendre'},
        {'name': 'external-link', 'categorie': 'navigation', 'description': 'Lien externe', 'tags': 'lien externe navigation'},
        
        # Outils techniques
        {'name': 'cpu', 'categorie': 'outils', 'description': 'Processeur', 'tags': 'cpu processeur puce'},
        {'name': 'hard-drive', 'categorie': 'outils', 'description': 'Disque dur', 'tags': 'disque dur stockage'},
        {'name': 'wifi', 'categorie': 'outils', 'description': 'WiFi', 'tags': 'wifi reseau sans-fil'},
        {'name': 'bluetooth', 'categorie': 'outils', 'description': 'Bluetooth', 'tags': 'bluetooth connexion'},
        {'name': 'tool', 'categorie': 'outils', 'description': 'Outil', 'tags': 'outil maintenance reparation'},
        
        # Interface
        {'name': 'eye', 'categorie': 'interface', 'description': 'Voir', 'tags': 'oeil voir afficher'},
        {'name': 'eye-off', 'categorie': 'interface', 'description': 'Masquer', 'tags': 'masquer cacher invisible'},
        {'name': 'edit', 'categorie': 'interface', 'description': 'Modifier', 'tags': 'modifier editer crayon'},
        {'name': 'trash-2', 'categorie': 'interface', 'description': 'Supprimer', 'tags': 'supprimer corbeille poubelle'},
        {'name': 'save', 'categorie': 'interface', 'description': 'Sauvegarder', 'tags': 'sauvegarder enregistrer'}
    ]
    
    icons_created = 0
    for icon in feather_icons:
        existing = IconLibrary.query.filter_by(
            external_name=icon['name'],
            external_library='feather'
        ).first()
        
        if not existing:
            new_icon = IconLibrary(
                nom_icon=f"Feather_{icon['name'].replace('-', '_').title()}",
                description_icon=icon['description'],
                categorie=icon['categorie'],
                type_source='external',
                external_name=icon['name'],
                external_library='feather',
                largeur_defaut=24,
                hauteur_defaut=24,
                couleur_defaut='#2a5298',
                tags_recherche=icon.get('tags', ''),
                date_creation=datetime.utcnow(),
                actif=True,
                version='1.0'
            )
            db.session.add(new_icon)
            icons_created += 1
    
    if icons_created > 0:
        db.session.commit()
        print(f"✅ {icons_created} icônes Feather créées")
    else:
        print("ℹ️ Icônes Feather déjà présentes")

# =================================================================
# FONCTIONS UTILITAIRES POUR LA GESTION DES PROJETS
# =================================================================

def creer_page_defaut():
    """Crée une page par défaut - CORRIGÉE pour projet spécifique"""
    from flask import session
    
    current_project_id = session.get('current_project_id')
    if not current_project_id:
        print("⚠️ Pas de projet actuel pour créer une page par défaut")
        return None
    
    # Vérifier dans le projet actuel
    page_existante = Page.query.filter_by(
        id_projet=current_project_id,
        page_accueil=True
    ).first()
    
    if not page_existante:
        page_defaut = Page(
            nom_page="Page d'accueil",
            largeur_page=1920,
            hauteur_page=1080,
            couleur_fond="#F0F0F0",
            ordre_affichage=1,
            page_accueil=True,
            id_projet=current_project_id
        )
        db.session.add(page_defaut)
        db.session.commit()
        print(f"✅ Page par défaut créée dans le projet {current_project_id}")
        return page_defaut
    
    return page_existante

def nettoyer_projet(project_id):
    """Nettoie toutes les données graphiques d'un projet"""
    try:
        # Récupérer toutes les pages du projet
        pages = Page.query.filter_by(id_projet=project_id).all()
        
        for page in pages:
            # Supprimer les liaisons animations-page
            ContenirAnimation.query.filter_by(id_page=page.id_page).delete()
            
            # Supprimer les animations de cette page
            animations = Animation.query.join(ContenirAnimation).filter(
                ContenirAnimation.id_page == page.id_page
            ).all()
            
            for anim in animations:
                db.session.delete(anim)
        
        # Supprimer les pages
        Page.query.filter_by(id_projet=project_id).delete()
        
        db.session.commit()
        print(f"✅ Projet {project_id} nettoyé (pages et animations supprimées)")
        
    except Exception as e:
        print(f"⚠️ Erreur nettoyage projet {project_id}: {e}")
        db.session.rollback()

def initialiser_structure_graphique_projet(project_id):
    """Initialise la structure graphique par défaut pour un nouveau projet"""
    try:
        # Temporairement stocker l'ID du projet en session
        from flask import session
        old_project_id = session.get('current_project_id')
        session['current_project_id'] = project_id
        
        # Créer la page d'accueil par défaut
        page_defaut = creer_page_defaut()
        
        # Restaurer l'ancien projet en session
        if old_project_id:
            session['current_project_id'] = old_project_id
        else:
            session.pop('current_project_id', None)
        
        print(f"✅ Structure graphique initialisée pour le projet {project_id}")
        return page_defaut
        
    except Exception as e:
        print(f"⚠️ Erreur initialisation graphique projet {project_id}: {e}")
        return None

def migrer_anciennes_animations():
    """Convertit d'anciennes animations pour supporter les icônes ET la navigation"""
    from flask import session
    
    current_project_id = session.get('current_project_id')
    if not current_project_id:
        print("⚠️ Pas de projet actuel pour la migration")
        return
    
    try:
        # Récupérer les pages du projet actuel
        pages_projet = Page.query.filter_by(id_projet=current_project_id).all()
        page_ids = [page.id_page for page in pages_projet]
        
        if not page_ids:
            print(f"Aucune page dans le projet {current_project_id}")
            return
        
        # Récupérer les animations avec règles manquantes ou incomplètes
        animations = Animation.query.join(ContenirAnimation).filter(
            ContenirAnimation.id_page.in_(page_ids),
            db.or_(
                Animation.regles_animation.is_(None),
                Animation.regles_animation == '',
                Animation.regles_animation == '{}'
            )
        ).all()
        
        for anim in animations:
            # Créer des règles par défaut complètes
            regles_defaut = {
                'tag_lie': '',
                'action_clic': 'read',
                'valeur_ecriture': '',
                'animation_type': 'couleur',
                'vitesse': 1000,
                # NOUVEAU : Support navigation
                'page_destination': ''
            }
            
            # Ajouter des propriétés d'icône si c'est un objet icône
            if anim.type_objet == 'icon':
                regles_defaut.update({
                    'icon_data': '{}',
                    'icon_source': 'upload',
                    'icon_size': 1.0,
                    'icon_rotation': 0,
                    'icon_keep_aspect': True,
                    'icon_opacity': 1.0,
                    'icon_flip_x': False,
                    'icon_flip_y': False
                })
            
            anim.set_regles_animation(regles_defaut)
        
        if animations:
            db.session.commit()
            print(f"✅ {len(animations)} animations migrées dans le projet {current_project_id}")
        
    except Exception as e:
        print(f"⚠️ Erreur migration animations projet {current_project_id}: {e}")
        db.session.rollback()

# =================================================================
# NOUVELLES FONCTIONS POUR LA NAVIGATION
# =================================================================

def get_pages_for_navigation(current_page_id=None, project_id=None):
    """Retourne la liste des pages disponibles pour la navigation"""
    try:
        from flask import session
        
        if not project_id:
            project_id = session.get('current_project_id')
        
        if not project_id:
            return []
        
        # Récupérer toutes les pages du projet sauf la page courante
        query = Page.query.filter_by(id_projet=project_id)
        
        if current_page_id:
            query = query.filter(Page.id_page != current_page_id)
        
        pages = query.order_by(Page.ordre_affichage, Page.nom_page).all()
        
        return [
            {
                'id': page.id_page,
                'nom': page.nom_page,
                'largeur': page.largeur_page,
                'hauteur': page.hauteur_page,
                'couleur_fond': page.couleur_fond,
                'page_accueil': page.page_accueil
            }
            for page in pages
        ]
        
    except Exception as e:
        print(f"Erreur récupération pages navigation: {e}")
        return []

def validate_navigation_setup(animation_id, target_page_id):
    """Valide une configuration de navigation"""
    try:
        animation = Animation.query.get(animation_id)
        if not animation:
            return False, "Animation introuvable"
        
        if not target_page_id:
            return False, "Page de destination manquante"
        
        target_page = Page.query.get(target_page_id)
        if not target_page:
            return False, "Page de destination introuvable"
        
        # Vérifier que les deux pages sont dans le même projet
        current_page = db.session.query(Page).join(
            ContenirAnimation, Page.id_page == ContenirAnimation.id_page
        ).filter(ContenirAnimation.id_animation == animation_id).first()
        
        if not current_page:
            return False, "Page courante introuvable"
        
        if current_page.id_projet != target_page.id_projet:
            return False, "La page de destination n'appartient pas au même projet"
        
        if current_page.id_page == target_page.id_page:
            return False, "Une page ne peut pas naviguer vers elle-même"
        
        return True, "Configuration de navigation valide"
        
    except Exception as e:
        return False, f"Erreur validation: {str(e)}"

def get_navigation_statistics(project_id=None):
    """Retourne des statistiques sur les navigations configurées"""
    try:
        from flask import session
        
        if not project_id:
            project_id = session.get('current_project_id')
        
        if not project_id:
            return {}
        
        # Compter les objets avec navigation
        pages = Page.query.filter_by(id_projet=project_id).all()
        page_ids = [p.id_page for p in pages]
        
        animations_with_navigation = Animation.query.join(ContenirAnimation).filter(
            ContenirAnimation.id_page.in_(page_ids),
            Animation.regles_animation.contains('"action_clic":"navigate"')
        ).all()
        
        return {
            'total_pages': len(pages),
            'objects_with_navigation': len(animations_with_navigation),
            'navigation_enabled': len(animations_with_navigation) > 0
        }
        
    except Exception as e:
        print(f"Erreur statistiques navigation: {e}")
        return {}

# =================================================================
# CONSTANTES ET CONFIGURATIONS
# =================================================================

TYPES_OBJETS_GRAPHICS = {
    'rectangle': {'nom': 'Rectangle', 'icone': '⬜'},
    'circle': {'nom': 'Cercle', 'icone': '⭕'},
    'button': {'nom': 'Bouton', 'icone': '🔘'},
    'text': {'nom': 'Texte', 'icone': '📝'},
    'led': {'nom': 'LED', 'icone': '💡'},
    'icon': {'nom': 'Icône', 'icone': '🖼️'},  # EXISTANT
    'gauge': {'nom': 'Jauge', 'icone': '📊'},
    'valve': {'nom': 'Vanne', 'icone': '⚙️'},
    'motor': {'nom': 'Moteur', 'icone': '⚡'}
}

CATEGORIES_ICONES_DEFAUT = [
    'actionneurs', 'capteurs', 'vannes', 'tuyauterie', 
    'indicateurs', 'controle', 'interface', 'navigation', 'outils', 'custom'  # NOUVEAU: navigation
]

# NOUVEAU : Actions disponibles pour les objets
ACTIONS_OBJETS_DISPONIBLES = {
    'read': {'nom': 'Lecture seule', 'description': 'Afficher la valeur du tag', 'icone': '👁️'},
    'write': {'nom': 'Écriture', 'description': 'Écrire une valeur dans le tag', 'icone': '✏️'},
    'toggle': {'nom': 'Basculer', 'description': 'Inverser la valeur booléenne', 'icone': '🔄'},
    'navigate': {'nom': 'Navigation', 'description': 'Naviguer vers une autre page', 'icone': '🧭'}  # NOUVEAU
}

# =================================================================
# PROJET HMI
# =================================================================
class HMIProject(db.Model):
    __tablename__ = 'hmi_project'

    id_projet = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nom_projet = db.Column(db.String(100), unique=True, nullable=False)
    chemin_fichier = db.Column(db.String(255), nullable=False)
    date_creation_projet = db.Column(db.DateTime, nullable=False)
    date_modification = db.Column(db.DateTime, nullable=False)
    version_projet = db.Column(db.String(10), nullable=False)
    actif_projet = db.Column(db.Boolean, nullable=False)
    id_utilisateur = db.Column(db.Integer, db.ForeignKey('utilisateur.id_utilisateur'), nullable=True)

    # Relation pour accéder facilement aux règles de couleur
    color_rules = db.relationship('ColorRule', backref='projet', cascade='all, delete-orphan')

# =================================================================
# COULEUR DYNAMIQUE
# =================================================================
class ColorRule(db.Model):
    """Règle de couleur dynamique simplifiée"""
    
    __tablename__ = 'color_rule'
    
    id_color_rule = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nom_regle = db.Column(db.String(100), nullable=False)
    id_projet = db.Column(db.Integer, db.ForeignKey("hmi_project.id_projet"), nullable=False)
    object_id = db.Column(db.Integer, nullable=False)  # ID de l'animation
    tag_name = db.Column(db.String(100), nullable=False)  # Nom du tag à surveiller
    operator = db.Column(db.String(3), nullable=False)   # '=', '!=', '>', '<', '>=', '<='
    target_value = db.Column(db.String(50), nullable=False)  # Valeur à comparer
    color = db.Column(db.String(7), nullable=False)      # Couleur à appliquer (#RRGGBB)
    priorite = db.Column(db.Integer, default=1)          # Priorité (1 = plus haute)
    actif = db.Column(db.Boolean, default=True)
    date_creation = db.Column(db.DateTime, default=datetime.utcnow)
    date_modification = db.Column(db.DateTime, default=datetime.utcnow)

    def __init__(self, **kwargs):
        self.nom_regle = kwargs.get('nom_regle')
        self.id_projet = kwargs.get('id_projet')
        self.object_id = kwargs.get('object_id')
        self.tag_name = kwargs.get('tag_name')
        self.operator = kwargs.get('operator', '=')
        self.target_value = str(kwargs.get('target_value', ''))
        self.color = kwargs.get('color', '#ff0000')
        self.priorite = kwargs.get('priorite', 1)
        self.actif = kwargs.get('actif', True)
        self.date_creation = datetime.utcnow()
        self.date_modification = datetime.utcnow()

    def to_dict(self):
        return {
            "id": self.id_color_rule,
            "nom_regle": self.nom_regle,
            "id_projet": self.id_projet,
            "object_id": self.object_id,
            "tag_name": self.tag_name,
            "operator": self.operator,
            "target_value": self.target_value,
            "color": self.color,
            "priorite": self.priorite,
            "actif": self.actif,
            "date_creation": self.date_creation.strftime("%Y-%m-%d %H:%M:%S"),
            "date_modification": self.date_modification.strftime("%Y-%m-%d %H:%M:%S")
        }

    def test_condition(self, tag_value):
        """Teste si la condition de la règle est remplie"""
        if not self.actif:
            return False
            
        try:
            # Conversion automatique des types
            rule_value = self._convert_value(self.target_value)
            test_value = self._convert_value(tag_value)
            
            # Application de l'opérateur
            operators_map = {
                '=': lambda x, y: x == y,
                '==': lambda x, y: x == y,
                '!=': lambda x, y: x != y,
                '>': lambda x, y: x > y,
                '<': lambda x, y: x < y,
                '>=': lambda x, y: x >= y,
                '<=': lambda x, y: x <= y
            }
            
            if self.operator in operators_map:
                result = operators_map[self.operator](test_value, rule_value)
                print(f"🔍 Test règle '{self.nom_regle}': {test_value} {self.operator} {rule_value} = {result}")
                return result
            else:
                print(f"❌ Opérateur invalide: {self.operator}")
                return False
                
        except Exception as e:
            print(f"❌ Erreur test condition règle {self.nom_regle}: {e}")
            return False

    def _convert_value(self, value):
        """Convertit intelligemment une valeur pour la comparaison"""
        if value is None:
            return None
            
        # Convertir en string d'abord
        str_value = str(value).strip().lower()
        
        # Booléens
        if str_value in ['true', '1', 'on', 'yes']:
            return True
        elif str_value in ['false', '0', 'off', 'no']:
            return False
        
        # Nombres
        try:
            # Essayer d'abord un entier
            if '.' not in str_value:
                return int(str_value)
            else:
                return float(str_value)
        except ValueError:
            # Retourner la chaîne originale si pas de conversion possible
            return str(value)

    @classmethod
    def get_rules_for_object(cls, object_id, project_id=None):
        """Récupère toutes les règles actives pour un objet, triées par priorité"""
        query = cls.query.filter_by(object_id=object_id, actif=True)
        
        if project_id:
            query = query.filter_by(id_projet=project_id)
            
        return query.order_by(cls.priorite.asc(), cls.date_creation.asc()).all()

    @classmethod
    def apply_rules_to_object(cls, animation, tag_value, project_id=None):
        """Applique les règles à un objet et retourne la couleur finale"""
        rules = cls.get_rules_for_object(animation.id_animation, project_id)
        
        if not rules:
            return animation.couleur_normale  # Couleur par défaut
        
        # Vérifier chaque règle par ordre de priorité
        for rule in rules:
            # Vérifier que le tag correspond
            if rule.tag_name.strip() != animation.tag_lie.strip():
                continue
                
            # Tester la condition
            if rule.test_condition(tag_value):
                print(f"✅ Règle appliquée: {rule.nom_regle} -> couleur {rule.color}")
                return rule.color
        
        # Aucune règle ne s'applique, retourner la couleur normale
        return animation.couleur_normale    


# =================================================================
# FONCTION D'APPLICATION DES RÈGLES CORRIGÉE
# =================================================================
def apply_color_rules_batch(animations_with_values, project_id=None):
    """
    Applique les règles de couleur à un lot d'animations
    animations_with_values: liste de tuples (animation, tag_value)
    Retourne: dict {animation_id: couleur_finale}
    """
    result = {}
    
    for animation, tag_value in animations_with_values:
        try:
            final_color = ColorRule.apply_rules_to_object(animation, tag_value, project_id)
            result[animation.id_animation] = final_color
            
            # Log si couleur changée
            if final_color != animation.couleur_normale:
                print(f"🎨 Couleur dynamique: {animation.nom_animation} {animation.couleur_normale} -> {final_color}")
                
        except Exception as e:
            print(f"⚠ Erreur application règle pour {animation.nom_animation}: {e}")
            result[animation.id_animation] = animation.couleur_normale
    
    return result


