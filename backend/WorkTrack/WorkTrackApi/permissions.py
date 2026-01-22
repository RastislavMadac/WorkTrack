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