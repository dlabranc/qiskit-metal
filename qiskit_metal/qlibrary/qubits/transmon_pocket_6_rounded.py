# -*- coding: utf-8 -*-
"""
Transmon Pocket 6 with rounded corners.

Based on qiskit_metal.qlibrary.qubits.transmon_pocket_6.TransmonPocket6
Adds rounded corners to rectangular polygons (pads, pocket, connector pads).

How rounding works:
- If corner_radius == 0 -> identical geometry to the stock component
- If corner_radius > 0 -> rectangles are converted to rounded polygons via
  erosion+dilation buffering (keeps outer dimensions approximately unchanged)
"""

import numpy as np
from shapely.geometry import box as _box
from qiskit_metal import draw, Dict
from qiskit_metal.qlibrary.core import BaseQubit


def _rounded_rectangle(width, height, xoff=0.0, yoff=0.0, radius=0.0):
    """
    Return a shapely Polygon rectangle with optional rounded corners.

    Parameters
    ----------
    width, height : float
        Rectangle size in design units (already parsed).
    xoff, yoff : float
        Offset used like draw.rectangle(width, height, xoff, yoff).
        In Metal's draw.rectangle, xoff/yoff define the *upper-left* reference
        in some components; in practice, the stock code uses:
          - draw.rectangle(w,h) centered at origin
          - draw.rectangle(w,h, -w/2, h/2) to shift
          - draw.rectangle(w,h, 0, h/2) etc.
        Here we implement a faithful equivalent using shapely "box" built from
        those same offsets.
    radius : float
        Corner radius. Clamped to [0, min(width,height)/2].

    Notes
    -----
    We create the rectangle as a box, then apply:
        rect.buffer(-r, join_style=2).buffer(r, join_style=1)
    This rounds the corners while keeping the *outer* size ~constant.
    """
    w = float(width)
    h = float(height)
    r = float(radius)

    if r <= 0:
        # Equivalent to draw.rectangle(w, h, xoff, yoff)
        xmin = float(xoff)
        xmax = xmin + w
        ymax = float(yoff)
        ymin = ymax - h
        return _box(xmin, ymin, xmax, ymax)

    r = min(r, 0.5 * min(w, h))

    xmin = float(xoff)
    xmax = xmin + w
    ymax = float(yoff)
    ymin = ymax - h
    rect = _box(xmin, ymin, xmax, ymax)

    # Erode then dilate to round without changing outer bbox too much
    rounded = rect.buffer(-r, join_style=2).buffer(r, join_style=1)
    return rounded


class TransmonPocket6Rounded(BaseQubit):
    """Transmon pocket with 6 connection pads + optional rounded corners."""

    default_options = Dict(
        # --- pocket + islands ---
        pad_gap="30um",
        inductor_width="20um",
        pad_width="455um",
        pad_height="90um",
        pocket_width="650um",
        pocket_height="650um",

        # --- NEW: corner rounding ---
        # 0um -> identical to TransmonPocket6
        # applies to: pad_top, pad_bot, rect_pk, connector pads
        corner_radius="0um",

        # if you want different radii, you can override these (optional)
        pad_corner_radius=None,        # if None -> uses corner_radius
        pocket_corner_radius=None,     # if None -> uses corner_radius
        connector_corner_radius=None,  # if None -> uses corner_radius

        _default_connection_pads=Dict(
            pad_gap="15um",
            pad_width="125um",
            pad_height="30um",
            pad_cpw_shift="0um",
            pad_cpw_extent="25um",
            cpw_width="10um",
            cpw_gap="6um",
            cpw_extend="100um",
            pocket_extent="5um",
            pocket_rise="0um",
            loc_W="+1",
            loc_H="+1",
        ),
    )

    component_metadata = Dict(
        short_name="PocketRnd",
        _qgeometry_table_path="True",
        _qgeometry_table_poly="True",
        _qgeometry_table_junction="True",
    )

    TOOLTIP = "Transmon pocket with 6 connection pads + rounded corners."

    def make(self):
        self.make_pocket()
        self.make_connection_pads()

    def _get_radii(self):
        """Resolve the three radii from options (parsed values)."""
        p = self.p

        base = float(p.corner_radius)
        pad_r = base if p.pad_corner_radius is None else float(p.pad_corner_radius)
        pk_r = base if p.pocket_corner_radius is None else float(p.pocket_corner_radius)
        cn_r = base if p.connector_corner_radius is None else float(p.connector_corner_radius)

        return pad_r, pk_r, cn_r

    def make_pocket(self):
        p = self.p
        pad_r, pk_r, _ = self._get_radii()

        pad_width = p.pad_width
        pad_height = p.pad_height
        pad_gap = p.pad_gap

        # Island pads (rounded if requested)
        # draw.rectangle(w,h) returns a centered rect; we reproduce that with shapely:
        pad = _rounded_rectangle(pad_width, pad_height, xoff=-pad_width / 2, yoff=+pad_height / 2, radius=pad_r)
        pad_top = draw.translate(pad, 0, +(pad_height + pad_gap) / 2.0)
        pad_bot = draw.translate(pad, 0, -(pad_height + pad_gap) / 2.0)

        # Junction (keep as LineString like stock component)
        rect_jj = draw.LineString([(0, -pad_gap / 2), (0, +pad_gap / 2)])

        # Pocket cutout (rounded if requested)
        rect_pk = _rounded_rectangle(
            p.pocket_width, p.pocket_height,
            xoff=-p.pocket_width / 2, yoff=+p.pocket_height / 2,
            radius=pk_r
        )

        polys = [rect_jj, pad_top, pad_bot, rect_pk]
        polys = draw.rotate(polys, p.orientation, origin=(0, 0))
        polys = draw.translate(polys, p.pos_x, p.pos_y)
        [rect_jj, pad_top, pad_bot, rect_pk] = polys

        self.add_qgeometry("poly", dict(pad_top=pad_top, pad_bot=pad_bot))
        self.add_qgeometry("poly", dict(rect_pk=rect_pk), subtract=True)
        self.add_qgeometry("junction", dict(rect_jj=rect_jj), width=p.inductor_width)

    def make_connection_pads(self):
        for name in self.options.connection_pads:
            self.make_connection_pad(name)

    def make_connection_pad(self, name: str):
        p = self.p
        pc = self.p.connection_pads[name]
        _, _, cn_r = self._get_radii()

        cpw_width = pc.cpw_width
        cpw_extend = pc.cpw_extend
        pad_width = pc.pad_width
        pad_height = pc.pad_height
        pad_cpw_shift = pc.pad_cpw_shift
        pocket_rise = pc.pocket_rise
        pocket_extent = pc.pocket_extent

        loc_W, loc_H = float(pc.loc_W), float(pc.loc_H)
        if loc_W not in [-1.0, +1.0, 0.0] or loc_H not in [-1.0, +1.0]:
            self.logger.info(
                "Warning: loc_W should be -1, 0, +1 and loc_H should be -1, +1. "
                "You set loc_W=%s loc_H=%s", loc_W, loc_H
            )

        # Connector pad + wire path
        if loc_W != 0:
            # Stock: draw.rectangle(pad_width, pad_height, -pad_width/2, pad_height/2)
            connector_pad = _rounded_rectangle(
                pad_width, pad_height,
                xoff=-pad_width / 2, yoff=+pad_height / 2,
                radius=cn_r
            )

            connector_wire_path = draw.wkt.loads(
                f"""LINESTRING (
                    0 {pad_cpw_shift + cpw_width/2},
                    {pc.pad_cpw_extent} {pad_cpw_shift + cpw_width/2},
                    {(p.pocket_width - p.pad_width)/2 - pocket_extent} {pad_cpw_shift + cpw_width/2 + pocket_rise},
                    {(p.pocket_width - p.pad_width)/2 + cpw_extend} {pad_cpw_shift + cpw_width/2 + pocket_rise}
                )"""
            )
        else:
            # Stock: draw.rectangle(pad_width, pad_height, 0, pad_height/2)
            connector_pad = _rounded_rectangle(
                pad_width, pad_height,
                xoff=0.0, yoff=+pad_height / 2,
                radius=cn_r
            )

            connector_wire_path = draw.LineString(
                [
                    [0, pad_height],
                    [
                        0,
                        (p.pocket_width / 2 - p.pad_height - p.pad_gap / 2 - pc.pad_gap) + cpw_extend,
                    ],
                ]
            )

        objects = [connector_pad, connector_wire_path]

        # Keep stock scaling trick for loc_W=0
        loc_Woff = 1.0 if loc_W == 0 else loc_W

        objects = draw.scale(objects, loc_Woff, loc_H, origin=(0, 0))
        objects = draw.translate(
            objects,
            loc_W * (p.pad_width) / 2.0,
            loc_H * (p.pad_height + p.pad_gap / 2 + pc.pad_gap),
        )
        objects = draw.rotate_position(objects, p.orientation, [p.pos_x, p.pos_y])
        connector_pad, connector_wire_path = objects

        self.add_qgeometry("poly", {f"{name}_connector_pad": connector_pad})
        self.add_qgeometry("path", {f"{name}_wire": connector_wire_path}, width=cpw_width)
        self.add_qgeometry(
            "path",
            {f"{name}_wire_sub": connector_wire_path},
            width=cpw_width + 2 * pc.cpw_gap,
            subtract=True,
        )

        # Pins (unchanged)
        points = np.array(connector_wire_path.coords)
        self.add_pin(name, points=points[-2:], width=cpw_width, input_as_norm=True)
