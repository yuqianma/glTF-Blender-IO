# Copyright 2018-2021 The glTF-Blender-IO authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


import bpy
import typing
from io_scene_gltf2.io.com import gltf2_io
from io_scene_gltf2.blender.exp.gltf2_blender_gather_cache import cached
from io_scene_gltf2.blender.exp import gltf2_blender_gather_nodes
from io_scene_gltf2.blender.exp import gltf2_blender_gather_joints
from io_scene_gltf2.blender.exp import gltf2_blender_gather_skins
from io_scene_gltf2.blender.exp import gltf2_blender_get
from io_scene_gltf2.io.com.gltf2_io_extensions import Extension
from io_scene_gltf2.io.exp.gltf2_io_user_extensions import export_user_extensions

@cached
def gather_animation_channel_target(obj_uuid: int,
                                    channels: typing.Tuple[bpy.types.FCurve],
                                    bake_bone: typing.Union[str, None],
                                    bake_channel: typing.Union[str, None],
                                    driver_obj_uuid,
                                    export_settings
                                    ) -> gltf2_io.AnimationChannelTarget:

        blender_object = export_settings['vtree'].nodes[obj_uuid].blender_object

        animation_channel_target = gltf2_io.AnimationChannelTarget(
            extensions=__gather_extensions(channels, blender_object, export_settings, bake_bone),
            extras=__gather_extras(channels, blender_object, export_settings, bake_bone),
            node=__gather_node(channels, obj_uuid, export_settings, bake_bone, driver_obj_uuid),
            path=__gather_path(channels, blender_object, export_settings, bake_bone, bake_channel)
        )

        # FIXME: hard coded "pointer"
        if animation_channel_target.path is None:
            animation_channel_target = gltf2_io.AnimationChannelTarget(
                extensions=__gather_pointer_extensions(channels, blender_object, export_settings, bake_bone),
                extras=__gather_extras(channels, blender_object, export_settings, bake_bone),
                node=None,
                path="pointer"
            )

        export_user_extensions('gather_animation_channel_target_hook',
                               export_settings,
                               animation_channel_target,
                               channels,
                               blender_object,
                               bake_bone,
                               bake_channel)

        return animation_channel_target

def __gather_extensions(channels: typing.Tuple[bpy.types.FCurve],
                        blender_object: bpy.types.Object,
                        export_settings,
                        bake_bone: typing.Union[str, None]
                        ) -> typing.Any:
    return None

def __gather_pointer_extensions(channels: typing.Tuple[bpy.types.FCurve],
                        blender_object: bpy.types.Object,
                        export_settings,
                        bake_bone: typing.Union[str, None]
                        ) -> typing.Any:
    print(len(channels), channels[0].data_path)
    # assume only one material in an object
    material = blender_object.material_slots[0].material
    # we cannot know material index now, save name for later
    material_name_string = "/materials/" + material.name + "/"
    node_tree = material.node_tree
    node_path = channels[0].data_path.rsplit('.', 2)[0]
    node = node_tree.path_resolve(node_path)
    print(node)
    print(node.type)
    pointer = None
    if node is None:
        return None
    if node.type == 'MAPPING':
        transform_socket_path = channels[0].data_path.rsplit('.', 1)[0]
        transform_socket = node_tree.path_resolve(transform_socket_path)
        transform_type = {
            "Location": "offset",
            "Rotation": "rotation",
            "Scale": "scale"
        }.get(transform_socket.name)
        
        mat_socket_name = None
        tex_name = None
        try:
            mat_socket_name = node.outputs[0].links[0].to_node.outputs[0].links[0].to_socket.name
        except:
            try:
               mat_socket_name = node.outputs[0].links[0].to_node.outputs[1].links[0].to_socket.name
            except:
                pass
        if mat_socket_name == "Base Color":
            tex_name = "pbrMetallicRoughness/baseColorTexture"
        elif mat_socket_name == "Alpha":
            tex_name = "pbrMetallicRoughness/baseColorTexture"
        elif mat_socket_name == "Emission":
            tex_name = "emissiveTexture"

        if tex_name is None or transform_type is None:
            return None
        pointer = {
            "pointer": material_name_string + tex_name +"/extensions/KHR_texture_transform/" + transform_type
        }
    elif node.type == 'BSDF_PRINCIPLED':
        pbr_socket_path = channels[0].data_path.rsplit('.', 1)[0]
        pbr_socket = node_tree.path_resolve(pbr_socket_path)
        gltf_path_name = {
            "Base Color": "pbrMetallicRoughness/baseColorFactor",
            "Alpha": "pbrMetallicRoughness/baseColorFactor",
            "Emission": "emissiveFactor",
        }.get(pbr_socket.name)
        if gltf_path_name is None:
            return None
        pointer = {
            "pointer": material_name_string + gltf_path_name
        }

    extension = Extension("KHR_animation_pointer", pointer)
    return {"KHR_animation_pointer": extension}

def __gather_extras(channels: typing.Tuple[bpy.types.FCurve],
                    blender_object: bpy.types.Object,
                    export_settings,
                    bake_bone: typing.Union[str, None]
                    ) -> typing.Any:
    return None


def __gather_node(channels: typing.Tuple[bpy.types.FCurve],
                  obj_uuid: str,
                  export_settings,
                  bake_bone: typing.Union[str, None],
                  driver_obj_uuid
                  ) -> gltf2_io.Node:

    blender_object = export_settings['vtree'].nodes[obj_uuid].blender_object

    if driver_obj_uuid is not None:
        return export_settings['vtree'].nodes[driver_obj_uuid].node

    if blender_object.type == "ARMATURE":
        # TODO: get joint from fcurve data_path and gather_joint

        if bake_bone is not None:
            blender_bone = blender_object.pose.bones[bake_bone]
        else:
            blender_bone = blender_object.path_resolve(channels[0].data_path.rsplit('.', 1)[0])

        if isinstance(blender_bone, bpy.types.PoseBone):
            return gltf2_blender_gather_joints.gather_joint_vnode(export_settings['vtree'].nodes[obj_uuid].bones[blender_bone.name], export_settings)

    return export_settings['vtree'].nodes[obj_uuid].node


def __gather_path(channels: typing.Tuple[bpy.types.FCurve],
                  blender_object: bpy.types.Object,
                  export_settings,
                  bake_bone: typing.Union[str, None],
                  bake_channel: typing.Union[str, None]
                  ) -> str:
    if bake_channel is None:
        # Note: channels has some None items only for SK if some SK are not animated
        target = [c for c in channels if c is not None][0].data_path.split('.')[-1]
    else:
        target = bake_channel
    path = {
        "delta_location": "translation",
        "delta_rotation_euler": "rotation",
        "location": "translation",
        "rotation_axis_angle": "rotation",
        "rotation_euler": "rotation",
        "rotation_quaternion": "rotation",
        "scale": "scale",
        "value": "weights"
    }.get(target)

    if target is None:
        return None

    return path
