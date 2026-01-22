from django.test import TestCase
from rest_framework.test import APIClient
from datetime import date, time
from .models import Employees, TypeShift, PlannedShifts

class ErrorMessagesTest(TestCase):
    def setUp(self):
        """
        Príprava dát pred každým testom.
        """
        # 1. Nastavenie API klienta a prihlásenie manažéra
        self.client = APIClient()
        self.user = Employees.objects.create(
            username="manazer", 
            role="manager", 
            personal_number="111"
        )
        self.client.force_authenticate(user=self.user) 
        
        # 2. Vytvorenie typu smeny (Ranná)
        # --- TU BOLA CHYBA: Doplnil som duration_time=8.0 ---
        self.ranna = TypeShift.objects.create(
            nameShift="Ranná", 
            start_time=time(6, 0), 
            end_time=time(14, 0),
            duration_time=8.0  # <--- TOTO JE POVINNÉ POLE
        )
        
        # 3. Vytvorenie prvej (existujúcej) smeny v DB
        PlannedShifts.objects.create(
            user=self.user, 
            date=date(2025, 4, 5), 
            type_shift=self.ranna
        )

    def test_conflict_error_message(self):
        """
        Testuje, či backend vráti 400 a správny text, keď sa smeny prekrývajú.
        """
        
        # Pokúsime sa vytvoriť NOVÚ smenu v ten istý čas pre toho istého usera
        data = {
            "user": self.user.id,
            "date": "2025-04-05",     # Rovnaký deň
            "type_shift": self.ranna.id # Rovnaký čas (6:00 - 14:00)
        }
        
        # Pošleme POST na vytvorenie
        response = self.client.post('/api/plannedshift/', data)
        
        # --- OVERENIA ---
        
        # 1. Musí vrátiť chybu 400 Bad Request
        self.assertEqual(response.status_code, 400, f"Očakával som 400, prišlo {response.status_code}. Data: {response.data}")
        
        # 2. Musí obsahovať kľúč 'non_field_errors' (tam sme to v serializeri poslali)
        self.assertIn("non_field_errors", response.data)
        
        # 3. Text chyby musí obsahovať naše slovo "Konflikt"
        error_msg = response.data["non_field_errors"][0]
        
        self.assertIn("Konflikt: Zamestnanec už má smenu", error_msg)
        self.assertIn("Ranná", error_msg) # Malo by tam byť aj meno kolíznej smeny