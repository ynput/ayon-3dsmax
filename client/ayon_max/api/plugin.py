# -*- coding: utf-8 -*-
"""3dsmax specific AYON/Pyblish plugin definitions."""
from pymxs import runtime as rt

from ayon_core.lib import BoolDef
from ayon_core.pipeline import (
    CreatedInstance,
    Creator,
    CreatorError,
    AYON_INSTANCE_ID,
    AVALON_INSTANCE_ID,
)

from .lib import imprint, lsattr, read, get_tyflow_export_operators

MS_CUSTOM_ATTRIB = """attributes "openPypeData"
(
    parameters main rollout:OPparams
    (
        all_handles type:#maxObjectTab tabSize:0 tabSizeVariable:on
        sel_list type:#stringTab tabSize:0 tabSizeVariable:on
    )

    rollout OPparams "OP Parameters"
    (
        listbox list_node "Node References" items:#()
        button button_add "Add to Container"
        button button_del "Delete from Container"

        fn node_to_name the_node =
        (
            handle = the_node.handle
            obj_name = the_node.name
            handle_name = obj_name + "<" + handle as string + ">"
            return handle_name
        )
        fn nodes_to_add node =
        (
            sceneObjs = #()
            if classOf node == Container do return false
            n = node as string
            for obj in Objects do
            (
                tmp_obj = obj as string
                append sceneObjs tmp_obj
            )
            if sel_list != undefined do
            (
                for obj in sel_list do
                (
                    idx = findItem sceneObjs obj
                    if idx do
                    (
                        deleteItem sceneObjs idx
                    )
                )
            )
            idx = findItem sceneObjs n
            if idx then return true else false
        )

        fn nodes_to_rmv node =
        (
            n = node as string
            idx = findItem sel_list n
            if idx then return true else false
        )

        on button_add pressed do
        (
            current_sel = selectByName title:"Select Objects to add to
            the Container" buttontext:"Add" filter:nodes_to_add
            if current_sel == undefined then return False
            temp_arr = #()
            i_node_arr = #()
            for c in current_sel do
            (
                handle_name = node_to_name c
                node_ref = NodeTransformMonitor node:c
                idx = finditem list_node.items handle_name
                if idx do (
                    continue
                )
                name = c as string
                append temp_arr handle_name
                append i_node_arr node_ref
                append sel_list name
            )
            all_handles = join i_node_arr all_handles
            list_node.items = join temp_arr list_node.items
        )

        on button_del pressed do
        (
            current_sel = selectByName title:"Select Objects to remove
            from the Container" buttontext:"Remove" filter: nodes_to_rmv
            if current_sel == undefined or current_sel.count == 0 then
            (
                return False
            )
            temp_arr = #()
            i_node_arr = #()
            new_i_node_arr = #()
            new_temp_arr = #()

            for c in current_sel do
            (
                node_ref = NodeTransformMonitor node:c as string
                handle_name = node_to_name c
                n = c as string
                tmp_all_handles = #()
                for i in all_handles do
                (
                    tmp = i as string
                    append tmp_all_handles tmp
                )
                idx = finditem tmp_all_handles node_ref
                if idx do
                (
                    new_i_node_arr = DeleteItem all_handles idx

                )
                idx = finditem list_node.items handle_name
                if idx do
                (
                    new_temp_arr = DeleteItem list_node.items idx
                )
                idx = finditem sel_list n
                if idx do
                (
                    sel_list = DeleteItem sel_list idx
                )
            )
            all_handles = join i_node_arr new_i_node_arr
            list_node.items = join temp_arr new_temp_arr
        )

        on OPparams open do
        (
            if all_handles.count != 0 then
            (
                temp_arr = #()
                for x in all_handles do
                (
                    if x.node == undefined do continue
                    handle_name = node_to_name x.node
                    append temp_arr handle_name
                )
                list_node.items = temp_arr
            )
        )
    )
)"""


MS_TYCACHE_ATTRIB = """attributes "AYONTyCacheData"
(
    parameters main rollout:Cacheparams
    (
        tyc_exports type:#stringTab tabSize:0 tabSizeVariable:on
        tyc_handles type:#stringTab tabSize:0 tabSizeVariable:on
        sel_list type:#stringTab tabSize:0 tabSizeVariable:on
    )

    rollout Cacheparams "AYON TyCache Parameters"
    (
        listbox export_node "Export Nodes" items:#()
        button button_add "Add to Exports"
        button button_del "Delete from Exports"
        button button_refresh "Refresh"
        listbox tyflow_node "TyFlow Export Operators" items:#()

        on button_add pressed do
        (
            i_node_arr = #()
            temp_arr = #()
            current_sel = tyflow_node.selected
            idx = finditem export_node.items current_sel
            if idx == 0 do (
                append i_node_arr current_sel
                append temp_arr current_sel
            )
            tyc_exports = join i_node_arr tyc_exports
            export_node.items = join temp_arr export_node.items
            sel_list = export_node.items
        )
        on button_del pressed do
        (
            i_node_arr = #()
            temp_arr = #()
            updated_node_arr = #()
            new_temp_arr = #()
            current_sel = export_node.selected
            idx = finditem export_node.items current_sel
            if idx do (
                updated_node_arr = DeleteItem export_node.items idx
            )
            idx = finditem tyc_exports current_sel
            if idx do (
                new_temp_arr = DeleteItem tyc_exports idx
            )
            tyc_exports = join i_node_arr updated_node_arr
            export_node.items = join temp_arr new_temp_arr
            sel_list = export_node.items
        )
        on button_refresh pressed do
        (
            handle_arr = #()
            for obj in Objects do
            (
                if classof obj == tyflow then
                (
                    member = obj.baseobject
                    anim_names = GetSubAnimNames member
                    for anim_name in anim_names do
                    (
                        sub_anim = GetSubAnim member anim_name
                        if isKindOf sub_anim tyEvent do
                        (
                            node_names = GetSubAnimNames sub_anim
                            for node_name in node_names do
                            (
                                node_sub_anim = GetSubAnim sub_anim node_name
                                if hasProperty node_sub_anim "exportMode" do
                                (
                                    node_str = node_sub_anim.name as string
                                    append handle_arr node_str
                                )
                            )
                        )
                    )
                )
            )
            tyc_handles = handle_arr
            tyflow_node.items = handle_arr
        )
        on Cacheparams open do
        (
            temp_arr = #()
            tyflow_id_arr = #()
            if tyc_handles.count != 0 then
            (
                for x in tyc_handles do
                (
                    if x == undefined do continue
                    tyflow_op_name = x as string
                    append temp_arr tyflow_op_name
                )
                tyflow_node.items = temp_arr
            )
            if sel_list.count != 0 then
            (
                sel_arr = #()
                for x in sel_list do
                (
                    append sel_arr x
                )
                export_node.items = sel_arr
            )
        )
    )
)"""

class MaxCreatorBase(object):

    @staticmethod
    def cache_instance_data(shared_data):
        if shared_data.get("max_cached_instances") is not None:
            return shared_data

        shared_data["max_cached_instances"] = {}

        cached_instances = []
        for id_type in [AYON_INSTANCE_ID, AVALON_INSTANCE_ID]:
            cached_instances.extend(lsattr("id", id_type))

        for i in cached_instances:
            creator_id = rt.GetUserProp(i, "creator_identifier")
            if creator_id not in shared_data["max_cached_instances"]:
                shared_data["max_cached_instances"][creator_id] = [i.name]
            else:
                shared_data[
                    "max_cached_instances"][creator_id].append(i.name)
        return shared_data

    @staticmethod
    def create_instance_node(node):
        """Create instance node.

        If the supplied node is existing node, it will be used to hold the
        instance, otherwise new node of type Dummy will be created.

        Args:
            node (rt.MXSWrapperBase, str): Node or node name to use.

        Returns:
            instance
        """
        if not isinstance(node, str):
            raise CreatorError("Instance node is not at the string value.")

        node = rt.Container(name=node)
        attrs = rt.Execute(MS_CUSTOM_ATTRIB)
        modifier = rt.EmptyModifier()
        rt.addModifier(node, modifier)
        node.modifiers[0].name = "OP Data"
        rt.custAttributes.add(node.modifiers[0], attrs)

        return node


class MaxTyFlowDataCreatorBase(MaxCreatorBase):
    @staticmethod
    def create_instance_node(node):
        """Create instance node.

        If the supplied node is existing node, it will be used to hold the
        instance, otherwise new node of type Dummy will be created.

        Args:
            node (rt.MXSWrapperBase, str): Node or node name to use.

        Returns:
            instance
        """
        if not isinstance(node, str):
            raise CreatorError("Instance node is not at the string value.")
        node = rt.Container(name=node)
        attrs = rt.Execute(MS_TYCACHE_ATTRIB)
        modifier = rt.EmptyModifier()
        rt.addModifier(node, modifier)
        node.modifiers[0].name = "AYON TyCache Data"
        rt.custAttributes.add(node.modifiers[0], attrs)

        return node


class MaxCreator(Creator, MaxCreatorBase):
    selected_nodes = []

    def create(self, product_name, instance_data, pre_create_data):
        if pre_create_data.get("use_selection"):
            self.selected_nodes = rt.GetCurrentSelection()
        if rt.getNodeByName(product_name):
            raise CreatorError(f"'{product_name}' is already created..")

        instance_node = self.create_instance_node(product_name)
        instance_data["instance_node"] = instance_node.name
        instance = CreatedInstance(
            self.product_type,
            product_name,
            instance_data,
            self
        )
        if pre_create_data.get("use_selection"):

            node_list = []
            sel_list = []
            for i in self.selected_nodes:
                node_ref = rt.NodeTransformMonitor(node=i)
                node_list.append(node_ref)
                sel_list.append(str(i))

            # Setting the property
            rt.setProperty(
                instance_node.modifiers[0].openPypeData,
                "all_handles", node_list)
            rt.setProperty(
                instance_node.modifiers[0].openPypeData,
                "sel_list", sel_list)

        self._add_instance_to_context(instance)
        imprint(instance_node.name, instance.data_to_store())

        return instance

    def collect_instances(self):
        self.cache_instance_data(self.collection_shared_data)
        for instance in self.collection_shared_data["max_cached_instances"].get(self.identifier, []):  # noqa
            created_instance = CreatedInstance.from_existing(
                read(rt.GetNodeByName(instance)), self
            )
            self._add_instance_to_context(created_instance)

    def update_instances(self, update_list):
        for created_inst, changes in update_list:
            instance_node = created_inst.get("instance_node")
            new_values = {
                key: changes[key].new_value
                for key in changes.changed_keys
            }
            product_name = new_values.get("productName", "")
            if product_name and instance_node != product_name:
                node = rt.getNodeByName(instance_node)
                new_product_name = new_values["productName"]
                if rt.getNodeByName(new_product_name):
                    raise CreatorError(
                        "The product '{}' already exists.".format(
                            new_product_name))
                instance_node = new_product_name
                created_inst["instance_node"] = instance_node
                node.name = instance_node

            imprint(
                instance_node,
                created_inst.data_to_store(),
            )

    def remove_instances(self, instances):
        """Remove specified instance from the scene.

        This is only removing `id` parameter so instance is no longer
        instance, because it might contain valuable data for artist.

        """
        for instance in instances:
            instance_node = rt.GetNodeByName(
                instance.data.get("instance_node"))
            if instance_node:
                count = rt.custAttributes.count(instance_node.modifiers[0])
                rt.custAttributes.delete(instance_node.modifiers[0], count)
                rt.Delete(instance_node)

            self._remove_instance_from_context(instance)

    def get_pre_create_attr_defs(self):
        return [
            BoolDef("use_selection", label="Use selection")
        ]


class MaxCacheCreator(Creator, MaxTyFlowDataCreatorBase):
    settings_category = "max"
    def create(self, product_name, instance_data, pre_create_data):
        tyflow_op_nodes = get_tyflow_export_operators()
        if not tyflow_op_nodes:
            raise CreatorError("No Export Particle Operators"
                               " found in tyCache Editor.")
        instance_node = self.create_instance_node(product_name)
        instance_data["instance_node"] = instance_node.name
        instance = CreatedInstance(
            self.product_type,
            product_name,
            instance_data,
            self
        )
        # Setting the property
        node_list = [sub_anim.name for sub_anim in tyflow_op_nodes]
        rt.setProperty(
            instance_node.modifiers[0].AYONTyCacheData,
            "tyc_handles", node_list)
        self._add_instance_to_context(instance)
        imprint(instance_node.name, instance.data_to_store())

        return instance

    def collect_instances(self):
        self.cache_instance_data(self.collection_shared_data)
        for instance in self.collection_shared_data["max_cached_instances"].get(self.identifier, []):  # noqa
            created_instance = CreatedInstance.from_existing(
                read(rt.GetNodeByName(instance)), self
            )
            self._add_instance_to_context(created_instance)

    def update_instances(self, update_list):
        for created_inst, changes in update_list:
            instance_node = created_inst.get("instance_node")
            new_values = {
                key: changes[key].new_value
                for key in changes.changed_keys
            }
            product_name = new_values.get("productName", "")
            if product_name and instance_node != product_name:
                node = rt.getNodeByName(instance_node)
                new_product_name = new_values["productName"]
                if rt.getNodeByName(new_product_name):
                    raise CreatorError(
                        "The product '{}' already exists.".format(
                            new_product_name))
                instance_node = new_product_name
                created_inst["instance_node"] = instance_node
                node.name = instance_node

            imprint(
                instance_node,
                created_inst.data_to_store(),
            )

    def remove_instances(self, instances):
        """Remove specified instance from the scene.

        This is only removing AYON-related parameters based on the modifier
        so instance is no longer instance, because it might contain
        valuable data for artist.

        """
        for instance in instances:
            instance_node = rt.GetNodeByName(
                instance.data.get("instance_node"))
            if instance_node:
                count = rt.custAttributes.count(instance_node.modifiers[0])
                rt.custAttributes.delete(instance_node.modifiers[0], count)
                rt.Delete(instance_node)

            self._remove_instance_from_context(instance)
