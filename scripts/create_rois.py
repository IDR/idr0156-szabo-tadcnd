import numpy as np
import omero
import omero.cli
from omero.gateway import BlitzGateway, ColorHolder
import omero_rois
from omero.rtypes import rdouble, rint, rstring

from tifffile import tifffile
from omero.model import RoiI, MaskI


# Based on Julio's script: https://github.com/Georgesalzoghby/Image-Data-Annotation/blob/main/scripts/annotate_rois.py


PROJECT_NAME = "idr0156-szabo-tadcnd/experiment"
# /uod/idr/filesets/idr0156-szabo-tadcnd/20220614-Globus/idr0xxx-szabo-tads_ExperimentA/ESC
PATH = "/uod/idr/filesets/idr0156-szabo-tadcnd/20220614-Globus/idr0xxx-szabo-tads_Experiment<ID>/<DATASET_NAME>/<IMAGE_NAME>"


def load_images(conn):
    for exp in ["A", "B", "C", "D", "E", "F", "G"]:
        proj_name = f"PROJECT_NAME{exp}"
        project = conn.getObject("Project", attributes={"name": proj_name})
        for dataset in project.listChildren():
            images = []
            for image in dataset.listChildren():
                images.append(image)
            yield exp, dataset, images


def delete_masks(conn, img):
    to_delete = []
    result = conn.getRoiService().findByImage(img.id, None)
    for roi in result.rois:
        try:
            s = roi.copyShapes()[0]
            if type(s) == omero.model.MaskI:
                to_delete.append(roi.getId().getValue())
        except Exception as e:
            print(e)
    if to_delete:
        conn.deleteObjects("Roi", to_delete, deleteChildren=True, wait=True)


def masks_from_labels_image_3d(
        labels_3d, rgba=None, c=None, t=None, text=None,
        raise_on_no_mask=True):
    rois = {}
    for i in range(1, labels_3d.max() + 1):
        if not np.any(labels_3d == i):
            continue

        masks = []
        bin_img = labels_3d == i
        # Find bounding box to minimise size of mask
        xmask = bin_img.sum(0).sum(0).nonzero()[0]
        ymask = bin_img.sum(0).sum(1).nonzero()[0]
        if any(xmask) and any(ymask):
            x0 = min(xmask)
            w = max(xmask) - x0 + 1
            y0 = min(ymask)
            h = max(ymask) - y0 + 1
            submask = bin_img[:, y0:(y0 + h), x0:(x0 + w)]
        else:
            if raise_on_no_mask:
                raise omero_rois.NoMaskFound()
            x0 = 0
            w = 0
            y0 = 0
            h = 0
            submask = []

        for z, plane in enumerate(submask):
            if np.any(plane):
                mask = MaskI()
                mask.setBytes(np.packbits(np.asarray(plane, dtype=int)))
                mask.setWidth(rdouble(w))
                mask.setHeight(rdouble(h))
                mask.setX(rdouble(x0))
                mask.setY(rdouble(y0))
                mask.setTheZ(rint(z))

                if rgba is not None:
                    ch = ColorHolder.fromRGBA(*rgba)
                    mask.setFillColor(rint(ch.getInt()))
                if c is not None:
                    mask.setTheC(rint(c))
                if t is not None:
                    mask.setTheT(rint(t))
                if text is not None:
                    mask.setTextValue(rstring(text))

                masks.append(mask)

        rois[i] = masks

    return rois


def rois_from_labels_3d(conn, img, labels_3d, rgba=None, c=None, t=None, text=None):
    rois = masks_from_labels_image_3d(labels_3d, rgba=rgba, c=c, t=t,
                                      raise_on_no_mask=False)

    for label, masks in rois.items():
        if len(masks) > 0:
            if c is None:
                roi_name = f'{text}_label-{label}'
            else:
                roi_name = f'ch-{c}_{text}_label-{label}'
            create_roi(conn, img=img, shapes=masks, name=roi_name)


def create_roi(conn, img, shapes, name):
    # create an ROI, link it to Image
    roi = RoiI()
    # use the omero.model.ImageI that underlies the 'image' wrapper
    roi.setImage(img._obj)
    roi.setName(rstring(name))
    for shape in shapes:
        # shape.setTextValue(rstring(name))
        roi.addShape(shape)
    # Save the ROI (saves any linked shapes too)
    print(f"Save ROI for image {img.getName()}")
    return conn.getUpdateService().saveAndReturnObject(roi)


def create_masks(conn, exp, ds_name, base_img, label_img_name, kind):
    try:
        path = PATH.replace("<ID>", exp)
        path = path.replace("<DATASET_NAME>", ds_name)
        path = path.replace("<IMAGE_NAME>", label_img_name)
        label_img = tifffile.imread(path)
        if label_img.ndim == 4:
            label_img = label_img.transpose((1, 0, 2, 3))
        elif label_img.ndim == 3:
            label_img = np.expand_dims(label_img, 0)

        for c, channel_labels in enumerate(label_img):
            if c == 0:
                rgba = (255, 0, 0, 30)
            elif c == 1:
                rgba = (0, 255, 0, 30)
            else:
                rgba = (0, 0, 255, 30)

            rois_from_labels_3d(conn, img=base_img,
                                labels_3d=channel_labels,
                                rgba=rgba,
                                c=c,
                                text=kind)
    except FileNotFoundError:
        pass


def main():
    with omero.cli.cli_login() as c:
        conn = BlitzGateway(client_obj=c.get_client())
        for exp, ds, images in load_images(conn):
            for img in images:
                delete_masks(conn, img)

                label_img_name = img.getName().replace(".ome.tiff", "_domains-ROIs.ome.tiff")
                create_masks(conn, exp, ds.getName(), img, label_img_name, "domain")

                label_img_name = img.getName().replace(".ome.tiff", "_subdomains-ROIs.ome.tiff")
                create_masks(conn, exp, ds.getName(), img, label_img_name, "subdomain")

                label_img_name = img.getName().replace(".ome.tiff", "_overlap-ROIs.ome.tiff")
                create_masks(conn, exp, ds.getName(), img, label_img_name, "overlap")


if __name__ == "__main__":
    main()
