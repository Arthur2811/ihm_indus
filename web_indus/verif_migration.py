import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app, db
from app.models.modele_tag import Tag, HMIProject  
from app.models.modele_graphics import Page

app = create_app()

with app.app_context():
    print("=== VÉRIFICATION POST-MIGRATION ===")
    
    # Projets
    projets = HMIProject.query.all()
    print(f"Projets : {len(projets)}")
    for p in projets:
        print(f"  - ID {p.id_projet}: {p.nom_projet}")
    
    # Tags orphelins restants
    tags_orphelins = Tag.query.filter_by(id_projet=None).count()
    pages_orphelines = Page.query.filter_by(id_projet=None).count()
    
    print(f"\nDonnées orphelines restantes:")
    print(f"  - Tags sans projet : {tags_orphelins}")
    print(f"  - Pages sans projet : {pages_orphelines}")
    
    # Répartition par projet
    for projet in projets:
        tags_count = Tag.query.filter_by(id_projet=projet.id_projet).count()
        pages_count = Page.query.filter_by(id_projet=projet.id_projet).count()
        print(f"\nProjet '{projet.nom_projet}':")
        print(f"  - Tags : {tags_count}")
        print(f"  - Pages : {pages_count}")