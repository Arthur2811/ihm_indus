from app import db
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
import bcrypt
import secrets
import re

class UserManagement:
    """Classe utilitaire pour la gestion des utilisateurs"""
    
    # =================================================================
    #  USER1: AJOUTER UTILISATEUR
    # =================================================================
    
    @staticmethod
    def create_user(user_data):
        """USER1: Créer un nouvel utilisateur"""
        try:
            from app.models.modele_tag import Utilisateur
            
            # Validation des données avant création
            valid, errors = UserManagement.validate_user_data(user_data)
            if not valid:
                return False, f"Données invalides: {', '.join(errors)}"
            
            # Vérifier l'unicité de l'identifiant
            existing_user = Utilisateur.query.filter_by(
                identifiant_utilisateur=user_data['identifiant_utilisateur']
            ).first()
            
            if existing_user:
                return False, "Identifiant utilisateur déjà existant"
            
            # Vérifier l'unicité de l'email si fourni
            if user_data.get('email_utilisateur'):
                existing_email = Utilisateur.query.filter_by(
                    email_utilisateur=user_data['email_utilisateur']
                ).first()
                
                if existing_email:
                    return False, "Email déjà utilisé"
            
            # Vérifier que le rôle existe
            role_exists = UserManagement._validate_role_exists(user_data['id_role'])
            if not role_exists:
                return False, "Rôle spécifié inexistant"
            
            # Hasher le mot de passe de manière sécurisée
            try:
                hashed_password = UserManagement._hash_password_secure(user_data['mot_de_passe'])
            except Exception as e:
                return False, f"Erreur sécurisation mot de passe: {str(e)}"
            
            # Créer l'utilisateur
            nouvel_utilisateur = Utilisateur(
                identifiant_utilisateur=user_data['identifiant_utilisateur'],
                mot_de_passe=hashed_password,
                nom_utilisateur=user_data['nom_utilisateur'],
                prenom_utilisateur=user_data['prenom_utilisateur'],
                email_utilisateur=user_data.get('email_utilisateur'),
                telephone_utilisateur=user_data.get('telephone_utilisateur'),
                date_creation_utilisateur=datetime.utcnow(),
                actif=user_data.get('actif', True),
                id_role=user_data['id_role']
            )
            
            db.session.add(nouvel_utilisateur)
            db.session.commit()
            
            # Log de l'action pour audit
            UserManagement._log_user_action(
                user_id=nouvel_utilisateur.id_utilisateur,
                action="CREATE_USER",
                details=f"Utilisateur {user_data['identifiant_utilisateur']} créé"
            )
            
            return True, f"Utilisateur '{user_data['identifiant_utilisateur']}' créé avec succès"
            
        except Exception as e:
            db.session.rollback()
            print(f"Erreur création utilisateur: {e}")
            return False, f"Erreur système lors de la création: {str(e)}"
    
    # =================================================================
    # USER2: SUPPRIMER UTILISATEUR
    # =================================================================
    
    @staticmethod
    def delete_user(user_id):
        """USER2: Supprimer un utilisateur"""
        try:
            from app.models.modele_tag import Utilisateur, SessionUtilisateur
            
            # Vérifier que l'utilisateur existe
            user = Utilisateur.query.get(user_id)
            if not user:
                return False, "Utilisateur non trouvé"
            
            # Sauvegarder l'identifiant pour le log
            user_identifier = user.identifiant_utilisateur
            
            # Vérifier qu'il ne s'agit pas du dernier administrateur
            if UserManagement._is_last_admin(user_id):
                return False, "Impossible de supprimer le dernier administrateur du système"
            
            # Supprimer d'abord les sessions associées (contrainte FK)
            try:
                SessionUtilisateur.query.filter_by(id_utilisateur=user_id).delete()
                db.session.flush()  # Force la suppression avant de continuer
            except Exception as e:
                print(f"Erreur suppression sessions: {e}")
                # Continuer même si erreur sessions (peut ne pas exister)
            
            # Supprimer l'utilisateur
            db.session.delete(user)
            db.session.commit()
            
            # Log de l'action pour audit
            UserManagement._log_user_action(
                user_id=user_id,
                action="DELETE_USER",
                details=f"Utilisateur {user_identifier} supprimé"
            )
            
            return True, f"Utilisateur '{user_identifier}' supprimé avec succès"
            
        except Exception as e:
            db.session.rollback()
            print(f"Erreur suppression utilisateur: {e}")
            return False, f"Erreur système lors de la suppression: {str(e)}"
    
    # =================================================================
    # USER3: ATTRIBUER RÔLES
    # =================================================================
    
    @staticmethod
    def assign_role(user_id, new_role_id):
        """USER3: Attribuer un rôle à un utilisateur"""
        try:
            from app.models.modele_tag import Utilisateur, Role
            
            # Vérifier que l'utilisateur existe
            user = Utilisateur.query.get(user_id)
            if not user:
                return False, "Utilisateur non trouvé"
            
            # Vérifier que le rôle existe
            role = Role.query.get(new_role_id)
            if not role:
                return False, "Rôle non trouvé"
            
            # Sauvegarder l'ancien rôle pour le log
            old_role = Role.query.get(user.id_role)
            old_role_name = old_role.nom_role if old_role else "Aucun"
            
            # Vérifier qu'on ne retire pas le rôle admin du dernier admin
            if old_role and old_role.nom_role == 'ADMIN' and UserManagement._is_last_admin(user_id):
                return False, "Impossible de retirer le rôle administrateur du dernier admin"
            
            # Attribuer le nouveau rôle
            user.id_role = new_role_id
            db.session.commit()
            
            # Log de l'action pour audit
            UserManagement._log_user_action(
                user_id=user_id,
                action="CHANGE_ROLE",
                details=f"Rôle changé de {old_role_name} vers {role.nom_role} pour {user.identifiant_utilisateur}"
            )
            
            return True, f"Rôle '{role.nom_role}' attribué à '{user.identifiant_utilisateur}' avec succès"
            
        except Exception as e:
            db.session.rollback()
            print(f"Erreur attribution rôle: {e}")
            return False, f"Erreur système lors de l'attribution: {str(e)}"
    
    @staticmethod
    def update_user(user_id, user_data):
        """Met à jour un utilisateur (extension USER1)"""
        try:
            from app.models.modele_tag import Utilisateur
            
            user = Utilisateur.query.get(user_id)
            if not user:
                return False, "Utilisateur non trouvé"
            
            # Sauvegarder les données originales pour le log
            original_data = {
                'identifiant': user.identifiant_utilisateur,
                'email': user.email_utilisateur
            }
            
            # Vérifier l'unicité de l'identifiant si modifié
            if 'identifiant_utilisateur' in user_data and user_data['identifiant_utilisateur'] != user.identifiant_utilisateur:
                existing_user = Utilisateur.query.filter_by(
                    identifiant_utilisateur=user_data['identifiant_utilisateur']
                ).first()
                
                if existing_user:
                    return False, "Identifiant utilisateur déjà existant"
            
            # Vérifier l'unicité de l'email si modifié
            if 'email_utilisateur' in user_data and user_data['email_utilisateur'] != user.email_utilisateur:
                if user_data['email_utilisateur']:  # Si email non vide
                    existing_email = Utilisateur.query.filter_by(
                        email_utilisateur=user_data['email_utilisateur']
                    ).first()
                    
                    if existing_email:
                        return False, "Email déjà utilisé"
            
            # Préparer les changements pour le log
            changes = []
            
            # Mettre à jour les champs
            for field, value in user_data.items():
                if field == 'mot_de_passe' and value:
                    # Hasher le nouveau mot de passe de manière sécurisée
                    try:
                        value = UserManagement._hash_password_secure(value)
                        changes.append("mot de passe modifié")
                    except Exception as e:
                        return False, f"Erreur sécurisation mot de passe: {str(e)}"
                
                if hasattr(user, field):
                    old_value = getattr(user, field)
                    if old_value != value:
                        if field != 'mot_de_passe':  # Ne pas logger les mots de passe
                            changes.append(f"{field}: {old_value} → {value}")
                        setattr(user, field, value)
            
            db.session.commit()
            
            # Log de l'action pour audit
            UserManagement._log_user_action(
                user_id=user_id,
                action="UPDATE_USER",
                details=f"Utilisateur {original_data['identifiant']} modifié: {', '.join(changes)}"
            )
            
            return True, f"Utilisateur '{user.identifiant_utilisateur}' modifié avec succès"
            
        except Exception as e:
            db.session.rollback()
            print(f"Erreur modification utilisateur: {e}")
            return False, f"Erreur système lors de la modification: {str(e)}"
    
    @staticmethod
    def get_all_users():
        """Récupère tous les utilisateurs avec leurs rôles"""
        try:
            from app.models.modele_tag import Utilisateur, Role
            users = db.session.query(Utilisateur, Role).join(
                Role, Utilisateur.id_role == Role.id_role
            ).order_by(Utilisateur.nom_utilisateur, Utilisateur.prenom_utilisateur).all()
            
            users_list = []
            for user, role in users:
                users_list.append({
                    'id_utilisateur': user.id_utilisateur,
                    'identifiant_utilisateur': user.identifiant_utilisateur,
                    'nom_utilisateur': user.nom_utilisateur,
                    'prenom_utilisateur': user.prenom_utilisateur,
                    'email_utilisateur': user.email_utilisateur,
                    'telephone_utilisateur': user.telephone_utilisateur,
                    'date_creation_utilisateur': user.date_creation_utilisateur,
                    'derniere_connexion': user.derniere_connexion,
                    'actif': user.actif,
                    'role_nom': role.nom_role,
                    'role_niveau': role.niveau_role,
                    'id_role': role.id_role
                })
            
            return users_list
        except Exception as e:
            print(f"Erreur récupération utilisateurs: {e}")
            return []
    
    @staticmethod
    def get_all_roles():
        """Récupère tous les rôles disponibles (pour USE CASE USER3)"""
        try:
            from app.models.modele_tag import Role
            roles = Role.query.order_by(Role.niveau_role.desc()).all()
            return [{
                'id_role': role.id_role,
                'nom_role': role.nom_role,
                'niveau_role': role.niveau_role
            } for role in roles]
        except Exception as e:
            print(f"Erreur récupération rôles: {e}")
            return []
    
    @staticmethod
    def get_user_by_id(user_id):
        """Récupère un utilisateur spécifique par son ID"""
        try:
            from app.models.modele_tag import Utilisateur, Role
            
            user_with_role = db.session.query(Utilisateur, Role).join(
                Role, Utilisateur.id_role == Role.id_role
            ).filter(Utilisateur.id_utilisateur == user_id).first()
            
            if not user_with_role:
                return None
            
            user_obj, role_obj = user_with_role
            
            return {
                'id_utilisateur': user_obj.id_utilisateur,
                'identifiant_utilisateur': user_obj.identifiant_utilisateur,
                'nom_utilisateur': user_obj.nom_utilisateur,
                'prenom_utilisateur': user_obj.prenom_utilisateur,
                'email_utilisateur': user_obj.email_utilisateur,
                'telephone_utilisateur': user_obj.telephone_utilisateur,
                'date_creation_utilisateur': user_obj.date_creation_utilisateur.isoformat() if user_obj.date_creation_utilisateur else None,
                'derniere_connexion': user_obj.derniere_connexion.isoformat() if user_obj.derniere_connexion else None,
                'actif': user_obj.actif,
                'role_nom': role_obj.nom_role,
                'role_niveau': role_obj.niveau_role,
                'id_role': role_obj.id_role
            }
            
        except Exception as e:
            print(f"Erreur récupération utilisateur {user_id}: {e}")
            return None
    
    # =================================================================
    # MÉTHODES UTILITAIRES ET SÉCURITÉ
    # =================================================================
    
    @staticmethod
    def _hash_password_secure(password):
        """Hash sécurisé du mot de passe avec bcrypt uniquement"""
        try:
            if not password or len(password.strip()) == 0:
                raise ValueError("Mot de passe vide")
            
            # Configuration bcrypt sécurisée pour production
            rounds = 12  # Coût computationnel élevé
            salt = bcrypt.gensalt(rounds=rounds)
            hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
            return hashed.decode('utf-8')
            
        except Exception as e:
            # Ne jamais utiliser de fallback non sécurisé
            raise Exception(f"Erreur critique hashage mot de passe: {e}")
    
    @staticmethod
    def verify_password(password, hashed_password):
        """Vérifie un mot de passe contre son hash"""
        try:
            return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))
        except Exception as e:
            print(f"Erreur vérification mot de passe: {e}")
            return False
    
    @staticmethod
    def validate_user_data(user_data, is_update=False):
        """Validation complète des données utilisateur"""
        errors = []
        
        # Champs obligatoires pour création
        if not is_update:
            required_fields = ['identifiant_utilisateur', 'mot_de_passe', 'nom_utilisateur', 'prenom_utilisateur', 'id_role']
            for field in required_fields:
                if not user_data.get(field) or str(user_data.get(field)).strip() == '':
                    errors.append(f"Le champ {field} est obligatoire")
        
        # Validation identifiant
        if 'identifiant_utilisateur' in user_data and user_data['identifiant_utilisateur']:
            identifiant = str(user_data['identifiant_utilisateur']).strip()
            if len(identifiant) < 3:
                errors.append("L'identifiant doit faire au moins 3 caractères")
            if len(identifiant) > 50:
                errors.append("L'identifiant ne peut dépasser 50 caractères")
            if not re.match(r'^[a-zA-Z0-9_-]+$', identifiant):
                errors.append("L'identifiant ne peut contenir que des lettres, chiffres, _ et -")
        
        # Validation mot de passe
        if 'mot_de_passe' in user_data and user_data['mot_de_passe']:
            password = user_data['mot_de_passe']
            if len(password) < 6:
                errors.append("Le mot de passe doit faire au moins 6 caractères")
            if len(password) > 255:
                errors.append("Le mot de passe ne peut dépasser 255 caractères")
        
        # Validation nom et prénom
        for field in ['nom_utilisateur', 'prenom_utilisateur']:
            if field in user_data and user_data[field]:
                value = str(user_data[field]).strip()
                if len(value) < 2:
                    errors.append(f"Le {field} doit faire au moins 2 caractères")
                if len(value) > 50:
                    errors.append(f"Le {field} ne peut dépasser 50 caractères")
                if not re.match(r'^[a-zA-ZÀ-ÿ\s\'-]+$', value):
                    errors.append(f"Le {field} contient des caractères invalides")
        
        # Validation email
        if 'email_utilisateur' in user_data and user_data['email_utilisateur']:
            email = str(user_data['email_utilisateur']).strip()
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, email):
                errors.append("Format d'email invalide")
            if len(email) > 100:
                errors.append("L'email ne peut dépasser 100 caractères")
        
        # Validation téléphone
        if 'telephone_utilisateur' in user_data and user_data['telephone_utilisateur']:
            telephone = str(user_data['telephone_utilisateur']).strip().replace(' ', '').replace('-', '').replace('.', '').replace('+', '')
            if not telephone.isdigit():
                errors.append("Le téléphone ne peut contenir que des chiffres, espaces, - et .")
            if len(telephone) < 8 or len(telephone) > 15:
                errors.append("Le téléphone doit contenir entre 8 et 15 chiffres")
        
        return len(errors) == 0, errors
    
    @staticmethod
    def _validate_role_exists(role_id):
        """Vérifie qu'un rôle existe"""
        try:
            from app.models.modele_tag import Role
            return Role.query.get(role_id) is not None
        except Exception:
            return False
    
    @staticmethod
    def _is_last_admin(user_id):
        """Vérifie si c'est le dernier administrateur"""
        try:
            from app.models.modele_tag import Utilisateur, Role
            
            # Récupérer le rôle admin
            admin_role = Role.query.filter_by(nom_role='ADMIN').first()
            if not admin_role:
                return False
            
            # Compter les admins actifs
            admin_count = Utilisateur.query.filter_by(
                id_role=admin_role.id_role,
                actif=True
            ).count()
            
            # Si c'est le seul admin, empêcher la suppression/modification
            return admin_count <= 1
            
        except Exception as e:
            print(f"Erreur vérification dernier admin: {e}")
            return True  # Par sécurité, on bloque
    
    @staticmethod
    def _log_user_action(user_id, action, details):
        """Log simple des actions pour audit (version basique)"""
        try:
            timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[USER_AUDIT] {timestamp} - User {user_id} - {action} - {details}")
            # TODO: Implémenter en base si table d'audit créée
        except Exception as e:
            print(f"Erreur log audit: {e}")
    
    # =================================================================
    # MÉTHODES D'INITIALISATION
    # =================================================================
    
    @staticmethod
    def create_default_roles():
        """Crée les rôles par défaut"""
        try:
            from app.models.modele_tag import Role
            
            # Rôles : ADMIN, AUTO (Automaticien), OP (Opérateur)
            default_roles = [
                {'nom_role': 'ADMIN', 'niveau_role': 3},  # Gestion utilisateurs uniquement
                {'nom_role': 'AUTO', 'niveau_role': 2},   # Configuration technique complète
                {'nom_role': 'OP', 'niveau_role': 1}      # Consultation uniquement
            ]
            
            for role_data in default_roles:
                existing_role = Role.query.filter_by(nom_role=role_data['nom_role']).first()
                if not existing_role:
                    new_role = Role(
                        nom_role=role_data['nom_role'],
                        niveau_role=role_data['niveau_role']
                    )
                    db.session.add(new_role)
            
            db.session.commit()
            print("✅ Rôles par défaut créés selon Use Case")
            
        except Exception as e:
            db.session.rollback()
            print(f"Erreur création rôles par défaut: {e}")
    
    @staticmethod
    def create_default_admin():
        """Crée un administrateur par défaut"""
        try:
            from app.models.modele_tag import Utilisateur, Role
            
            # Vérifier si un admin existe déjà 
            admin_role = Role.query.filter_by(nom_role='ADMIN').first()
            if not admin_role:
                return False, "Rôle ADMIN non trouvé"
            
            existing_admin = Utilisateur.query.filter_by(id_role=admin_role.id_role).first()
            if existing_admin:
                return True, "Admin par défaut déjà existant"
            
            # Créer l'admin par défaut
            admin_data = {
                'identifiant_utilisateur': 'admin',
                'mot_de_passe': 'admin123',  # À changer en production !
                'nom_utilisateur': 'Administrateur',
                'prenom_utilisateur': 'Système',
                'email_utilisateur': 'admin@ihm-industrielle.local',
                'id_role': admin_role.id_role,
                'actif': True
            }
            
            success, message = UserManagement.create_user(admin_data)
            if success:
                print("✅ Administrateur par défaut créé (admin/admin123)")
                return True, "Administrateur par défaut créé"
            else:
                return False, message
                
        except Exception as e:
            print(f"Erreur création admin par défaut: {e}")
            return False, f"Erreur: {str(e)}"
    
    @staticmethod
    def get_user_stats():
        """Récupère les statistiques des utilisateurs"""
        try:
            from app.models.modele_tag import Utilisateur, Role
            
            total_users = Utilisateur.query.count()
            active_users = Utilisateur.query.filter_by(actif=True).count()
            
            # Statistiques par rôle
            role_stats = db.session.query(
                Role.nom_role,
                db.func.count(Utilisateur.id_utilisateur).label('count')
            ).join(
                Utilisateur, Role.id_role == Utilisateur.id_role
            ).group_by(Role.nom_role).all()
            
            role_stats_dict = {role: count for role, count in role_stats}
            
            return {
                'total_users': total_users,
                'active_users': active_users,
                'inactive_users': total_users - active_users,
                'role_stats': role_stats_dict
            }
            
        except Exception as e:
            print(f"Erreur récupération statistiques: {e}")
            return {
                'total_users': 0,
                'active_users': 0,
                'inactive_users': 0,
                'role_stats': {}
            }