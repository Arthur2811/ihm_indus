import os
import socket
import subprocess
import ipaddress
from flask import render_template, request, jsonify, redirect, url_for, flash, current_app, session
from app.controleur import main_bp
from app.models.modele_tag import Tag
from app.models.modele_auth import AuthSystem
from app import db
import json
import time
import threading
from datetime import datetime

# Communication industrielle Siemens S7
try:
    import snap7
    SNAP7_AVAILABLE = True
except ImportError:
    SNAP7_AVAILABLE = False
    print("⚠️ snap7 non installé. Installation: pip install python-snap7")

class AutomateSiemensS7Complete:
    """Gestionnaire de communication S7 intégrant la logique de test_lect_ecr.py"""
    
    def __init__(self, app=None):
        self.client = None
        self.connected = False
        self.ip_address = ''
        self.rack = 0
        self.slot = 1
        self.simulation_mode = False
        self.simulation_data = {}
        self.derniere_lecture = {}
        self.app = app
        self.validation_ping = True
        
        if app is not None:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialisation avec le contexte Flask"""
        self.app = app
        
        with app.app_context():
            config_ip = app.config.get('AUTOMATE_IP')
            if config_ip and not self.ip_address:
                self.ip_address = config_ip
            
            self.rack = app.config.get('AUTOMATE_RACK', 0)
            self.slot = app.config.get('AUTOMATE_SLOT', 1)
            self.validation_ping = app.config.get('VALIDATION_PING', True)
            
            # CORRECTION: Respecter le mode configuré quand snap7 est disponible
            mode_config = app.config.get('MODE_COMMUNICATION', 'SIMULATEUR')
            
            if mode_config == 'REEL' and SNAP7_AVAILABLE:
                self.simulation_mode = False  # Mode réel si demandé et snap7 dispo
                print(f"🚀 Mode RÉEL activé - snap7 disponible")
            else:
                self.simulation_mode = True   # Simulation sinon
                print(f"🎮 Mode SIMULATION - snap7: {SNAP7_AVAILABLE}, config: {mode_config}")
            
            self._init_simulation_data()
    
    def connect(self, ip_address=None, rack=None, slot=None, force_simulation=False):
        """Connexion à l'automate Siemens S7"""
        if ip_address:
            self.ip_address = ip_address
        if rack is not None:
            self.rack = rack
        if slot is not None:
            self.slot = slot
        
        if not self.ip_address:
            return False, "❌ Veuillez saisir une adresse IP d'automate"
        
        print(f"🔍 Tentative de connexion S7 à {self.ip_address}...")
        
        # Mode simulation forcé
        if force_simulation or self.simulation_mode:
            self.connected = True
            self.simulation_mode = True
            return True, f"MODE SIMULATION - Connexion simulée S7 avec {self.ip_address}"
        
        # Validation IP
        ip_valide, message_ip = self.valider_ip(self.ip_address)
        if not ip_valide:
            return False, message_ip
        
        # Test de connectivité réseau
        if self.validation_ping:
            print(f"📡 Test ping vers {self.ip_address}...")
            if not self.ping_automate(self.ip_address):
                return False, f"❌ Ping échoué - {self.ip_address} non accessible"
        
        # Test du port S7
        print(f"🔌 Test port S7 (102) vers {self.ip_address}...")
        if not self.tester_port_s7(self.ip_address):
            return False, f"❌ Port S7 (102) fermé sur {self.ip_address}"
        
        # Connexion S7 réelle
        if not SNAP7_AVAILABLE:
            return False, "❌ Bibliothèque snap7 non disponible"
        
        try:
            print(f"🔗 Connexion S7 vers {self.ip_address}...")
            self.client = snap7.client.Client()
            self.client.connect(self.ip_address, self.rack, self.slot)
            
            if self.client.get_connected():
                # Test de lecture pour valider la connexion
                try:
                    test_data = self.client.db_read(1, 0, 1)
                    self.connected = True
                    self.simulation_mode = False
                    return True, f"✅ Connexion S7 RÉELLE établie avec {self.ip_address}"
                except Exception as e:
                    self.client.disconnect()
                    return False, f"❌ Connexion établie mais lecture impossible: {str(e)}"
            else:
                return False, f"❌ Impossible d'établir la connexion S7"
                
        except Exception as e:
            self.connected = False
            return False, f"❌ Erreur de connexion S7: {str(e)}"
    
    def disconnect(self):
        """Déconnexion de l'automate"""
        if not self.simulation_mode and self.client:
            try:
                self.client.disconnect()
                print("🔌 Déconnexion S7 effectuée")
            except Exception as e:
                print(f"Erreur déconnexion: {e}")
        
        self.connected = False
        return True, "Déconnecté de l'automate S7"
    
    def lire_bit(self, db, byte_offset, bit_offset):
        """Lit un bit dans un DB"""
        try:
            if self.simulation_mode:
                # Simulation
                adresse_sim = f"DB{db}.DBX{byte_offset}.{bit_offset}"
                return self.simulation_data.get(adresse_sim, False)
            
            # Lecture réelle
            data = self.client.db_read(db, byte_offset, 1)
            byte_val = data[0]
            return bool(byte_val & (1 << bit_offset))
        except Exception as e:
            print(f"Erreur lecture bit DB{db}.DBX{byte_offset}.{bit_offset}: {e}")
            return None
    
    def lire_word(self, db, word_offset):
        """Lit un word (16-bit) dans un DB"""
        try:
            if self.simulation_mode:
                # Simulation
                adresse_sim = f"DB{db}.DBW{word_offset}"
                return self.simulation_data.get(adresse_sim, 0)
            
            # Lecture réelle
            data = self.client.db_read(db, word_offset, 2)
            return int.from_bytes(data, byteorder='big', signed=True)
        except Exception as e:
            print(f"Erreur lecture word DB{db}.DBW{word_offset}: {e}")
            return None
    
    def lire_dword(self, db, dword_offset):
        """Lit un double word (32-bit) dans un DB"""
        try:
            if self.simulation_mode:
                # Simulation
                adresse_sim = f"DB{db}.DBD{dword_offset}"
                return self.simulation_data.get(adresse_sim, 0)
            
            # Lecture réelle
            data = self.client.db_read(db, dword_offset, 4)
            return int.from_bytes(data, byteorder='big', signed=True)
        except Exception as e:
            print(f"Erreur lecture dword DB{db}.DBD{dword_offset}: {e}")
            return None
    
    def lire_real(self, db, real_offset):
        """Lit un real (32-bit float) dans un DB"""
        try:
            if self.simulation_mode:
                # Simulation
                adresse_sim = f"DB{db}.DBD{real_offset}"
                return self.simulation_data.get(adresse_sim, 0.0)
            
            # Lecture réelle
            data = self.client.db_read(db, real_offset, 4)
            import struct
            return struct.unpack('>f', data)[0]  # Big-endian float
        except Exception as e:
            print(f"Erreur lecture real DB{db}.DBD{real_offset}: {e}")
            return None
    
    def ecrire_bit(self, db, byte_offset, bit_offset, valeur):
        """Écrit un bit dans un DB"""
        try:
            if self.simulation_mode:
                # Simulation
                adresse_sim = f"DB{db}.DBX{byte_offset}.{bit_offset}"
                self.simulation_data[adresse_sim] = bool(valeur)
                return True
            
            # Écriture réelle
            # Lire le byte actuel
            data = self.client.db_read(db, byte_offset, 1)
            byte_val = data[0]
            
            # Modifier le bit
            if valeur:
                byte_val |= (1 << bit_offset)
            else:
                byte_val &= ~(1 << bit_offset)
            
            # Écrire le byte modifié
            self.client.db_write(db, byte_offset, bytes([byte_val]))
            return True
            
        except Exception as e:
            print(f"Erreur écriture bit DB{db}.DBX{byte_offset}.{bit_offset}: {e}")
            return False
    
    def ecrire_word(self, db, word_offset, valeur):
        """Écrit un word dans un DB"""
        try:
            if self.simulation_mode:
                # Simulation
                adresse_sim = f"DB{db}.DBW{word_offset}"
                self.simulation_data[adresse_sim] = int(valeur)
                return True
            
            # Écriture réelle
            word_bytes = int(valeur).to_bytes(2, byteorder='big', signed=True)
            self.client.db_write(db, word_offset, word_bytes)
            return True
            
        except Exception as e:
            print(f"Erreur écriture word DB{db}.DBW{word_offset}: {e}")
            return False
    
    def ecrire_dword(self, db, dword_offset, valeur):
        """Écrit un double word dans un DB"""
        try:
            if self.simulation_mode:
                # Simulation
                adresse_sim = f"DB{db}.DBD{dword_offset}"
                self.simulation_data[adresse_sim] = int(valeur)
                return True
            
            # Écriture réelle
            dword_bytes = int(valeur).to_bytes(4, byteorder='big', signed=True)
            self.client.db_write(db, dword_offset, dword_bytes)
            return True
            
        except Exception as e:
            print(f"Erreur écriture dword DB{db}.DBD{dword_offset}: {e}")
            return False
    
    def ecrire_real(self, db, real_offset, valeur):
        """Écrit un real dans un DB"""
        try:
            if self.simulation_mode:
                # Simulation
                adresse_sim = f"DB{db}.DBD{real_offset}"
                self.simulation_data[adresse_sim] = float(valeur)
                return True
            
            # Écriture réelle
            import struct
            real_bytes = struct.pack('>f', float(valeur))  # Big-endian float
            self.client.db_write(db, real_offset, real_bytes)
            return True
            
        except Exception as e:
            print(f"Erreur écriture real DB{db}.DBD{real_offset}: {e}")
            return False
    
    # =================================================================
    # MÉTHODES UNIVERSELLES POUR TOUT TYPE D'ADRESSE
    # =================================================================
    
    def parse_adresse_s7(self, adresse):
        """Parse une adresse S7 et retourne les composants"""
        try:
            # Format: DB1.DBX0.0, DB1.DBW2, DB1.DBD4, etc.
            if not adresse.startswith('DB') or '.DB' not in adresse:
                raise ValueError(f"Format d'adresse invalide: {adresse}")
            
            parts = adresse.split('.')
            db_num = int(parts[0][2:])  # DB1 -> 1
            
            if 'DBX' in parts[1]:  # Bit
                byte_offset = int(parts[1][3:])
                bit_offset = int(parts[2])
                return {
                    'type': 'BOOL',
                    'db': db_num,
                    'byte_offset': byte_offset,
                    'bit_offset': bit_offset
                }
            elif 'DBW' in parts[1]:  # Word (16-bit)
                word_offset = int(parts[1][3:])
                return {
                    'type': 'INT',
                    'db': db_num,
                    'offset': word_offset
                }
            elif 'DBD' in parts[1]:  # Double Word (32-bit)
                dword_offset = int(parts[1][3:])
                return {
                    'type': 'DINT',  # Peut être DINT ou REAL
                    'db': db_num,
                    'offset': dword_offset
                }
            else:
                raise ValueError(f"Type d'adresse non supporté: {parts[1]}")
                
        except (ValueError, IndexError) as e:
            raise ValueError(f"Erreur parsing adresse '{adresse}': {str(e)}")
    
    def lire_tag_par_adresse(self, adresse, type_attendu=None):
        """Lit un tag selon son adresse S7 complète"""
        if not self.connected:
            return None, "AUTOMATE_NON_CONNECTE"
        
        try:
            parsed = self.parse_adresse_s7(adresse)
            
            if parsed['type'] == 'BOOL':
                valeur = self.lire_bit(parsed['db'], parsed['byte_offset'], parsed['bit_offset'])
            elif parsed['type'] == 'INT':
                valeur = self.lire_word(parsed['db'], parsed['offset'])
            elif parsed['type'] == 'DINT':
                if type_attendu == 'REAL':
                    valeur = self.lire_real(parsed['db'], parsed['offset'])
                else:
                    valeur = self.lire_dword(parsed['db'], parsed['offset'])
            else:
                return None, f"TYPE_NON_SUPPORTE: {parsed['type']}"
            
            if valeur is not None:
                self.derniere_lecture[adresse] = {
                    'valeur': valeur,
                    'timestamp': datetime.now(),
                    'qualite': 'GOOD'
                }
                return valeur, "GOOD"
            else:
                return None, "ERREUR_LECTURE_S7"
                
        except Exception as e:
            return None, f"EXCEPTION_S7: {str(e)}"
    
    def ecrire_tag_par_adresse(self, adresse, valeur, type_attendu=None):
        """Écrit un tag selon son adresse S7 complète"""
        if not self.connected:
            return False, "AUTOMATE_NON_CONNECTE"
        
        try:
            parsed = self.parse_adresse_s7(adresse)
            
            if parsed['type'] == 'BOOL':
                success = self.ecrire_bit(parsed['db'], parsed['byte_offset'], parsed['bit_offset'], valeur)
            elif parsed['type'] == 'INT':
                success = self.ecrire_word(parsed['db'], parsed['offset'], valeur)
            elif parsed['type'] == 'DINT':
                if type_attendu == 'REAL':
                    success = self.ecrire_real(parsed['db'], parsed['offset'], valeur)
                else:
                    success = self.ecrire_dword(parsed['db'], parsed['offset'], valeur)
            else:
                return False, f"TYPE_NON_SUPPORTE: {parsed['type']}"
            
            if success:
                return True, "ECRITURE_S7_OK"
            else:
                return False, "ERREUR_ECRITURE_S7"
                
        except Exception as e:
            return False, f"EXCEPTION_ECRITURE_S7: {str(e)}"
    
    # =================================================================
    # MÉTHODES DE COMPATIBILITÉ AVEC L'ANCIEN SYSTÈME
    # =================================================================
    
    def lire_tag(self, adresse_tag):
        """Méthode de compatibilité avec l'ancien système"""
        return self.lire_tag_par_adresse(adresse_tag)
    
    def ecrire_tag(self, adresse_tag, valeur):
        """Méthode de compatibilité avec l'ancien système"""
        return self.ecrire_tag_par_adresse(adresse_tag, valeur)
    
    # =================================================================
    # UTILITAIRES ET VALIDATION
    # =================================================================
    
    def valider_ip(self, ip_address):
        """Valide si l'IP est dans la plage autorisée"""
        try:
            ip = ipaddress.IPv4Address(ip_address)
            return True, "IP valide"
        except ipaddress.AddressValueError:
            return False, f"Format IP invalide: {ip_address}"
    
    def ping_automate(self, ip_address, timeout=3):
        """Ping l'automate pour vérifier la connectivité réseau"""
        try:
            if os.name == 'nt':  # Windows
                cmd = ['ping', '-n', '1', '-w', str(timeout * 1000), ip_address]
            else:  # Linux/Mac
                cmd = ['ping', '-c', '1', '-W', str(timeout), ip_address]
            
            result = subprocess.run(cmd, capture_output=True, timeout=timeout + 2)
            return result.returncode == 0
        except Exception as e:
            print(f"Erreur ping: {e}")
            return False
    
    def tester_port_s7(self, ip_address, port=102, timeout=3):
        """Teste si le port S7 (102) est ouvert"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((ip_address, port))
            sock.close()
            return result == 0
        except Exception as e:
            print(f"Erreur test port S7: {e}")
            return False
    
    def _init_simulation_data(self):
        """Initialise les données de simulation avec vos tags Siemens"""
        self.simulation_data = {
            # DB1 - Static
            'DB1.DBX0.0': False,  # bp_marche
            'DB1.DBX0.1': False,  # bp_arret  
            'DB1.DBX0.2': False,  # bp_rearmement
            'DB1.DBX0.3': True,   # ARU
            'DB1.DBW2': 50,       # quantite_produit
            'DB1.DBW4': 123,      # TestInt
            
            # DB2 - lec_ecr_ihm_indus
            'DB2.DBX0.0': False,  # bit_de_vie
            'DB2.DBX0.1': False,  # temp_de_prod
            
            # DB3 - sorti_ihm_indus
            'DB3.DBX0.0': False,  # voyant_marche
            'DB3.DBX0.1': False,  # voyant_arret
            'DB3.DBX0.2': False,  # voyant_marche_1
            'DB3.DBX0.3': False,  # marche_moteur
        }
        
        if self.simulation_mode:
            self._start_simulation()
    
    def _start_simulation(self):
        """Démarre la simulation avec valeurs qui évoluent"""
        def update_simulation():
            import random
            while self.simulation_mode and self.connected:
                try:
                    # Simule un bit de vie qui clignote
                    self.simulation_data['DB2.DBX0.0'] = not self.simulation_data.get('DB2.DBX0.0', False)
                    
                    # Simule la quantité qui augmente
                    if 'DB1.DBW2' in self.simulation_data:
                        self.simulation_data['DB1.DBW2'] = (self.simulation_data['DB1.DBW2'] + 1) % 100
                    
                    # Simule les états des voyants selon les boutons
                    if self.simulation_data.get('DB1.DBX0.0'):  # Si bp_marche pressé
                        self.simulation_data['DB3.DBX0.0'] = True  # voyant_marche ON
                        self.simulation_data['DB3.DBX0.3'] = True  # marche_moteur ON
                    
                    if self.simulation_data.get('DB1.DBX0.1'):  # Si bp_arret pressé
                        self.simulation_data['DB3.DBX0.0'] = False  # voyant_marche OFF
                        self.simulation_data['DB3.DBX0.1'] = True   # voyant_arret ON
                        self.simulation_data['DB3.DBX0.3'] = False  # marche_moteur OFF
                    
                    time.sleep(1)
                except Exception as e:
                    print(f"Erreur simulation: {e}")
                    time.sleep(5)
        
        thread = threading.Thread(target=update_simulation, daemon=True)
        thread.start()
        print("🔄 Simulation S7 démarrée")
    
    def get_status(self):
        """Retourne le statut de connexion détaillé"""
        status = {
            "connected": self.connected,
            "ip_address": self.ip_address,
            "rack": self.rack,
            "slot": self.slot,
            "protocol": "Siemens S7",
            "simulation_mode": self.simulation_mode,
            "driver_available": SNAP7_AVAILABLE,
            "validation_ping": self.validation_ping,
            "timestamp": datetime.now().isoformat(),
            "tags_en_cache": len(self.derniere_lecture)
        }
        
        if not self.simulation_mode and self.ip_address:
            status["network_ping"] = self.ping_automate(self.ip_address, timeout=1)
            status["s7_port_open"] = self.tester_port_s7(self.ip_address, timeout=1)
        
        return status

# Instance globale de l'automate Siemens
automate = AutomateSiemensS7Complete()

def init_automate(app):
    """Initialise l'automate avec le contexte de l'app"""
    automate.init_app(app)

# =================================================================
# MODÈLE TAG ÉTENDU POUR GESTION FLEXIBLE
# =================================================================

class TagSiemensEtendu:
    """Classe utilitaire pour la gestion flexible des tags"""
    
    @staticmethod
    def generer_adresse(db, type_donnee, offset):
        """Génère une adresse S7 selon les paramètres"""
        if type_donnee == 'BOOL':
            if '.' not in str(offset):
                raise ValueError("Pour BOOL, offset doit être au format 'byte.bit' (ex: 0.0)")
            return f"DB{db}.DBX{offset}"
        elif type_donnee == 'INT':
            return f"DB{db}.DBW{offset}"
        elif type_donnee in ['DINT', 'REAL']:
            return f"DB{db}.DBD{offset}"
        else:
            raise ValueError(f"Type de donnée non supporté: {type_donnee}")
    
    @staticmethod
    def valider_offset(type_donnee, offset):
        """Valide un offset selon le type de donnée"""
        try:
            if type_donnee == 'BOOL':
                if '.' not in str(offset):
                    return False, "Format invalide pour BOOL, utilisez 'byte.bit'"
                byte_part, bit_part = str(offset).split('.')
                byte_val = int(byte_part)
                bit_val = int(bit_part)
                if byte_val < 0 or bit_val < 0 or bit_val > 7:
                    return False, "Offset BOOL invalide (bit doit être 0-7)"
                return True, "Offset BOOL valide"
            
            elif type_donnee == 'INT':
                offset_val = int(offset)
                if offset_val < 0 or offset_val % 2 != 0:
                    return False, "Offset INT doit être un nombre pair positif"
                return True, "Offset INT valide"
            
            elif type_donnee in ['DINT', 'REAL']:
                offset_val = int(offset)
                if offset_val < 0 or offset_val % 4 != 0:
                    return False, f"Offset {type_donnee} doit être multiple de 4"
                return True, f"Offset {type_donnee} valide"
            
            else:
                return False, f"Type {type_donnee} non supporté"
                
        except (ValueError, AttributeError):
            return False, "Format d'offset invalide"
    
    @staticmethod
    def convertir_valeur(valeur, type_donnee):
        """Convertit une valeur selon le type de donnée"""
        try:
            if type_donnee == 'BOOL':
                if isinstance(valeur, str):
                    return valeur.lower() in ['true', '1', 'on', 'yes']
                return bool(valeur)
            elif type_donnee == 'INT':
                val = int(valeur)
                if val < -32768 or val > 32767:
                    raise ValueError("Valeur INT hors limites (-32768 à 32767)")
                return val
            elif type_donnee == 'DINT':
                val = int(valeur)
                if val < -2147483648 or val > 2147483647:
                    raise ValueError("Valeur DINT hors limites")
                return val
            elif type_donnee == 'REAL':
                return float(valeur)
            else:
                return str(valeur)
        except (ValueError, TypeError) as e:
            raise ValueError(f"Conversion impossible vers {type_donnee}: {str(e)}")

# =================================================================
# ROUTES WEB ÉTENDUES
# =================================================================

@main_bp.route('/automate')
@AuthSystem.login_required
def index():
    """Page de connexion automate (maintenant protégée)"""
    current_project_id = session.get('current_project_id')
    all_tags = Tag.query.filter_by(id_projet=current_project_id).all()
    tags_actifs = [tag for tag in all_tags if tag.actif]
    status = automate.get_status()
    return render_template('monitoring/connexion.html', tags=tags_actifs, status=status)

@main_bp.route('/connect', methods=['POST'])
@AuthSystem.login_required
def connect_automate():
    """Connexion à l'automate Siemens S7"""
    ip = request.form.get('ip_address', automate.ip_address)
    rack = int(request.form.get('rack', automate.rack))
    slot = int(request.form.get('slot', automate.slot))
    force_simulation = request.form.get('force_simulation') == 'on'
    
    success, message = automate.connect(ip, rack, slot, force_simulation)
    flash(f"{'✅' if success else '❌'} {message}", "success" if success else "error")
    return redirect(url_for('main.index'))

@main_bp.route('/disconnect', methods=['POST'])
@AuthSystem.login_required
def disconnect_automate():
    """Déconnexion de l'automate"""
    success, message = automate.disconnect()
    flash(f"🔌 {message}", "info")
    return redirect(url_for('main.index'))

@main_bp.route('/tags')
@AuthSystem.auto_required   
def tags():
    """Page de gestion des tags - FILTRÉE PAR PROJET"""
    current_project_id = session.get('current_project_id')
    if not current_project_id:
        flash('Aucun projet sélectionné', 'warning')
        return redirect(url_for('main.projects_management'))
    
    # ✅ CORRIGÉ : filtrer par projet
    tags = Tag.query.filter_by(id_projet=current_project_id).all()
    print(f"Debug - Tags du projet {current_project_id}: {len(tags)}")
    
    return render_template('monitoring/tags.html', tags=tags)

@main_bp.route('/supervision')
@AuthSystem.login_required
def supervision():
    """Page de supervision"""
    current_project_id = session.get('current_project_id')
    all_tags = Tag.query.filter_by(id_projet=current_project_id).all()
    tags_actifs = [tag for tag in all_tags if tag.actif]
    status = automate.get_status()
    return render_template('monitoring/supervision.html', tags=tags_actifs, status=status)


# =================================================================
# API REST COMPLÈTE ET ÉTENDUE - TOUTES LES ROUTES CORRIGÉES
# =================================================================

@main_bp.route('/api/read_tag_direct', methods=['POST'])
@AuthSystem.auto_required
def api_read_tag_direct():
    """API: Lecture directe d'un tag par adresse S7"""
    data = request.get_json()
    
    if not data or 'adresse' not in data:
        return jsonify({"error": "Paramètre 'adresse' manquant"}), 400
    
    adresse = data['adresse']
    type_attendu = data.get('type', None)
    
    try:
        valeur, qualite = automate.lire_tag_par_adresse(adresse, type_attendu)
        
        return jsonify({
            "success": valeur is not None,
            "adresse": adresse,
            "valeur": valeur,
            "qualite": qualite,
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "adresse": adresse
        }), 500

@main_bp.route('/api/write_tag_direct', methods=['POST'])
@AuthSystem.auto_required
def api_write_tag_direct():
    """API: Écriture directe d'un tag par adresse S7"""
    data = request.get_json()
    
    if not data or 'adresse' not in data or 'valeur' not in data:
        return jsonify({"error": "Paramètres 'adresse' et 'valeur' requis"}), 400
    
    adresse = data['adresse']
    valeur = data['valeur']
    type_attendu = data.get('type', None)
    
    try:
        success, status = automate.ecrire_tag_par_adresse(adresse, valeur, type_attendu)
        
        return jsonify({
            "success": success,
            "adresse": adresse,
            "valeur": valeur,
            "status": status,
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "adresse": adresse
        }), 500

@main_bp.route('/api/create_tag_flexible', methods=['POST'])
@AuthSystem.auto_required
def api_create_tag_flexible():
    """API: Création d'un tag - CORRIGÉE avec projet"""
    current_project_id = session.get('current_project_id')
    if not current_project_id:
        return jsonify({"error": "Aucun projet sélectionné"}), 400
    
    data = request.get_json()
    
    # Validation des champs requis
    champs_requis = ['nom_tag', 'db', 'type_donnee', 'offset']
    for champ in champs_requis:
        if champ not in data:
            return jsonify({"error": f"Champ '{champ}' requis"}), 400
    
    nom_tag = data['nom_tag']
    db_num = data['db']
    type_donnee = data['type_donnee']
    offset = data['offset']
    acces = data.get('acces', 'R')
    description = data.get('description_tag', '')
    
    try:
        # Validation de l'offset
        offset_valide, message_offset = TagSiemensEtendu.valider_offset(type_donnee, offset)
        if not offset_valide:
            return jsonify({"error": message_offset}), 400
        
        # Génération de l'adresse S7
        adresse = TagSiemensEtendu.generer_adresse(db_num, type_donnee, offset)
        
        # Vérification de l'unicité
        tag_existant = Tag.query.filter_by(nom_tag=nom_tag).first()
        if tag_existant:
            return jsonify({"error": f"Tag '{nom_tag}' existe déjà"}), 409
        
        # lier au projet actuel
        nouveau_tag = Tag(
            nom_tag=nom_tag,
            adresse_tag=adresse,
            type_donnee=type_donnee,
            description_tag=description,
            acces=acces,
            id_projet=current_project_id
        )
        
        db.session.add(nouveau_tag)
        db.session.commit()
        
        return jsonify({
            "message": f"Tag '{nom_tag}' créé dans le projet {current_project_id}",
            "tag": nouveau_tag.to_dict(),
            "adresse_generee": adresse
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Erreur création: {str(e)}"}), 500


@main_bp.route('/api/test_tous_tags')
@AuthSystem.auto_required
def api_test_tous_tags():
    """API: Test de lecture de tous vos tags comme dans test_lect_ecr.py"""
    if not automate.connected:
        return jsonify({"error": "Automate non connecté"}), 400
    
    resultats = {
        "DB1_Static": {},
        "DB2_lec_ecr_ihm_indus": {},
        "DB3_sorti_ihm_indus": {},
        "timestamp": datetime.now().isoformat()
    }
    
    try:
        # DB1 - Static
        resultats["DB1_Static"]["bp_marche"] = automate.lire_bit(1, 0, 0)
        resultats["DB1_Static"]["bp_arret"] = automate.lire_bit(1, 0, 1)
        resultats["DB1_Static"]["bp_rearmement"] = automate.lire_bit(1, 0, 2)
        resultats["DB1_Static"]["ARU"] = automate.lire_bit(1, 0, 3)
        resultats["DB1_Static"]["quantite_produit"] = automate.lire_word(1, 2)
        resultats["DB1_Static"]["TestInt"] = automate.lire_word(1, 4)
        
        # DB2 - lec_ecr_ihm_indus
        resultats["DB2_lec_ecr_ihm_indus"]["bit_de_vie"] = automate.lire_bit(2, 0, 0)
        resultats["DB2_lec_ecr_ihm_indus"]["temp_de_prod"] = automate.lire_bit(2, 0, 1)
        
        # DB3 - sorti_ihm_indus
        resultats["DB3_sorti_ihm_indus"]["voyant_marche"] = automate.lire_bit(3, 0, 0)
        resultats["DB3_sorti_ihm_indus"]["voyant_arret"] = automate.lire_bit(3, 0, 1)
        resultats["DB3_sorti_ihm_indus"]["voyant_marche_1"] = automate.lire_bit(3, 0, 2)
        resultats["DB3_sorti_ihm_indus"]["marche_moteur"] = automate.lire_bit(3, 0, 3)
        
        return jsonify({
            "success": True,
            "message": "Lecture complète effectuée",
            "donnees": resultats,
            "mode": "SIMULATION" if automate.simulation_mode else "REEL"
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "donnees_partielles": resultats
        }), 500

@main_bp.route('/api/valider_adresse', methods=['POST'])
def api_valider_adresse():
    """API: Validation d'une adresse S7"""
    data = request.get_json()
    
    if not data or 'db' not in data or 'type_donnee' not in data or 'offset' not in data:
        return jsonify({"error": "Paramètres 'db', 'type_donnee' et 'offset' requis"}), 400
    
    try:
        db = data['db']
        type_donnee = data['type_donnee']
        offset = data['offset']
        
        # Validation de l'offset
        offset_valide, message_offset = TagSiemensEtendu.valider_offset(type_donnee, offset)
        
        if offset_valide:
            adresse = TagSiemensEtendu.generer_adresse(db, type_donnee, offset)
            return jsonify({
                "valide": True,
                "message": message_offset,
                "adresse_generee": adresse
            })
        else:
            return jsonify({
                "valide": False,
                "message": message_offset
            })
            
    except Exception as e:
        return jsonify({
            "valide": False,
            "message": f"Erreur validation: {str(e)}"
        })

@main_bp.route('/api/read/<nom_tag>')
@AuthSystem.auto_required
def api_read_tag(nom_tag):
    """API: Lecture d'un tag par nom - VERSION CORRIGÉE"""
    if not automate.connected:
        return jsonify({"error": "Automate non connecté"}), 400
    
    current_project_id = session.get('current_project_id')
    print(f"DEBUG: current_project_id = {current_project_id}")
    
    # CORRECTION TEMPORAIRE: Chercher le tag partout si pas de projet
    if current_project_id:
        tag = Tag.query.filter_by(nom_tag=nom_tag, id_projet=current_project_id).first()
    else:
        tag = Tag.query.filter_by(nom_tag=nom_tag).first()
        print(f"DEBUG: Pas de projet, recherche globale")
    
    if not tag:
        return jsonify({"error": f"Tag '{nom_tag}' non trouvé"}), 404
    
    print(f"DEBUG: Tag trouvé - {tag.nom_tag}, projet: {tag.id_projet}")
    
    try:
        valeur, qualite = automate.lire_tag_par_adresse(tag.adresse_tag, tag.type_donnee)
        print(f"DEBUG: Lecture réussie - valeur: {valeur}, qualite: {qualite}")
        
        # Mise à jour en base (avec protection)
        try:
            if valeur is not None and hasattr(tag, 'mettre_a_jour_valeur'):
                tag.mettre_a_jour_valeur(valeur, qualite)
                db.session.commit()
        except Exception as e:
            print(f"DEBUG: Erreur mise à jour base: {e}")
        
        return jsonify({
            "success": valeur is not None,
            "nom_tag": nom_tag,
            "adresse": tag.adresse_tag,
            "type_donnee": tag.type_donnee,
            "valeur": valeur,
            "qualite": qualite,
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        print(f"DEBUG: Erreur lecture: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@main_bp.route('/api/write/<nom_tag>', methods=['POST'])
@AuthSystem.auto_required
def api_write_tag(nom_tag):
    """API: Écriture d'un tag par nom - AVEC FILTRAGE PROJET"""
    if not automate.connected:
        return jsonify({"error": "Automate non connecté"}), 400
    
    # CORRECTION: Ajouter le filtrage par projet
    current_project_id = session.get('current_project_id')
    if not current_project_id:
        return jsonify({"error": "Aucun projet sélectionné"}), 400
    
    tag = Tag.query.filter_by(
        nom_tag=nom_tag,
        id_projet=current_project_id  # CORRECTION: Filtrer par projet
    ).first()
    
    if not tag:
        return jsonify({"error": f"Tag '{nom_tag}' non trouvé dans le projet actuel"}), 404
    
    # Vérifier si le tag est actif (propriété calculée)
    if not tag.actif:
        return jsonify({"error": f"Tag '{nom_tag}' non actif"}), 400
    
    if not tag.est_accessible_en_ecriture():
        return jsonify({"error": f"Tag '{nom_tag}' non accessible en écriture"}), 403
    
    data = request.get_json()
    if not data or 'valeur' not in data:
        return jsonify({"error": "Paramètre 'valeur' requis"}), 400
    
    try:
        # Validation de la valeur
        valide, valeur_convertie, message = tag.valider_valeur(data['valeur'])
        if not valide:
            return jsonify({"error": message}), 400
        
        # Écriture
        success, status = automate.ecrire_tag_par_adresse(tag.adresse_tag, valeur_convertie, tag.type_donnee)
        
        if success:
            # Mettre à jour le tag en base
            tag.mettre_a_jour_valeur(valeur_convertie, 'GOOD')
            db.session.commit()
            
            return jsonify({
                "success": True,
                "nom_tag": nom_tag,
                "valeur": valeur_convertie,
                "status": status,
                "projet_id": current_project_id,  # Pour debug
                "timestamp": datetime.now().isoformat()
            })
        else:
            return jsonify({
                "success": False,
                "error": status,
                "nom_tag": nom_tag
            }), 500
            
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "nom_tag": nom_tag
        }), 500

@main_bp.route('/api/read_all')
@AuthSystem.auto_required
def api_read_all_tags():
    """API: Lecture de tous les tags - VERSION CORRIGÉE"""
    if not automate.connected:
        return jsonify({"error": "Automate non connecté"}), 400

    current_project_id = session.get('current_project_id')
    print(f"DEBUG: current_project_id pour read_all = {current_project_id}")
    
    # CORRECTION: Permettre lecture même sans projet
    if current_project_id:
        all_tags = Tag.query.filter_by(id_projet=current_project_id).all()
        print(f"DEBUG: {len(all_tags)} tags dans le projet {current_project_id}")
    else:
        all_tags = Tag.query.all()
        print(f"DEBUG: {len(all_tags)} tags au total (pas de projet)")
    
    # TEMPORAIRE: Ne plus filtrer par tag.actif
    # tags_actifs = [tag for tag in all_tags if tag.actif]
    tags_actifs = all_tags  # Prendre tous les tags
    print(f"DEBUG: {len(tags_actifs)} tags à lire")
    
    resultats = []
    for tag in tags_actifs:
        try:
            valeur, qualite = automate.lire_tag_par_adresse(tag.adresse_tag, tag.type_donnee)
            resultats.append({
                "nom_tag": tag.nom_tag,
                "adresse": tag.adresse_tag,
                "valeur": valeur,
                "qualite": qualite,
                "timestamp": datetime.now().isoformat()
            })
        except Exception as e:
            print(f"DEBUG: Erreur lecture {tag.nom_tag}: {e}")
    
    return jsonify({
        "success": True,
        "nombre_tags": len(resultats),
        "tags": resultats,
        "timestamp": datetime.now().isoformat()
    })

@main_bp.route('/api/tags/<int:tag_id>', methods=['DELETE'])
@AuthSystem.auto_required
def api_delete_tag(tag_id):
    """API: Suppression d'un tag - AVEC FILTRAGE PROJET"""
    current_project_id = session.get('current_project_id')
    if not current_project_id:
        return jsonify({"error": "Aucun projet sélectionné"}), 400
    
    tag = Tag.query.filter_by(
        id=tag_id,
        id_projet=current_project_id  # CORRECTION: Filtrer par projet
    ).first()
    
    if not tag:
        return jsonify({"error": f"Tag avec ID {tag_id} non trouvé dans le projet actuel"}), 404
    
    try:
        nom_tag = tag.nom_tag
        db.session.delete(tag)
        db.session.commit()
        
        return jsonify({
            "success": True,
            "message": f"Tag '{nom_tag}' supprimé avec succès"
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Erreur suppression: {str(e)}"}), 500

@main_bp.route('/api/tags', methods=['GET'])
@AuthSystem.auto_required
def api_list_tags():
    """API: Liste de tous les tags - CORRIGÉE !"""
    current_project_id = session.get('current_project_id')
    all_tags = Tag.query.filter_by(id_projet=current_project_id).all()
    tags_actifs = [tag for tag in all_tags if tag.actif]
    
    return jsonify({
        "success": True,
        "nombre_tags": len(tags_actifs),
        "tags": [tag.to_dict() for tag in tags_actifs],
        "timestamp": datetime.now().isoformat()
    })

@main_bp.route('/api/status')
@AuthSystem.auto_required
def api_status():
    """API: Statut de l'automate"""
    status = automate.get_status()
    return jsonify(status)

@main_bp.route('/api/test_ping')
def api_test_ping():
    """API: Test ping d'une IP"""
    ip = request.args.get('ip')
    if not ip:
        return jsonify({"error": "Paramètre IP requis"}), 400
    
    try:
        success = automate.ping_automate(ip, timeout=2)
        return jsonify({
            "success": success,
            "ip": ip,
            "message": "Ping réussi" if success else "Ping échoué"
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@main_bp.route('/api/scan_network')
@AuthSystem.auto_required
def api_scan_network():
    """API: Scan réseau pour trouver des automates"""
    base_ip = request.args.get('base_ip', '192.168.0')
    start = int(request.args.get('start', 1))
    end = int(request.args.get('end', 20))
    
    automates_found = []
    
    for i in range(start, end + 1):
        ip = f"{base_ip}.{i}"
        try:
            ping_ok = automate.ping_automate(ip, timeout=1)
            s7_port = automate.tester_port_s7(ip, timeout=1) if ping_ok else False
            
            if ping_ok:
                automates_found.append({
                    "ip": ip,
                    "ping": ping_ok,
                    "s7_port": s7_port
                })
        except Exception:
            continue
    
    return jsonify({
        "success": True,
        "base_ip": base_ip,
        "range": f"{start}-{end}",
        "automates_found": automates_found,
        "total_found": len(automates_found)
    })

# =================================================================
# ROUTE DE DEBUG POUR VÉRIFIER LES TAGS
# =================================================================

@main_bp.route('/api/debug_tags')
@AuthSystem.auto_required
def api_debug_tags():
    """API: Debug - Affiche tous les tags avec leurs propriétés"""
    current_project_id = session.get('current_project_id')
    all_tags = Tag.query.filter_by(id_projet=current_project_id).all()
    debug_info = []
    
    for tag in all_tags:
        debug_info.append({
            "nom_tag": tag.nom_tag,
            "adresse_tag": tag.adresse_tag,
            "disponibilite_externe": tag.disponibilite_externe,
            "actif": tag.actif,  # Propriété calculée
            "acces": tag.acces,
            "type_donnee": tag.type_donnee
        })
    
    return jsonify({
        "total_tags": len(all_tags),
        "tags_details": debug_info
    })

@main_bp.route('/api/debug_session')
@AuthSystem.auto_required
def api_debug_session():
    """Debug: Vérifier l'état de la session"""
    current_project_id = session.get('current_project_id')
    return jsonify({
        "current_project_id": current_project_id,
        "session_keys": list(session.keys()),
        "automate_connected": automate.connected,
        "tags_projet_4": Tag.query.filter_by(id_projet=4).count() if current_project_id else 0,
        "total_tags": Tag.query.count()
    })
# =================================================================
# ROUTES ADMIN
# =================================================================

@main_bp.route('/admin/init_tags', methods=['POST'])
@AuthSystem.auto_required
def admin_init_tags():
    """Admin: Initialise les tags par défaut"""
    try:
        tags_crees = creer_tags_siemens_defaut()
        return jsonify({
            "success": True,
            "message": f"{len(tags_crees)} tags créés",
            "tags": [tag.nom_tag for tag in tags_crees]
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@main_bp.route('/admin/reset_simulation', methods=['POST'])
@AuthSystem.auto_required
def admin_reset_simulation():
    """Admin: Remet à zéro la simulation"""
    if automate.simulation_mode:
        automate._init_simulation_data()
        return jsonify({
            "success": True,
            "message": "Simulation réinitialisée"
        })
    else:
        return jsonify({
            "success": False,
            "error": "Pas en mode simulation"
        }), 400

def creer_tags_siemens_defaut():
    """Crée les tags Siemens par défaut - CORRIGÉE"""
    current_project_id = session.get('current_project_id')
    if not current_project_id:
        print("⚠️ Pas de projet actuel pour créer les tags par défaut")
        return []
    
    # CORRECTION: Définir la liste AVANT de l'utiliser
    tags_siemens = [
        # DB1 - Static
        {
            'nom_tag': 'bp_marche',
            'adresse_tag': 'DB1.DBX0.0',
            'type_donnee': 'BOOL',
            'description_tag': 'Bouton poussoir marche',
            'acces': 'RW'
        },
        {
            'nom_tag': 'bp_arret',
            'adresse_tag': 'DB1.DBX0.1',
            'type_donnee': 'BOOL',
            'description_tag': 'Bouton poussoir arrêt',
            'acces': 'RW'
        },
        {
            'nom_tag': 'bp_rearmement',
            'adresse_tag': 'DB1.DBX0.2',
            'type_donnee': 'BOOL',
            'description_tag': 'Bouton poussoir réarmement',
            'acces': 'RW'
        },
        {
            'nom_tag': 'ARU',
            'adresse_tag': 'DB1.DBX0.3',
            'type_donnee': 'BOOL',
            'description_tag': 'Arrêt d\'urgence',
            'acces': 'R'
        },
        {
            'nom_tag': 'quantite_produit',
            'adresse_tag': 'DB1.DBW2',
            'type_donnee': 'INT',
            'description_tag': 'Quantité de produit',
            'acces': 'RW'
        },
        {
            'nom_tag': 'TestInt',
            'adresse_tag': 'DB1.DBW4',
            'type_donnee': 'INT',
            'description_tag': 'Entier de test',
            'acces': 'RW'
        },
        
        # DB2 - lec_ecr_ihm_indus
        {
            'nom_tag': 'bit_de_vie',
            'adresse_tag': 'DB2.DBX0.0',
            'type_donnee': 'BOOL',
            'description_tag': 'Bit de vie IHM',
            'acces': 'R'
        },
        {
            'nom_tag': 'temp_de_prod',
            'adresse_tag': 'DB2.DBX0.1',
            'type_donnee': 'BOOL',
            'description_tag': 'Temps de production',
            'acces': 'R'
        },
        
        # DB3 - sorti_ihm_indus
        {
            'nom_tag': 'voyant_marche',
            'adresse_tag': 'DB3.DBX0.0',
            'type_donnee': 'BOOL',
            'description_tag': 'Voyant marche',
            'acces': 'R'
        },
        {
            'nom_tag': 'voyant_arret',
            'adresse_tag': 'DB3.DBX0.1',
            'type_donnee': 'BOOL',
            'description_tag': 'Voyant arrêt',
            'acces': 'R'
        },
        {
            'nom_tag': 'voyant_marche_1',
            'adresse_tag': 'DB3.DBX0.2',
            'type_donnee': 'BOOL',
            'description_tag': 'Voyant marche 1',
            'acces': 'R'
        },
        {
            'nom_tag': 'marche_moteur',
            'adresse_tag': 'DB3.DBX0.3',
            'type_donnee': 'BOOL',
            'description_tag': 'Marche moteur',
            'acces': 'R'
        }
    ]
    
    tags_crees = []
    for tag_data in tags_siemens:
        # Ajouter l'ID du projet actuel
        tag_data['id_projet'] = current_project_id
        
        # Vérifier unicité DANS LE PROJET
        tag_existant = Tag.query.filter_by(
            nom_tag=tag_data['nom_tag'],
            id_projet=current_project_id
        ).first()
        
        if not tag_existant:
            # CORRECTION: Manipuler l'adresse correctement
            adresse = tag_data['adresse_tag']
            tag_data_copy = tag_data.copy()
            tag_data_copy.pop('adresse_tag')
            
            nouveau_tag = Tag(**tag_data_copy)
            nouveau_tag.adresse_tag = adresse
            db.session.add(nouveau_tag)
            tags_crees.append(nouveau_tag)
    
    if tags_crees:
        db.session.commit()
        print(f"✅ {len(tags_crees)} tags créés dans le projet {current_project_id}")
    
    return tags_crees