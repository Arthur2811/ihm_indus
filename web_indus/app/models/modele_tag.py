from app import db
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, DECIMAL
from sqlalchemy.orm import relationship
import re

class Tag(db.Model):
    """Modèle Tag selon le schéma existant"""
    
    __tablename__ = 'Tag'
    
    # Structure selon le schéma
    id_tag = Column(Integer, primary_key=True, autoincrement=True)
    nom_tag = Column(String(100), nullable=False)
    type_donnee = Column(String(20), nullable=False)
    description_tag = Column(Text)
    acces = Column(String(10))
    valeur = Column(String(50))  # Valeur actuelle du tag
    alarmes_actives = Column(Boolean)
    historisation_active = Column(Boolean)
    disponibilite_externe = Column(Boolean)
    id_projet = Column(Integer, ForeignKey('HMI_Project.id_projet'))
    
    # Variables internes pour la compatibilité (non stockées en BDD)
    _qualite_temp = 'UNKNOWN'
    _timestamp_temp = None
    
    def __init__(self, nom_tag, type_donnee, adresse_tag=None, **kwargs):
        """Initialisation du tag"""
        self.nom_tag = nom_tag
        self.type_donnee = type_donnee
        
        # Paramètres optionnels selon votre schéma
        self.description_tag = kwargs.get('description_tag', '')
        self.acces = kwargs.get('acces', 'R')
        self.alarmes_actives = kwargs.get('alarmes_actives', False)
        self.historisation_active = kwargs.get('historisation_active', False)
        self.disponibilite_externe = kwargs.get('disponibilite_externe', True)
        self.id_projet = kwargs.get('id_projet', None)
        self.valeur = kwargs.get('valeur', None)
        
        # Si une adresse est fournie, créer le mapping
        if adresse_tag:
            self._creer_mapping_communication(adresse_tag)
    
    def _creer_mapping_communication(self, adresse):
        """Crée ou met à jour le mapping de communication"""
        try:
            # Chercher un mapping existant
            mapping = MappingCom.query.filter_by(nom_du_tag=self.nom_tag).first()
            
            if mapping:
                mapping.adresse = adresse
            else:
                nouveau_mapping = MappingCom(
                    nom_du_tag=self.nom_tag,
                    adresse=adresse
                )
                db.session.add(nouveau_mapping)
        except Exception as e:
            print(f"Erreur création mapping: {e}")
    
    # ================================================================= 
    # PROPRIÉTÉS POUR COMPATIBILITÉ AVEC LE CONTRÔLEUR
    # =================================================================
    
    @property
    def adresse_tag(self):
        """Récupère l'adresse depuis la table Mapping_Com"""
        try:
            mapping = MappingCom.query.filter_by(nom_du_tag=self.nom_tag).first()
            if mapping:
                return mapping.adresse
            return "DB1.DBX0.0"  # Adresse par défaut
        except:
            return "DB1.DBX0.0"
    
    @adresse_tag.setter
    def adresse_tag(self, value):
        """Définit l'adresse dans la table Mapping_Com"""
        self._creer_mapping_communication(value)
    
    @property
    def valeur_courante(self):
        """Compatibilité - retourne la valeur actuelle"""
        return self.valeur
    
    @valeur_courante.setter
    def valeur_courante(self, value):
        """Compatibilité - définit la valeur actuelle"""
        self.valeur = str(value) if value is not None else None
    
    @property
    def qualite(self):
        """Retourne la qualité temporaire du tag"""
        return self._qualite_temp
    
    @qualite.setter
    def qualite(self, value):
        """Définit la qualité temporaire du tag"""
        self._qualite_temp = value
    
    @property
    def timestamp_lecture(self):
        """Retourne le timestamp temporaire de lecture"""
        return self._timestamp_temp
    
    @timestamp_lecture.setter
    def timestamp_lecture(self, value):
        """Définit le timestamp temporaire de lecture"""
        self._timestamp_temp = value
    
    @property
    def actif(self):
        """Compatibilité - considère le tag comme actif s'il est disponible"""
        return bool(self.disponibilite_externe)
    
    @property
    def db_number(self):
        """Extrait le numéro de DB de l'adresse"""
        try:
            adresse = self.adresse_tag
            match = re.search(r'DB(\d+)', adresse)
            return int(match.group(1)) if match else 1
        except:
            return 1
    
    @property
    def offset_address(self):
        """Extrait l'offset de l'adresse"""
        try:
            adresse = self.adresse_tag
            pattern = r'DB\d+\.DB[XWD](.+)'
            match = re.search(pattern, adresse)
            return match.group(1) if match else "0.0"
        except:
            return "0.0"
    
    @property
    def data_size(self):
        """Calcule la taille des données selon le type"""
        if self.type_donnee == 'BOOL':
            return 1
        elif self.type_donnee == 'INT':
            return 2
        elif self.type_donnee in ['DINT', 'REAL']:
            return 4
        return 1
    
    # =================================================================
    # MÉTHODES POUR COMPATIBILITÉ AVEC LE CONTRÔLEUR
    # =================================================================
    
    def to_dict(self):
        """Conversion en dictionnaire pour API"""
        return {
            'id_tag': self.id_tag,
            'nom_tag': self.nom_tag,
            'adresse_tag': self.adresse_tag,
            'type_donnee': self.type_donnee,
            'description_tag': self.description_tag,
            'acces': self.acces,
            'valeur_courante': self.valeur,
            'valeur_typee': self.valeur_typee(),
            'qualite': self.qualite,
            'timestamp_lecture': self.timestamp_lecture.isoformat() if self.timestamp_lecture else None,
            'historisation_active': self.historisation_active,
            'alarmes_actives': self.alarmes_actives,
            'disponibilite_externe': self.disponibilite_externe,
            'actif': self.actif,
            'id_projet': self.id_projet,
            'db_number': self.db_number,
            'offset_address': self.offset_address,
            'data_size': self.data_size
        }
    
    def mettre_a_jour_valeur(self, nouvelle_valeur, qualite='GOOD'):
        """Met à jour la valeur du tag"""
        self.valeur = str(nouvelle_valeur) if nouvelle_valeur is not None else None
        self.qualite = qualite
        self.timestamp_lecture = datetime.utcnow()
        
        # Historiser si activé
        if self.historisation_active:
            self._ajouter_historique(nouvelle_valeur, qualite)
    
    def _ajouter_historique(self, valeur, qualite):
        """Ajoute une entrée dans l'historique selon votre schéma"""
        try:
            # Créer l'entrée d'historique
            historique = HistoriqueTag(
                valeur_historique=str(valeur),
                timestamp_hist=datetime.utcnow(),
                qualite_hist=qualite,
                type_changement='LECTURE_AUTO'
            )
            db.session.add(historique)
            db.session.flush()  # Pour obtenir l'ID
            
            # Créer la relation dans la table de liaison
            relation = Historiser(
                id_tag=self.id_tag,
                id_historique=historique.id_historique
            )
            db.session.add(relation)
            
        except Exception as e:
            print(f"Erreur historisation: {e}")
    
    def valeur_typee(self):
        """Retourne la valeur convertie selon le type"""
        if not self.valeur:
            return None
            
        try:
            if self.type_donnee == 'BOOL':
                return self.valeur.lower() in ['true', '1', 'on', 'yes']
            elif self.type_donnee == 'INT':
                val = int(self.valeur)
                return val if -32768 <= val <= 32767 else None
            elif self.type_donnee == 'DINT':
                val = int(self.valeur)
                return val if -2147483648 <= val <= 2147483647 else None
            elif self.type_donnee == 'REAL':
                return float(self.valeur)
            else:
                return self.valeur
        except (ValueError, AttributeError):
            return None
    
    def est_accessible_en_ecriture(self):
        """Vérifie si le tag est accessible en écriture"""
        return self.acces in ['W', 'RW']
    
    def est_accessible_en_lecture(self):
        """Vérifie si le tag est accessible en lecture"""
        return self.acces in ['R', 'RW']
    
    def valider_valeur(self, valeur):
        """Valide une valeur avant écriture"""
        try:
            if self.type_donnee == 'BOOL':
                if isinstance(valeur, str):
                    valeur_convertie = valeur.lower() in ['true', '1', 'on', 'yes']
                else:
                    valeur_convertie = bool(valeur)
                return True, valeur_convertie, "Valeur BOOL valide"
            
            elif self.type_donnee == 'INT':
                valeur_convertie = int(valeur)
                if valeur_convertie < -32768 or valeur_convertie > 32767:
                    return False, None, "Valeur INT hors limites (-32768 à 32767)"
                return True, valeur_convertie, "Valeur INT valide"
            
            elif self.type_donnee == 'DINT':
                valeur_convertie = int(valeur)
                if valeur_convertie < -2147483648 or valeur_convertie > 2147483647:
                    return False, None, "Valeur DINT hors limites"
                return True, valeur_convertie, "Valeur DINT valide"
            
            elif self.type_donnee == 'REAL':
                valeur_convertie = float(valeur)
                return True, valeur_convertie, "Valeur REAL valide"
            
            else:
                return True, str(valeur), "Valeur STRING valide"
                
        except (ValueError, TypeError) as e:
            return False, None, f"Erreur conversion: {str(e)}"
    
    def get_adresse_components(self):
        """Retourne les composants de l'adresse S7"""
        adresse = self.adresse_tag
        components = {
            'adresse_complete': adresse,
            'type': self.type_donnee
        }
        
        try:
            # Parse l'adresse S7
            pattern = r'DB(\d+)\.DB([XWD])(.+)'
            match = re.match(pattern, adresse)
            
            if match:
                components['db'] = int(match.group(1))
                type_access = match.group(2)
                offset_part = match.group(3)
                
                if type_access == 'X':  # Bit
                    if '.' in offset_part:
                        byte_part, bit_part = offset_part.split('.')
                        components['byte_offset'] = int(byte_part)
                        components['bit_offset'] = int(bit_part)
                elif type_access in ['W', 'D']:  # Word ou DWord
                    components['offset'] = int(offset_part)
            
        except Exception as e:
            print(f"Erreur parsing adresse {adresse}: {e}")
        
        return components
    
    # =================================================================
    # MÉTHODES STATIQUES POUR CRÉER LES TAGS PAR DÉFAUT
    # =================================================================
    
    @staticmethod
    def creer_tags_siemens_defaut():
        """Crée les tags Siemens par défaut dans votre BDD"""
        
        # D'abord, créer un projet par défaut si nécessaire
        projet = HMIProject.query.filter_by(actif_projet=True).first()
        if not projet:
            projet = HMIProject(
                nom_projet="IHM_Industrielle_Arthur",
                chemin_fichier="/projets/ihm_arthur",
                date_creation_projet=datetime.utcnow(),
                date_modification=datetime.utcnow(),
                version_projet="1.0",
                actif_projet=True
            )
            db.session.add(projet)
            db.session.commit()
        
        tags_siemens = [
            # DB1 - Static
            {
                'nom_tag': 'bp_marche',
                'type_donnee': 'BOOL',
                'adresse_tag': 'DB1.DBX0.0',
                'description_tag': 'Bouton poussoir marche',
                'acces': 'RW',
                'id_projet': projet.id_projet
            },
            {
                'nom_tag': 'bp_arret',
                'type_donnee': 'BOOL',
                'adresse_tag': 'DB1.DBX0.1',
                'description_tag': 'Bouton poussoir arrêt',
                'acces': 'RW',
                'id_projet': projet.id_projet
            },
            {
                'nom_tag': 'bp_rearmement',
                'type_donnee': 'BOOL',
                'adresse_tag': 'DB1.DBX0.2',
                'description_tag': 'Bouton poussoir réarmement',
                'acces': 'RW',
                'id_projet': projet.id_projet
            },
            {
                'nom_tag': 'ARU',
                'type_donnee': 'BOOL',
                'adresse_tag': 'DB1.DBX0.3',
                'description_tag': 'Arrêt d\'urgence',
                'acces': 'R',
                'id_projet': projet.id_projet
            },
            {
                'nom_tag': 'quantite_produit',
                'type_donnee': 'INT',
                'adresse_tag': 'DB1.DBW2',
                'description_tag': 'Quantité de produit',
                'acces': 'RW',
                'id_projet': projet.id_projet
            },
            {
                'nom_tag': 'TestInt',
                'type_donnee': 'INT',
                'adresse_tag': 'DB1.DBW4',
                'description_tag': 'Entier de test',
                'acces': 'RW',
                'id_projet': projet.id_projet
            },
            
            # DB2 - lec_ecr_ihm_indus
            {
                'nom_tag': 'bit_de_vie',
                'type_donnee': 'BOOL',
                'adresse_tag': 'DB2.DBX0.0',
                'description_tag': 'Bit de vie IHM',
                'acces': 'R',
                'id_projet': projet.id_projet
            },
            {
                'nom_tag': 'temp_de_prod',
                'type_donnee': 'BOOL',
                'adresse_tag': 'DB2.DBX0.1',
                'description_tag': 'Temps de production',
                'acces': 'R',
                'id_projet': projet.id_projet
            },
            
            # DB3 - sorti_ihm_indus
            {
                'nom_tag': 'voyant_marche',
                'type_donnee': 'BOOL',
                'adresse_tag': 'DB3.DBX0.0',
                'description_tag': 'Voyant marche',
                'acces': 'R',
                'id_projet': projet.id_projet
            },
            {
                'nom_tag': 'voyant_arret',
                'type_donnee': 'BOOL',
                'adresse_tag': 'DB3.DBX0.1',
                'description_tag': 'Voyant arrêt',
                'acces': 'R',
                'id_projet': projet.id_projet
            },
            {
                'nom_tag': 'voyant_marche_1',
                'type_donnee': 'BOOL',
                'adresse_tag': 'DB3.DBX0.2',
                'description_tag': 'Voyant marche 1',
                'acces': 'R',
                'id_projet': projet.id_projet
            },
            {
                'nom_tag': 'marche_moteur',
                'type_donnee': 'BOOL',
                'adresse_tag': 'DB3.DBX0.3',
                'description_tag': 'Marche moteur',
                'acces': 'R',
                'id_projet': projet.id_projet
            }
        ]
        
        tags_crees = []
        for tag_data in tags_siemens:
            # Vérifier si le tag existe déjà
            tag_existant = Tag.query.filter_by(nom_tag=tag_data['nom_tag']).first()
            if not tag_existant:
                adresse = tag_data.pop('adresse_tag')  # Extraire l'adresse
                nouveau_tag = Tag(**tag_data)
                nouveau_tag.adresse_tag = adresse  # Utiliser le setter pour créer le mapping
                db.session.add(nouveau_tag)
                tags_crees.append(nouveau_tag)
        
        if tags_crees:
            db.session.commit()
            print(f"✅ {len(tags_crees)} tags Siemens créés")
        
        return tags_crees

# =================================================================
# MODÈLES COMPLÉMENTAIRES SELON LE SCHÉMA
# =================================================================

class MappingCom(db.Model):
    """Table Mapping_Com selon votre schéma existant"""
    __tablename__ = 'Mapping_Com'
    
    id_mapping_com = Column(Integer, primary_key=True, autoincrement=True)
    nom_du_tag = Column(String(100), nullable=False)
    adresse = Column(String(50), nullable=False)

class ConfigMappingCom(db.Model):
    """Table Config_Mapping_Com selon le schéma"""
    __tablename__ = 'Config_Mapping_Com'
    
    id_mapping_config_comm = Column(Integer, primary_key=True, autoincrement=True)
    description = Column(String(255))
    augmenter_priorite = Column(Boolean)
    trigger_lecture = Column(String(50))
    lecture_continue = Column(String(50))
    lecture_effectuee = Column(String(50))
    etat_lecture = Column(String(50))
    trigger_erreur = Column(String(50))
    autoriser_ecriture_continue = Column(String(50))
    ecriture_effectuee = Column(String(50))
    etat_ecriture = Column(String(50))
    station = Column(String(50))
    entete = Column(String(50))
    valeur_min = Column(Integer)
    valeur_max = Column(Integer)
    id_mapping_com = Column(Integer, ForeignKey('Mapping_Com.id_mapping_com'), nullable=False)

class HistoriqueTag(db.Model):
    """Table Historique_tag selon le schéma"""
    __tablename__ = 'Historique_tag'
    
    id_historique = Column(Integer, primary_key=True, autoincrement=True)
    valeur_historique = Column(String(100), nullable=False)
    timestamp_hist = Column(DateTime, nullable=False)
    qualite_hist = Column(String(10), nullable=False)
    type_changement = Column(String(20), nullable=False)

class Alarme(db.Model):
    """Table Alarme selon le schéma"""
    __tablename__ = 'Alarme'
    
    id_alarme = Column(Integer, primary_key=True, autoincrement=True)
    nom_du_tag = Column(String(100), nullable=False)
    type_alarme = Column(String(20), nullable=False)
    limite = Column(DECIMAL(10, 2))
    message = Column(String(255))
    priorite = Column(String(10))

class HMIProject(db.Model):
    """Table HMI_Project selon le schéma"""
    __tablename__ = 'HMI_Project'
    
    id_projet = Column(Integer, primary_key=True, autoincrement=True)
    nom_projet = Column(String(100), nullable=False)
    chemin_fichier = Column(String(255), nullable=False)
    date_creation_projet = Column(DateTime, nullable=False)
    date_modification = Column(DateTime, nullable=False)
    version_projet = Column(String(10), nullable=False)
    actif_projet = Column(Boolean, nullable=False)
    id_utilisateur = Column(Integer, ForeignKey('Utilisateur.id_utilisateur'))

class Role(db.Model):
    """Table Role selon le schéma"""
    __tablename__ = 'Role'
    
    id_role = Column(Integer, primary_key=True, autoincrement=True)
    nom_role = Column(String(30), nullable=False)
    niveau_role = Column(Integer, nullable=False)

class Utilisateur(db.Model):
    """Table Utilisateur selon le schéma"""
    __tablename__ = 'Utilisateur'
    
    id_utilisateur = Column(Integer, primary_key=True, autoincrement=True)
    identifiant_utilisateur = Column(String(50), nullable=False)
    mot_de_passe = Column(String(255), nullable=False)
    nom_utilisateur = Column(String(50), nullable=False)
    prenom_utilisateur = Column(String(50), nullable=False)
    email_utilisateur = Column(String(100))
    telephone_utilisateur = Column(String(15))
    date_creation_utilisateur = Column(DateTime, nullable=False)
    derniere_connexion = Column(DateTime)
    actif = Column(Boolean, nullable=False)
    id_role = Column(Integer, ForeignKey('Role.id_role'), nullable=False)

# Tables de liaison selon le schéma
class Historiser(db.Model):
    """Table de liaison HISTORISER selon le schéma"""
    __tablename__ = 'HISTORISER'
    
    id_tag = Column(Integer, ForeignKey('Tag.id_tag'), primary_key=True)
    id_historique = Column(Integer, ForeignKey('Historique_tag.id_historique'), primary_key=True)

class GererAlarme(db.Model):
    """Table de liaison GERER_ALARME selon le schéma"""
    __tablename__ = 'GERER_ALARME'
    
    id_tag = Column(Integer, ForeignKey('Tag.id_tag'), primary_key=True)
    id_alarme = Column(Integer, ForeignKey('Alarme.id_alarme'), primary_key=True)

class DefinirConfigCom(db.Model):
    """Table de liaison DEFINIR_CONFIG_COM selon le schéma"""
    __tablename__ = 'DEFINIR_CONFIG_COM'
    
    id_tag = Column(Integer, ForeignKey('Tag.id_tag'), primary_key=True)
    id_mapping_config_comm = Column(Integer, ForeignKey('Config_Mapping_Com.id_mapping_config_comm'), primary_key=True)

class SessionUtilisateur(db.Model):
    """Table Session_Utilisateur selon votre schéma existant"""
    __tablename__ = 'Session_Utilisateur'
    
    id_utilisateur_session = Column(Integer, primary_key=True, autoincrement=True)
    token_session = Column(String(50))
    adresse_ip = Column(String(15))
    user_agent = Column(String(500))
    date_debut_session = Column(DateTime, nullable=False)
    date_fin_session = Column(DateTime)
    duree_session = Column(Integer)
    actif_session = Column(Boolean, nullable=False)
    id_utilisateur = Column(Integer, ForeignKey('Utilisateur.id_utilisateur'), nullable=False)
    
    def __init__(self, **kwargs):
        self.token_session = kwargs.get('token_session')
        self.adresse_ip = kwargs.get('adresse_ip')
        self.user_agent = kwargs.get('user_agent')
        self.date_debut_session = kwargs.get('date_debut_session', datetime.utcnow())
        self.date_fin_session = kwargs.get('date_fin_session')
        self.duree_session = kwargs.get('duree_session')
        self.actif_session = kwargs.get('actif_session', True)
        self.id_utilisateur = kwargs.get('id_utilisateur')
    
    def calculer_duree(self):
        """Calcule la durée de la session en secondes"""
        if self.date_fin_session and self.date_debut_session:
            delta = self.date_fin_session - self.date_debut_session
            self.duree_session = int(delta.total_seconds())
        return self.duree_session
    
    def fermer_session(self):
        """Ferme la session"""
        self.actif_session = False
        self.date_fin_session = datetime.utcnow()
        self.calculer_duree()
    
    def to_dict(self):
        """Conversion en dictionnaire"""
        return {
            'id_utilisateur_session': self.id_utilisateur_session,
            'token_session': self.token_session,
            'adresse_ip': self.adresse_ip,
            'user_agent': self.user_agent,
            'date_debut_session': self.date_debut_session.isoformat() if self.date_debut_session else None,
            'date_fin_session': self.date_fin_session.isoformat() if self.date_fin_session else None,
            'duree_session': self.duree_session,
            'actif_session': self.actif_session,
            'id_utilisateur': self.id_utilisateur
        }