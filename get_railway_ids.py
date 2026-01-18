import json
import subprocess

def get_ids():
    try:
        res = subprocess.run(["railway", "list", "--json"], capture_output=True, text=True)
        data = json.loads(res.stdout)
        for project in data:
            print(f"Project: {project.get('name')} | ID: {project.get('id')}")
            for service in project.get('services', {}).get('edges', []):
                node = service.get('node', {})
                print(f"  Service: {node.get('name')} | ID: {node.get('id')}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    get_ids()
