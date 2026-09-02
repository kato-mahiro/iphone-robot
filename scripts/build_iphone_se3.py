import adsk.core
import adsk.fusion
import math

# Parametric iPhone SE (3rd generation) model based on:
# references/iphone-se-3rd-generation.pdf
# Fusion's internal geometric unit is cm. All public parameters use mm.


def cm(mm):
    return mm / 10.0


def value(expression):
    return adsk.core.ValueInput.createByString(expression)


# Remove the previous generated component and its parameters.
root = design.rootComponent
for index in range(root.occurrences.count - 1, -1, -1):
    occurrence = root.occurrences.item(index)
    if occurrence.component.name.startswith('iPhone SE 3'):
        occurrence.deleteMe()
for index in range(design.userParameters.count - 1, -1, -1):
    parameter = design.userParameters.item(index)
    if parameter.name.startswith('SE3_'):
        parameter.deleteMe()

occurrence = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
phone = occurrence.component
phone.name = 'iPhone SE 3 - Parametric Drawing Model'

# Drawing and model parameters. Edit these in Modify > Change Parameters.
parameter_definitions = [
    ('SE3_OverallWidth', '67.27 mm', 'Overall product width'),
    ('SE3_OverallHeight', '138.44 mm', 'Overall product height'),
    ('SE3_ProductThickness', '7.31 mm', 'Nominal product thickness'),
    ('SE3_CornerRadius', '9.10 mm', 'Parameterized plan-view corner radius'),
    ('SE3_RearGlassThickness', '0.90 mm', 'Modeled rear glass thickness'),
    ('SE3_FrontGlassThickness', '0.90 mm', 'Modeled front glass thickness'),
    ('SE3_ActiveWidth', '58.50 mm', 'Front active-area width'),
    ('SE3_ActiveHeight', '104.05 mm', 'Front active-area height'),
    ('SE3_ActiveTopOffset', '17.19 mm', 'Top product datum to active area'),
    ('SE3_HomeDiameter', '10.90 mm', 'Home/Touch ID sensor diameter'),
    ('SE3_HomeBottomOffset', '9.25 mm', 'Bottom datum to Home sensor center'),
    ('SE3_ReceiverWidth', '11.87 mm', 'Receiver width'),
    ('SE3_ReceiverHeight', '1.20 mm', 'Receiver height'),
    ('SE3_ReceiverTopOffset', '9.10 mm', 'Top datum to receiver center'),
    ('SE3_FrontCameraDiameter', '3.21 mm', 'Front camera opening/keepout diameter'),
    ('SE3_FrontCameraXFromLeft', '22.99 mm', 'Left datum to front camera center'),
    ('SE3_FrontCameraTopOffset', '9.10 mm', 'Top datum to front camera center'),
    ('SE3_ProximityDiameter', '2.00 mm', 'Proximity sensor display diameter'),
    ('SE3_ProximityXFromLeft', '33.63 mm', 'Left datum to proximity center'),
    ('SE3_ProximityTopOffset', '4.84 mm', 'Top datum to proximity center'),
    ('SE3_ALSDiameter', '2.00 mm', 'Ambient light sensor display diameter'),
    ('SE3_ALSXFromLeft', '37.32 mm', 'Left datum to ALS center'),
    ('SE3_ALSTopOffset', '4.84 mm', 'Top datum to ALS center'),
    ('SE3_RearCameraDiameter', '8.57 mm', 'Rear camera opening diameter'),
    ('SE3_RearMicDiameter', '1.50 mm', 'Rear microphone diameter'),
    ('SE3_RearFlashDiameter', '3.75 mm', 'Rear flash diameter'),
    ('SE3_RearCameraXFromLeft', '10.44 mm', 'Left datum to rear camera center'),
    ('SE3_RearMicXFromLeft', '18.13 mm', 'Left datum to rear microphone center'),
    ('SE3_RearFlashXFromLeft', '22.84 mm', 'Left datum to rear flash center'),
    ('SE3_RearFeatureTopOffset', '15.40 mm', 'Top datum to rear feature centers'),
    ('SE3_CameraBumpHeight', '0.87 mm', 'Modeled rear camera projection'),
    ('SE3_RingTopOffset', '17.56 mm', 'Top datum to top of ring/silent switch'),
    ('SE3_RingLength', '5.61 mm', 'Ring/silent switch length'),
    ('SE3_VolumePlusCenterFromTop', '34.56 mm', 'Top datum to volume-plus center'),
    ('SE3_VolumeMinusCenterFromTop', '47.17 mm', 'Top datum to volume-minus center'),
    ('SE3_ButtonLength', '10.62 mm', 'Button length: 2 x 5.31'),
    ('SE3_ButtonFaceWidth', '1.80 mm', 'Modeled button width in product-thickness direction'),
    ('SE3_RingProjection', '0.42 mm', 'Ring/silent switch projection'),
    ('SE3_ButtonProjection', '0.40 mm', 'Volume and side-button projection'),
    ('SE3_SideButtonCenterFromTop', '34.64 mm', 'Top datum to side-button center'),
    ('SE3_SIMTrayTopOffset', '52.72 mm', 'Top datum to SIM tray top'),
    ('SE3_SIMTrayLength', '15.67 mm', 'SIM tray length'),
    ('SE3_SIMTrayWidth', '2.30 mm', 'SIM tray visible width'),
    ('SE3_BottomHoleDiameter', '1.45 mm', 'Bottom microphone/speaker hole diameter'),
    ('SE3_BottomHoleFirstFromLeft', '10.26 mm', 'Left datum to first left acoustic hole'),
    ('SE3_BottomHolePitch', '2.40 mm', 'Bottom acoustic-hole pitch: 12.00 / 5'),
    ('SE3_BottomRightFirstFromLeft', '45.01 mm', 'Left datum to first right acoustic hole'),
    ('SE3_ScrewDiameter', '1.60 mm', 'Bottom screw diameter'),
    ('SE3_LeftScrewFromLeft', '27.24 mm', 'Left datum to left screw'),
    ('SE3_RightScrewFromLeft', '40.03 mm', 'Left datum to right screw'),
    ('SE3_LightningWidth', '8.70 mm', 'Lightning opening width: 37.98 - 29.28'),
    ('SE3_LightningHeight', '1.60 mm', 'Modeled Lightning opening height'),
    ('SE3_DetailOverlay', '0.02 mm', 'Visual reference overlay thickness'),
]
for parameter_name, expression, comment in parameter_definitions:
    design.userParameters.add(parameter_name, value(expression), 'mm', comment)


# Appearance helpers.
def find_or_make_appearance(name, rgb):
    existing = design.appearances.itemByName(name)
    if existing:
        return existing
    source = None
    for library_index in range(app.materialLibraries.count):
        library = app.materialLibraries.item(library_index)
        if library.appearances.count:
            source = library.appearances.item(0)
            break
    if not source:
        return None
    appearance = design.appearances.addByCopy(source, name)
    for property_id in ('opaque_albedo', 'generic_diffuse', 'metal_f0'):
        appearance_property = appearance.appearanceProperties.itemById(property_id)
        color_property = adsk.core.ColorProperty.cast(appearance_property) if appearance_property else None
        if color_property:
            color_property.value = adsk.core.Color.create(rgb[0], rgb[1], rgb[2], 255)
            break
    return appearance


silver = find_or_make_appearance('SE3 Silver Aluminum', (165, 168, 172))
black = find_or_make_appearance('SE3 Black Glass', (12, 14, 17))
blue = find_or_make_appearance('SE3 Display', (18, 35, 52))
dark = find_or_make_appearance('SE3 Dark Detail', (20, 20, 22))
white = find_or_make_appearance('SE3 Ceramic White', (225, 225, 220))
flash_appearance = find_or_make_appearance('SE3 Flash', (238, 220, 150))


def apply_appearance(body, appearance):
    if body and appearance:
        try:
            body.appearance = appearance
        except RuntimeError:
            pass


# Parametric sketch helpers.
def offset_plane(base_plane, expression, name):
    plane_input = phone.constructionPlanes.createInput()
    plane_input.setByOffset(base_plane, value(expression))
    plane = phone.constructionPlanes.add(plane_input)
    plane.name = name
    plane.isLightBulbOn = False
    return plane


def set_expression(dimension, expression):
    dimension.parameter.expression = expression
    return dimension


def horizontal_dimension(sketch, point1, point2, expression, text_x, text_y):
    dimension = sketch.sketchDimensions.addDistanceDimension(
        point1,
        point2,
        adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
        adsk.core.Point3D.create(cm(text_x), cm(text_y), 0),
    )
    return set_expression(dimension, expression)


def vertical_dimension(sketch, point1, point2, expression, text_x, text_y):
    dimension = sketch.sketchDimensions.addDistanceDimension(
        point1,
        point2,
        adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
        adsk.core.Point3D.create(cm(text_x), cm(text_y), 0),
    )
    return set_expression(dimension, expression)


def diameter_dimension(sketch, circle, expression, text_x, text_y):
    dimension = sketch.sketchDimensions.addDiameterDimension(
        circle, adsk.core.Point3D.create(cm(text_x), cm(text_y), 0)
    )
    return set_expression(dimension, expression)


def radius_dimension(sketch, arc, expression, text_x, text_y):
    dimension = sketch.sketchDimensions.addRadialDimension(
        arc, adsk.core.Point3D.create(cm(text_x), cm(text_y), 0)
    )
    return set_expression(dimension, expression)


def largest_profile(sketch):
    return max(
        (sketch.profiles.item(i) for i in range(sketch.profiles.count)),
        key=lambda profile: profile.areaProperties().area,
    )


def parametric_rounded_rectangle(
    plane,
    width_expression,
    height_expression,
    radius_expression,
    initial_width,
    initial_height,
    initial_radius,
    initial_center_x,
    initial_center_y,
    name,
    center_x_expression=None,
    center_y_expression=None,
):
    sketch = phone.sketches.add(plane)
    sketch.name = name
    arcs = sketch.sketchCurves.sketchArcs
    lines = sketch.sketchCurves.sketchLines
    constraints = sketch.geometricConstraints

    half_width = cm(initial_width / 2)
    half_height = cm(initial_height / 2)
    radius = cm(initial_radius)
    center_x = cm(initial_center_x)
    center_y = cm(initial_center_y)

    # Fusion only accepts a positive sweep here. Start points are selected so
    # each arc is the intended 90-degree corner, not the complementary 270 degrees.
    top_right = arcs.addByCenterStartSweep(
        adsk.core.Point3D.create(center_x + half_width - radius, center_y + half_height - radius, 0),
        adsk.core.Point3D.create(center_x + half_width, center_y + half_height - radius, 0),
        math.pi / 2,
    )
    bottom_right = arcs.addByCenterStartSweep(
        adsk.core.Point3D.create(center_x + half_width - radius, center_y - half_height + radius, 0),
        adsk.core.Point3D.create(center_x + half_width - radius, center_y - half_height, 0),
        math.pi / 2,
    )
    bottom_left = arcs.addByCenterStartSweep(
        adsk.core.Point3D.create(center_x - half_width + radius, center_y - half_height + radius, 0),
        adsk.core.Point3D.create(center_x - half_width, center_y - half_height + radius, 0),
        math.pi / 2,
    )
    top_left = arcs.addByCenterStartSweep(
        adsk.core.Point3D.create(center_x - half_width + radius, center_y + half_height - radius, 0),
        adsk.core.Point3D.create(center_x - half_width + radius, center_y + half_height, 0),
        math.pi / 2,
    )

    top = lines.addByTwoPoints(top_left.startSketchPoint, top_right.endSketchPoint)
    right = lines.addByTwoPoints(top_right.startSketchPoint, bottom_right.endSketchPoint)
    bottom = lines.addByTwoPoints(bottom_right.startSketchPoint, bottom_left.endSketchPoint)
    left = lines.addByTwoPoints(bottom_left.startSketchPoint, top_left.endSketchPoint)

    constraints.addHorizontal(top)
    constraints.addHorizontal(bottom)
    constraints.addVertical(left)
    constraints.addVertical(right)
    for line, arc in (
        (top, top_right), (right, top_right),
        (right, bottom_right), (bottom, bottom_right),
        (bottom, bottom_left), (left, bottom_left),
        (left, top_left), (top, top_left),
    ):
        try:
            constraints.addTangent(line, arc)
        except RuntimeError:
            pass
    for arc in (bottom_right, bottom_left, top_left):
        constraints.addEqual(top_right, arc)

    horizontal_dimension(
        sketch, top.startSketchPoint, top.endSketchPoint,
        f'{width_expression}-2*{radius_expression}',
        initial_center_x, initial_center_y + initial_height / 2 + 4,
    )
    vertical_dimension(
        sketch, right.startSketchPoint, right.endSketchPoint,
        f'{height_expression}-2*{radius_expression}',
        initial_center_x + initial_width / 2 + 4, initial_center_y,
    )
    radius_dimension(
        sketch, top_right, radius_expression,
        initial_center_x + initial_width / 2 + 2,
        initial_center_y + initial_height / 2 - 2,
    )

    center_arc = top_right.centerSketchPoint
    x_expression = f'{width_expression}/2-{radius_expression}'
    y_expression = f'{height_expression}/2-{radius_expression}'
    if center_x_expression:
        x_expression = f'({center_x_expression})+{x_expression}'
    if center_y_expression:
        y_expression = f'({center_y_expression})+{y_expression}'
    horizontal_dimension(
        sketch, sketch.originPoint, center_arc, x_expression,
        initial_center_x + initial_width / 4, initial_center_y - 5,
    )
    vertical_dimension(
        sketch, sketch.originPoint, center_arc, y_expression,
        initial_center_x - 5, initial_center_y + initial_height / 4,
    )
    sketch.isLightBulbOn = False
    return sketch


def extrude_first_profile(
    sketch,
    distance_expression,
    feature_name,
    appearance=None,
    operation=adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
    direction=None,
):
    profile = largest_profile(sketch)
    extrude_input = phone.features.extrudeFeatures.createInput(profile, operation)
    if direction is None:
        extrude_input.setDistanceExtent(False, value(distance_expression))
    else:
        extent = adsk.fusion.DistanceExtentDefinition.create(value(distance_expression))
        extrude_input.setOneSideExtent(extent, direction)
    feature = phone.features.extrudeFeatures.add(extrude_input)
    feature.name = feature_name
    for body_index in range(feature.bodies.count):
        body = feature.bodies.item(body_index)
        body.name = feature_name if body_index == 0 else f'{feature_name} {body_index + 1}'
        apply_appearance(body, appearance)
    return feature


# A vertical capsule on an offset YZ plane. YZ sketch X=-global Z, Y=global Y.
def vertical_capsule_sketch(
    plane,
    initial_center_y,
    initial_length,
    initial_width,
    center_y_expression,
    length_expression,
    width_expression,
    name,
):
    sketch = phone.sketches.add(plane)
    sketch.name = name
    center_x = -cm(7.31 / 2)
    center_y = cm(initial_center_y)
    length = cm(initial_length)
    thickness = cm(initial_width)
    radius = thickness / 2
    top_center = center_y + length / 2 - radius
    bottom_center = center_y - length / 2 + radius

    arcs = sketch.sketchCurves.sketchArcs
    lines = sketch.sketchCurves.sketchLines
    constraints = sketch.geometricConstraints
    # Top cap runs from right to left over the top; bottom cap runs from
    # left to right under the bottom. Positive sweeps avoid major arcs.
    top = arcs.addByCenterStartSweep(
        adsk.core.Point3D.create(center_x, top_center, 0),
        adsk.core.Point3D.create(center_x + radius, top_center, 0),
        math.pi,
    )
    bottom = arcs.addByCenterStartSweep(
        adsk.core.Point3D.create(center_x, bottom_center, 0),
        adsk.core.Point3D.create(center_x - radius, bottom_center, 0),
        math.pi,
    )
    right = lines.addByTwoPoints(top.startSketchPoint, bottom.endSketchPoint)
    left = lines.addByTwoPoints(bottom.startSketchPoint, top.endSketchPoint)
    constraints.addVertical(right)
    constraints.addVertical(left)
    constraints.addEqual(top, bottom)
    axis = lines.addByTwoPoints(top.centerSketchPoint, bottom.centerSketchPoint)
    axis.isConstruction = True
    center_point = sketch.sketchPoints.add(adsk.core.Point3D.create(center_x, center_y, 0))
    constraints.addMidPoint(center_point, axis)

    vertical_dimension(
        sketch, top.centerSketchPoint, bottom.centerSketchPoint,
        f'{length_expression}-{width_expression}', -7, initial_center_y,
    )
    radius_dimension(
        sketch, top, f'{width_expression}/2',
        -6, initial_center_y + initial_length / 2,
    )
    horizontal_dimension(
        sketch, sketch.originPoint, center_point,
        'SE3_ProductThickness/2', -2, initial_center_y - 5,
    )
    vertical_dimension(
        sketch, sketch.originPoint, center_point,
        center_y_expression, -8, initial_center_y / 2,
    )
    sketch.isLightBulbOn = False
    return sketch


# Add a horizontal capsule to a supplied sketch and constrain its center.
def horizontal_capsule_geometry(
    sketch,
    initial_center_x,
    initial_center_y,
    initial_length,
    initial_height,
    length_expression,
    height_expression,
    center_x_expression=None,
    center_y_expression=None,
):
    center_x = cm(initial_center_x)
    center_y = cm(initial_center_y)
    length = cm(initial_length)
    height = cm(initial_height)
    radius = height / 2
    left_center = center_x - length / 2 + radius
    right_center = center_x + length / 2 - radius

    arcs = sketch.sketchCurves.sketchArcs
    lines = sketch.sketchCurves.sketchLines
    constraints = sketch.geometricConstraints
    # Right cap runs bottom-to-top around the outside; left cap runs
    # top-to-bottom around the outside.
    right = arcs.addByCenterStartSweep(
        adsk.core.Point3D.create(right_center, center_y, 0),
        adsk.core.Point3D.create(right_center, center_y - radius, 0),
        math.pi,
    )
    left = arcs.addByCenterStartSweep(
        adsk.core.Point3D.create(left_center, center_y, 0),
        adsk.core.Point3D.create(left_center, center_y + radius, 0),
        math.pi,
    )
    top = lines.addByTwoPoints(left.startSketchPoint, right.endSketchPoint)
    bottom = lines.addByTwoPoints(right.startSketchPoint, left.endSketchPoint)
    constraints.addHorizontal(top)
    constraints.addHorizontal(bottom)
    constraints.addEqual(right, left)
    axis = lines.addByTwoPoints(left.centerSketchPoint, right.centerSketchPoint)
    axis.isConstruction = True
    center_point = sketch.sketchPoints.add(adsk.core.Point3D.create(center_x, center_y, 0))
    constraints.addMidPoint(center_point, axis)

    horizontal_dimension(
        sketch, left.centerSketchPoint, right.centerSketchPoint,
        f'{length_expression}-{height_expression}',
        initial_center_x, initial_center_y + 4,
    )
    radius_dimension(
        sketch, right, f'{height_expression}/2',
        initial_center_x + initial_length / 2 + 2, initial_center_y,
    )
    if center_x_expression:
        horizontal_dimension(
            sketch, sketch.originPoint, center_point,
            center_x_expression, initial_center_x / 2, initial_center_y - 4,
        )
    else:
        constraints.addVerticalPoints(sketch.originPoint, center_point)
    if center_y_expression:
        vertical_dimension(
            sketch, sketch.originPoint, center_point,
            center_y_expression, initial_center_x - 5, initial_center_y / 2,
        )
    else:
        constraints.addHorizontalPoints(sketch.originPoint, center_point)
    return center_point


# Main exact product envelope: 67.27 x 138.44 x 7.31 mm.
rear_sketch = parametric_rounded_rectangle(
    phone.xYConstructionPlane,
    'SE3_OverallWidth', 'SE3_OverallHeight', 'SE3_CornerRadius',
    67.27, 138.44, 9.10, 0, 0, 'SK01 Rear Glass Envelope',
)
extrude_first_profile(rear_sketch, 'SE3_RearGlassThickness', 'Rear Glass', white)

frame_bottom_plane = offset_plane(
    phone.xYConstructionPlane, 'SE3_RearGlassThickness', 'PL02 Frame Bottom'
)
frame_sketch = parametric_rounded_rectangle(
    frame_bottom_plane,
    'SE3_OverallWidth', 'SE3_OverallHeight', 'SE3_CornerRadius',
    67.27, 138.44, 9.10, 0, 0, 'SK02 Aluminum Frame Envelope',
)
extrude_first_profile(
    frame_sketch,
    'SE3_ProductThickness-SE3_RearGlassThickness-SE3_FrontGlassThickness',
    'Aluminum Frame', silver,
)

front_bottom_plane = offset_plane(
    phone.xYConstructionPlane,
    'SE3_ProductThickness-SE3_FrontGlassThickness',
    'PL03 Front Glass Bottom',
)
front_sketch = parametric_rounded_rectangle(
    front_bottom_plane,
    'SE3_OverallWidth', 'SE3_OverallHeight', 'SE3_CornerRadius',
    67.27, 138.44, 9.10, 0, 0, 'SK03 Front Glass Envelope',
)
extrude_first_profile(front_sketch, 'SE3_FrontGlassThickness', 'Front Cover Glass', black)

front_surface = offset_plane(
    phone.xYConstructionPlane, 'SE3_ProductThickness', 'PL10 Front Product Surface'
)

# Front active area. Its Y position uses the specified 17.19 mm top datum.
active_center_y = 138.44 / 2 - 17.19 - 104.05 / 2
active_sketch = parametric_rounded_rectangle(
    front_surface,
    'SE3_ActiveWidth', 'SE3_ActiveHeight', '0.80 mm',
    58.50, 104.05, 0.80, 0, active_center_y,
    'SK10 Front Active Area',
    center_y_expression='SE3_OverallHeight/2-SE3_ActiveTopOffset-SE3_ActiveHeight/2',
)
extrude_first_profile(
    active_sketch, 'SE3_DetailOverlay', 'Front Active Area Reference', blue
)

# Home/Touch ID: center is 9.25 mm from the bottom product datum.
home_sketch = phone.sketches.add(front_surface)
home_sketch.name = 'SK11 Home Button Position - EDIT HERE'
home_circle = home_sketch.sketchCurves.sketchCircles.addByCenterRadius(
    adsk.core.Point3D.create(0, cm(-69.22 + 9.25), 0), cm(10.90 / 2)
)
home_sketch.geometricConstraints.addVerticalPoints(
    home_sketch.originPoint, home_circle.centerSketchPoint
)
vertical_dimension(
    home_sketch,
    home_sketch.originPoint,
    home_circle.centerSketchPoint,
    'SE3_OverallHeight/2-SE3_HomeBottomOffset',
    -8,
    -30,
)
diameter_dimension(home_sketch, home_circle, 'SE3_HomeDiameter', 7, -59.97)
home_sketch.isLightBulbOn = False
extrude_first_profile(home_sketch, 'SE3_DetailOverlay', 'Home Touch ID Sensor', dark)


# Front camera and sensors.
def make_front_circle(sketch_name, x_from_left, top_offset, diameter, x_expr, y_expr, diameter_expr):
    sketch = phone.sketches.add(front_surface)
    sketch.name = sketch_name + ' - EDIT HERE'
    x = -67.27 / 2 + x_from_left
    y = 138.44 / 2 - top_offset
    circle = sketch.sketchCurves.sketchCircles.addByCenterRadius(
        adsk.core.Point3D.create(cm(x), cm(y), 0), cm(diameter / 2)
    )
    horizontal_dimension(sketch, sketch.originPoint, circle.centerSketchPoint, x_expr, x / 2, y - 4)
    vertical_dimension(sketch, sketch.originPoint, circle.centerSketchPoint, y_expr, x + 5, y / 2)
    diameter_dimension(sketch, circle, diameter_expr, x + 3, y + 3)
    sketch.isLightBulbOn = False
    extrude_first_profile(sketch, 'SE3_DetailOverlay', sketch_name.replace('SK', 'Front Detail '), dark)


make_front_circle(
    'SK12 Front Camera Position', 22.99, 9.10, 3.21,
    'SE3_OverallWidth/2-SE3_FrontCameraXFromLeft',
    'SE3_OverallHeight/2-SE3_FrontCameraTopOffset',
    'SE3_FrontCameraDiameter',
)
make_front_circle(
    'SK13 Proximity Sensor Position', 33.63, 4.84, 2.00,
    'SE3_OverallWidth/2-SE3_ProximityXFromLeft',
    'SE3_OverallHeight/2-SE3_ProximityTopOffset',
    'SE3_ProximityDiameter',
)
make_front_circle(
    'SK14 ALS Position', 37.32, 4.84, 2.00,
    'SE3_ALSXFromLeft-SE3_OverallWidth/2',
    'SE3_OverallHeight/2-SE3_ALSTopOffset',
    'SE3_ALSDiameter',
)

receiver_sketch = phone.sketches.add(front_surface)
receiver_sketch.name = 'SK15 Receiver Position - EDIT HERE'
horizontal_capsule_geometry(
    receiver_sketch,
    0,
    69.22 - 9.10,
    11.87,
    1.20,
    'SE3_ReceiverWidth',
    'SE3_ReceiverHeight',
    center_y_expression='SE3_OverallHeight/2-SE3_ReceiverTopOffset',
)
receiver_sketch.isLightBulbOn = False
extrude_first_profile(receiver_sketch, 'SE3_DetailOverlay', 'Receiver Opening', dark)


# Rear camera, microphone and flash. Drawing coordinates are measured from
# the upper-left product datums: 10.44/18.13/22.84 horizontally and 15.40 vertically.
def make_rear_circle(sketch_name, body_name, x_from_left, diameter, x_parameter, diameter_parameter, appearance, depth):
    sketch = phone.sketches.add(phone.xYConstructionPlane)
    sketch.name = sketch_name + ' - EDIT HERE'
    x = -67.27 / 2 + x_from_left
    y = 138.44 / 2 - 15.40
    circle = sketch.sketchCurves.sketchCircles.addByCenterRadius(
        adsk.core.Point3D.create(cm(x), cm(y), 0), cm(diameter / 2)
    )
    horizontal_dimension(
        sketch, sketch.originPoint, circle.centerSketchPoint,
        f'SE3_OverallWidth/2-{x_parameter}', x / 2, y - 5,
    )
    vertical_dimension(
        sketch, sketch.originPoint, circle.centerSketchPoint,
        'SE3_OverallHeight/2-SE3_RearFeatureTopOffset', x + 5, y / 2,
    )
    diameter_dimension(sketch, circle, diameter_parameter, x + 3, y + 3)
    sketch.isLightBulbOn = False
    extrude_first_profile(
        sketch,
        depth,
        body_name,
        appearance,
        direction=adsk.fusion.ExtentDirections.NegativeExtentDirection,
    )


make_rear_circle(
    'SK20 Rear Camera Position', 'Rear Camera Bump', 10.44, 8.57,
    'SE3_RearCameraXFromLeft', 'SE3_RearCameraDiameter', dark, 'SE3_CameraBumpHeight',
)
make_rear_circle(
    'SK21 Rear Microphone Position', 'Rear Microphone', 18.13, 1.50,
    'SE3_RearMicXFromLeft', 'SE3_RearMicDiameter', dark, 'SE3_DetailOverlay',
)
make_rear_circle(
    'SK22 Rear Flash Position', 'Rear Flash', 22.84, 3.75,
    'SE3_RearFlashXFromLeft', 'SE3_RearFlashDiameter', flash_appearance, 'SE3_DetailOverlay',
)

# Side controls. All positions are driven by sketch dimensions from the top datum.
left_side_plane = offset_plane(
    phone.yZConstructionPlane, '-SE3_OverallWidth/2', 'PL30 Left Side Button Datum'
)
right_side_plane = offset_plane(
    phone.yZConstructionPlane, 'SE3_OverallWidth/2', 'PL34 Right Side Button Datum'
)

ring_center_y = 69.22 - 17.56 - 5.61 / 2
ring_sketch = vertical_capsule_sketch(
    left_side_plane, ring_center_y, 5.61, 1.80,
    'SE3_OverallHeight/2-SE3_RingTopOffset-SE3_RingLength/2',
    'SE3_RingLength', 'SE3_ButtonFaceWidth',
    'SK30 Ring Silent Switch Position - EDIT HERE',
)
extrude_first_profile(
    ring_sketch, 'SE3_RingProjection', 'Ring Silent Switch', silver,
    direction=adsk.fusion.ExtentDirections.NegativeExtentDirection,
)

volume_plus_center_y = 69.22 - 34.56
volume_plus_sketch = vertical_capsule_sketch(
    left_side_plane, volume_plus_center_y, 10.62, 1.80,
    'SE3_OverallHeight/2-SE3_VolumePlusCenterFromTop',
    'SE3_ButtonLength', 'SE3_ButtonFaceWidth',
    'SK31 Volume Plus Position - EDIT HERE',
)
extrude_first_profile(
    volume_plus_sketch, 'SE3_ButtonProjection', 'Volume Plus Button', silver,
    direction=adsk.fusion.ExtentDirections.NegativeExtentDirection,
)

volume_minus_center_y = 69.22 - 47.17
volume_minus_sketch = vertical_capsule_sketch(
    left_side_plane, volume_minus_center_y, 10.62, 1.80,
    'SE3_OverallHeight/2-SE3_VolumeMinusCenterFromTop',
    'SE3_ButtonLength', 'SE3_ButtonFaceWidth',
    'SK32 Volume Minus Position - EDIT HERE',
)
extrude_first_profile(
    volume_minus_sketch, 'SE3_ButtonProjection', 'Volume Minus Button', silver,
    direction=adsk.fusion.ExtentDirections.NegativeExtentDirection,
)

side_button_center_y = 69.22 - 34.64
side_button_sketch = vertical_capsule_sketch(
    right_side_plane, side_button_center_y, 10.62, 1.80,
    'SE3_OverallHeight/2-SE3_SideButtonCenterFromTop',
    'SE3_ButtonLength', 'SE3_ButtonFaceWidth',
    'SK34 Side Button Position - EDIT HERE',
)
extrude_first_profile(
    side_button_sketch, 'SE3_ButtonProjection', 'Side Button', silver,
    direction=adsk.fusion.ExtentDirections.PositiveExtentDirection,
)

sim_center_y = 69.22 - 52.72 - 15.67 / 2
sim_sketch = vertical_capsule_sketch(
    right_side_plane, sim_center_y, 15.67, 2.30,
    'SE3_OverallHeight/2-SE3_SIMTrayTopOffset-SE3_SIMTrayLength/2',
    'SE3_SIMTrayLength', 'SE3_SIMTrayWidth',
    'SK35 SIM Tray Position - EDIT HERE',
)
extrude_first_profile(
    sim_sketch, '0.05 mm', 'SIM Tray Seam', None,
    operation=adsk.fusion.FeatureOperations.CutFeatureOperation,
    direction=adsk.fusion.ExtentDirections.NegativeExtentDirection,
)

# Bottom port, screws and acoustic holes. XZ sketch coordinates are
# local X=global X and local Y=-global Z.
bottom_plane = offset_plane(
    phone.xZConstructionPlane, '-SE3_OverallHeight/2', 'PL40 Bottom Product Datum'
)
bottom_sketch = phone.sketches.add(bottom_plane)
bottom_sketch.name = 'SK40 Bottom Port Screws and Speaker Holes - EDIT HERE'

horizontal_capsule_geometry(
    bottom_sketch,
    0,
    -7.31 / 2,
    8.70,
    1.60,
    'SE3_LightningWidth',
    'SE3_LightningHeight',
    center_y_expression='SE3_ProductThickness/2',
)

# Detail E gives 2 bottom-mic holes plus 10 speaker holes: six openings on
# each side. First/last centers are 10.26/22.26 and 45.01/57.01 mm from
# the left datum, so the five equal intervals are 2.40 mm.
for side in ('left', 'right'):
    initial_first = 10.26 if side == 'left' else 45.01
    first_parameter = (
        'SE3_BottomHoleFirstFromLeft'
        if side == 'left'
        else 'SE3_BottomRightFirstFromLeft'
    )
    for hole_index in range(6):
        from_left = initial_first + 2.40 * hole_index
        x = -67.27 / 2 + from_left
        circle = bottom_sketch.sketchCurves.sketchCircles.addByCenterRadius(
            adsk.core.Point3D.create(cm(x), cm(-7.31 / 2), 0), cm(1.45 / 2)
        )
        if x < 0:
            x_expression = (
                f'SE3_OverallWidth/2-({first_parameter}+{hole_index}*SE3_BottomHolePitch)'
            )
        else:
            x_expression = (
                f'({first_parameter}+{hole_index}*SE3_BottomHolePitch)-SE3_OverallWidth/2'
            )
        horizontal_dimension(
            bottom_sketch, bottom_sketch.originPoint, circle.centerSketchPoint,
            x_expression, x / 2, -7,
        )
        vertical_dimension(
            bottom_sketch, bottom_sketch.originPoint, circle.centerSketchPoint,
            'SE3_ProductThickness/2', x + 1, -1.8,
        )
        diameter_dimension(
            bottom_sketch, circle, 'SE3_BottomHoleDiameter', x + 1, -4.8,
        )

# Screw centers are 27.24 and 40.03 mm from the left datum.
for from_left, parameter_name in (
    (27.24, 'SE3_LeftScrewFromLeft'),
    (40.03, 'SE3_RightScrewFromLeft'),
):
    x = -67.27 / 2 + from_left
    circle = bottom_sketch.sketchCurves.sketchCircles.addByCenterRadius(
        adsk.core.Point3D.create(cm(x), cm(-7.31 / 2), 0), cm(1.60 / 2)
    )
    if x < 0:
        x_expression = f'SE3_OverallWidth/2-{parameter_name}'
    else:
        x_expression = f'{parameter_name}-SE3_OverallWidth/2'
    horizontal_dimension(
        bottom_sketch, bottom_sketch.originPoint, circle.centerSketchPoint,
        x_expression, x / 2, -7,
    )
    vertical_dimension(
        bottom_sketch, bottom_sketch.originPoint, circle.centerSketchPoint,
        'SE3_ProductThickness/2', x + 1, -1.8,
    )
    diameter_dimension(bottom_sketch, circle, 'SE3_ScrewDiameter', x + 1, -4.8)

bottom_sketch.isLightBulbOn = False
bottom_profiles = adsk.core.ObjectCollection.create()
for profile_index in range(bottom_sketch.profiles.count):
    bottom_profiles.add(bottom_sketch.profiles.item(profile_index))
bottom_cut_input = phone.features.extrudeFeatures.createInput(
    bottom_profiles, adsk.fusion.FeatureOperations.CutFeatureOperation
)
bottom_cut_input.setOneSideExtent(
    adsk.fusion.DistanceExtentDefinition.create(value('1.00 mm')),
    adsk.fusion.ExtentDirections.PositiveExtentDirection,
)
bottom_cut = phone.features.extrudeFeatures.add(bottom_cut_input)
bottom_cut.name = 'Bottom Port and Acoustic Openings'
# Cut features may inherit their name onto the modified target body.
for body_index in range(phone.bRepBodies.count):
    body = phone.bRepBodies.item(body_index)
    bounds = body.boundingBox
    body_thickness_mm = (bounds.maxPoint.z - bounds.minPoint.z) * 10
    if abs(body_thickness_mm - 5.51) < 0.02:
        body.name = 'Aluminum Frame'
        apply_appearance(body, silver)

# Midplane envelope for downstream robot fixture design.
midplane = offset_plane(
    phone.xYConstructionPlane, 'SE3_ProductThickness/2', 'PL90 Product Midplane'
)
parametric_rounded_rectangle(
    midplane,
    'SE3_OverallWidth', 'SE3_OverallHeight', 'SE3_CornerRadius',
    67.27, 138.44, 9.10, 0, 0, 'SK90 Nominal Product Envelope',
)

try:
    app.activeViewport.fit()
    app.activeViewport.refresh()
except RuntimeError:
    pass

result = {
    'component': phone.name,
    'body_count': phone.bRepBodies.count,
    'sketch_count': phone.sketches.count,
    'feature_count': phone.features.count,
    'parameter_count': design.userParameters.count,
}
