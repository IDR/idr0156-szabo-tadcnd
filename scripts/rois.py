import omero
import omero.cli
import omero.gateway
import os
from omero.gateway import ColorHolder
from omero.rtypes import rdouble, rint, rstring
from omero.model import RoiI, MaskI
import omero_rois
import numpy as np
from tifffile import tifffile

# Based on https://github.com/Georgesalzoghby/Image-Data-Annotation/blob/19096ce6e69f7c1bcf7ff153810418be042a973e/scripts/annotate_rois.py

ROI_IMG_DIR = "/uod/idr/filesets/idr0000-szabo/20220616-ftp/CTCF-AID"
DATASET_NAME = "CTCF-AID"


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
    """
    Create a mask shape from a binary image (background=0)

    :param numpy.array labels_3d: labels 3D array
    :param rgba int-4-tuple: Optional (red, green, blue, alpha) colour
    :param c: Optional C-index for the mask
    :param t: Optional T-index for the mask
    :param text: Optional text for the mask
    :param raise_on_no_mask: If True (default) throw an exception if no mask
           found, otherwise return an empty Mask
    :return: An OMERO mask
    :raises NoMaskFound: If no labels were found
    :raises InvalidBinaryImage: If the maximum labels is greater than 1
    """
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
                # BUG in older versions of Numpy:
                # https://github.com/numpy/numpy/issues/5377
                # Need to convert to an int array
                # mask.setBytes(np.packbits(submask))
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


def create_roi(conn, img, shapes, name):
    # create an ROI, link it to Image
    roi = RoiI()
    # use the omero.model.ImageI that underlies the 'image' wrapper
    roi.setImage(img._obj)
    roi.setName(rstring(name))
    for shape in shapes:
        roi.addShape(shape)
    # Save the ROI (saves any linked shapes too)
    return conn.getUpdateService().saveAndReturnObject(roi)


def rois_from_labels_3d(conn, img, labels_3d, rgba, c=None, t=None, text=None):
    rois = masks_from_labels_image_3d(labels_3d, rgba=rgba, c=c, t=t,
                                      raise_on_no_mask=False)

    for label, masks in rois.items():
        if len(masks) > 0:
            create_roi(conn, img=img, shapes=masks, name=f'{text}_{label}')


def main():
    with omero.cli.cli_login() as c:
        conn = omero.gateway.BlitzGateway(client_obj=c.get_client())

        dataset = conn.getObject('Dataset', attributes={"name": DATASET_NAME})
        for image in dataset.listChildren():
            image_name = image.getName()
            print(f"annotating image: {image_name}")

            delete_masks(conn, image)

            # Domains
            try:
                domains_img = tifffile.imread(os.path.join(ROI_IMG_DIR, f"{image_name[:-9]}_domains-ROIs.ome.tiff"))
                domains_img = domains_img.transpose((1, 0, 2, 3))
                for c, channel_labels in enumerate(domains_img):
                    if c == 0:
                        rgba = (255, 0, 0, 30)
                    elif c == 1:
                        rgba = (0, 255, 0, 30)
                    else:
                        rgba = (0, 0, 255, 30)

                    rois_from_labels_3d(conn, img=image,
                                        labels_3d=channel_labels,
                                        rgba=rgba,
                                        c=c,
                                        text='domain')
            except FileNotFoundError:
                pass

            # Subdomains
            try:
                subdomains_img = tifffile.imread(os.path.join(ROI_IMG_DIR, f"{image_name[:-9]}_subdomains-ROIs.ome.tiff"))
                subdomains_img = subdomains_img.transpose((1, 0, 2, 3))
                for c, channel_labels in enumerate(subdomains_img):
                    if c == 0:
                        rgba = (180, 0, 0, 50)
                    elif c == 1:
                        rgba = (0, 180, 0, 50)
                    else:
                        rgba = (0, 0, 180, 50)

                    rois_from_labels_3d(conn, img=image,
                                        labels_3d=channel_labels,
                                        rgba=rgba,
                                        c=c,
                                        text='subdomain')
            except FileNotFoundError:
                pass


if __name__ == "__main__":
    main()
