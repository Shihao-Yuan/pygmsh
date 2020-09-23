import gmsh

from .ball import Ball
from .boolean import Boolean
from .box import Box
from .cone import Cone
from .cylinder import Cylinder
from .disk import Disk
from .ellipsoid import Ellipsoid
from .rectangle import Rectangle
from .surface_base import SurfaceBase
from .torus import Torus
from .volume_base import VolumeBase
from .wedge import Wedge


class Geometry:
    def __init__(self, characteristic_length_min=None, characteristic_length_max=None):
        self._AFTER_SYNC_QUEUE = []
        self._EMBED_QUEUE = []
        self._COMPOUND_ENTITIES = []
        self._RECOMBINE_ENTITIES = []
        self._TRANSFINITE_CURVE_QUEUE = []
        self._TRANSFINITE_SURFACE_QUEUE = []
        self._SIZE_QUEUE = []

        gmsh.initialize()

        if characteristic_length_min is not None:
            gmsh.option.setNumber(
                "Mesh.CharacteristicLengthMin", characteristic_length_min
            )

        if characteristic_length_max is not None:
            gmsh.option.setNumber(
                "Mesh.CharacteristicLengthMax", characteristic_length_max
            )

    def __del__(self):
        gmsh.finalize()

    def synchronize(self):
        gmsh.model.occ.synchronize()

    def add_rectangle(self, *args, mesh_size=None, **kwargs):
        entity = Rectangle(*args, **kwargs)
        if mesh_size is not None:
            self._SIZE_QUEUE.append((entity, mesh_size))
        return entity

    def add_disk(self, *args, mesh_size=None, **kwargs):
        entity = Disk(*args, **kwargs)
        if mesh_size is not None:
            self._SIZE_QUEUE.append((entity, mesh_size))
        return entity

    def add_ball(self, *args, mesh_size=None, **kwargs):
        cone = Ball(*args, **kwargs)
        if mesh_size is not None:
            self._SIZE_QUEUE.append((cone, mesh_size))
        return cone

    def add_box(self, *args, mesh_size=None, **kwargs):
        box = Box(*args, **kwargs)
        if mesh_size is not None:
            self._SIZE_QUEUE.append((box, mesh_size))
        return box

    def add_cone(self, *args, mesh_size=None, **kwargs):
        cone = Cone(*args, **kwargs)
        if mesh_size is not None:
            self._SIZE_QUEUE.append((cone, mesh_size))
        return cone

    def add_cylinder(self, *args, **kwargs):
        p = Cylinder(*args, **kwargs)
        self._GMSH_CODE.append(p.code)
        return p

    def add_ellipsoid(self, *args, **kwargs):
        p = Ellipsoid(*args, **kwargs)
        self._GMSH_CODE.append(p.code)
        return p

    def add_torus(self, *args, **kwargs):
        p = Torus(*args, **kwargs)
        self._GMSH_CODE.append(p.code)
        return p

    def add_wedge(self, *args, **kwargs):
        p = Wedge(*args, **kwargs)
        self._GMSH_CODE.append(p.code)
        return p

    def _boolean_operation(
        self,
        operation,
        input_entities,
        tool_entities,
        delete_first=True,
        delete_other=True,
    ):
        """Boolean operations, see
        https://gmsh.info/doc/texinfo/gmsh.html#Boolean-operations input_entity
        and tool_entity are called object and tool in gmsh documentation.
        """
        self._BOOLEAN_ID += 1

        # assert that all entities are of the same dimensionality
        dim = None
        legal_dim_types = {1: "Line", 2: "Surface", 3: "Volume"}
        for ldt in legal_dim_types:
            if input_entities[0].dimension == ldt:
                dim = ldt
                break
        assert dim is not None, "Illegal input type '{}' for Boolean operation.".format(
            type(input_entities[0])
        )
        for e in input_entities[1:] + tool_entities:
            assert (
                e.dimension == dim
            ), "Incompatible input type '{}' for Boolean operation.".format(type(e))

        name = f"bo{self._BOOLEAN_ID}"

        input_delete = "Delete;" if delete_first else ""

        tool_delete = "Delete;" if delete_other else ""

        legal_dim_type = legal_dim_types[dim]

        if input_entities:
            formatted_input_entities = (
                ";".join([f"{legal_dim_type}{{{e.id}}}" for e in input_entities]) + ";"
            )
        else:
            formatted_input_entities = ""

        if tool_entities:
            formatted_tool_entities = (
                ";".join([f"{legal_dim_type}{{{e.id}}}" for e in tool_entities]) + ";"
            )
        else:
            formatted_tool_entities = ""

        self._GMSH_CODE.append(
            # I wonder what this line does in Lisp. ;)
            # '{}[] = {}{{{} {{{}}}; {}}} {{{} {{{}}}; {}}};'
            # .format(
            #    name,
            #    operation,
            #    legal_dim_types[dim],
            #    ';'.join(e.id for e in input_entities),
            #    'Delete;' if delete_first else '',
            #    legal_dim_types[dim],
            #    ';'.join(e.id for e in tool_entities),
            #    'Delete;' if delete_other else ''
            #    ))
            "%(name)s[] = %(op)s{ %(ientities)s %(idelete)s } { %(tentities)s %(tdelete)s};"
            % {
                "name": name,
                "op": operation,
                "ientities": formatted_input_entities,
                "idelete": input_delete,
                "tentities": formatted_tool_entities,
                "tdelete": tool_delete,
            }
        )
        mapping = {"Line": None, "Surface": SurfaceBase, "Volume": VolumeBase}
        return mapping[legal_dim_types[dim]](id0=name, is_list=True)

    def boolean_intersection(self, entities):
        """Boolean intersection, see
        https://gmsh.info/doc/texinfo/gmsh.html#Boolean-operations input_entity
        and tool_entity are called object and tool in gmsh documentation.
        """
        ent = entities[0].dim_tags
        # form subsequent intersections
        # https://gitlab.onelab.info/gmsh/gmsh/-/issues/999
        for e in entities[1:]:
            out, _ = gmsh.model.occ.intersect(
                [ent],
                [e.dim_tags],
                removeObject=True,
                removeTool=True,
            )
            assert all(out[0] == item for item in out)
            ent = out[0]
        return Boolean([ent], "Intersection")

    def boolean_union(self, entities):
        """Boolean union, see
        https://gmsh.info/doc/texinfo/gmsh.html#Boolean-operations input_entity
        and tool_entity are called object and tool in gmsh documentation.
        """
        out, _ = gmsh.model.occ.fuse(
            [entities[0].dim_tags],
            [e.dim_tags for e in entities[1:]],
            removeObject=True,
            removeTool=True,
        )
        return Boolean(out, "Union")

    def boolean_difference(self, d0, d1):
        """Boolean difference, see
        https://gmsh.info/doc/texinfo/gmsh.html#Boolean-operations input_entity
        and tool_entity are called object and tool in gmsh documentation.
        """
        print(d0)
        print(d1)
        out, _ = gmsh.model.occ.cut(d0.dim_tags, d1.dim_tags)
        assert len(out) == 1
        return Boolean(out, "Difference")

    def boolean_fragments(self, *args, **kwargs):
        """Boolean fragments, see
        https://gmsh.info/doc/texinfo/gmsh.html#Boolean-operations input_entity
        and tool_entity are called object and tool in gmsh documentation.
        """
        return self._boolean_operation("BooleanFragments", *args, **kwargs)
