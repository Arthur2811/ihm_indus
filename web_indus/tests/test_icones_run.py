# test_icones.py
import mysql.connector
from datetime import datetime

# ⚙️ Paramètres BDD
DB_CONFIG = {
    "host": "localhost",
    "user": "arthur",
    "password": "#taNoniry0",
    "database": "ihm_indus",
    "port": 3306
}

def ajouter_icone_test():
    conn = None
    cursor = None
    try:
        # Connexion
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()

        print("🛠️ Test complet Icon_Library")

        icone_data = {
            "id_icon": 1,
            "nom_icon": "Test Icon",
            "description_icon": "Icône de test",
            "categorie": "Test",
            "type_source": "SVG",
            "external_name": None,
            "external_library": None,
            "fichier_path": "/icons/test_icon.svg",
            "fichier_original": "test_icon.svg",
            "mime_type": "image/svg+xml",
            "taille_fichier": 1024,
            "largeur_defaut": 64,
            "hauteur_defaut": 64,
            "couleur_defaut": "#000000",
            "date_creation": datetime.now(),
            "cree_par": 1,
            "actif": True
        }

        sql = """
        INSERT INTO Icon_Library
        (id_icon, nom_icon, description_icon, categorie, type_source, external_name, external_library,
         fichier_path, fichier_original, mime_type, taille_fichier, largeur_defaut, hauteur_defaut,
         couleur_defaut, date_creation, cree_par, actif)
        VALUES (%(id_icon)s, %(nom_icon)s, %(description_icon)s, %(categorie)s, %(type_source)s,
                %(external_name)s, %(external_library)s, %(fichier_path)s, %(fichier_original)s,
                %(mime_type)s, %(taille_fichier)s, %(largeur_defaut)s, %(hauteur_defaut)s,
                %(couleur_defaut)s, %(date_creation)s, %(cree_par)s, %(actif)s)
        """
        cursor.execute(sql, icone_data)
        conn.commit()
        print("✅ Icône test ajoutée")

        cursor.execute("SELECT id_icon, nom_icon, fichier_path FROM Icon_Library WHERE id_icon = 1")
        icone = cursor.fetchone()
        print(f"📖 Lecture icône: {icone}")

        cursor.execute("DELETE FROM Icon_Library WHERE id_icon = 1")
        conn.commit()
        print("✅ Icône test supprimée")

    except mysql.connector.Error as e:
        print(f"❌ Erreur BDD: {e}")

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

if __name__ == "__main__":
    ajouter_icone_test()
