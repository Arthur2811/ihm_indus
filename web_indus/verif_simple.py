# verif_simple.py
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))

import pymysql
from dotenv import load_dotenv

load_dotenv()

try:
    connection = pymysql.connect(
        host='localhost',
        user=os.environ.get('DB_USER', 'root'),
        password=os.environ.get('DB_PASSWORD', ''),
        database=os.environ.get('DB_NAME', 'ihm_indus')
    )
    
    cursor = connection.cursor()
    
    print("=== VÉRIFICATION MIGRATION ===")
    
    # Vérifier projets
    cursor.execute("SELECT id_projet, nom_projet FROM HMI_Project")
    projets = cursor.fetchall()
    print(f"Projets: {len(projets)}")
    for p in projets:
        print(f"  - ID {p[0]}: {p[1]}")
    
    # Vérifier tags orphelins
    cursor.execute("SELECT COUNT(*) FROM Tag WHERE id_projet IS NULL")
    tags_orphelins = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM Page WHERE id_projet IS NULL") 
    pages_orphelines = cursor.fetchone()[0]
    
    print(f"\nDonnées orphelines:")
    print(f"  - Tags sans projet: {tags_orphelins}")
    print(f"  - Pages sans projet: {pages_orphelines}")
    
    # Répartition par projet
    for p in projets:
        cursor.execute("SELECT COUNT(*) FROM Tag WHERE id_projet = %s", (p[0],))
        tags_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM Page WHERE id_projet = %s", (p[0],))
        pages_count = cursor.fetchone()[0]
        
        print(f"\nProjet '{p[1]}':")
        print(f"  - Tags: {tags_count}")
        print(f"  - Pages: {pages_count}")
    
    connection.close()
    
except Exception as e:
    print(f"Erreur: {e}")