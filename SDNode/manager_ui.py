import bpy
from .comfy_manager import ComfyManager
from ..utils import _T, update_screen, logger
from threading import Thread
import json
from ..timer import Timer

# --- PROPERTY GROUPS ---

class SDN_ManagerNodeItem(bpy.types.PropertyGroup):
    title: bpy.props.StringProperty()
    author: bpy.props.StringProperty()
    description: bpy.props.StringProperty()
    url: bpy.props.StringProperty()
    channel: bpy.props.StringProperty()
    reference: bpy.props.StringProperty() # The URL identifier used by manager
    node_id: bpy.props.StringProperty()   # The internal ID used by server
    version: bpy.props.StringProperty(default="unknown")
    selected: bpy.props.BoolProperty(name="Select", default=False)
    installed: bpy.props.EnumProperty(
        items=[
            ("INSTALLED", "Installed", ""),
            ("NOT_INSTALLED", "Not Installed", ""),
            ("UPDATE_AVAILABLE", "Update Available", ""),
            ("DISABLED", "Disabled", "")
        ],
        default="NOT_INSTALLED"
    )
    version_spec: bpy.props.EnumProperty(
        items=[
            ("nightly", "Nightly", "Safest / Development version"),
            ("latest", "Latest", "Stable / Latest release"),
        ],
        name="Version",
        description="Select which version to install/update",
        default="nightly"
    )

class SDN_ManagerModelItem(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty()
    type: bpy.props.StringProperty()
    base: bpy.props.StringProperty()
    description: bpy.props.StringProperty()
    url: bpy.props.StringProperty()
    installed: bpy.props.BoolProperty(default=False)

class SDN_ManagerProperties(bpy.types.PropertyGroup):
    tabs: bpy.props.EnumProperty(
        items=[
            ("NODES", "Custom Nodes", "Install or update custom nodes", "NODETREE", 0),
            ("MODELS", "Models", "Install models via Civitai/HuggingFace", "ASSET_MANAGER", 1),
            ("MISSING", "Fix Missing", "Automatically install missing nodes from current workflow", "WARNING_LARGE", 2),
            ("SYSTEM", "System", "Update ComfyUI and Manager", "SETTINGS", 3)
        ],
        name="Manager Tabs",
        default="NODES"
    )
    
    search_query: bpy.props.StringProperty(
        name="Search",
        description="Filter nodes or models",
        update=lambda s, c: update_screen()
    )
    
    filter_status: bpy.props.EnumProperty(
        items=[
            ("ALL", "All Nodes", "Show all nodes"),
            ("INSTALLED", "Installed", "Show only installed nodes"),
            ("NOT_INSTALLED", "Not Installed", "Show only nodes not yet installed"),
            ("UPDATE_AVAILABLE", "Updates", "Show only nodes with updates available"),
        ],
        name="Filter",
        default="ALL",
        update=lambda s, c: update_screen()
    )

    is_fetching: bpy.props.BoolProperty(default=False)
    status_msg: bpy.props.StringProperty(name="Status")
    reboot_needed: bpy.props.BoolProperty(name="Reboot Needed", default=False)
    
    nodes: bpy.props.CollectionProperty(type=SDN_ManagerNodeItem)
    nodes_index: bpy.props.IntProperty()
    
    models: bpy.props.CollectionProperty(type=SDN_ManagerModelItem)
    models_index: bpy.props.IntProperty()
    
    missing_nodes: bpy.props.CollectionProperty(type=SDN_ManagerNodeItem)
    missing_index: bpy.props.IntProperty()

# --- UI LISTS ---

class SDN_UL_NodeList(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        row = layout.row(align=True)
        
        # Selection Checkbox for Multi-Download
        row.prop(item, "selected", text="")
        
        # Status Icon
        if item.installed == "INSTALLED":
            row.label(text="", icon='CHECKMARK')
        elif item.installed == "UPDATE_AVAILABLE":
            row.label(text="", icon='RECOVER_LAST')
        else:
            row.label(text="", icon='FILE_BLANK')
        
        col = row.column()
        name_row = col.row()
        name_row.label(text=item.title if item.title else item.node_id)
        if item.installed == "INSTALLED":
            name_row.label(text="Installed", icon='NONE')
        elif item.installed == "UPDATE_AVAILABLE":
            name_row.label(text="UPDATE", icon='NONE')
            
        col.scale_y = 0.8
        col.label(text=f"by {item.author}", icon='USER')
        
        # Action Buttons
        row = layout.row(align=True)
        if item.installed == "NOT_INSTALLED":
             op = row.operator("sdn.manager_action", text="Install", icon='IMPORT')
             op.action = "INSTALL_NODE"
             op.target_url = item.reference
        elif item.installed == "INSTALLED":
             op = row.operator("sdn.manager_action", text="Uninstall", icon='CANCEL_LARGE')
             op.action = "UNINSTALL_NODE"
             op.target_url = item.reference
        elif item.installed == "UPDATE_AVAILABLE":
             op = row.operator("sdn.manager_action", text="Update", icon='FILE_REFRESH')
             op.action = "UPDATE_NODE"
             op.target_url = item.reference
        
        # Version Selection Dropdown
        if item.installed != "INSTALLED":
            row.prop(item, "version_spec", text="")

    def filter_items(self, context, data, propname):
        nodes = getattr(data, propname)
        helper = context.scene.sdn_manager
        
        flt_flags = []
        flt_neworder = []
        
        if not nodes:
            return flt_flags, flt_neworder
        
        for node in nodes:
            flag = self.bitflag_filter_item
            
            # 1. Search Query Filter - Bypass for missing nodes unless user actually typed something while in this tab
            # But the search box is shared, so it's safer to bypass for now or handle specifically
            if helper.search_query and propname != "missing_nodes":
                query = helper.search_query.lower()
                if query not in node.title.lower() and query not in node.author.lower():
                    flag = 0
            
            # 2. Status Filter - Only apply to main nodes list
            if flag and propname == "nodes" and helper.filter_status != 'ALL':
                if node.installed != helper.filter_status:
                    flag = 0
                    
            flt_flags.append(flag)
            
        return flt_flags, flt_neworder

class SDN_UL_ModelList(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        row = layout.row(align=True)
        
        if item.installed:
            row.label(text="", icon='CHECKMARK')
            row.label(text=item.name)
        else:
            row.label(text="", icon='FILE_BLANK')
            row.label(text=item.name)
            
        row.label(text=f"({item.type})", icon='FILE_FOLDER')
        
        if not item.installed:
            op = row.operator("sdn.manager_action", text="Install", icon='IMPORT')
            op.action = "INSTALL_MODEL"
            op.target_url = item.url
        else:
            row.label(text="Installed")

    def filter_items(self, context, data, propname):
        props = context.scene.sdn_manager
        items = getattr(data, propname)
        
        flt_flags = [self.bitflag_filter_item] * len(items)
        
        if props.search_query:
            query = props.search_query.lower()
            for i, item in enumerate(items):
                if query not in item.name.lower() and query not in item.type.lower():
                    flt_flags[i] &= ~self.bitflag_filter_item
        
        return flt_flags, []

# --- OPERATORS ---

class SDN_OT_ManagerAction(bpy.types.Operator):
    bl_idname = "sdn.manager_action"
    bl_label = "Manager Action"
    
    action: bpy.props.StringProperty()
    target_url: bpy.props.StringProperty()
    
    def execute(self, context):
        props = context.scene.sdn_manager
        sdn_props = context.scene.sdn
        action = self.action
        target_url = self.target_url
        
        def run_action():
            Timer.put(lambda: setattr(props, "is_fetching", True))
            Timer.put(lambda: setattr(props, "status_msg", f"Running {action}..."))
            Timer.put(update_screen)
            
            try:
                if action == "FETCH_NODES":
                    data = ComfyManager.get_custom_node_list(mode="cache")
                    installed_packs = ComfyManager.get_installed_packs() or {}
                    
                    if data and "node_packs" in data:
                        def update_nodes(nodes_data, installed):
                            props.nodes.clear()
                            for node_id, n in nodes_data.items():
                                title = n.get("title", node_id)
                                author = n.get("author", "Unknown")
                                reference = n.get("reference", n.get("repository", n.get("url", "")))
                                
                                item = props.nodes.add()
                                item.node_id = node_id
                                item.title = title
                                item.author = author
                                item.reference = reference
                                item.version = str(n.get("version", "unknown"))
                                
                                is_installed = False
                                for key in ["installed", "is_installed", "status"]:
                                    val = n.get(key)
                                    if val is True or str(val).lower() in ("true", "1", "installed", "enabled"):
                                        is_installed = True
                                        break
                                if not is_installed:
                                    inst_v = n.get("installed_version")
                                    if inst_v and inst_v != "None" and inst_v != "unknown":
                                        is_installed = True
                                is_updatable = str(n.get("updatable", "False")).lower() == "true"
                                if is_updatable:
                                    is_installed = True
                                if not is_installed:
                                    if node_id in installed:
                                        is_installed = True
                                    elif reference in installed:
                                        is_installed = True
                                    else:
                                        for pack_info in installed.values():
                                            if pack_info.get('cnr_id') == node_id:
                                                is_installed = True
                                                break
                                if is_updatable:
                                    item.installed = "UPDATE_AVAILABLE"
                                elif is_installed:
                                    item.installed = "INSTALLED"
                                else:
                                    item.installed = "NOT_INSTALLED"
                            props.status_msg = "Node list updated."
                        
                        Timer.put((update_nodes, data["node_packs"], installed_packs))
                
                elif action == "INSTALL_NODE":
                    # Check both lists for node data
                    target_list = list(props.nodes) + list(props.missing_nodes)
                    node_data = next((n for n in target_list if n.reference == target_url), None)

                    if node_data:
                        logger.info(f"Manager: Requesting install for {node_data.title} ({node_data.version_spec})")
                        Timer.put(lambda: setattr(props, "status_msg", f"Installing {node_data.title}..."))
                        Timer.put(update_screen)
                        
                        res = ComfyManager.install_custom_node_queue("default", node_data.author, node_data.title, node_data.reference, node_data.node_id, node_data.version_spec)
                        if res is None:
                            logger.info("Manager: Queue install failed, trying direct git install fallback...")
                            res = ComfyManager.install_custom_node_git(node_data.reference)

                        if res is not None:
                            Timer.put(lambda: setattr(props, "status_msg", f"Install success: {node_data.title}. Restart ComfyUI."))
                        else:
                            Timer.put(lambda: setattr(props, "status_msg", "Installation failed. Check ComfyUI Console."))
                    else:
                        logger.error(f"Manager: Target node not found in cache for URL {target_url}")
                        Timer.put(lambda: setattr(props, "status_msg", "Internal Error: Node data missing."))
                
                elif action == "BATCH_INSTALL":
                    target_list = props.nodes if props.tabs == "NODES" else props.missing_nodes
                    selected = [n for n in target_list if n.selected]
                    if not selected:
                        Timer.put(lambda: setattr(props, "status_msg", "No nodes selected."))
                        return
                    
                    total = len(selected)
                    logger.info(f"Manager: Starting batch install of {total} nodes")
                    
                    for i, node in enumerate(selected):
                        Timer.put(lambda i=i, node=node: setattr(props, "status_msg", f"Batch: [{i+1}/{total}] Installing {node.title}..."))
                        Timer.put(update_screen)
                        
                        res = ComfyManager.install_custom_node_queue("default", node.author, node.title, node.reference, node.node_id, node.version_spec)
                        if res is None:
                            ComfyManager.install_custom_node_git(node.reference)
                        
                        Timer.put(lambda node=node: setattr(node, "selected", False))
                    
                    Timer.put(lambda: setattr(props, "status_msg", f"Batch Complete: {total} installations queued."))

                elif action == "UNINSTALL_NODE":
                    target_list = list(props.nodes) + list(props.missing_nodes)
                    node_data = next((n for n in target_list if n.reference == target_url), None)
                    if node_data:
                        ComfyManager.uninstall_custom_node(node_data.reference, node_data.title, node_data.node_id, node_data.version_spec)
                        Timer.put(lambda: setattr(props, "status_msg", "Node uninstalled. Restart ComfyUI to apply."))

                elif action == "UPDATE_NODE":
                    target_list = list(props.nodes) + list(props.missing_nodes)
                    node_data = next((n for n in target_list if n.reference == target_url), None)
                    if node_data:
                        ComfyManager.update_custom_node(node_data.reference, node_data.title, node_data.node_id, node_data.version_spec)
                        Timer.put(lambda: setattr(props, "status_msg", "Update started. Please check ComfyUI console."))
                
                elif action == "FETCH_MODELS":
                    data = ComfyManager.get_model_list()
                    if data and "models" in data:
                        def update_models(models):
                            props.models.clear()
                            for m in models:
                                item = props.models.add()
                                item.name = m.get("name", "Unknown")
                                item.type = m.get("type", "Unknown")
                                item.url = m.get("url", "")
                                item.installed = str(m.get("installed", "False")).lower() == "true"
                            props.status_msg = "Model list updated."
                        Timer.put((update_models, data["models"]))

                elif action == "FIX_MISSING":
                    # Force fresh fetch from tree instead of using potentially stale _last_workflow_json
                    from .utils import get_default_tree
                    tree = get_default_tree()
                    wf_data = None
                    if tree:
                        wf_data = json.dumps(tree.save_json())
                    
                    if wf_data:
                        try:
                            if isinstance(wf_data, str):
                                wf_data = json.loads(wf_data)
                                
                            data = ComfyManager.get_missing_nodes(wf_data)
                            
                            def update_missing(missing):
                                props.missing_nodes.clear()
                                if missing:
                                    for n in missing:
                                        item = props.missing_nodes.add()
                                        item.title = n.get("title", "Unknown")
                                        item.reference = n.get("reference", n.get("url", ""))
                                        item.author = n.get("author", "Unknown")
                                        item.node_id = n.get("node_id", "")
                                        item.url = n.get("url", "")
                                        item.installed = "NOT_INSTALLED"
                                    props.status_msg = f"Detected {len(missing)} missing packages."
                                else:
                                    props.status_msg = "No missing nodes detected."
                                props.tabs = "MISSING"

                            Timer.put((update_missing, data.get("missing_nodes", []) if data else []))
                        except Exception as e:
                            logger.error(f"Manager: Failed to parse check missing: {e}")
                            Timer.put(lambda: setattr(props, "status_msg", "Error parsing workflow data."))
                    else:
                        Timer.put(lambda: setattr(props, "status_msg", "No workflow data available to check."))
                
                elif action == "REBOOT":
                    from .manager import TaskManager
                    if TaskManager.server.server_type == "Remote":
                        ComfyManager.reboot_server()
                    else:
                        TaskManager.restart_server()
                    
                    Timer.put(lambda: setattr(props, "status_msg", "Server rebooting..."))
                    Timer.put(lambda: setattr(props, "reboot_needed", False))

            except Exception as e:
                err_msg = str(e)
                Timer.put(lambda: setattr(props, "status_msg", f"Error: {err_msg}"))
            finally:
                Timer.put(lambda: setattr(props, "is_fetching", False))
                Timer.put(update_screen)

        Thread(target=run_action).start()
        return {"FINISHED"}

# --- PANEL ---

class SDN_PT_Manager(bpy.types.Panel):
    bl_idname = "SDN_PT_Manager"
    bl_label = "ComfyUI Manager"
    bl_space_type = "NODE_EDITOR"
    bl_region_type = "UI"
    bl_category = "ComfyUI"
    bl_order = 0
    
    def draw(self, context):
        layout = self.layout
        props = context.scene.sdn_manager
        
        # Header Status
        if props.reboot_needed:
            box = layout.box()
            box.alert = True
            row = box.row()
            row.label(text="REBOOT REQUIRED", icon='ERROR')
            row.operator("sdn.manager_action", text="Reboot ComfyUI", icon='RECOVER_LAST').action = "REBOOT"

        row = layout.row()
        if props.is_fetching:
            row.label(text="Communicating with ComfyUI...", icon='URL')
        else:
            row.label(text=props.status_msg if props.status_msg else "Ready", icon='INFO')
            
        # Tab Bar
        layout.prop(props, "tabs", expand=True)
        
        separator = layout.separator()
        
        if props.tabs == "NODES":
            # Filter & Actions Row
            row = layout.row(align=True)
            row.prop(props, "filter_status", text="")
            row.prop(props, "search_query", text="", icon='VIEW_ZOOM')
            op = row.operator("sdn.manager_action", text="", icon='FILE_REFRESH')
            op.action = "FETCH_NODES"

            # Batch Actions
            if props.nodes:
                selected_count = sum(1 for n in props.nodes if n.selected)
                if selected_count > 0:
                    row = layout.row()
                    box = row.box()
                    row_box = box.row(align=True)
                    row_box.label(text=f"Selected: {selected_count}", icon='RESTRICT_SELECT_OFF')
                    op = row_box.operator("sdn.manager_action", text="Install Selected", icon='IMPORT')
                    op.action = "BATCH_INSTALL"
            
            # Node List
            layout.template_list("SDN_UL_NodeList", "", props, "nodes", props, "nodes_index")
            
        elif props.tabs == "MODELS":
            # Search & Refresh
            row = layout.row(align=True)
            row.prop(props, "search_query", text="", icon='VIEW_ZOOM')
            op = row.operator("sdn.manager_action", text="", icon='FILE_REFRESH')
            op.action = "FETCH_MODELS"
            
            layout.template_list("SDN_UL_ModelList", "", props, "models", props, "models_index")

        elif props.tabs == "MISSING":
            layout.label(text="Missing nodes from current tree:")
            op = layout.operator("sdn.manager_action", text="Detect Missing Nodes", icon='VIEW_ZOOM')
            op.action = "FIX_MISSING"
            
            layout.template_list("SDN_UL_NodeList", "", props, "missing_nodes", props, "missing_index")
            
        elif props.tabs == "SYSTEM":
            box = layout.box()
            box.label(text="System Update", icon='SETTINGS')
            box.operator("sdn.manager_action", text="Update ComfyUI", icon='FILE_REFRESH').action = "UPDATE_COMFYUI"
            box.operator("sdn.manager_action", text="Update All Nodes", icon='ASSET_MANAGER').action = "UPDATE_ALL"
            box.operator("sdn.manager_action", text="Reboot Server", icon='RECOVER_LAST').action = "REBOOT"

# --- REGISTRATION ---

classes = [
    SDN_ManagerNodeItem,
    SDN_ManagerModelItem,
    SDN_ManagerProperties,
    SDN_UL_NodeList,
    SDN_UL_ModelList,
    SDN_OT_ManagerAction,
    SDN_PT_Manager,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.sdn_manager = bpy.props.PointerProperty(type=SDN_ManagerProperties)

def unregister():
    if hasattr(bpy.types.Scene, "sdn_manager"):
        del bpy.types.Scene.sdn_manager
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
