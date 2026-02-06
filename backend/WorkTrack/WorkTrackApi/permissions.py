from rest_framework import permissions

class IsManagerOrReadOnly(permissions.BasePermission):
    """
    Vlastné oprávnenie:
    - Worker (Robotník): Môže iba čítať (GET, HEAD, OPTIONS).
    - Manager / Admin: Môžu robiť všetko (POST, PUT, DELETE).
    """

    def has_permission(self, request, view):
        # 1. Ak používateľ nie je prihlásený, zamietneme prístup
        if not request.user or not request.user.is_authenticated:
            return False

        # 2. Ak je metóda "bezpečná" (GET, HEAD, OPTIONS), povolíme prístup každému prihlásenému
        if request.method in permissions.SAFE_METHODS:
            return True

        # 3. Ak je metóda "zapisovacia" (POST, PUT, DELETE),
        # povolíme to len ak má rolu 'manager' alebo 'admin'
        # (Predpokladáme, že máš v modeli pole 'role')
        return request.user.role in ['manager', 'admin']
    


class IsManagerOrWorkerExchangeOnly(permissions.BasePermission):
    """
    1. Worker môže čítať (GET).
    2. Worker môže vykonať akciu 'request_exchange'.
    3. Worker NEMÔŽE vytvárať, upravovať ani mazať smeny.
    4. Manager a Admin môžu všetko.
    """
    def has_permission(self, request, view):
        # Ak používateľ nie je prihlásený, zakáž všetko
        if not request.user or not request.user.is_authenticated:
            return False

        # Admin a Manager môžu všetko
        if request.user.role in ['admin', 'manager']:
            return True

        # --- LOGIKA PRE WORKERA ---
        
        # 1. Povolíme bezpečné metódy (GET, HEAD, OPTIONS) - čítanie
        if request.method in permissions.SAFE_METHODS:
            return True

        # 2. Povolíme ŠPECIFICKÚ akciu 'request_exchange'
        # view.action obsahuje názov metódy pod @action
        if view.action == 'request_exchange':
            return True

        # 3. Všetko ostatné (Create, Update, Delete, decide_exchange) je pre Workera ZAKÁZANÉ
        return False

    def has_object_permission(self, request, view, obj):
        # Táto metóda kontroluje prístup k konkrétnemu objektu (smena ID 5)
        
        # Admin a Manager môžu všetko
        if request.user.role in ['admin', 'manager']:
            return True

        # Worker môže čítať len svoje smeny (to už rieši get_queryset, ale poistíme to)
        if request.method in permissions.SAFE_METHODS:
            return obj.user == request.user

        # Worker môže žiadať o výmenu LEN SVOJEJ smeny
        if view.action == 'request_exchange':
            return obj.user == request.user

        return False