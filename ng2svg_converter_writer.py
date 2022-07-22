import os
import re
import bpy
import sverchok
from sverchok.utils.sv_node_utils import recursive_framed_location_finder as absloc
from dataclasses import dataclass

# for prettyprint xml there is only one sane solution:
# from sverchok.utils.pip_utils import install_package
# install_package("lxml")

from lxml import etree as et   

nt = bpy.data.node_groups['NodeTree']
nt_dict = {}
bbox = [[None, None], [None, None]]

@dataclass
class NodeProxy():
    name: str
    label: str
    abs_location: tuple
    width: float
    color: tuple
    inputs: dict
    outputs: dict


def find_children(node):
    return [n.name for n in node.id_data.nodes if n.parent == node]

def absloc_int(n, loc):
    loc = absloc(n, loc)
    return int(loc[0]), int(loc[1])

def convert_rgb(a):
    return f"rgb{tuple(int(i*255) for i in a)}"

def get_component(value, component, func):
    return component if not value else func(value, component)

class FrameBBox():
    def __init__(self):
        self.xmin, self.xmax, self.ymin, self.ymax = None, None, None, None

    def add(self, loc, w, h):
        x, y = loc
        prin(f"{loc, w, h}")
        self.xmin = get_component(self.xmin, x, min)
        self.xmax = get_component(self.xmax, x + w, max)
        self.ymin = get_component(self.ymin, y, min)
        self.ymax = get_component(self.ymax, y + h, max)
        
    def get_box(self, padding=0):
        x = self.xmin - padding
        y = self.ymin - padding
        width = (self.xmax - self.xmin) + (2 * padding) 
        height = (self.ymax - self.ymin) + (2 * padding)
        return x, y, int(width), int(height)

def generate_bbox(x, y):
    bbox[0][0] = get_component(bbox[0][0], x, min)
    bbox[0][1] = get_component(bbox[0][1], x, max)
    bbox[1][0] = get_component(bbox[1][0], y, min)
    bbox[1][1] = get_component(bbox[1][1], y, max)

def gather_socket_data(sockets):
    return {s.name: (s.index, s.color) for s in sockets if not (s.hide or not s.enabled)}
    
for n in nt.nodes:
    if n.bl_idname in {'NodeReroute', 'NodeFrame'}:
        outputs, inputs = {}, {}
        color = n.color if n.bl_idname == "NodeFrame" else [1.0, 0.91764, 0]
    else:
        inputs = gather_socket_data(n.inputs)
        outputs = gather_socket_data(n.outputs)
        color = n.color
    
    x, y = absloc_int(n, n.location[:])
    # not sure wtf is going on with frame nodes but there seems to be an offset incorrectly applied.
    # so for the timebeing, i'm dropping them from the main-frame-bounding-box
    if not n.bl_idname == "NodeFrame":
        generate_bbox(x, y)
    nt_dict[n.name] = NodeProxy(n.name, n.label, (x, y), n.width, color, inputs, outputs)

bw = abs(bbox[0][1] - bbox[0][0])
bh = abs(bbox[1][1] - bbox[1][0])

for n, k in nt_dict.items():
    k.abs_location = k.abs_location[0] - bbox[0][0], bh - (k.abs_location[1] - bbox[1][0])


doc = et.Element('svg', width=str(bw*2), height=str(bh*2), version='1.1', xmlns='http://www.w3.org/2000/svg')
fdoc = et.SubElement(doc, "g", transform=f"translate({30}, {30})", id="frames", style="stroke-width: 1.0;")
gdoc = et.SubElement(doc, "g", transform=f"translate({30}, {30})", id="node ui")
ldoc = et.SubElement(doc, "g", transform=f"translate({30}, {30})", id="link noodles", style="stroke-width: 3.0;")
xdoc = et.SubElement(doc, "g", transform=f"translate({30}, {30})", id="origin", style="stroke-width: 1.0;")
origin = et.SubElement(xdoc, "path", d=f"M-20,0 L20,0 M0,-20 L0,20", stroke="#333")

# Step 1: draw Nodes, Names and Sockets
node_heights = {}
for k, v in nt_dict.items():
    node = nt.nodes.get(v.name) 
    bl_idname = node.bl_idname
    if bl_idname == "NodeFrame": continue

    g = et.SubElement(gdoc, "g", transform=f"translate{v.abs_location}", id=f"NODE:{node.name}")
    
    if bl_idname == "NodeReroute":
        m = et.SubElement(g, "circle", r="10", cx=str(v.width/2), fill=convert_rgb(v.color[:3]))
        continue
    else:
        node_height = (max(len(v.inputs), len(v.outputs)) * 15)
        node_heights[node.name] = node_height
        m = et.SubElement(g, "rect", width=str(v.width), height=f"{node_height-5}", fill=convert_rgb(v.color[:3]))
        t = et.SubElement(g, "text", fill="#333", y="-2", x="3")
        t.text = v.name
    
    sog = et.SubElement(g, "g", width="400", height="200")
    for idx, (socket_name, socket) in enumerate(v.inputs.items()):
        et.SubElement(sog, "circle", r="5", cy=f"{idx*15}", fill=convert_rgb(socket[1][:3]), id=f"index_{idx}")
    for idx, (socket_name, socket) in enumerate(v.outputs.items()):
        et.SubElement(sog, "circle", r="5", cx=str(v.width), cy=f"{idx*15}", fill=convert_rgb(socket[1][:3]), id=f"index_{idx}")    

# Step 2: draw nodeframes on lower layer, using node dimensions generated in step 1
for k, v in nt_dict.items():
    node = nt.nodes.get(v.name) 
    if not node.bl_idname == "NodeFrame": continue

    # calculate bounding frame
    box = FrameBBox()
    children = find_children(node)
    if children:
        for name in children:
            child_node = nt_dict[name] 
            box.add(child_node.abs_location, child_node.width, node_heights[name])
        _x, _y, _w, _h = box.get_box(padding=20)
    else:
        (_x, _y), _w, _h = v.abs_location, node.width, node.height
    dimensions = dict(x=str(_x), y=str(_y), width=str(_w), height=str(_h))
    m = et.SubElement(fdoc, "rect", fill=convert_rgb(v.color[:3]), id=f"FRAME:{v.name}", style="opacity: 0.3;", **dimensions)

prin("------")

calculated_offsets = {}
def calculate_offset(node, socket, sockets=None):
    if socket.bl_idname == "NodeReroute": return 0
    if socket in calculated_offsets:
        return calculated_offsets[socket]

    vis_idx = 0
    for idx, s in enumerate(sockets):
        if s.hide or not s.enabled:
            continue
        if s.is_linked and socket == s:
            offset = vis_idx * 15
            break
        vis_idx += 1
    
    return offset


socket_distance = 5
for link in nt.links:
    n1, s1, n2, s2 = link.from_node, link.from_socket, link.to_node, link.to_socket
    (x1, y1), (x2, y2) = nt_dict[n1.name].abs_location, nt_dict[n2.name].abs_location

    # y1 and y2 should be offset depending on the visible socket indices. using info from s1 and s2
    y1_offset = calculate_offset(n1, s1, n1.outputs)
    y2_offset = calculate_offset(n2, s2, n2.inputs)

    xdist = min((x2 - x1), 40)
    ctrl_1 = int(x1 + n1.width + xdist),              int(y1) + y1_offset
    knot_1 = int(x1 + n1.width + socket_distance),    int(y1) + y1_offset
    knot_2 = int(x2) - socket_distance,               int(y2) + y2_offset
    ctrl_2 = int(x2) - xdist,                         int(y2) + y2_offset

    dpath = re.sub("\(|\)", "", f"M{knot_1} C{ctrl_1} {ctrl_2} {knot_2}")
    path = et.SubElement(ldoc, "path", d=dpath, stroke="#333", fill="transparent") 


svg_filename = "wooooop"
svg_path = os.path.join(bpy.path.abspath('//'), svg_filename + '.svg')
with open(svg_path, 'w') as f:
    f.write(f"<!--{bbox}-->\n")
    f.write(et.tostring(doc, pretty_print=True).decode())
