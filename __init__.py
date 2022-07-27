bl_info = {
    "name": "Sverchok to svg",
    "author": "zeffii",
    "version": (0, 0, 1),
    "blender": (2, 93, 0),
    "location": "Node Editor",
    "category": "Node",
    "description": "approximate SVG of your sverchok nodetree",
    "warning": "",
    "wiki_url": "",
    "tracker_url": "https://github.com/zeffii/sverchok_to_svg/issues"
}

from ng2svg_convert_writer import create

def register(): pass
def unregister(): pass