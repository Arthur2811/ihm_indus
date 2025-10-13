import os
import sys
from pathlib import Path

# Ajouter le répertoire racine au PYTHONPATH
root_dir = Path(__file__).parent
sys.path.insert(0, str(root_dir))

from app import create_app, db

# Création de l'application Flask
app = create_app(os.getenv('FLASK_ENV', 'development'))

@app.shell_context_processor
def make_shell_context():
    from app.models.modele_tag import Tag
    return {
        'db': db,
        'Tag': Tag
    }



@app.cli.command()
def init_db():
    try:
        db.create_all()
        print("Base de données initialisée")
    except Exception as e:
        print(f"Erreur initialisation DB: {e}")

@app.cli.command()
def create_test_tags():
    try:
        from app.models.modele_tag import Tag
        Tag.creer_tags_par_defaut()
        print("Tags de test créés")
    except Exception as e:
        print(f"Erreur création tags: {e}")

if __name__ == '__main__':
    print("=" * 60)
    print("IHM INDUSTRIELLE ARTHUR - DÉMARRAGE")
    print("=" * 60)
    
    try:
        print(f"Mode: {app.config.get('FLASK_ENV', 'development')}")
        print(f"Debug: {app.config.get('DEBUG', False)}")
        print(f"Communication: {app.config.get('MODE_COMMUNICATION', 'REEL')}")
        print(f"Automate IP: {app.config.get('AUTOMATE_IP', '192.168.0.1')}")
        print("-" * 60)
        print("Interface web: http://localhost:5000")
        print("API REST: http://localhost:5000/api/")
        print("=" * 60)
        
        # Démarre l'application Flask
        app.run(
            host='0.0.0.0',
            port=5000,
            debug=app.config.get('DEBUG', False),
            use_reloader=True,
            threaded=True
        )
        
    except KeyboardInterrupt:
        print("\nArrêt de l'application demandé")
    except Exception as e:
        print(f"Erreur lors du démarrage: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("IHM Industrielle Arthur - Arrêtée")