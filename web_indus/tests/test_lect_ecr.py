# test_icones_autonome.py
import mysql.connector
from datetime import datetime

# ⚙️ Configuration BDD
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "votre_mdp",
    "database": "ihm_indus"
}

# Fonction de lecture de tous les icones
def lire_icones():
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("SELECT * FROM Icon_Library")
    icones = cursor.fetchall()
    
    print(f"📦 {len(icones)} icônes trouvées dans la bibliothèque :")
    for icone in icones:
        print(f"  - ID {icone['id_icon']} | {icone['nom_icon']} | Catégorie: {icone['categorie']} | Actif: {icone['actif']}")
    
    cursor.close()
    conn.close()

# Fonction d'ajout d'une icône test
def ajouter_icone_test():
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()
    
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sql = """
    INSERT INTO Icon_Library
    (id_icon, nom_icon, description_icon, categorie, type_source, date_creation, actif)
    VALUES (%s, %s, %s, %s, %s, %s, %s)
    """
    data = (9999, "Test Icon", "Icône créée pour test", "Test", "SVG", now, 1)
    
    try:
        cursor.execute(sql, data)
        conn.commit()
        print("✅ Icône test ajoutée avec succès")
    except mysql.connector.Error as e:
        print(f"❌ Erreur ajout icône: {e}")
        conn.rollback()
    
    cursor.close()
    conn.close()

# Fonction de suppression de l'icône test
def supprimer_icone_test():
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()
    
    try:
        cursor.execute("DELETE FROM Icon_Library WHERE id_icon = 9999")
        conn.commit()
        print("✅ Icône test supprimée")
    except mysql.connector.Error as e:
        print(f"❌ Erreur suppression icône: {e}")
        conn.rollback()
    
    cursor.close()
    conn.close()

if __name__ == "__main__":
    print("🛠️ Test complet Icon_Library")
    ajouter_icone_test()
    lire_icones()
    supprimer_icone_test()
