"""Railway Deploy Manager (API-first)."""
import os
import logging
from typing import Dict, Any
import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RailwayAPIDeployManager:
    def __init__(self):
        self.token = os.getenv("RAILWAY_TOKEN")
        self.service_id = os.getenv("RAILWAY_SERVICE_ID")
        self.project_id = os.getenv("RAILWAY_PROJECT_ID")
        self.domain = os.getenv("RAILWAY_DOMAIN")
        self.api_base = "https://backboard.railway.app/graphql"

    def get_config_status(self) -> Dict[str, Any]:
        return {
            "railway_token_set": bool(self.token),
            "service_id_set": bool(self.service_id),
            "project_id_set": bool(self.project_id),
            "domain_set": bool(self.domain),
            "service_id": self.service_id if self.service_id else None,
            "project_id": self.project_id if self.project_id else None,
            "domain": self.domain if self.domain else None,
        }

    def get_service_info(self) -> Dict[str, Any]:
        return {
            "service_id": self.service_id,
            "project_id": self.project_id,
            "domain": self.domain,
            "service_url": f"https://{self.domain}" if self.domain else None,
            "dashboard_url": f"https://railway.com/project/{self.project_id}/service/{self.service_id}"
            if self.project_id and self.service_id else None,
        }

    def deploy(self) -> Dict[str, Any]:
        if not self.token or not self.service_id:
            return {"success": False, "error": "Missing RAILWAY_TOKEN or RAILWAY_SERVICE_ID"}

        headers = {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}
        mutation = f'''
        mutation {{
          serviceInstanceRedeploy(serviceId: "{self.service_id}") {{
            id
          }}
        }}
        '''
        r = requests.post(self.api_base, json={"query": mutation}, headers=headers, timeout=30)
        if r.status_code != 200:
            return {"success": False, "error": f"Railway API error: {r.status_code}", "details": r.text}
        return {"success": True, "message": "Deploy triggered", "service_id": self.service_id, "domain": self.domain}

_deploy_manager = None

def get_deploy_manager() -> RailwayAPIDeployManager:
    global _deploy_manager
    if _deploy_manager is None:
        _deploy_manager = RailwayAPIDeployManager()
    return _deploy_manager
