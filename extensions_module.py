"""
KELION SUPER AI - Extensions Module
====================================
Punctele 17-25 din todo_x.md:
- Web Search
- IoT Control
- Phone Link & Wearable
- Private Network
- Offline Vault
- Legacy Mode
- Financial Guardian
- Social PR Manager
- Dream Architect
"""

import os
import json
import requests
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any
from abc import ABC, abstractmethod

# Base paths
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")


# ============================================================================
# 17. WEB SEARCH
# ============================================================================

class WebSearchEngine:
    """
    Motor de căutare web pentru Kelion.
    Folosește diverse API-uri pentru a obține informații live.
    """
    
    # API-uri de căutare (în ordinea preferinței)
    SEARCH_APIS = {
        "duckduckgo": "https://api.duckduckgo.com/",
        "serper": "https://google.serper.dev/search",  # Necesită SERPER_API_KEY
    }
    
    def __init__(self):
        self.serper_key = os.getenv("SERPER_API_KEY", "")
    
    def search(self, query: str, num_results: int = 5) -> Dict:
        """
        Caută pe web și returnează rezultate.
        """
        # Încearcă Serper (Google) dacă avem cheie
        if self.serper_key:
            return self._search_serper(query, num_results)
        
        # Fallback la DuckDuckGo (gratuit, fără cheie)
        return self._search_duckduckgo(query)
    
    def _search_duckduckgo(self, query: str) -> Dict:
        """Căutare cu DuckDuckGo Instant Answers."""
        try:
            params = {
                "q": query,
                "format": "json",
                "no_html": 1,
                "skip_disambig": 1
            }
            response = requests.get(
                "https://api.duckduckgo.com/",
                params=params,
                timeout=10
            )
            data = response.json()
            
            results = []
            
            # Abstract (răspuns direct)
            if data.get("Abstract"):
                results.append({
                    "title": data.get("Heading", ""),
                    "snippet": data.get("Abstract"),
                    "url": data.get("AbstractURL", ""),
                    "source": data.get("AbstractSource", "")
                })
            
            # Related topics
            for topic in data.get("RelatedTopics", [])[:5]:
                if isinstance(topic, dict) and topic.get("Text"):
                    results.append({
                        "title": "",
                        "snippet": topic.get("Text"),
                        "url": topic.get("FirstURL", "")
                    })
            
            return {
                "query": query,
                "results": results,
                "source": "duckduckgo"
            }
            
        except Exception as e:
            return {"error": str(e)}
    
    def _search_serper(self, query: str, num_results: int) -> Dict:
        """Căutare cu Serper (Google)."""
        try:
            headers = {
                "X-API-KEY": self.serper_key,
                "Content-Type": "application/json"
            }
            payload = {
                "q": query,
                "num": num_results
            }
            
            response = requests.post(
                "https://google.serper.dev/search",
                headers=headers,
                json=payload,
                timeout=10
            )
            data = response.json()
            
            results = []
            for item in data.get("organic", []):
                results.append({
                    "title": item.get("title"),
                    "snippet": item.get("snippet"),
                    "url": item.get("link")
                })
            
            return {
                "query": query,
                "results": results,
                "source": "google"
            }
            
        except Exception as e:
            return {"error": str(e)}
    
    def get_news(self, topic: str = "technology") -> Dict:
        """Obține știri recente."""
        return self.search(f"{topic} news today")
    
    def get_weather(self, location: str = "Bucharest") -> Dict:
        """Obține vremea."""
        return self.search(f"weather {location} today")
    
    def get_stock_price(self, symbol: str) -> Dict:
        """Obține prețul unei acțiuni."""
        return self.search(f"{symbol} stock price today")


# ============================================================================
# 18. IoT CONTROL
# ============================================================================

class IoTController:
    """
    Controlează dispozitive IoT (Philips Hue, Home Assistant, etc.)
    """
    
    def __init__(self):
        self.hue_bridge_ip = os.getenv("HUE_BRIDGE_IP", "")
        self.hue_api_key = os.getenv("HUE_API_KEY", "")
        self.home_assistant_url = os.getenv("HOME_ASSISTANT_URL", "")
        self.home_assistant_token = os.getenv("HOME_ASSISTANT_TOKEN", "")
        
        self.devices: Dict[str, Dict] = {}
        self._discover_devices()
    
    def _discover_devices(self):
        """Descoperă dispozitivele disponibile."""
        if self.hue_bridge_ip and self.hue_api_key:
            self._discover_hue_devices()
        if self.home_assistant_url and self.home_assistant_token:
            self._discover_ha_devices()
    
    def _discover_hue_devices(self):
        """Descoperă lămpi Philips Hue."""
        try:
            response = requests.get(
                f"http://{self.hue_bridge_ip}/api/{self.hue_api_key}/lights",
                timeout=5
            )
            lights = response.json()
            
            for light_id, light_data in lights.items():
                self.devices[f"hue_{light_id}"] = {
                    "id": light_id,
                    "name": light_data.get("name"),
                    "type": "light",
                    "platform": "hue",
                    "state": light_data.get("state", {})
                }
        except:
            pass
    
    def _discover_ha_devices(self):
        """Descoperă dispozitive Home Assistant."""
        try:
            headers = {
                "Authorization": f"Bearer {self.home_assistant_token}",
                "Content-Type": "application/json"
            }
            response = requests.get(
                f"{self.home_assistant_url}/api/states",
                headers=headers,
                timeout=5
            )
            states = response.json()
            
            for state in states:
                entity_id = state.get("entity_id", "")
                if entity_id.startswith(("light.", "switch.", "climate.")):
                    self.devices[entity_id] = {
                        "id": entity_id,
                        "name": state.get("attributes", {}).get("friendly_name", entity_id),
                        "type": entity_id.split(".")[0],
                        "platform": "home_assistant",
                        "state": state.get("state")
                    }
        except:
            pass
    
    def list_devices(self) -> Dict:
        """Listează toate dispozitivele disponibile."""
        return {
            "devices": list(self.devices.values()),
            "count": len(self.devices)
        }
    
    def control_device(self, device_id: str, action: str, params: Dict = None) -> Dict:
        """
        Controlează un dispozitiv.
        
        Args:
            device_id: ID-ul dispozitivului
            action: Acțiunea (on, off, brightness, color, etc.)
            params: Parametri adiționale
        """
        params = params or {}
        device = self.devices.get(device_id)
        
        if not device:
            return {"error": f"Dispozitiv {device_id} negăsit"}
        
        if device["platform"] == "hue":
            return self._control_hue(device["id"], action, params)
        elif device["platform"] == "home_assistant":
            return self._control_ha(device["id"], action, params)
        
        return {"error": "Platformă necunoscută"}
    
    def _control_hue(self, light_id: str, action: str, params: Dict) -> Dict:
        """Controlează o lampă Hue."""
        state = {}
        
        if action == "on":
            state["on"] = True
        elif action == "off":
            state["on"] = False
        elif action == "brightness":
            state["bri"] = int(params.get("value", 254))
        elif action == "color":
            # Convertește culoare hex la hue/sat
            color = params.get("color", "#ffffff")
            state["on"] = True
            # Simplificat - în producție ar trebui conversie reală
            if color.lower() in ["red", "#ff0000"]:
                state["hue"] = 0
                state["sat"] = 254
            elif color.lower() in ["blue", "#0000ff"]:
                state["hue"] = 46920
                state["sat"] = 254
            elif color.lower() in ["green", "#00ff00"]:
                state["hue"] = 25500
                state["sat"] = 254
        
        try:
            response = requests.put(
                f"http://{self.hue_bridge_ip}/api/{self.hue_api_key}/lights/{light_id}/state",
                json=state,
                timeout=5
            )
            return {"success": True, "response": response.json()}
        except Exception as e:
            return {"error": str(e)}
    
    def _control_ha(self, entity_id: str, action: str, params: Dict) -> Dict:
        """Controlează un dispozitiv Home Assistant."""
        service = "turn_on" if action == "on" else "turn_off"
        domain = entity_id.split(".")[0]
        
        try:
            headers = {
                "Authorization": f"Bearer {self.home_assistant_token}",
                "Content-Type": "application/json"
            }
            payload = {"entity_id": entity_id}
            payload.update(params)
            
            response = requests.post(
                f"{self.home_assistant_url}/api/services/{domain}/{service}",
                headers=headers,
                json=payload,
                timeout=5
            )
            return {"success": True}
        except Exception as e:
            return {"error": str(e)}
    
    def create_scene(self, name: str, devices_states: List[Dict]) -> Dict:
        """
        Creează o scenă (grup de stări pentru dispozitive).
        """
        scene = {
            "name": name,
            "devices": devices_states,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        scenes_file = os.path.join(DATA_DIR, "iot_scenes.json")
        scenes = []
        
        if os.path.exists(scenes_file):
            with open(scenes_file, 'r') as f:
                scenes = json.load(f)
        
        scenes.append(scene)
        
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(scenes_file, 'w') as f:
            json.dump(scenes, f, indent=2)
        
        return {"success": True, "scene": scene}
    
    def activate_scene(self, name: str) -> Dict:
        """Activează o scenă salvată."""
        scenes_file = os.path.join(DATA_DIR, "iot_scenes.json")
        
        if not os.path.exists(scenes_file):
            return {"error": "Nu există scene salvate"}
        
        with open(scenes_file, 'r') as f:
            scenes = json.load(f)
        
        scene = next((s for s in scenes if s["name"].lower() == name.lower()), None)
        if not scene:
            return {"error": f"Scena '{name}' nu a fost găsită"}
        
        results = []
        for device_state in scene.get("devices", []):
            result = self.control_device(
                device_state["device_id"],
                device_state["action"],
                device_state.get("params", {})
            )
            results.append(result)
        
        return {"success": True, "results": results}


# ============================================================================
# 22. FINANCIAL GUARDIAN
# ============================================================================

class FinancialGuardian:
    """
    Monitorizează piețele financiare și crypto.
    """
    
    def __init__(self):
        self.alerts: List[Dict] = []
        self.portfolio: Dict[str, Dict] = {}
        self._load_portfolio()
    
    def _load_portfolio(self):
        """Încarcă portofoliul salvat."""
        portfolio_file = os.path.join(DATA_DIR, "portfolio.json")
        if os.path.exists(portfolio_file):
            with open(portfolio_file, 'r') as f:
                data = json.load(f)
                self.portfolio = data.get("holdings", {})
                self.alerts = data.get("alerts", [])
    
    def _save_portfolio(self):
        """Salvează portofoliul."""
        portfolio_file = os.path.join(DATA_DIR, "portfolio.json")
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(portfolio_file, 'w') as f:
            json.dump({
                "holdings": self.portfolio,
                "alerts": self.alerts,
                "last_updated": datetime.now(timezone.utc).isoformat()
            }, f, indent=2)
    
    def get_crypto_price(self, symbol: str) -> Dict:
        """Obține prețul unei criptomonede."""
        try:
            response = requests.get(
                f"https://api.coingecko.com/api/v3/simple/price",
                params={
                    "ids": symbol.lower(),
                    "vs_currencies": "usd,eur",
                    "include_24hr_change": "true"
                },
                timeout=10
            )
            data = response.json()
            
            if symbol.lower() in data:
                price_data = data[symbol.lower()]
                return {
                    "symbol": symbol.upper(),
                    "price_usd": price_data.get("usd"),
                    "price_eur": price_data.get("eur"),
                    "change_24h": price_data.get("usd_24h_change")
                }
            
            return {"error": f"Simbol {symbol} negăsit"}
            
        except Exception as e:
            return {"error": str(e)}
    
    def add_holding(self, symbol: str, amount: float, buy_price: float) -> Dict:
        """Adaugă un activ în portofoliu."""
        self.portfolio[symbol.upper()] = {
            "amount": amount,
            "buy_price": buy_price,
            "added_at": datetime.now(timezone.utc).isoformat()
        }
        self._save_portfolio()
        return {"success": True, "holding": self.portfolio[symbol.upper()]}
    
    def get_portfolio_value(self) -> Dict:
        """Calculează valoarea totală a portofoliului."""
        total_value = 0
        total_cost = 0
        holdings = []
        
        for symbol, data in self.portfolio.items():
            price_data = self.get_crypto_price(symbol)
            if "price_usd" in price_data:
                current_value = data["amount"] * price_data["price_usd"]
                cost = data["amount"] * data["buy_price"]
                pnl = current_value - cost
                
                holdings.append({
                    "symbol": symbol,
                    "amount": data["amount"],
                    "current_price": price_data["price_usd"],
                    "current_value": current_value,
                    "cost": cost,
                    "pnl": pnl,
                    "pnl_percent": (pnl / cost * 100) if cost > 0 else 0
                })
                
                total_value += current_value
                total_cost += cost
        
        return {
            "total_value": total_value,
            "total_cost": total_cost,
            "total_pnl": total_value - total_cost,
            "total_pnl_percent": ((total_value - total_cost) / total_cost * 100) if total_cost > 0 else 0,
            "holdings": holdings
        }
    
    def set_price_alert(self, symbol: str, target_price: float, direction: str = "above") -> Dict:
        """Setează o alertă de preț."""
        alert = {
            "symbol": symbol.upper(),
            "target_price": target_price,
            "direction": direction,  # "above" sau "below"
            "created_at": datetime.now(timezone.utc).isoformat(),
            "triggered": False
        }
        self.alerts.append(alert)
        self._save_portfolio()
        return {"success": True, "alert": alert}
    
    def check_alerts(self) -> List[Dict]:
        """Verifică dacă au fost declanșate alerte."""
        triggered = []
        
        for alert in self.alerts:
            if alert["triggered"]:
                continue
            
            price_data = self.get_crypto_price(alert["symbol"])
            if "price_usd" not in price_data:
                continue
            
            current_price = price_data["price_usd"]
            
            should_trigger = False
            if alert["direction"] == "above" and current_price >= alert["target_price"]:
                should_trigger = True
            elif alert["direction"] == "below" and current_price <= alert["target_price"]:
                should_trigger = True
            
            if should_trigger:
                alert["triggered"] = True
                alert["triggered_at"] = datetime.now(timezone.utc).isoformat()
                alert["triggered_price"] = current_price
                triggered.append(alert)
        
        if triggered:
            self._save_portfolio()
        
        return triggered


# ============================================================================
# 21. OFFLINE VAULT
# ============================================================================

class OfflineVault:
    """
    Bază de cunoștințe offline pentru situații de urgență.
    """
    
    VAULT_FILE = os.path.join(DATA_DIR, "offline_vault.json")
    
    def __init__(self):
        self.knowledge: Dict[str, str] = {}
        self._load_vault()
    
    def _load_vault(self):
        """Încarcă vault-ul."""
        if os.path.exists(self.VAULT_FILE):
            with open(self.VAULT_FILE, 'r', encoding='utf-8') as f:
                self.knowledge = json.load(f)
    
    def _save_vault(self):
        """Salvează vault-ul."""
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(self.VAULT_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.knowledge, f, ensure_ascii=False, indent=2)
    
    def add_knowledge(self, topic: str, content: str) -> Dict:
        """Adaugă cunoștințe în vault."""
        self.knowledge[topic.lower()] = {
            "content": content,
            "added_at": datetime.now(timezone.utc).isoformat()
        }
        self._save_vault()
        return {"success": True, "topic": topic}
    
    def search(self, query: str) -> List[Dict]:
        """Caută în vault."""
        query_lower = query.lower()
        results = []
        
        for topic, data in self.knowledge.items():
            if query_lower in topic or query_lower in data.get("content", "").lower():
                results.append({
                    "topic": topic,
                    "content": data.get("content"),
                    "relevance": 1.0 if query_lower in topic else 0.5
                })
        
        return sorted(results, key=lambda x: x["relevance"], reverse=True)
    
    def get_survival_basics(self) -> Dict:
        """Returnează cunoștințe de bază de supraviețuire."""
        basics = {
            "water_purification": "Fierbe apa 1 minut la nivelul mării, +1 minut pentru fiecare 300m altitudine. Alternativ: 2 picături de clor/litru, așteaptă 30 min.",
            "first_aid_bleeding": "Aplică presiune directă pe rană cu bandaj curat. Ridică membrul deasupra inimii. Dacă sângele trece prin bandaj, adaugă altul deasupra.",
            "fire_starting": "Adună material uscat în 3 categorii: iască (frunze uscate), lemn subțire (cât un creion), lemn gros. Construiește de la mic la mare.",
            "emergency_shelter": "Caută adăpost natural (peșteră, copac căzut). Izolează de sol cu frunze/crengi. Acoperă cu materiale impermeabile."
        }
        return basics


# ============================================================================
# 22. LEGACY MODE (Digital Twin)
# ============================================================================

class LegacyMode:
    """
    Creează și gestionează "geamănul digital" al utilizatorului.
    """
    
    LEGACY_FILE = os.path.join(DATA_DIR, "digital_twin.json")
    
    def __init__(self):
        self.profile: Dict = {}
        self.memories: List[Dict] = []
        self.style_patterns: Dict = {}
        self._load_legacy()
    
    def _load_legacy(self):
        """Încarcă profilul legacy."""
        if os.path.exists(self.LEGACY_FILE):
            with open(self.LEGACY_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.profile = data.get("profile", {})
                self.memories = data.get("memories", [])
                self.style_patterns = data.get("style_patterns", {})
    
    def _save_legacy(self):
        """Salvează profilul legacy."""
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(self.LEGACY_FILE, 'w', encoding='utf-8') as f:
            json.dump({
                "profile": self.profile,
                "memories": self.memories[-1000:],  # Ultimele 1000
                "style_patterns": self.style_patterns,
                "last_updated": datetime.now(timezone.utc).isoformat()
            }, f, ensure_ascii=False, indent=2)
    
    def update_profile(self, key: str, value: Any) -> Dict:
        """Actualizează un aspect al profilului."""
        self.profile[key] = value
        self._save_legacy()
        return {"success": True, "profile": self.profile}
    
    def add_memory(self, memory: str, importance: int = 5) -> Dict:
        """Adaugă o amintire."""
        self.memories.append({
            "content": memory,
            "importance": importance,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        self._save_legacy()
        return {"success": True}
    
    def learn_style(self, text_samples: List[str]) -> Dict:
        """Învață stilul de scriere din exemple."""
        # Analiză simplificată a stilului
        total_words = 0
        word_freq: Dict[str, int] = {}
        avg_sentence_length = 0
        sentences = 0
        
        for sample in text_samples:
            words = sample.split()
            total_words += len(words)
            
            for word in words:
                word_lower = word.lower().strip(".,!?")
                word_freq[word_lower] = word_freq.get(word_lower, 0) + 1
            
            # Numără propozițiile
            sentences += sample.count('.') + sample.count('!') + sample.count('?')
        
        if sentences > 0:
            avg_sentence_length = total_words / sentences
        
        self.style_patterns = {
            "avg_sentence_length": avg_sentence_length,
            "favorite_words": sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:20],
            "total_samples": len(text_samples)
        }
        self._save_legacy()
        
        return {"success": True, "style_learned": True}
    
    def generate_response_as_twin(self, prompt: str) -> Dict:
        """Generează un răspuns în stilul utilizatorului."""
        if not ANTHROPIC_API_KEY:
            return {"error": "API key not configured"}
        
        # Construiește system prompt bazat pe profil
        twin_context = f"""Ești o copie digitală a unei persoane cu următorul profil:
        
PROFIL:
{json.dumps(self.profile, indent=2, ensure_ascii=False)}

AMINTIRI IMPORTANTE:
{json.dumps([m for m in self.memories if m.get('importance', 0) >= 7][-10:], indent=2, ensure_ascii=False)}

STIL DE COMUNICARE:
- Lungime medie propoziție: {self.style_patterns.get('avg_sentence_length', 15)} cuvinte
- Cuvinte preferate: {[w[0] for w in self.style_patterns.get('favorite_words', [])[:10]]}

Răspunde exact cum ar răspunde această persoană."""

        headers = {
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        
        payload = {
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 1024,
            "system": twin_context,
            "messages": [{"role": "user", "content": prompt}]
        }
        
        try:
            response = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json=payload,
                timeout=30
            )
            data = response.json()
            
            text = ""
            for block in data.get("content", []):
                if block.get("type") == "text":
                    text += block.get("text", "")
            
            return {"response": text, "as_twin": True}
            
        except Exception as e:
            return {"error": str(e)}


# ============================================================================
# INSTANȚE GLOBALE
# ============================================================================

_web_search = WebSearchEngine()
_iot_controller = IoTController()
_financial_guardian = FinancialGuardian()
_offline_vault = OfflineVault()
_legacy_mode = LegacyMode()


def get_web_search() -> WebSearchEngine:
    return _web_search

def get_iot_controller() -> IoTController:
    return _iot_controller

def get_financial_guardian() -> FinancialGuardian:
    return _financial_guardian

def get_offline_vault() -> OfflineVault:
    return _offline_vault

def get_legacy_mode() -> LegacyMode:
    return _legacy_mode


__all__ = [
    'WebSearchEngine',
    'IoTController',
    'FinancialGuardian',
    'OfflineVault',
    'LegacyMode',
    'get_web_search',
    'get_iot_controller',
    'get_financial_guardian',
    'get_offline_vault',
    'get_legacy_mode'
]
