# Test connexion IHM automate
import snap7

# CONFIGURATION AUTOMATE
IP_AUTOMATE = "192.168.0.1"  # ← Bonne IP détectée
RACK = 0
SLOT = 1

def test_lecture_tags_siemens():
    """Test avec tags Siemens définis"""
    print("🏭 TEST IHM SIEMENS - TAGS RÉELS")
    print("=" * 40)
    
    try:
        # Connexion
        client = snap7.client.Client()
        client.connect(IP_AUTOMATE, RACK, SLOT)
        
        if not client.get_connected():
            print("❌ Connexion échouée")
            return
            
        print("✅ Connexion établie !")
        
        # Test des tags définis dans l'IHM
        tags_tests = [
            {"nom": "bp_marche", "adresse": "DB1.DBX0.0", "type": "BOOL"},
            {"nom": "bp_arret", "adresse": "DB1.DBX0.1", "type": "BOOL"},
            {"nom": "quantite_produit", "adresse": "DB1.DBW2", "type": "INT"},
            {"nom": "voyant_marche", "adresse": "DB3.DBX0.0", "type": "BOOL"},
        ]
        
        print("\n📊 LECTURE DES TAGS:")
        for tag in tags_tests:
            try:
                valeur = lire_tag_s7(client, tag["adresse"], tag["type"])
                print(f"✅ {tag['nom']} ({tag['adresse']}): {valeur}")
            except Exception as e:
                print(f"⚠️ {tag['nom']} ({tag['adresse']}): Erreur - {e}")
        
        # Test d'écriture
        print("\n✏️ TEST D'ÉCRITURE:")
        try:
            # Test écriture boolean
            ecrire_tag_s7(client, "DB1.DBX0.0", True, "BOOL")
            valeur = lire_tag_s7(client, "DB1.DBX0.0", "BOOL")
            print(f"✅ Écriture DB1.DBX0.0 = True → Lecture: {valeur}")
            
            # Remettre à False
            ecrire_tag_s7(client, "DB1.DBX0.0", False, "BOOL")
            print("✅ Remis à False")
            
        except Exception as e:
            print(f"⚠️ Test écriture: {e}")
        
        client.disconnect()
        print("\n🎉 L IHM EST PRÊTE À FONCTIONNER !")
        
    except Exception as e:
        print(f"❌ Erreur: {e}")

def lire_tag_s7(client, adresse, type_donnee):
    """Lecture d'un tag S7"""
    if adresse.startswith('DB') and '.DB' in adresse:
        parts = adresse.split('.')
        db_num = int(parts[0][2:])  # DB1 -> 1
        
        if 'DBX' in parts[1]:  # Bit
            byte_offset = int(parts[1][3:])
            bit_offset = int(parts[2])
            
            data = client.db_read(db_num, byte_offset, 1)
            byte_val = data[0]
            bit_val = bool(byte_val & (1 << bit_offset))
            return bit_val
            
        elif 'DBW' in parts[1]:  # Word (16-bit)
            word_offset = int(parts[1][3:])
            data = client.db_read(db_num, word_offset, 2)
            word_val = int.from_bytes(data, byteorder='big', signed=True)
            return word_val
    
    return None

def ecrire_tag_s7(client, adresse, valeur, type_donnee):
    """Écriture d'un tag S7"""
    if adresse.startswith('DB') and '.DB' in adresse:
        parts = adresse.split('.')
        db_num = int(parts[0][2:])
        
        if 'DBX' in parts[1]:  # Bit
            byte_offset = int(parts[1][3:])
            bit_offset = int(parts[2])
            
            # Lire le byte actuel
            data = client.db_read(db_num, byte_offset, 1)
            byte_val = data[0]
            
            # Modifier le bit
            if valeur:
                byte_val |= (1 << bit_offset)
            else:
                byte_val &= ~(1 << bit_offset)
            
            # Écrire le byte modifié
            client.db_write(db_num, byte_offset, bytes([byte_val]))
            return True

if __name__ == "__main__":
    test_lecture_tags_siemens()