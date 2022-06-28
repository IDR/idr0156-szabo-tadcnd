import re
import omero
import omero.cli
import omero.gateway
from omero_rois import mask_from_binary_image
from skimage.io import imread


# /uod/idr/filesets/idr0000-szabo/20220616-ftp/CTCF-AID/20190723_RI512_CTCF-AID_AUX-CTL_111_112_SIR_2C_ALN_THR_1_domains-ROIs.ome.tiff
# /uod/idr/filesets/idr0000-szabo/20220616-ftp/CTCF-AID/20190730_RI512_CTCF-AID_AUX-CTL_21_22_SIR_2C_ALN_THR_83.ome.tiff
# /uod/idr/filesets/idr0000-szabo/20220616-ftp/CTCF-AID/20190722_RI512_CTCF-AID_AUX-CTL_52_51b_SIR_2C_ALN_THR_29_subdomains-ROIs.ome.tiff
DOM_FORMAT = ".*/(.+)_domains-ROIs.ome.tiff"
SUBDOM_FORMAT = ".*/(.+)_subdomains-ROIs.ome.tiff"


def get_masks(filename, ch):
    # mask images aren't labelled, but the two masks are in two different channels
    # [z][ch][x][y]
    bytes = imread(filename)
    for z in range(bytes.shape[0]):
        yield z, bytes[z][ch]


def add_masks(conn, image_name, filename, text):
    img = conn.getObject('Image', attributes={"name": image_name})
    delete_masks(conn, img, text)
    count = 0
    for z, mask_data in get_masks(filename, 0):
        # convert to binary
        mask_data[mask_data > 1] = 1
        try:
            mask = mask_from_binary_image(mask_data, rgba=(255, 255, 255, 128),
                                          t=0, z=z, text=text)
            roi = omero.model.RoiI()
            roi.addShape(mask)
            us = conn.getUpdateService()
            roi.setImage(img._obj)
            roi = us.saveAndReturnObject(roi)
            count += 1
        except:
            pass
    print(f"Added {count} {text} masks to {image_name}")


def delete_masks(conn, img, text):
    to_delete = []
    result = conn.getRoiService().findByImage(img.id, None)
    for roi in result.rois:
        try:
            s = roi.copyShapes()[0]
            if type(s) == omero.model.MaskI and s.getTextValue().getValue() == text:
                to_delete.append(roi.getId().getValue())
        except Exception as e:
            print(e)
    if to_delete:
        conn.deleteObjects("Roi", to_delete, deleteChildren=True, wait=True)


def main():
    with omero.cli.cli_login() as c:
        conn = omero.gateway.BlitzGateway(client_obj=c.get_client())

        entries = open("rois.txt", 'r').readlines()
        for entry in entries:
            entry = entry.strip()
            match = re.search(DOM_FORMAT, entry, re.IGNORECASE)
            if match:
                image_name = f"{match.group(1)}.ome.tiff"
                add_masks(conn, image_name, entry, "Domain")
            match = re.search(SUBDOM_FORMAT, entry, re.IGNORECASE)
            if match:
                image_name = f"{match.group(1)}.ome.tiff"
                add_masks(conn, image_name, entry, "Subdomain")


if __name__ == "__main__":
    main()
