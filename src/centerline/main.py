# -*- coding: utf-8 -*-

from __future__ import unicode_literals

from numpy import array
from scipy.spatial import Voronoi
from shapely.geometry import (
    LineString, MultiLineString, MultiPolygon, Point, Polygon
)
from shapely.ops import unary_union

from . import exceptions


class Centerline(MultiLineString):
    """
    The polygon's skeleton.

    The polygon's attributes are copied and set as the centerline's
    attributes. The rest of the attributes are inherited from the
    MultiLineString class.

    Attributes:
        geoms (shapely.geometry.base.GeometrySequence): A sequence of
            LineStrings

    """

    def __init__(self, input_geom, interpolation_dist=0.5, **attributes):
        """
        Create a centerline object.

        The values provided under `attributes` are used for creating
        the object's attributes.

        Args:
            input_geom (shapely.geometry.Polygon): shapely geometry
            interpolation_dist (:obj:`float`, optional): interpolation
                distance. Defaults to 0.5 (meters).
            attributes (dict): The object's attributes that should be
                copied to the new Centerline object

        Raises:
            ValueError: invalid input geometry

        """
        self._input_geom = input_geom
        self._interpolation_dist = abs(interpolation_dist)

        if not self.input_geometry_is_valid():
            raise exceptions.InvalidInputTypeError

        self._min_x, self._min_y = self.get_reduction_coordinates()
        self.assign_attributes_to_instance(attributes)

        super(Centerline, self).__init__(lines=self.construct_centerline())

    def input_geometry_is_valid(self):
        if isinstance(self._input_geom, Polygon) or isinstance(
            self._input_geom, MultiPolygon
        ):
            return True
        else:
            return False

    def get_reduction_coordinates(self):
        min_x = int(min(self._input_geom.envelope.exterior.xy[0]))
        min_y = int(min(self._input_geom.envelope.exterior.xy[1]))
        return min_x, min_y

    def assign_attributes_to_instance(self, attributes):
        for key in attributes:
            setattr(self, key, attributes.get(key))

    def construct_centerline(self):
        """
        Calculate the centerline of a polygon.

        Densifies the border of a polygon which is then represented by a Numpy
        array of points necessary for creating the Voronoi diagram. Once the
        diagram is created, the ridges located within the polygon are
        joined and returned.

        Returns:
            a union of lines that are located within the polygon.

        """
        vertices, ridges = self._get_voronoi_vertices_and_ridges()
        linestrings = []
        for ridge in ridges:
            if self.ridge_is_finite(ridge):
                starting_point = self._create_point_with_restored_coordinates(
                    x=vertices[ridge[0]][0], y=vertices[ridge[0]][1]
                )
                ending_point = self._create_point_with_restored_coordinates(
                    x=vertices[ridge[1]][0], y=vertices[ridge[1]][1]
                )
                linestring = LineString((starting_point, ending_point))

                if self.linestring_is_within_input_geometry(linestring):
                    linestrings.append(linestring)

        if len(linestrings) < 2:
            raise exceptions.TooFewRidgesError

        return unary_union(linestrings)

    def _get_voronoi_vertices_and_ridges(self):
        borders = self.get_densified_borders()

        voronoi_diagram = Voronoi(borders)
        vertices = voronoi_diagram.vertices
        ridges = voronoi_diagram.ridge_vertices

        return vertices, ridges

    def ridge_is_finite(self, ridge):
        return -1 not in ridge

    def _create_point_with_restored_coordinates(self, x, y):
        return (x + self._min_x, y + self._min_y)

    def linestring_is_within_input_geometry(self, linestring):
        return (
            linestring.within(self._input_geom)
            and len(linestring.coords[0]) > 1
        )

    def get_densified_borders(self):
        polygons = self.extract_polygons_from_input_geometry()
        points = []
        for polygon in polygons:
            points += self._get_interpolated_boundary(polygon.exterior)
            if self._polygon_has_interior_rings(polygon):
                for interior in polygon.interiors:
                    points += self._get_interpolated_boundary(interior)

        return array(points)

    def extract_polygons_from_input_geometry(self):
        if isinstance(self._input_geom, MultiPolygon):
            return (polygon for polygon in self._input_geom)
        else:
            return (self._input_geom,)

    def _polygon_has_interior_rings(self, polygon):
        return len(polygon.interiors) > 0

    def _get_interpolated_boundary(self, boundary):
        line = LineString(boundary)

        first_point = self._get_coordinates_of_first_point(line)
        last_point = self._get_coordinates_of_last_point(line)

        intermediate_points = self._get_coordinates_of_interpolated_points(
            line
        )

        return [first_point] + intermediate_points + [last_point]

    def _get_coordinates_of_first_point(self, linestring):
        return self._create_point_with_reduced_coordinates(
            x=linestring.xy[0][0], y=linestring.xy[1][0]
        )

    def _get_coordinates_of_last_point(self, linestring):
        return self._create_point_with_reduced_coordinates(
            x=linestring.xy[0][-1], y=linestring.xy[1][-1]
        )

    def _get_coordinates_of_interpolated_points(self, linestring):
        intermediate_points = []
        interpolation_distance = self._interpolation_dist
        line_length = linestring.length
        while interpolation_distance < line_length:
            point = linestring.interpolate(interpolation_distance)
            reduced_point = self._create_point_with_reduced_coordinates(
                x=point.x, y=point.y
            )
            intermediate_points.append(reduced_point)
            interpolation_distance += self._interpolation_dist

        return intermediate_points

    def _create_point_with_reduced_coordinates(self, x, y):
        return (x - self._min_x, y - self._min_y)
