import click
from frappe.commands import get_site, pass_context


@click.command("photos-demo-data")
@click.option("--images", "images_dir", help="Folder of .jpg or .png files to use instead of downloading")
@click.option("--count", default=80, show_default=True, help="Number of photos to load")
@pass_context
def photos_demo_data(context, images_dir=None, count=80):
    "Load demo photos, people and shared albums into Photos"
    import frappe

    frappe.init(site=get_site(context))
    frappe.connect()
    try:
        from suite.photos.demo import load

        load(images_dir=images_dir, count=count)
    finally:
        frappe.destroy()


@click.command("photos-setup-faces")
@click.option("--scan", is_flag=True, help="Also scan existing photos for faces")
@pass_context
def photos_setup_faces(context, scan=False):
    "Download the face models used by Photos and optionally scan existing photos"
    import frappe

    frappe.init(site=get_site(context))
    frappe.connect()
    try:
        from suite.photos import faces

        faces.setup_models()
        if not faces.available():
            print("Install opencv-python-headless to turn on faces: bench pip install opencv-python-headless")
            return
        if scan:
            faces.scan_all()
    finally:
        frappe.destroy()


commands = [photos_demo_data, photos_setup_faces]
