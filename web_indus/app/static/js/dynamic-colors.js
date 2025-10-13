/**
 * Module de gestion des couleurs dynamiques
 * Chaque règle contient son propre tag - architecture simplifiée
 */

const DynamicColors = {
    // Stockage des règles par objet
    objectRules: new Map(),
    
    // Valeurs actuelles des tags
    currentTagValues: new Map(),
    
    // Mappings tag -> éléments DOM
    tagMappings: new Map(),

    /**
     * Ajouter des règles de couleur pour un objet
     * @param {string} objectId - ID de l'objet
     * @param {Array} rules - Tableau de règles avec tag inclus
     */
    setObjectRules(objectId, rules) {
        console.log(`🎨 Configuration règles pour objet ${objectId}:`, rules);
        
        // Valider que chaque règle a bien un tag
        const validRules = rules.filter(rule => {
            if (!rule.tag) {
                console.warn('⚠️ Règle sans tag ignorée:', rule);
                return false;
            }
            return true;
        });

        this.objectRules.set(objectId, validRules);
        
        // Mapper automatiquement les tags vers l'élément
        validRules.forEach(rule => {
            this.addTagMapping(rule.tag, objectId);
        });
        
        // Appliquer immédiatement les règles si on a des valeurs
        this.applyRulesForObject(objectId);
    },

    /**
     * Ajouter un mapping tag -> élément DOM
     */
    addTagMapping(tagName, elementId) {
        if (!this.tagMappings.has(tagName)) {
            this.tagMappings.set(tagName, new Set());
        }
        this.tagMappings.get(tagName).add(elementId);
        console.log(`🔗 Mapping ajouté: ${tagName} -> ${elementId}`);
    },

    /**
     * Mettre à jour la valeur d'un tag et appliquer les couleurs
     */
    onTagValueChange(tagName, newValue) {
        const oldValue = this.currentTagValues.get(tagName);
        if (oldValue === newValue) return; // Pas de changement

        console.log(`📊 Tag ${tagName}: ${oldValue} → ${newValue}`);
        this.currentTagValues.set(tagName, newValue);

        // Appliquer les couleurs pour tous les objets qui utilisent ce tag
        const elements = this.tagMappings.get(tagName);
        if (elements) {
            elements.forEach(elementId => {
                this.applyRulesForObject(elementId);
            });
        }
    },

    /**
     * Appliquer les règles de couleur pour un objet spécifique
     */
    applyRulesForObject(objectId) {
        const rules = this.objectRules.get(objectId);
        if (!rules || rules.length === 0) return;

        const element = document.getElementById(`runtime-object-${objectId}`) || 
                       document.getElementById(`object-${objectId}`);
        
        if (!element) {
            console.warn(`⚠️ Élément ${objectId} non trouvé`);
            return;
        }

        // Trier les règles par priorité (plus haute en premier)
        const sortedRules = [...rules].sort((a, b) => (b.priority || 0) - (a.priority || 0));

        // Trouver la première règle qui correspond
        for (const rule of sortedRules) {
            const tagValue = this.currentTagValues.get(rule.tag);
            
            if (tagValue !== undefined && this.evaluateCondition(tagValue, rule)) {
                this.applyStyle(element, rule);
                console.log(`✅ Règle appliquée pour ${objectId}: ${rule.tag} ${rule.operator} ${rule.value} → ${rule.color}`);
                return;
            }
        }

        // Aucune règle ne correspond - revenir au style par défaut
        this.resetToDefault(element);
    },

    /**
     * Évaluer si une condition est remplie
     */
    evaluateCondition(tagValue, rule) {
        const ruleValue = this.parseValue(rule.value, rule.type);
        
        switch (rule.operator) {
            case '==': return tagValue == ruleValue;
            case '!=': return tagValue != ruleValue;
            case '<': return Number(tagValue) < Number(ruleValue);
            case '>': return Number(tagValue) > Number(ruleValue);
            case '<=': return Number(tagValue) <= Number(ruleValue);
            case '>=': return Number(tagValue) >= Number(ruleValue);
            default: return false;
        }
    },

    /**
     * Parser une valeur selon son type
     */
    parseValue(value, type) {
        switch (type) {
            case 'BOOL': return value === 'true' || value === true;
            case 'INT':
            case 'DINT': return parseInt(value) || 0;
            case 'REAL': return parseFloat(value) || 0.0;
            default: return String(value);
        }
    },

    /**
     * Appliquer le style d'une règle
     */
    applyStyle(element, rule) {
        // Couleur de fond
        element.style.setProperty('--object-color', rule.color);
        element.style.backgroundColor = rule.color;
        
        // Couleur de bordure (légèrement plus sombre)
        const borderColor = this.adjustColor(rule.color, -20);
        element.style.borderColor = borderColor;
        
        // Animation de changement
        element.classList.add('dynamic-color-applied');
        setTimeout(() => element.classList.remove('dynamic-color-applied'), 300);
    },

    /**
     * Revenir au style par défaut
     */
    resetToDefault(element) {
        const defaultColor = element.dataset.defaultColor || element.style.getPropertyValue('--object-color-normal') || '#CCCCCC';
        element.style.setProperty('--object-color', defaultColor);
        element.style.backgroundColor = defaultColor;
        element.style.borderColor = '';
    },

    /**
     * Ajuster une couleur (éclaircir/assombrir)
     */
    adjustColor(color, percent) {
        const num = parseInt(color.replace("#", ""), 16);
        const amt = Math.round(2.55 * percent);
        const R = Math.max(0, Math.min(255, (num >> 16) + amt));
        const G = Math.max(0, Math.min(255, (num >> 8 & 0x00FF) + amt));
        const B = Math.max(0, Math.min(255, (num & 0x0000FF) + amt));
        return "#" + (0x1000000 + R * 0x10000 + G * 0x100 + B).toString(16).slice(1);
    },

    /**
     * Nettoyer les règles d'un objet
     */
    clearObjectRules(objectId) {
        this.objectRules.delete(objectId);
        
        // Supprimer les mappings
        this.tagMappings.forEach((elements, tag) => {
            elements.delete(objectId);
            if (elements.size === 0) {
                this.tagMappings.delete(tag);
            }
        });
    },

    /**
     * Débugger l'état actuel
     */
    debug() {
        console.group('🎨 État DynamicColors');
        console.log('Règles par objet:', this.objectRules);
        console.log('Valeurs des tags:', this.currentTagValues);
        console.log('Mappings tags:', this.tagMappings);
        console.groupEnd();
    }
};

// Ajouter les styles CSS pour les animations
const dynamicColorsCSS = `
.dynamic-color-applied {
    animation: dynamicColorChange 0.3s ease-in-out;
}

@keyframes dynamicColorChange {
    0% { transform: scale(1); }
    50% { transform: scale(1.02); box-shadow: 0 0 15px rgba(0,255,0,0.5); }
    100% { transform: scale(1); }
}
`;

// Injecter les styles
if (!document.getElementById('dynamic-colors-styles')) {
    const style = document.createElement('style');
    style.id = 'dynamic-colors-styles';
    style.textContent = dynamicColorsCSS;
    document.head.appendChild(style);
}

// Exporter le module
if (typeof module !== 'undefined' && module.exports) {
    module.exports = DynamicColors;
}

console.log('🎨 Module DynamicColors chargé avec architecture simplifiée (règle = tag)');