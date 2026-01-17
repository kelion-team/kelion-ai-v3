
import sys
import os
from claude_brain import call_claude

# Prompt for the AI to write the procedure
prompt = """
Ești Kelion AI. Administratorul ți-a cerut să scrii "Procedura de Securitate și Mentenanță" pentru a fi publicată pe site.
Trebuie să explici utilizatorilor (public):
1. Cum le protejezi datele (K-Armor, criptare).
2. Cine are acces la date (Doar Admin, nimeni altcineva).
3. Cum funcționează sistemul tău de audit în timp real.
4. Faptul că ești monitorizat 24/7.

Ton: Profesional, Sigur, Transparent, Futuristic.
Scrie textul în format HTML (doar contentul, fără <html>/<body> tags), folosind titluri <h2>, <h3> și paragrafe <p>.
"""

try:
    response = call_claude(prompt, include_context=False)
    print(response.get("text", "Eroare la generarea procedurii."))
except Exception as e:
    print(f"Error: {e}")
