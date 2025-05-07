

# See https://forum.image.sc/t/importing-ndpa-annotations-into-omero/99874/5

import argparse
import sys

import omero
import omero.clients
from omero.sys import ParametersI
from omero.rtypes import wrap
from omero.cli import cli_login
from omero.gateway import BlitzGateway
import random
from datetime import datetime

roi_colors = {}


def get_roi_color(roi_id):
    """ Return the color of the ROI as an Integer in RGBA encoding """
    if roi_id not in roi_colors:
        red = random.randint(0, 55) + 200
        green = random.randint(0, 55) + 200
        blue = random.randint(0, 55) + 200
        alpha = 150
        roi_colors[roi_id] = rgba_to_int(red, green, blue, alpha)
    return roi_colors[roi_id]


def rgba_to_int(red, green, blue, alpha=255):
    """ Return the color as an Integer in RGBA encoding """
    r = red << 24
    g = green << 16
    b = blue << 8
    a = alpha
    rgba_int = r+g+b+a
    if (rgba_int > (2**31-1)):       # convert to signed 32-bit int
        rgba_int = rgba_int - 2**32
    return rgba_int


def main(argv):

    start = datetime.now()
    print("Start", start)

    # We run the script for each Dataset...
    parser = argparse.ArgumentParser()
    parser.add_argument('dataset_id', help='Dataset ID')
    args = parser.parse_args(argv)

    with cli_login() as cli:
        conn = BlitzGateway(client_obj=cli._client)
        roi_service = conn.getRoiService()

        # for name in ["A", "B", "C", "D"]:
        #     pname = f"idr0156-szabo-tadcnd/experiment{name}"
        #     project = conn.getObject("Project", attributes={"name": pname})
        #     print(f"Project {pname}", project.id)
        #     if project is None:
        #         print(f"Project {pname} not found")
        #         continue

        dataset = conn.getObject("Dataset", args.dataset_id)

        print("Dataset", dataset.id, dataset.name)
        images = list(dataset.listChildren())
        images.sort(key=lambda x: x.id)

        for count, image in enumerate(images):
            to_save = []
            print(f"  Image {count + 1}/{len(images)}", image.id, image.name)
            print("   duration", datetime.now() - start)
            result = roi_service.findByImage(image.id, None)
            for roi in result.rois:
                for s in roi.copyShapes():
                    shapeWrapper = conn.getObject("Shape", s.id.val)
                    fill_color = get_roi_color(roi.getId().getValue())
                    shapeWrapper.setFillColor(wrap(fill_color))
                    # shapeWrapper.save()
                    to_save.append(shapeWrapper._obj)
            conn.getUpdateService().saveArray(to_save)

if __name__ == '__main__':
    main(sys.argv[1:])
