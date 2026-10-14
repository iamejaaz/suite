import json
import re

import frappe
from pypika import Criterion, CustomFunction, Order
from pypika import functions as fn

from suite.drive.api.files import create_folder
from suite.drive.api.list import get_query_data
from suite.drive.api.permissions import get_user_access, user_has_permission
from suite.drive.utils import STATUS_ACTIVE, STATUS_TRASHED, get_principals, get_user_folder
from suite.drive.utils.overrides import file_permission_criterion
from suite.photos.metadata import enqueue_missing

File = frappe.qb.DocType("File")
Metadata = frappe.qb.DocType("Photo Metadata")
Archive = frappe.qb.DocType("Photo Archive")
Year = CustomFunction("YEAR", ["date"])
Month = CustomFunction("MONTH", ["date"])
DayOfYear = CustomFunction("DAYOFYEAR", ["date"])

UPLOAD_FOLDER = "Photos"
PAGE_SIZE = 120
MONTHS = [
    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
]

taken = fn.Coalesce(Metadata.taken_on, File.file_modified, File.creation)


def media_query(**kwargs):
    return (
        media_base(**kwargs)
        .select(
            taken.as_("taken"),
            File.mime_type,
            Metadata.name.as_("metadata"),
            Metadata.width,
            Metadata.height,
            Metadata.duration,
            Metadata.camera,
            Metadata.latitude,
            Metadata.longitude,
        )
        .orderby(taken, order=Order.desc)
    )


def media_base(status=STATUS_ACTIVE, check_permission=True, archived=False):
    query = (
        frappe.qb.from_(File)
        .left_join(Metadata)
        .on(Metadata.file == File.name)
        .where(File.status == status)
        .where(File.is_folder == 0)
        .where(File.attached_to_doctype.isnull())
        .where(Criterion.any([File.mime_type.like("image/%"), File.mime_type.like("video/%")]))
    )
    archived_files = frappe.qb.from_(Archive).select(Archive.file).where(Archive.user == frappe.session.user)
    if archived is not None:
        query = query.where(File.name.isin(archived_files) if archived else File.name.notin(archived_files))
    if check_permission and (permission := _permission_criterion()):
        query = query.where(permission)
    return query


def _permission_criterion():
    criterion = file_permission_criterion(table=File)
    if criterion is None:
        return None
    folders = _shared_folders()
    return criterion | File.folder.isin(folders) if folders else criterion


def _shared_folders():
    principals = get_principals()
    return frappe.db.sql_list(
        """
        with recursive shared as (
            select f.name from `tabFile` f
            join `tabDrive Permission` p on p.entity = f.name
            where f.is_folder = 1 and p.user in %(principals)s and p.`read` = 1 and p.deny = 0
            union
            select child.name from `tabFile` child join shared on child.folder = shared.name
            where child.is_folder = 1
        )
        select name from shared limit 5000
        """,
        {"principals": principals},
    )


def _apply_search(query, search):
    for token in (search or "").lower().split():
        if re.fullmatch(r"(19|20)\d\d", token):
            query = query.where(Year(taken) == int(token))
        elif month := next(
            (i for i, m in enumerate(MONTHS, 1) if len(token) >= 3 and m.startswith(token)), None
        ):
            query = query.where(Month(taken) == month)
        elif token in ("video", "videos"):
            query = query.where(File.mime_type.like("video/%"))
        elif token in ("photo", "photos", "image", "images"):
            query = query.where(File.mime_type.like("image/%"))
        else:
            like = f"%{token}%"
            query = query.where(File.file_name.like(like) | Metadata.camera.like(like))
    return query


def page(query, start, limit, favourites_only=False):
    result = get_query_data(
        query,
        favourites_only=favourites_only,
        order_by="creation",
        ascending=False,
        start=start,
        limit=limit or PAGE_SIZE,
        paginated=True,
    )
    missing = [row["name"] for row in result["rows"] if not row.get("metadata")]
    if missing:
        enqueue_missing(missing)
    return result


@frappe.whitelist()
def timeline(
    start: int = 0,
    limit: int | None = None,
    search: str | None = None,
    camera: str | None = None,
    place: str | None = None,
):
    query = _apply_search(media_query(), search)
    if camera:
        query = query.where(Metadata.camera == camera)
    if place:
        lat, lon = (float(x) for x in place.split(","))
        query = query.where(
            (fn.Abs(Metadata.latitude - lat) < 0.05) & (fn.Abs(Metadata.longitude - lon) < 0.05)
        )
    return page(query, start, limit)


@frappe.whitelist()
def favourites(start: int = 0, limit: int | None = None):
    return page(media_query(), start, limit, favourites_only=True)


@frappe.whitelist()
def archived(start: int = 0, limit: int | None = None):
    return page(media_query(archived=True), start, limit)


@frappe.whitelist()
def trash(start: int = 0, limit: int | None = None):
    query = media_query(status=STATUS_TRASHED, check_permission=False, archived=None).where(
        File.owner == frappe.session.user
    )
    return page(query, start, limit)


@frappe.whitelist()
def set_archived(files: list[str] | str, archived: bool = True):
    files = _as_list(files)
    archived = frappe.parse_json(archived) if isinstance(archived, str) else archived
    user = frappe.session.user
    frappe.db.delete("Photo Archive", {"user": user, "file": ["in", files]})
    if archived:
        for file in files:
            if user_has_permission(file, "read"):
                frappe.get_doc({"doctype": "Photo Archive", "user": user, "file": file}).insert(
                    ignore_permissions=True
                )


@frappe.whitelist()
def months():
    return (
        media_base()
        .select(Year(taken).as_("year"), Month(taken).as_("month"), fn.Count(File.name).as_("count"))
        .groupby(Year(taken), Month(taken))
        .orderby(Year(taken), order=Order.desc)
        .orderby(Month(taken), order=Order.desc)
        .run(as_dict=True)
    )


@frappe.whitelist()
def memories():
    today = frappe.utils.getdate()
    query = media_query().where(Year(taken) < today.year)
    query = query.where(fn.Abs(DayOfYear(taken) - today.timetuple().tm_yday) <= 3)
    rows = page(query, 0, 60)["rows"]
    years = {}
    for row in rows:
        years.setdefault(row["taken"].year, []).append(row)
    return [
        {"year": year, "years_ago": today.year - year, "photos": photos[:12]}
        for year, photos in sorted(years.items(), reverse=True)
    ]


@frappe.whitelist()
def places():
    query = media_query().where((Metadata.latitude != 0) | (Metadata.longitude != 0))
    rows = page(query, 0, 1000)["rows"]
    groups = {}
    for row in rows:
        key = (round(row["latitude"], 1), round(row["longitude"], 1))
        group = groups.setdefault(
            key, {"latitude": key[0], "longitude": key[1], "count": 0, "cover": row["name"]}
        )
        group["count"] += 1
    return sorted(groups.values(), key=lambda g: -g["count"])


@frappe.whitelist()
def explore():
    cameras = (
        media_base()
        .where(Metadata.camera.isnotnull())
        .select(
            Metadata.camera.as_("camera"), fn.Max(File.name).as_("cover"), fn.Count(File.name).as_("count")
        )
        .groupby(Metadata.camera)
        .orderby(fn.Count(File.name), order=Order.desc)
        .limit(12)
    )
    videos = (
        media_base()
        .where(File.mime_type.like("video/%"))
        .select(fn.Count(File.name).as_("count"), fn.Max(File.name).as_("cover"))
    )
    return {
        "places": places()[:12],
        "cameras": cameras.run(as_dict=True),
        "videos": videos.run(as_dict=True)[0],
    }


@frappe.whitelist()
def get_upload_folder():
    home = get_user_folder()
    folder = frappe.db.get_value(
        "File",
        {"folder": home.name, "file_name": UPLOAD_FOLDER, "is_folder": 1, "status": STATUS_ACTIVE},
        "name",
    )
    return folder or create_folder(UPLOAD_FOLDER, home.name).name


@frappe.whitelist(allow_guest=True)
def get_details(name: str):
    if not user_has_permission(name, "read"):
        frappe.throw("You don't have access.", frappe.PermissionError)
    file = frappe.db.get_value(
        "File",
        name,
        ["name", "file_name", "file_size", "mime_type", "folder", "owner", "creation"],
        as_dict=True,
    )
    file.owner_name = frappe.db.get_value("User", file.owner, "full_name")
    file.metadata = frappe.db.get_value(
        "Photo Metadata",
        name,
        ["taken_on", "width", "height", "duration", "camera", "latitude", "longitude"],
        as_dict=True,
    )
    if frappe.session.user == "Guest" or not get_user_access(name).get("read"):
        file.folder = None
        file.albums = []
        return file

    file.folder_title = frappe.db.get_value("File", file.folder, "file_name")
    if file.folder == get_user_folder().name:
        file.folder_title = "Home"
    from suite.photos.api.albums import readable_albums

    file.albums = frappe.get_all(
        "Photo Album Item",
        filters={"file": name, "album": ["in", readable_albums() or [""]]},
        pluck="album",
    )
    file.archived = frappe.db.exists("Photo Archive", {"user": frappe.session.user, "file": name})
    return file


def _as_list(value):
    return json.loads(value) if isinstance(value, str) else value
