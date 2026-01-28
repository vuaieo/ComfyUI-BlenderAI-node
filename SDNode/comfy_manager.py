import json
import urllib.request
import urllib.parse
from .manager import get_url
from ..utils import logger

class ComfyManager:
    """
    Client for interacting with the ComfyUI-Manager API.
    """
    
    @staticmethod
    def _api_get(endpoint, params=None):
        url = f"{get_url()}/{endpoint}"
        if params:
            url += "?" + urllib.parse.urlencode(params)
        logger.debug(f"ComfyManager GET: {url}")
        try:
            with urllib.request.urlopen(url, timeout=10) as response:
                body = response.read().decode()
                logger.debug(f"ComfyManager Response: {body[:200]}")
                if not body:
                    return {}
                return json.loads(body)
        except Exception as e:
            logger.error(f"ComfyManager GET Error ({endpoint}): {e}")
            return None

    @staticmethod
    def _api_post(endpoint, data=None):
        url = f"{get_url()}/{endpoint}"
        logger.debug(f"ComfyManager POST: {url} | Data: {json.dumps(data)}")
        try:
            req = urllib.request.Request(
                url, 
                data=json.dumps(data).encode() if data else b"",
                headers={'Content-Type': 'application/json'}
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                body = response.read().decode()
                logger.debug(f"ComfyManager Response: {body[:200]}")
                if not body:
                    return {}
                return json.loads(body)
        except Exception as e:
            logger.error(f"ComfyManager POST Error ({endpoint}): {e}")
            return None

    # CUSTOM NODES
    @classmethod
    def get_custom_node_list(cls, mode="cache"):
        return cls._api_get("customnode/getlist", {"mode": mode})

    @classmethod
    def install_custom_node_queue(cls, channel, author, title, url, node_id=None, version="nightly"):
        # This is for newer versions with a background task queue
        # Using "nightly" as default instead of "unknown" because ComfyUI-Manager 
        # often crashes with 'KeyError: files' when version is "unknown"
        data = {
            "channel": channel,
            "author": author,
            "title": title,
            "repository": url,
            "id": node_id if node_id else title, 
            "version": version if version else "nightly",
            "files": [url],
            "mode": "cache"
        }
        res = cls._api_post("manager/queue/install", data)
        # We MUST start the queue after adding a task
        cls.start_install_queue()
        return res
    
    @classmethod
    def install_custom_node_git(cls, url):
        # This is a direct git install (POST text)
        url_api = f"{get_url()}/customnode/install/git_url"
        logger.debug(f"ComfyManager Direct Git: {url_api}")
        try:
            req = urllib.request.Request(url_api, data=url.encode(), headers={'Content-Type': 'text/plain'})
            with urllib.request.urlopen(req, timeout=30) as response:
                return {"success": True}
        except Exception as e:
            logger.error(f"ComfyManager Git Install Error: {e}")
            return None

    @classmethod
    def start_install_queue(cls):
        # Starts the background worker thread for tasks added to the queue
        return cls._api_get("manager/queue/start")

    @classmethod
    def uninstall_custom_node(cls, url, title, node_id=None, version="nightly"):
        data = {
            "repository": url,
            "id": node_id if node_id else title,
            "version": version if version else "nightly",
            "files": [url]
        }
        return cls._api_post("manager/queue/uninstall", data)

    @classmethod
    def update_custom_node(cls, url, title, node_id=None, version="nightly"):
        data = {
            "repository": url,
            "id": node_id if node_id else title,
            "version": version,
            "files": [url]
        }
        return cls._api_post("manager/queue/update", data)

    @classmethod
    def get_missing_nodes(cls, workflow_data):
        """
        Detect missing nodes from a workflow JSON locally.
        """
        try:
            # 1. Get current installed/object_info from ComfyUI
            from .manager import get_url
            url = f"{get_url()}/object_info"
            object_info = {}
            try:
                with urllib.request.urlopen(url, timeout=10) as response:
                    content = response.read().decode('utf-8')
                    object_info = json.loads(content)
            except Exception:
                logger.info("ComfyManager: Server offline, assuming all nodes in workflow are missing.")
            
            # 2. Get global node->package mappings from Manager
            mappings = {}
            try:
                mappings = cls.get_mappings(mode="cache")
            except Exception:
                # Fallback: Read local extension-node-map.json from ComfyUI-Manager folder
                from ..preference import get_pref
                try:
                    comfy_path = Path(get_pref().model_path)
                    m_path = comfy_path / "custom_nodes" / "ComfyUI-Manager" / "extension-node-map.json"
                    if m_path.exists():
                        mappings = json.loads(m_path.read_text(encoding="utf-8"))
                        logger.info(f"ComfyManager: Loaded {len(mappings)} mappings from local file.")
                except Exception as e:
                    logger.error(f"ComfyManager: Fallback mappings load failed: {e}")

            if not mappings:
                logger.error("ComfyManager: Failed to fetch mappings for missing node detection.")
                return {"missing_nodes": []}

            # 3. Identify which node types in the workflow are missing from object_info
            # Workflow format can be either {nodes: [...]} or a direct prompt dict
            missing_types = set()
            nodes_in_wf = workflow_data.get("nodes", [])
            if not nodes_in_wf and isinstance(workflow_data, dict):
                # Fallback for prompt format
                for node_id in workflow_data:
                    node = workflow_data[node_id]
                    if isinstance(node, dict) and "class_type" in node:
                        node_type = node["class_type"]
                        if node_type not in object_info:
                            missing_types.add(node_type)
            else:
                logger.info(f"ComfyManager: Scanning workflow with {len(nodes_in_wf)} nodes")
                for node in nodes_in_wf:
                    node_type = node.get("type")
                    if node_type == "SDN_MissingNode":
                        props = node.get("properties", {})
                        node_type = props.get("missing_type")
                        logger.info(f"ComfyManager: Found SDN_MissingNode proxy for: {node_type}")
                    if node_type and node_type not in object_info:
                        logger.info(f"ComfyManager: Identified missing type: {node_type}")
                        missing_types.add(node_type)
            
            logger.info(f"ComfyManager: Total missing types found: {missing_types}")
            if not missing_types:
                return {"missing_nodes": []}

            # 4. Cross-reference missing types with mappings to find required packages
            required_packages = []
            seen_urls = set()

            for pkg_url, data in mappings.items():
                node_list = data[0] if isinstance(data, list) and len(data) > 0 else []
                for m_type in missing_types:
                    if m_type in node_list:
                        if pkg_url not in seen_urls:
                            meta = data[1] if isinstance(data, list) and len(data) > 1 else {}
                            title = meta.get("title_aux", pkg_url.split("/")[-1])
                            
                            required_packages.append({
                                "title": title,
                                "url": pkg_url,
                                "author": "Unknown",
                                "node_id": title,
                                "reference": pkg_url,
                                "version": "nightly"
                            })
                            seen_urls.add(pkg_url)
                            break
            
            return {"missing_nodes": required_packages}

        except Exception as e:
            logger.error(f"ComfyManager: Error in local get_missing_nodes: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {"missing_nodes": []}

    @classmethod
    def get_mappings(cls, mode="cache"):
        return cls._api_get("customnode/getmappings", {"mode": mode})

    # MODELS
    @classmethod
    def get_model_list(cls, mtype="all", mode="cache"):
        return cls._api_get("externalmodel/getlist", {"mode": mode})

    @classmethod
    def install_model(cls, model_data):
        return cls._api_post("manager/queue/install_model", model_data)

    # SYSTEM
    @classmethod
    def update_comfyui(cls):
        # Use simple GET for these as per server code
        return cls._api_get("manager/queue/update_comfyui")

    @classmethod
    def update_all(cls, mode="cache"):
        return cls._api_get("manager/queue/update_all", {"mode": mode})

    @classmethod
    def get_installed_packs(cls):
        # Accurate check for what the server thinks is installed
        return cls._api_get("customnode/installed")

    @classmethod
    def reboot_server(cls):
        # Rebooting naturally closes the connection.
        url = f"{get_url()}/manager/reboot"
        logger.info("Manager: Sending reboot command...")
        try:
            # Short timeout and ignore response content/errors since server will die
            import urllib.request
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=2) as _:
                pass
        except Exception:
            # Connection reset/closed is expected here
            pass
        return {"success": True}
