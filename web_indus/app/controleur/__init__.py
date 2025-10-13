from flask import Blueprint

# Blueprint principal pour les routes
main_bp = Blueprint('main', __name__)

# Import des routes (pour charger toutes les routes dans le blueprint)
from app.controleur import controleur_tags
from app.controleur import controleur_graphics
from app.controleur import controleur_user_management
from app.controleur import controleur_auth
from app.controleur import controleur_projects
from app.controleur import controleur_icons