import csv
import sys
import omero.cli
from omero.gateway import BlitzGateway


# Have to call it with the csv file as argument, within the experimentX directory, e.g.
# python update_processed.py idr0156-experimentA-processed.csv
# Will create one csv / dataset, e.g. experimentA-ESC-processed.csv which then can be attached
# to the dataset like
# omero metadata populate Dataset:12345 --allow_nan --file experimentA-ESC-processed.csv


PROJECT_NAME = "idr0156-szabo-tadcnd/experiment"
HEADER = "# header roi,image,s,d,s,d,d,d,d,d,d,d,d,d,d,d,d,d,d,d,d,s,d,d,d,d,d,s,s"

def load_images(conn, proj_name):
    project = conn.getObject("Project", attributes={"name": proj_name})
    images = []
    ds_names = dict()
    for dataset in project.listChildren():
        for image in dataset.listChildren():
            images.append(image)
            ds_names[image.getName()] = dataset.getName()
    return ds_names, images


def get_roi_id(conn, image, roi_name):
    roi_service = conn.getRoiService()
    result = roi_service.findByImage(image.getId(), None)
    for roi in result.rois:
        if roi.getName().getValue() == roi_name:
            return roi.getId().getValue()
    return None


def main(filename):
    exp_no = filename.replace("idr0156-experiment", "").replace("-processed.csv", "")
    proj = f"{PROJECT_NAME}{exp_no}"
    with omero.cli.cli_login() as c:
        conn = BlitzGateway(client_obj=c.get_client())
        ds_names, images = load_images(conn, proj)
        with open(filename, mode="r") as csvfile:
            reader = csv.DictReader(csvfile)
            fnames = reader.fieldnames.copy()
            fnames.insert(0, "Image")
            fnames.insert(0, "Roi")
            writers = dict()
            ofiles = []
            for ds in set(ds_names.values()):
                outfile = open(f"experiment{exp_no}-{ds}-processed.csv", mode="w")
                ofiles.append(outfile)
                outfile.write(f"{HEADER}\n")
                writer = csv.DictWriter(outfile, fieldnames=fnames)
                writer.writeheader()
                writers[ds] = writer

            for row in reader:
                img_name = row["Image Name"]
                roi_name = row["Roi Name"]
                ds_name = ds_names.get(img_name)
                row["Image"] = "-1"
                row["Roi"] = "-1"
                img = list(filter(lambda i: i.getName() == img_name, images))
                if not img:
                    print(f"Could not find image {img_name}")
                    continue
                roi_id = get_roi_id(conn, img[0], roi_name)
                if not roi_id:
                    print(f"Could not find ROI {roi_name}")
                    continue
                row["Image"] = img[0].getId()
                row["Roi"] = roi_id
                writers[ds_name].writerow(row)

            for ofile in ofiles:
                ofile.close()


if __name__ == "__main__":
    main(sys.argv[1])
